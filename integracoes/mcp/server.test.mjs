import test from "node:test";
import assert from "node:assert/strict";
import { createHash, randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import { createCompanion } from "./server.mjs";
import { validateContext } from "./context.mjs";

const BASE = "https://mcp.example.invalid";
const CALLBACKS = ["https://chatgpt.example.invalid/callback", "https://claude.example.invalid/callback"];
const revocation = "a".repeat(64);
const sample = { schema_version: 1, leitura: { estados: ["estimado"], fontes: ["librera"] } };
async function fixture(t) {
  let time = 1000000;
  const server = createCompanion({ baseUrl: BASE, redirects: CALLBACKS, now: () => time });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  t.after(() => new Promise((r) => { server.close(r); server.closeAllConnections(); }));
  const local = `http://127.0.0.1:${server.address().port}`;
  const request = (path, value, options = {}) => fetch(local + path, {
    method: value === undefined ? "GET" : "POST", redirect: "manual",
    headers: { ...(value === undefined ? {} : { "content-type": "application/json" }), ...options.headers },
    ...(value === undefined ? {} : { body: JSON.stringify(value) }), ...options,
  });
  async function start(callback = CALLBACKS[0], resource = `${BASE}/mcp`) {
    const registered = await request("/oauth/register", { redirect_uris: [callback], token_endpoint_auth_method: "none" });
    assert.equal(registered.status, 201);
    const client = await registered.json(), verifier = randomBytes(32).toString("base64url");
    const q = new URLSearchParams({ client_id: client.client_id, redirect_uri: callback, response_type: "code", scope: "context:read", state: "state-private", resource,
      code_challenge: createHash("sha256").update(verifier).digest("base64url"), code_challenge_method: "S256" });
    const auth = await request(`/oauth/authorize?${q}`), html = await auth.text();
    assert.equal(auth.status, 200, html);
    assert.ok(!html.includes("state-private"));
    return { client: client.client_id, verifier, callback, code: /class="code">([^<]+)/.exec(html)[1].replaceAll("-", ""), poll: /data-poll="([^"]+)/.exec(html)[1] };
  }
  async function approve(s, context = sample, secret = revocation) {
    return request("/api/link", { code: s.code, context, revocation: secret }, { headers: { "content-type": "application/json", origin: BASE } });
  }
  async function tokens(s, overrides = {}) {
    const poll = await (await request("/api/poll", { poll: s.poll })).json();
    const url = new URL(poll.redirect);
    assert.equal(url.origin + url.pathname, s.callback);
    assert.equal(url.searchParams.get("state"), "state-private");
    assert.equal(url.searchParams.get("iss"), BASE);
    return request("/oauth/token", { grant_type: "authorization_code", client_id: s.client, code: url.searchParams.get("code"), redirect_uri: s.callback,
      code_verifier: s.verifier, resource: `${BASE}/mcp`, ...overrides });
  }
  const mcp = (token, method = "tools/call", params = { name: "ler_contexto_revisado", arguments: {} }) => request("/mcp", { jsonrpc: "2.0", id: 1, method, params },
    { headers: { "content-type": "application/json", ...(token ? { authorization: `Bearer ${token}` } : {}) } });
  return { request, start, approve, tokens, mcp, advance: (ms) => { time += ms; } };
}

test("allowlist aceita o ouro Python e rejeita PII em qualquer nível", () => {
  const gold = JSON.parse(readFileSync(new URL("../../kotlin/motor/src/jvmTest/resources/ouro/contexto-ia.json", import.meta.url)));
  for (const c of gold.casos) {
    if (Object.keys(c.resultado).length > 1) assert.deepEqual(validateContext(c.resultado), c.resultado);
    else assert.throws(() => validateContext(c.resultado));
  }
  for (const c of [null, [], {}, { ...sample, nome: "Pessoa inventada" }, { ...sample, leitura: { ...sample.leitura, titulo: "Livro de exemplo" } },
    { ...sample, leitura: { estados: ["texto livre"], fontes: ["usuario"] } }, { ...sample, leitura: { estados: ["estimado", "estimado"], fontes: ["usuario"] } },
    { ...sample, leitura: { estados: [], fontes: ["usuario"] } }]) assert.throws(() => validateContext(c));
});

test("mesmo MCP: handshake, descoberta e OAuth PKCE para os dois clientes", async (t) => {
  const f = await fixture(t);
  const metadata = await (await f.request("/.well-known/oauth-protected-resource/mcp")).json();
  assert.equal(metadata.resource, `${BASE}/mcp`); assert.deepEqual(metadata.authorization_servers, [BASE]);
  const init = await (await f.mcp(null, "initialize", { protocolVersion: "2025-06-18" })).json();
  assert.equal(init.result.protocolVersion, "2025-06-18");
  const tools = (await (await f.mcp(null, "tools/list")).json()).result.tools;
  assert.equal(tools.length, 1); assert.equal(tools[0].annotations.readOnlyHint, true);
  assert.equal((await f.mcp()).status, 401);
  for (const cb of CALLBACKS) {
    const s = await f.start(cb);
    assert.equal((await f.approve(s)).status, 200);
    const tokenResponse = await f.tokens(s); assert.equal(tokenResponse.status, 200);
    const token = await tokenResponse.json();
    const data = await (await f.mcp(token.access_token)).json();
    assert.deepEqual(data.result.structuredContent.contexto, sample);
    assert.equal(data.result.structuredContent.sincronizacao, "snapshot_revisado");
    assert.equal((await f.tokens(s)).status, 400, "código de autorização não pode ser reutilizado");
  }
});

