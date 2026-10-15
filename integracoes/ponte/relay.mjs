/** MCP remoto → canal autenticado → MCP no telefone. Sem snapshots ou arquivos.
 * Uma instância; deploy/reinício revoga sessões. Nunca registrar pedidos/tokens.
 */
import { createServer } from "node:http";
import { randomBytes, createHash, timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { WebSocketServer, WebSocket } from "ws";
import { validateContext } from "../mcp/context.mjs";

const secret = () => randomBytes(32).toString("base64url");
const hash = (s) => createHash("sha256").update(s).digest("hex");
const challenge = (s) => createHash("sha256").update(s).digest("base64url");
const same = (a, b) => typeof a === "string" && typeof b === "string" && Buffer.byteLength(a) === Buffer.byteLength(b) && timingSafeEqual(Buffer.from(a), Buffer.from(b));
const object = (o) => o && typeof o === "object" && !Array.isArray(o);
const exact = (o, keys) => object(o) && Object.keys(o).sort().join() === [...keys].sort().join();
const SCOPES = ["rotina", "planos", "leitura"];
const scopesValid = (s) => Array.isArray(s) && s.length > 0 && JSON.stringify(s) === JSON.stringify(SCOPES.filter((v) => s.includes(v)));
const tokenPattern = /^[A-Za-z0-9_-]{43}$/;
const joinPattern = /^(?:[A-Za-z0-9_-]{43}|[A-Za-z0-9_-]{64})$/;
const VERSIONS = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"];
const SCOPE = "context:read";
const PROTOCOL = "fintips-phone-v1";
const DAY30 = 30 * 24 * 60 * 60 * 1000;
const headers = { "cache-control": "no-store", "referrer-policy": "no-referrer", "x-content-type-options": "nosniff", "x-frame-options": "DENY",
  "content-security-policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'" };
const json = (res, status, data, extra = {}) => {
  if (res.destroyed || res.writableEnded) return;
  res.writeHead(status, { ...headers, "content-type": "application/json; charset=utf-8", ...extra });
  res.end(data === undefined ? "" : JSON.stringify(data));
};
const escape = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
async function body(req) {
  let n = 0; const chunks = [];
  for await (const c of req) { n += c.length; if (n > 16384) throw new Error("limit"); chunks.push(c); }
  const s = new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks));
  const type = req.headers["content-type"]?.split(";")[0].trim();
  if (type === "application/json") return JSON.parse(s);
  if (type === "application/x-www-form-urlencoded") {
    const p = new URLSearchParams(s);
    if ([...p.keys()].length !== new Set(p.keys()).size) throw new Error("duplicate");
    return Object.fromEntries(p);
  }
  throw new Error("content-type");
}
function page(res, title, content) {
  res.writeHead(200, { ...headers, "content-type": "text/html; charset=utf-8" });
  res.end(`<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)} · FinTips</title><link rel="stylesheet" href="/portal.css"><main><div class="brand">FT / FINTIPS</div>${content}</main><script type="module" src="/portal.js"></script></html>`);
}

