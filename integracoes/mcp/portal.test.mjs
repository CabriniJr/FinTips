import test from "node:test";
import assert from "node:assert/strict";
const context = { schema_version: 1, leitura: { estados: ["estimado"], fontes: ["usuario"] } };
const payload = { code: "ABCDEFGHIJKL", context, revocation: "a".repeat(64) };

async function portal(t, initial = payload) {
  const elements = Object.fromEntries(["status", "link", "confirm", "operation", "context"].map((k) => [k, { textContent: "", hidden: false, disabled: false, onclick: null }]));
  const listeners = {}, requests = [];
  globalThis.document = { getElementById: (k) => elements[k] || null };
  globalThis.location = { hash: "#" + encodeURIComponent(JSON.stringify(initial)), pathname: "/link" };
  globalThis.history = { replaceState() { globalThis.location.hash = ""; } };
  globalThis.addEventListener = (name, fn) => { listeners[name] = fn; };
  globalThis.fetch = async (path, options) => {
    requests.push({ path, value: JSON.parse(options.body) });
    return { ok: true, json: async () => ({ status: "ok" }) };
  };
  t.after(() => { for (const k of ["document", "location", "history", "addEventListener", "fetch"]) delete globalThis[k]; });
  await import(`./portal.js?fixture=${Math.random()}`);
  return { elements, requests, receive(value) {
    globalThis.location.hash = "#" + encodeURIComponent(JSON.stringify(value));
    listeners.hashchange();
  } };
}

test("só envia depois de confirmar e remove o fragmento do histórico", async (t) => {
  const p = await portal(t);
  assert.equal(globalThis.location.hash, "");
  assert.equal(p.elements.link.hidden, false); assert.equal(p.requests.length, 0);
  assert.deepEqual(JSON.parse(p.elements.context.textContent), context);
  await p.elements.confirm.onclick();
  assert.deepEqual(p.requests, [{ path: "/api/link", value: payload }]);
  assert.match(p.elements.status.textContent, /Contexto autorizado/);
});

test("reabrir a mesma aba processa novo fragmento e não reutiliza consentimento", async (t) => {
  const p = await portal(t);
  await p.elements.confirm.onclick();
  p.receive({ ...payload, context: { ...context, nome: "Pessoa inventada" } });
  assert.equal(p.elements.link.hidden, true); assert.match(p.elements.status.textContent, /Pedido inválido/);
  assert.equal(p.requests.length, 1); assert.equal(globalThis.location.hash, "");
  p.receive({ revoke: true, revocation: payload.revocation });
  assert.equal(p.elements.link.hidden, false); assert.equal(p.elements.confirm.textContent, "Revogar e apagar");
  assert.equal(p.requests.length, 1);
  await p.elements.confirm.onclick();
  assert.deepEqual(p.requests[1], { path: "/api/revoke", value: { revocation: payload.revocation } });
  assert.match(p.elements.status.textContent, /Vínculo revogado/);
});

test("resposta antiga não pode ocultar uma nova autorização", async (t) => {
  const p = await portal(t);
  let resolve;
  globalThis.fetch = () => new Promise((r) => { resolve = r; });
  const first = p.elements.confirm.onclick();
  p.receive({ revoke: true, revocation: payload.revocation });
  resolve({ ok: true, json: async () => ({ status: "approved" }) });
  await first;
  assert.equal(p.elements.link.hidden, false); assert.equal(p.elements.confirm.disabled, false);
  assert.equal(p.elements.confirm.textContent, "Revogar e apagar");
  assert.match(p.elements.status.textContent, /Confira o domínio/);
});

test("payload malformado e tipos ambíguos não são enviados", async (t) => {
  const p = await portal(t);
  for (const invalid of [null, [], { ...payload, code: [payload.code] }, { ...payload, revocation: [payload.revocation] }, { ...payload, texto: "Pessoa inventada" }]) {
    p.receive(invalid);
    assert.equal(p.elements.link.hidden, true); assert.equal(p.requests.length, 0);
    assert.match(p.elements.status.textContent, /Pedido inválido/);
  }
});
