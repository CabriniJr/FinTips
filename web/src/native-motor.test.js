import test from "node:test";
import assert from "node:assert/strict";
import { nativeMotor, hasNativeMotor } from "./native-motor.js";

test("não expõe o canal nativo fora da origem Android", async () => {
  globalThis.location = { hostname: "localhost" };
  globalThis.FinTipsMotor = { postMessage() { throw new Error("não chamar"); } };
  assert.equal(hasNativeMotor(), false);
  await assert.rejects(nativeMotor("status"), /motor embarcado/);
  delete globalThis.FinTipsMotor; delete globalThis.location;
});

test("correlaciona respostas fora de ordem e ignora JSON malformado", async () => {
  globalThis.location = { hostname: "appassets.androidplatform.net" };
  const requests = [];
  globalThis.FinTipsMotor = { postMessage(s) { requests.push(JSON.parse(s)); } };
  try {
    const first = nativeMotor("status"), second = nativeMotor("vida.frentes", { today: "2026-10-14" });
    const reply = (r) => globalThis.FinTipsMotor.onmessage({ data: JSON.stringify(r) });
    globalThis.FinTipsMotor.onmessage({ data: "broken" }); reply({ id: "unknown", result: {} });
    reply({ id: requests[1].id, result: { done: 2 } }); reply({ id: requests[0].id, result: { motor: "kotlin" } });
    assert.deepEqual(await second, { done: 2 }); assert.deepEqual(await first, { motor: "kotlin" });
    const failure = nativeMotor("invalid"); reply({ id: requests[2].id, error: "pedido recusado" });
    await assert.rejects(failure, /pedido recusado/);
  } finally { delete globalThis.FinTipsMotor; delete globalThis.location; }
});

test("falha de transporte não deixa uma promessa pendurada", async () => {
  globalThis.location = { hostname: "appassets.androidplatform.net" };
  globalThis.FinTipsMotor = { postMessage() { throw new Error("sem canal"); } };
  try { await assert.rejects(nativeMotor("status"), /Não foi possível/); }
  finally { delete globalThis.FinTipsMotor; delete globalThis.location; }
});