export function createRelay({ baseUrl, redirects = [], now = () => Date.now(), queryTimeout = 15000, joinSecret, httpServer } = {}) {
  const base = new URL(baseUrl);
  if (base.protocol !== "https:" || base.pathname !== "/" || base.search || base.hash || base.username || base.password) throw new Error("HTTPS origin required");
  if (!joinPattern.test(joinSecret || "")) throw new Error("PHONE_JOIN_SECRET must have 256 bits (43 base64url or 64 hex characters)");
  const issuer = base.origin, resource = issuer + "/mcp";
  if (!redirects.length) throw new Error("Exact OAuth callbacks required");
  const providers = new Map();
  for (const entry of redirects) {
    const { uri, provider } = entry;
    const u = new URL(uri);
    if (u.protocol !== "https:" || u.hash || u.username || u.password || !["chatgpt", "claude"].includes(provider) || providers.has(uri)) throw new Error("Invalid callback");
    providers.set(uri, provider);
  }
  const clients = new Map(), pending = new Map(), polls = new Map(), codes = new Map();
  const devices = new Map(), deviceTokens = new Map(), grants = new Map(), tokens = new Map(), refresh = new Map(), spentRefresh = new Map(), jobs = new Map();
  let windowStart = now(), count = 0;
  const server = httpServer ?? createServer();
  const websocket = new WebSocketServer({ noServer: true, maxPayload: 16384, perMessageDeflate: false, clientTracking: false,
    handleProtocols: (p) => p.has(PROTOCOL) ? PROTOCOL : false });
  const send = (d, data) => { if (d.ws?.readyState === WebSocket.OPEN) d.ws.send(JSON.stringify(data)); };
  function finish(job, result) {
    if (!jobs.delete(job.id)) return;
    clearTimeout(job.timer);
    json(job.res, 200, { jsonrpc: "2.0", id: job.rpcId, result });
  }
  const unavailable = (reason = "O telefone não disponibilizou contexto autorizado. Abra o FinTips e confira a conexão.") => ({ isError: true, content: [{ type: "text", text: reason }] });
  function revoke(g) {
    if (!grants.delete(g.id)) return;
    for (const m of [tokens, refresh, spentRefresh, codes]) for (const [key, v] of m) if (v.grant === g) m.delete(key);
    for (const job of jobs.values()) if (job.grant === g) finish(job, unavailable("A autorização foi revogada."));
    send(g.device, { type: "grant_revoked", id: g.id });
  }
  function forgetDevice(d) {
    if (!devices.delete(d.id)) return;
    deviceTokens.delete(d.tokenHash);
    for (const g of [...grants.values()]) if (g.device === d) revoke(g);
    d.ws?.close(1000, "revoked");
  }
  function clean() {
    const t = now();
    for (const d of devices.values()) if (d.expires <= t) forgetDevice(d);
    for (const g of grants.values()) if (g.expires <= t) revoke(g);
    for (const m of [clients, pending, polls, codes, tokens, refresh, spentRefresh]) for (const [k, v] of m) if (v.expires <= t) m.delete(k);
  }
  const bearer = (req) => /^Bearer ([A-Za-z0-9_-]{43})$/.exec(req.headers.authorization || "")?.[1];
  const phone = (req) => { const b = bearer(req); return b && deviceTokens.get(hash(b)); };
  const unauthorized = (res) => json(res, 401, { error: "invalid_token" }, { "www-authenticate": `Bearer resource_metadata="${issuer}/.well-known/oauth-protected-resource"` });
  function issue(g, clientId) {
    if (tokens.size + refresh.size + spentRefresh.size >= 25000) { revoke(g); throw new Error("token limit"); }
    const access = secret(), renew = secret();
    tokens.set(hash(access), { grant: g, clientId, expires: Math.min(g.expires, now() + 900000) });
    refresh.set(hash(renew), { grant: g, clientId, expires: g.expires });
    g.activated = true;
    send(g.device, { type: "grant_activated", id: g.id });
    return { access_token: access, token_type: "Bearer", expires_in: Math.min(900, Math.floor((g.expires - now()) / 1000)), refresh_token: renew, scope: SCOPE, resource };
  }
  function redirect(p) {
    const u = new URL(p.redirect_uri);
    u.searchParams.set("state", p.state); u.searchParams.set("iss", issuer);
    if (p.denied) u.searchParams.set("error", "access_denied"); else u.searchParams.set("code", p.authCode);
    return u.toString();
  }
  server.on("upgrade", (req, socket, head) => {
    clean();
    const d = phone(req);
    if (req.url !== "/phone/channel" || !d || (req.headers.origin && req.headers.origin !== issuer) || req.headers["sec-websocket-protocol"] !== PROTOCOL) {
      socket.end("HTTP/1.1 401 Unauthorized\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"); return;
    }
    websocket.handleUpgrade(req, socket, head, (ws) => {
      d.ws?.terminate();
      d.ws = ws; d.alive = true;
      ws.on("error", () => {});
      ws.on("pong", () => { d.alive = true; });
      ws.on("close", () => {
        if (d.ws !== ws) return;
        d.ws = null;
        for (const job of jobs.values()) if (job.device === d) finish(job, unavailable());
      });
      ws.on("message", (raw, binary) => {
        try {
          if (binary || d.ws !== ws || !devices.has(d.id)) throw new Error("frame");
          const b = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(raw));
          const keys = b.error ? ["type", "id", "nonce", "error"] : ["type", "id", "nonce", "contexto", "validade_restante_segundos"];
          if (!exact(b, keys) || b.type !== "result" || !tokenPattern.test(b.id || "") || !tokenPattern.test(b.nonce || "")) throw new Error("frame");
          const job = jobs.get(b.id);
          if (!job || job.device !== d || job.ws !== ws || !same(job.nonce, b.nonce) || !grants.has(job.grant.id)) return;
          if (b.error) {
            if (!["contexto_indisponivel", "autorizacao_indisponivel"].includes(b.error)) throw new Error("error");
            return finish(job, unavailable());
          }
          const context = validateContext(b.contexto);
          if (!Number.isInteger(b.validade_restante_segundos) || b.validade_restante_segundos < 1 || b.validade_restante_segundos > 3600 ||
              JSON.stringify(SCOPES.filter((s) => Object.hasOwn(context, s))) !== JSON.stringify(job.grant.scopes)) throw new Error("scope");
          const data = { contexto: context, validade_restante_segundos: b.validade_restante_segundos, sincronizacao: "consulta_ao_celular" };
          finish(job, { isError: false, content: [{ type: "text", text: JSON.stringify(data) }], structuredContent: data });
        } catch {
          for (const job of jobs.values()) if (job.device === d) finish(job, unavailable("O telefone recusou ou devolveu um contexto inválido."));
          ws.close(1008, "invalid response");
        }
      });
      send(d, { type: "ready", protocol: 1, activated: [...grants.values()].filter((g) => g.device === d && g.activated).map((g) => g.id) });
    });
  });
  server.on("request", async (req, res) => {
    try {
      clean();
      if (now() - windowStart >= 60000) { count = 0; windowStart = now(); }
      if (++count > 3000) return json(res, 429, { error: "temporarily_unavailable" });
      const u = new URL(req.url, issuer), path = u.pathname;
      if (req.headers.origin && req.headers.origin !== issuer) return json(res, 403, { error: "invalid_origin" });
      if (req.method === "GET" && path === "/health") return json(res, 200, { ok: true, mode: "phone_relay" });
      if (req.method === "GET" && ["/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"].includes(path))
        return json(res, 200, { resource, authorization_servers: [issuer], scopes_supported: [SCOPE], bearer_methods_supported: ["header"] });
      if (req.method === "GET" && path === "/.well-known/oauth-authorization-server") return json(res, 200, {
        issuer, authorization_endpoint: issuer + "/oauth/authorize", token_endpoint: issuer + "/oauth/token", registration_endpoint: issuer + "/oauth/register",
        revocation_endpoint: issuer + "/oauth/revoke", authorization_response_iss_parameter_supported: true,
        response_types_supported: ["code"], grant_types_supported: ["authorization_code", "refresh_token"], token_endpoint_auth_methods_supported: ["none"],
        code_challenge_methods_supported: ["S256"], scopes_supported: [SCOPE],
      });
      if (req.method === "POST" && path === "/oauth/register") {
        const b = await body(req);
        if (!object(b) || (b.token_endpoint_auth_method !== undefined && b.token_endpoint_auth_method !== "none") ||
            !Array.isArray(b.redirect_uris) || b.redirect_uris.length < 1 || b.redirect_uris.length > 4 || new Set(b.redirect_uris).size !== b.redirect_uris.length || !b.redirect_uris.every((v) => providers.has(v)) ||
            (b.grant_types && (!Array.isArray(b.grant_types) || !b.grant_types.includes("authorization_code") || b.grant_types.some((v) => !["authorization_code", "refresh_token"].includes(v)) || new Set(b.grant_types).size !== b.grant_types.length)) ||
            (b.response_types && JSON.stringify(b.response_types) !== JSON.stringify(["code"]))) return json(res, 400, { error: "invalid_client_metadata" });
        if (clients.size >= 1000) return json(res, 429, { error: "temporarily_unavailable" });
        const id = secret(); clients.set(id, { redirects: [...b.redirect_uris], expires: now() + DAY30 });
        return json(res, 201, { client_id: id, redirect_uris: b.redirect_uris, token_endpoint_auth_method: "none", grant_types: ["authorization_code", "refresh_token"], response_types: ["code"] });
      }
      if (req.method === "GET" && path === "/oauth/authorize") {
        const p = Object.fromEntries(u.searchParams), c = clients.get(p.client_id);
        if ([...u.searchParams.keys()].length !== new Set(u.searchParams.keys()).size || !c || !c.redirects.includes(p.redirect_uri) || p.resource !== resource ||
            p.response_type !== "code" || p.scope !== SCOPE || p.code_challenge_method !== "S256" || !tokenPattern.test(p.code_challenge || "") || !p.state || p.state.length > 1024)
          return json(res, 400, { error: "invalid_request" });
        if (pending.size >= 1000) return json(res, 429, { error: "temporarily_unavailable" });
        const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567", code = [...randomBytes(12)].map((v) => alphabet[v & 31]).join("");
        const poll = secret(), request = { ...p, provider: providers.get(p.redirect_uri), expires: now() + 300000 };
        pending.set(hash(code), request); polls.set(hash(poll), request);
        return page(res, "Autorizar conexão", `<p class="eyebrow">MCP / CONSULTA AO CELULAR</p><h1>Autorize no FinTips.</h1><p>Retorno para <strong>${escape(new URL(p.redirect_uri).hostname)}</strong>.</p><p>No app, abra Conectar IA e informe:</p><div class="code">${code.match(/.{4}/g).join("-")}</div><p>Revise as áreas antes de autorizar. O código expira em cinco minutos. Nenhum registro completo é solicitado.</p><div id="oauth" data-poll="${poll}"></div><p id="status" role="status">Aguardando autorização no celular…</p>`);
      }
      if (req.method === "POST" && path === "/api/poll") {
        const b = await body(req), p = typeof b.poll === "string" && polls.get(hash(b.poll));
        if (!p) return json(res, 410, { error: "expired" });
        return json(res, 200, p.authCode || p.denied ? { redirect: redirect(p) } : { waiting: true });
      }
      if (req.method === "POST" && path === "/phone/enroll") {
        const b = await body(req);
        if (!exact(b, ["protocol", "invite"]) || b.protocol !== 1 || !same(b.invite, joinSecret)) return json(res, 400, { error: "invalid_request" });
        if (devices.size >= 100) return json(res, 429, { error: "temporarily_unavailable" });
        const token = secret(), d = { id: secret(), tokenHash: hash(token), ws: null, expires: now() + DAY30 };
        devices.set(d.id, d); deviceTokens.set(d.tokenHash, d);
        return json(res, 201, { device: d.id, token, protocol: 1, expires_in: DAY30 / 1000 });
      }
      if (path.startsWith("/phone/")) {
        const d = phone(req); if (!d) return unauthorized(res);
        if (req.method !== "POST") return json(res, 405, { error: "method_not_allowed" }, { allow: "POST" });
        const b = await body(req);
        if (path === "/phone/disconnect" && exact(b, [])) { forgetDevice(d); return json(res, 200, { status: "revoked" }); }
        if (path === "/phone/revoke" && exact(b, ["grant"]) && tokenPattern.test(b.grant || "")) {
          const g = grants.get(b.grant); if (g?.device === d) revoke(g);
          return json(res, 200, { status: "revoked" });
        }
        if (["/phone/authorization", "/phone/approve", "/phone/deny"].includes(path)) {
          if (typeof b.code !== "string" || !/^[A-Z2-7]{12}$/.test(b.code)) return json(res, 400, { error: "invalid_request" });
          const p = pending.get(hash(b.code));
          if (!p || p.authCode || p.denied) return json(res, 410, { error: "expired" });
          if (path === "/phone/authorization" && exact(b, ["code"])) return json(res, 200, { provider: p.provider, callback_host: new URL(p.redirect_uri).hostname, expires_in: Math.max(0, Math.floor((p.expires - now()) / 1000)) });
          if (path === "/phone/deny" && exact(b, ["code"])) { p.denied = true; return json(res, 200, { status: "denied" }); }
          if (path === "/phone/approve" && exact(b, ["code", "scopes"]) && scopesValid(b.scopes)) {
            if (d.ws?.readyState !== WebSocket.OPEN) return json(res, 409, { error: "phone_offline" });
            if (grants.size >= 1000 || [...grants.values()].filter((g) => g.device === d).length >= 20) return json(res, 429, { error: "temporarily_unavailable" });
            const g = { id: secret(), device: d, clientId: p.client_id, provider: p.provider, scopes: [...b.scopes], expires: Math.min(d.expires, now() + DAY30), activated: false };
            grants.set(g.id, g); p.authCode = secret(); p.expires = now() + 120000;
            codes.set(hash(p.authCode), { ...p, grant: g, expires: p.expires });
            return json(res, 200, { grant: g.id, provider: g.provider, scopes: g.scopes, status: "approved" });
          }
        }
        return json(res, 400, { error: "invalid_request" });
      }
      if (req.method === "POST" && path === "/oauth/token") {
        const b = await body(req);
        if (b.resource !== resource || !clients.has(b.client_id)) return json(res, 400, { error: "invalid_request" });
        if (b.grant_type === "authorization_code") {
          const key = hash(String(b.code || "")), p = codes.get(key);
          if (!p || p.client_id !== b.client_id || p.redirect_uri !== b.redirect_uri || !/^[A-Za-z0-9._~-]{43,128}$/.test(b.code_verifier || "") || !same(challenge(b.code_verifier), p.code_challenge) || !grants.has(p.grant.id)) return json(res, 400, { error: "invalid_grant" });
          codes.delete(key); return json(res, 200, issue(p.grant, p.client_id));
        }
        if (b.grant_type === "refresh_token") {
          const key = hash(String(b.refresh_token || "")), entry = refresh.get(key), replay = spentRefresh.get(key);
          if (replay?.clientId === b.client_id) revoke(replay.grant);
          if (!entry || entry.clientId !== b.client_id || !grants.has(entry.grant.id)) return json(res, 400, { error: "invalid_grant" });
          refresh.delete(key); spentRefresh.set(key, entry); return json(res, 200, issue(entry.grant, entry.clientId));
        }
        return json(res, 400, { error: "unsupported_grant_type" });
      }
      if (req.method === "POST" && path === "/oauth/revoke") {
        const b = await body(req), key = hash(String(b.token || ""));
        const v = tokens.get(key) ?? refresh.get(key);
        if (v?.clientId === b.client_id) revoke(v.grant);
        return json(res, 200, {});
      }
      if (path === "/mcp") {
        if (req.method !== "POST") return json(res, 405, { error: "method_not_allowed" }, { allow: "POST" });
        const b = await body(req), id = b?.id ?? null;
        const fail = (code, message) => json(res, 200, { jsonrpc: "2.0", id, error: { code, message } });
        const result = (value) => json(res, 200, { jsonrpc: "2.0", id, result: value });
        if (!object(b) || b.jsonrpc !== "2.0" || typeof b.method !== "string" || (Object.hasOwn(b, "id") && typeof id !== "string" && typeof id !== "number" && id !== null)) return fail(-32600, "Invalid Request");
        if (req.headers["mcp-protocol-version"] && !VERSIONS.includes(req.headers["mcp-protocol-version"])) return json(res, 400, { error: "invalid_version" });
        if (!Object.hasOwn(b, "id")) return json(res, 202);
        if (b.params !== undefined && !object(b.params)) return fail(-32602, "Invalid params");
        if (b.method === "initialize") return result({ protocolVersion: VERSIONS.includes(b.params?.protocolVersion) ? b.params.protocolVersion : "2025-06-18", capabilities: { tools: {} }, serverInfo: { name: "fintips-ponte-celular", version: "0.1.0" }, instructions: "Cada consulta depende do celular conectado e de áreas autorizadas. Sem snapshots ou acesso aos registros completos. sem_registro não prova falha. Aparelho indisponível não equivale a meta descumprida." });
        if (b.method === "ping") return result({});
        if (b.method === "tools/list") return result({ tools: [{ name: "ler_contexto_revisado", description: "Consulta agora o MCP do celular, apenas nas áreas que você autorizou a este conector. Se o aparelho estiver indisponível, não devolve dados antigos.", inputSchema: { type: "object", properties: {}, additionalProperties: false }, annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false }, securitySchemes: [{ type: "oauth2", scopes: [SCOPE] }], _meta: { securitySchemes: [{ type: "oauth2", scopes: [SCOPE] }] } }] });
        if (b.method !== "tools/call") return fail(-32601, "Method not found");
        const token = bearer(req), auth = token && tokens.get(hash(token));
        if (!auth || !grants.has(auth.grant.id)) return unauthorized(res);
        if (b.params?.name !== "ler_contexto_revisado" || (b.params.arguments !== undefined && (!object(b.params.arguments) || Object.keys(b.params.arguments).length))) return fail(-32602, "Invalid params");
        const g = auth.grant, d = g.device;
        if (d.ws?.readyState !== WebSocket.OPEN) return result(unavailable());
        if (jobs.size >= 200 || [...jobs.values()].filter((j) => j.device === d).length >= 8) return result(unavailable("O telefone está atendendo outras consultas. Tente novamente."));
        const job = { id: secret(), nonce: secret(), device: d, grant: g, ws: d.ws, res, rpcId: id };
        job.timer = setTimeout(() => finish(job, unavailable()), queryTimeout).unref(); jobs.set(job.id, job);
        res.once("close", () => { if (jobs.delete(job.id)) clearTimeout(job.timer); });
        send(d, { type: "request", id: job.id, nonce: job.nonce, grant: g.id, scopes: g.scopes });
        return;
      }
      if (req.method === "GET" && path === "/") return page(res, "MCP no celular", `<p class="eyebrow">MOTOR NO ANDROID / MCP PARA OS CHATS</p><h1>O contexto vem do seu celular.</h1><p>Use este mesmo endereço em ChatGPT e Claude:</p><code>${escape(resource)}</code><p>Escolha OAuth com registro dinâmico. A autorização mostra um código para confirmar no FinTips. Somente as áreas revisadas podem ser consultadas enquanto o celular estiver conectado.</p><p>Esta ponte encaminha consultas. Ela não guarda uma cópia do contexto e não recebe registros completos.</p>`);
      if (req.method === "GET" && path === "/portal.css") { res.writeHead(200, { ...headers, "content-type": "text/css; charset=utf-8" }); return res.end(readFileSync(new URL("../mcp/portal.css", import.meta.url))); }
      if (req.method === "GET" && path === "/portal.js") { res.writeHead(200, { ...headers, "content-type": "text/javascript; charset=utf-8" }); return res.end(readFileSync(new URL("./portal.js", import.meta.url))); }
      return json(res, 404, { error: "not_found" });
    } catch { json(res, 400, { error: "invalid_request" }); }
  });
  const sweep = setInterval(clean, 15000).unref();
  const heartbeat = setInterval(() => {
    for (const d of devices.values()) if (d.ws) {
      if (!d.alive) { d.ws.terminate(); continue; }
      d.alive = false; d.ws.ping();
    }
  }, 60000).unref();
  server.requestTimeout = 20000; server.headersTimeout = 10000; server.maxRequestsPerSocket = 100;
  server.once("close", () => {
    clearInterval(sweep); clearInterval(heartbeat);
    for (const d of [...devices.values()]) { d.ws?.terminate(); forgetDevice(d); }
    for (const m of [clients, pending, polls, codes, grants, tokens, refresh, spentRefresh, jobs]) m.clear();
    websocket.close();
  });
  return server;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const redirects = JSON.parse(process.env.OAUTH_CALLBACKS || "[]");
  createRelay({ baseUrl: process.env.PUBLIC_URL || process.env.RENDER_EXTERNAL_URL, redirects, joinSecret: process.env.PHONE_JOIN_SECRET }).listen(Number(process.env.PORT || 8787), "0.0.0.0", () => process.stdout.write("FinTips relay ready; request logging disabled.\n"));
}