test("PKCE, recurso, redirect e cliente estão vinculados ao consentimento", async (t) => {
  const f = await fixture(t), s = await f.start(); await f.approve(s);
  for (const overrides of [{ code_verifier: "b".repeat(43) }, { resource: `${BASE}/outro` }, { redirect_uri: CALLBACKS[1] }, { client_id: "outro" }]) {
    assert.equal((await f.tokens(s, overrides)).status, 400);
  }
  assert.equal((await f.tokens(s)).status, 200);
  assert.equal((await f.request("/oauth/register", { redirect_uris: ["https://evil.example.invalid/callback"] })).status, 400);
});

test("contexto privado não é aceito e erro não reflete conteúdo", async (t) => {
  const f = await fixture(t), s = await f.start();
  const r = await f.approve(s, { ...sample, nome: "Pessoa inventada" });
  assert.equal(r.status, 400); assert.ok(!(await r.text()).includes("Pessoa inventada"));
  assert.equal((await f.approve(s)).status, 200);
  assert.equal((await f.approve(s)).status, 410);
});

test("vínculos são isolados; revogação elimina acesso, refresh e autorização pendente", async (t) => {
  const f = await fixture(t), a = await f.start(), b = await f.start(CALLBACKS[1]);
  await f.approve(a); await f.approve(b, { schema_version: 1, leitura: { estados: [], fontes: [] } }, "b".repeat(64));
  const at = await (await f.tokens(a)).json(), bt = await (await f.tokens(b)).json();
  assert.equal((await f.request("/api/revoke", { revocation }, { headers: { "content-type": "application/json", origin: BASE } })).status, 200);
  assert.equal((await f.mcp(at.access_token)).status, 401);
  assert.equal((await f.mcp(bt.access_token)).status, 200);
  assert.equal((await f.request("/oauth/token", { grant_type: "refresh_token", client_id: a.client, refresh_token: at.refresh_token, resource: `${BASE}/mcp` })).status, 400);
  assert.equal((await f.request("/api/poll", { poll: a.poll })).status, 410);
});

test("refresh rotaciona; replay revoga a família de tokens", async (t) => {
  const f = await fixture(t), s = await f.start(); await f.approve(s);
  const initial = await (await f.tokens(s)).json();
  const args = { grant_type: "refresh_token", client_id: s.client, refresh_token: initial.refresh_token, resource: `${BASE}/mcp` };
  const rotated = await (await f.request("/oauth/token", args)).json(); assert.ok(rotated.access_token);
  assert.equal((await f.request("/oauth/token", args)).status, 400);
  assert.equal((await f.mcp(rotated.access_token)).status, 401);
});

test("código expira em cinco minutos e contexto em uma hora, mesmo com token novo", async (t) => {
  const f = await fixture(t), expired = await f.start(); f.advance(5 * 60000 + 1);
  assert.equal((await f.approve(expired)).status, 410);
  const s = await f.start(); await f.approve(s); const token = await (await f.tokens(s)).json();
  f.advance(15 * 60000 + 1); assert.equal((await f.mcp(token.access_token)).status, 401);
  const fresh = await (await f.request("/oauth/token", { grant_type: "refresh_token", client_id: s.client, refresh_token: token.refresh_token, resource: `${BASE}/mcp` })).json();
  assert.equal((await f.mcp(fresh.access_token)).status, 200);
  f.advance(45 * 60000); assert.equal((await f.mcp(fresh.access_token)).status, 401);
});

test("não aceita escrita, argumentos ocultos, origem estrangeira ou corpo excessivo", async (t) => {
  const f = await fixture(t), s = await f.start(); await f.approve(s); const token = await (await f.tokens(s)).json();
  assert.equal((await (await f.mcp(token.access_token, "tools/call", { name: "ler_contexto_revisado", arguments: { raw: true } })).json()).error.code, -32602);
  assert.equal((await (await f.mcp(token.access_token, "tools/call", { name: "gravar_fato" })).json()).error.code, -32602);
  assert.equal((await f.request("/api/link", {}, { headers: { "content-type": "application/json", origin: "https://evil.example.invalid" } })).status, 403);
  assert.equal((await f.request("/api/revoke", { revocation })).status, 403);
  assert.equal((await f.request("/api/link", { value: "x".repeat(17000) })).status, 403);
  assert.equal((await f.request("/mcp", { value: "x".repeat(17000) })).status, 413);
  const portal = await f.request("/link");
  assert.match(portal.headers.get("content-security-policy"), /frame-ancestors 'none'/);
  assert.equal(portal.headers.get("referrer-policy"), "no-referrer");
});

test("produção exige HTTPS e callbacks exatos", () => {
  assert.throws(() => createCompanion({ baseUrl: "http://example.invalid", redirects: CALLBACKS }));
  assert.throws(() => createCompanion({ baseUrl: BASE, redirects: [] }));
  assert.throws(() => createCompanion({ baseUrl: BASE, redirects: ["https://example.invalid/callback#token"] }));
});
