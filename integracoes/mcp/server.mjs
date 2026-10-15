/** Piloto MCP comum: somente snapshots allowlisted; nada de workspace Python.
 * Estado efêmero, uma instância. Reiniciar revoga conexões. Sem logs de pedidos.
 */
import { createServer } from "node:http";
import { randomBytes, createHash, timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { validateContext } from "./context.mjs";

const secret = () => randomBytes(32).toString("base64url");
const digest = (s) => createHash("sha256").update(s).digest("hex");
const challenge = (s) => createHash("sha256").update(s).digest("base64url");
const equals = (a, b) => typeof a === "string" && typeof b === "string" && a.length === b.length && timingSafeEqual(Buffer.from(a), Buffer.from(b));
const SCOPE = "context:read";
const SUPPORTED = ["2024-11-05", "2025-03-26", "2025-06-18"];
const bodyLimit = 16384;
const json = (res, status, value, headers = {}) => {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8", ...headers });
  res.end(value === undefined ? "" : JSON.stringify(value));
};
const escape = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
function page(res, title, content) {
  res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  res.end(`<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)} · FinTips</title><link rel="stylesheet" href="/portal.css"><main><div class="brand">FT / FINTIPS</div>${content}</main><script type="module" src="/portal.js"></script></html>`);
}
async function body(req) {
  const chunks = []; let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > bodyLimit) { const e = new Error("pedido muito grande"); e.status = 413; throw e; }
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  if (req.headers["content-type"]?.split(";")[0].trim() === "application/json") return JSON.parse(raw);
  if (req.headers["content-type"]?.split(";")[0].trim() === "application/x-www-form-urlencoded") {
    const p = new URLSearchParams(raw);
    if (new Set(p.keys()).size !== [...p.keys()].length) throw new Error("parâmetro repetido");
    return Object.fromEntries(p);
  }
  const e = new Error("tipo de conteúdo inválido"); e.status = 415; throw e;
}

export function createCompanion({ baseUrl, redirects = [], now = () => Date.now() } = {}) {
  const base = new URL(baseUrl);
  if (base.protocol !== "https:" || base.pathname !== "/" || base.search || base.hash || base.username || base.password) throw new Error("PUBLIC_URL deve ser uma origem HTTPS");
  const issuer = base.origin, resource = `${issuer}/mcp`;
  if (!redirects.length) throw new Error("Defina OAUTH_REDIRECT_URIS com os callbacks exatos dos clientes");
  for (const uri of redirects) {
    const u = new URL(uri);
    if (u.protocol !== "https:" || u.hash || u.username || u.password) throw new Error("callback inválido");
  }
  const clients = new Map(), pending = new Map(), polls = new Map(), codes = new Map(), grants = new Map(), tokens = new Map();
  const refresh = new Map(), usedRefresh = new Map();
  let requests = 0, windowStart = now();
  const snapshotTtl = 60 * 60 * 1000;
  const clean = () => {
    const t = now();
    for (const [key, grant] of grants) if (grant.expires <= t) revoke(grant);
    for (const map of [clients, pending, polls, codes, tokens, refresh, usedRefresh]) for (const [key, value] of map) if (value.expires <= t) map.delete(key);
  };
  function revoke(g) {
    clearTimeout(g.timer);
    grants.delete(g.id);
    for (const map of [tokens, refresh, usedRefresh, codes]) for (const [k, v] of map) if (v.grant === g) map.delete(k);
    for (const map of [pending, polls]) for (const [k, v] of map) if (v.grant === g) map.delete(k);
    g.context = null;
  }
  const unauthorized = (res) => json(res, 401, { error: "invalid_token" }, {
    "www-authenticate": `Bearer resource_metadata="${issuer}/.well-known/oauth-protected-resource", scope="${SCOPE}"`,
  });
  function issue(grant, clientId) {
    if (tokens.size + refresh.size + usedRefresh.size >= 20000) { const e = new Error("limite temporário"); e.status = 429; throw e; }
    const accessToken = secret(), refreshToken = secret();
    tokens.set(digest(accessToken), { grant, clientId, expires: now() + 15 * 60 * 1000 });
    refresh.set(digest(refreshToken), { grant, clientId, expires: grant.expires });
    return { token_type: "Bearer", access_token: accessToken, refresh_token: refreshToken, expires_in: Math.min(900, Math.floor((grant.expires - now()) / 1000)), scope: SCOPE };
  }
  function redirectFor(p) {
    const url = new URL(p.redirect_uri);
    url.searchParams.set("code", p.authCode); url.searchParams.set("state", p.state); url.searchParams.set("iss", issuer);
    return url.href;
  }
  const server = createServer(async (req, res) => {
    res.setHeader("cache-control", "no-store");
    res.setHeader("referrer-policy", "no-referrer");
    res.setHeader("x-content-type-options", "nosniff");
    res.setHeader("content-security-policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
    res.setHeader("strict-transport-security", "max-age=31536000");
    try {
      if (req.headers.origin && req.headers.origin !== issuer) return json(res, 403, { error: "origem inválida" });
      clean();
      if (now() - windowStart >= 60000) { windowStart = now(); requests = 0; }
      if (++requests > 1200) return json(res, 429, { error: "limite temporário" }, { "retry-after": "60" });
      const url = new URL(req.url, issuer);
      const path = url.pathname;
      if (req.method === "GET" && path === "/health") return json(res, 200, { status: "ok", mode: "ephemeral-read-only" });
      if (req.method === "GET" && ["/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"].includes(path)) return json(res, 200, {
        resource, authorization_servers: [issuer], scopes_supported: [SCOPE], bearer_methods_supported: ["header"], resource_name: "FinTips · contexto revisado",
      });
      if (req.method === "GET" && path === "/.well-known/oauth-authorization-server") return json(res, 200, {
        issuer, authorization_endpoint: `${issuer}/oauth/authorize`, token_endpoint: `${issuer}/oauth/token`, registration_endpoint: `${issuer}/oauth/register`,
        response_types_supported: ["code"], grant_types_supported: ["authorization_code", "refresh_token"], code_challenge_methods_supported: ["S256"],
        token_endpoint_auth_methods_supported: ["none"], scopes_supported: [SCOPE], authorization_response_iss_parameter_supported: true,
      });
      if (req.method === "POST" && path === "/oauth/register") {
        const b = await body(req);
        if (!Array.isArray(b.redirect_uris) || b.redirect_uris.length !== 1 || !redirects.includes(b.redirect_uris[0]) ||
            (b.token_endpoint_auth_method && b.token_endpoint_auth_method !== "none") ||
            (b.grant_types && (!Array.isArray(b.grant_types) || !b.grant_types.includes("authorization_code") || b.grant_types.some((g) => !["authorization_code", "refresh_token"].includes(g)))) ||
            (b.response_types && JSON.stringify(b.response_types) !== JSON.stringify(["code"]))) return json(res, 400, { error: "invalid_client_metadata" });
        if (clients.size >= 1000) return json(res, 429, { error: "limite temporário" });
        const id = secret();
        clients.set(id, { redirect: b.redirect_uris[0], expires: Infinity });
        return json(res, 201, { client_id: id, redirect_uris: b.redirect_uris, token_endpoint_auth_method: "none", grant_types: ["authorization_code", "refresh_token"], response_types: ["code"] });
      }
      if (req.method === "GET" && path === "/oauth/authorize") {
        const p = Object.fromEntries(url.searchParams);
        const client = clients.get(p.client_id);
        if (new Set(url.searchParams.keys()).size !== [...url.searchParams.keys()].length || !client || p.redirect_uri !== client.redirect || p.resource !== resource ||
            p.response_type !== "code" || p.scope !== SCOPE || p.code_challenge_method !== "S256" || !/^[A-Za-z0-9_-]{43}$/.test(p.code_challenge || "") ||
            !p.state || p.state.length > 1024) return json(res, 400, { error: "invalid_request" });
        if (pending.size >= 1000) return json(res, 429, { error: "limite temporário" });
        const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
        const code = Array.from(randomBytes(12), (v) => alphabet[v & 31]).join("");
        const poll = secret();
        const request = { ...p, expires: now() + 5 * 60 * 1000 };
        pending.set(digest(code), request); polls.set(digest(poll), request);
        const target = new URL(client.redirect).hostname;
        return page(res, "Vincular IA", `<p class="eyebrow">MCP / SOMENTE LEITURA</p><h1>Autorize pelo app.</h1><p>Solicitação com retorno para <strong>${escape(target)}</strong>.</p><p>Abra FinTips → Contexto → Conectar IA. Confira o endereço deste servidor e digite:</p><div class="code">${code.match(/.{4}/g).join("-")}</div><p>O código expira em cinco minutos. Revise o contexto no app antes de autorizar. Nenhum registro completo será solicitado.</p><div id="oauth" data-poll="${poll}"></div><p id="status" role="status">Aguardando sua confirmação no app…</p>`);
      }
      if (req.method === "POST" && path === "/api/poll") {
        const b = await body(req), p = typeof b.poll === "string" && polls.get(digest(b.poll));
        if (!p) return json(res, 410, { error: "Solicitação expirada. Comece novamente na IA." });
        return json(res, 200, p.authCode ? { redirect: redirectFor(p) } : { waiting: true });
      }
      if (req.method === "POST" && path === "/api/link") {
        if (req.headers.origin !== issuer) return json(res, 403, { error: "origem inválida" });
        const b = await body(req);
        if (!b || Object.keys(b).sort().join(",") !== "code,context,revocation" || typeof b.code !== "string" || typeof b.revocation !== "string" || !/^[A-Z2-7]{12}$/.test(b.code) || !/^[a-f0-9]{64}$/.test(b.revocation)) return json(res, 400, { error: "pedido inválido" });
        const p = pending.get(digest(b.code));
        if (!p || p.authCode) return json(res, 410, { error: "Código usado ou expirado. Reinicie o vínculo na IA." });
        const context = validateContext(b.context);
        if (grants.size >= 1000) return json(res, 429, { error: "limite temporário" });
        const grant = { id: secret(), context, revocation: digest(b.revocation), expires: now() + snapshotTtl };
        grant.timer = setTimeout(() => revoke(grant), snapshotTtl).unref();
        grants.set(grant.id, grant);
        const code = secret(); p.authCode = code; p.grant = grant; p.expires = now() + 2 * 60 * 1000;
        codes.set(digest(code), { ...p, grant, expires: now() + 2 * 60 * 1000 });
        return json(res, 200, { status: "approved", expires_in: 3600 });
      }
      if (req.method === "POST" && path === "/api/revoke") {
        if (req.headers.origin !== issuer) return json(res, 403, { error: "origem inválida" });
        const b = await body(req);
        if (typeof b.revocation !== "string" || !/^[a-f0-9]{64}$/.test(b.revocation)) return json(res, 400, { error: "pedido inválido" });
        const hash = digest(b.revocation);
        for (const grant of grants.values()) if (equals(grant.revocation, hash)) revoke(grant);
        return json(res, 200, { status: "revoked" }); // Idempotente; não revela a existência de um vínculo.
      }
      if (req.method === "POST" && path === "/oauth/token") {
        const b = await body(req);
        if (b.resource !== resource || !clients.has(b.client_id)) return json(res, 400, { error: "invalid_request" });
        if (b.grant_type === "authorization_code") {
          const key = digest(String(b.code || "")), p = codes.get(key);
          if (!p || p.client_id !== b.client_id || p.redirect_uri !== b.redirect_uri || !/^[A-Za-z0-9._~-]{43,128}$/.test(b.code_verifier || "") ||
              !equals(challenge(b.code_verifier), p.code_challenge) || !grants.has(p.grant.id)) return json(res, 400, { error: "invalid_grant" });
          codes.delete(key);
          return json(res, 200, issue(p.grant, p.client_id));
        }
        if (b.grant_type === "refresh_token") {
          const key = digest(String(b.refresh_token || "")), entry = refresh.get(key);
          const replay = usedRefresh.get(key);
          if (replay?.clientId === b.client_id) revoke(replay.grant);
          if (!entry || entry.clientId !== b.client_id || !grants.has(entry.grant.id)) return json(res, 400, { error: "invalid_grant" });
          refresh.delete(key); usedRefresh.set(key, entry);
          return json(res, 200, issue(entry.grant, entry.clientId));
        }
        return json(res, 400, { error: "unsupported_grant_type" });
      }
      if (path === "/mcp") {
        if (req.method !== "POST") return json(res, 405, { error: "Use POST" }, { allow: "POST" });
        const b = await body(req);
        const fail = (code, message) => json(res, 200, { jsonrpc: "2.0", id: b?.id ?? null, error: { code, message } });
        if (!b || Array.isArray(b) || b.jsonrpc !== "2.0" || typeof b.method !== "string" ||
            (Object.hasOwn(b, "id") && typeof b.id !== "string" && typeof b.id !== "number" && b.id !== null)) return fail(-32600, "Invalid Request");
        if (req.headers["mcp-protocol-version"] && !SUPPORTED.includes(req.headers["mcp-protocol-version"])) return json(res, 400, { error: "versão MCP não suportada" });
        const result = (value) => json(res, 200, { jsonrpc: "2.0", id: b.id, result: value });
        if (!Object.hasOwn(b, "id")) return json(res, 202);
        if (b.method === "initialize") return result({ protocolVersion: SUPPORTED.includes(b.params?.protocolVersion) ? b.params.protocolVersion : "2025-06-18", capabilities: { tools: {} }, serverInfo: { name: "fintips-contexto", version: "0.1.0" }, instructions: "Só contexto mínimo revisado. sem_registro não significa falha. Não há dados brutos ou ferramentas de escrita. O snapshot expira em uma hora; não é sincronização contínua." });
        if (b.method === "ping") return result({});
        if (b.method === "tools/list") return result({ tools: [{ name: "ler_contexto_revisado", description: "Lê o snapshot mínimo aprovado no aparelho. Ausência de evidência não é descumprimento. Expira em uma hora, sem sincronização contínua.", inputSchema: { type: "object", properties: {}, additionalProperties: false }, annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false }, securitySchemes: [{ type: "oauth2", scopes: [SCOPE] }] }] });
        if (b.method !== "tools/call") return fail(-32601, "Method not found");
        const bearer = /^Bearer ([A-Za-z0-9_-]{43})$/.exec(req.headers.authorization || "")?.[1];
        const token = bearer && tokens.get(digest(bearer));
        if (!token || !grants.has(token.grant.id)) return unauthorized(res);
        if (b.params?.name !== "ler_contexto_revisado" || (b.params?.arguments && (typeof b.params.arguments !== "object" || Array.isArray(b.params.arguments) || Object.keys(b.params.arguments).length))) return fail(-32602, "Invalid params");
        const data = { contexto: token.grant.context, validade_restante_segundos: Math.max(0, Math.floor((token.grant.expires - now()) / 1000)), sincronizacao: "snapshot_revisado" };
        return result({ content: [{ type: "text", text: JSON.stringify(data) }], structuredContent: data, isError: false });
      }
      if (req.method === "GET" && (path === "/link" || path === "/")) return page(res, "Contexto para IA", `<p class="eyebrow">CLIENTE / MCP / IA</p><h1>Você escolhe o que atravessa.</h1><p>Um conector para ChatGPT e Claude. O motor fica no aparelho. A IA recebe apenas o snapshot revisado, válido por uma hora.</p><p>Endpoint MCP:</p><code>${escape(resource)}</code><section id="link" hidden><h2>Confira antes de confirmar</h2><p id="operation"></p><pre id="context"></pre><button id="confirm">Confirmar contexto</button></section><p id="status" role="status">Inicie o vínculo na IA e continue pelo app FinTips.</p>`);
      if (req.method === "GET" && ["/portal.js", "/portal.css", "/context.mjs"].includes(path)) {
        res.writeHead(200, { "content-type": path.endsWith("css") ? "text/css; charset=utf-8" : "text/javascript; charset=utf-8" });
        return res.end(readFileSync(new URL(`.${path}`, import.meta.url)));
      }
      return json(res, 404, { error: "não encontrado" });
    } catch (error) { json(res, error.status || 400, { error: "Pedido recusado. Confira os dados e tente novamente." }); }
  });
  server.requestTimeout = 15000; server.headersTimeout = 10000; server.maxRequestsPerSocket = 100;
  const timer = setInterval(clean, 30000).unref();
  server.once("close", () => {
    clearInterval(timer);
    for (const grant of grants.values()) revoke(grant);
    for (const map of [clients, pending, polls, codes, tokens, refresh, usedRefresh]) map.clear();
  });
  return server;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const server = createCompanion({ baseUrl: process.env.PUBLIC_URL, redirects: (process.env.OAUTH_REDIRECT_URIS || "").split(",").filter(Boolean) });
  server.listen(Number(process.env.PORT || 8787), "0.0.0.0", () => process.stdout.write("FinTips MCP pronto. Sem logs de pedidos.\n"));
}
