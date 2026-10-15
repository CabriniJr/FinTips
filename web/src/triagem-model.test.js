import test from "node:test";
import assert from "node:assert/strict";
import { answerField, containsKey, inferArea, makeDraft } from "./triagem-model.js";
import { readBundle, commitBundle, backupAll } from "./triagem-store.js";
import { CLIENT_STATE_KEY, writeSlice } from "./client-state.js";
import { STORAGE_KEY, readLife } from "./life-store.js";
import { READING_KEY, readReading } from "./reading-model.js";
const store = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v), removeItem: (k) => m.delete(k) }; };

test("extração é proposta local, respeita área ambígua e não trunca valores monetários", () => {
  const d = makeDraft("Tarefa: treinar amanhã todos os dias", undefined, "2026-10-15");
  assert.equal(d.tipo, "tarefa"); assert.equal(d.campos.inicio, "2026-10-16"); assert.equal(d.campos.repetir, true); assert.equal(d.campos.atributo, "FOR");
  assert.equal(inferArea("Treinar e estudar"), null);
  assert.equal(makeDraft("Assinatura: exemplo R$ 1.234,56").campos.valor_centavos, undefined);
  assert.equal(makeDraft("Assinatura: exemplo R$ 123,45").campos.valor_centavos, 12345);
  assert.equal(makeDraft("Livro: exemplo 25%").campos.progresso_bp, 2500);
});

test("respostas numéricas usam unidades humanas e recusam zero inventado ou dados ambíguos", () => {
  const n = { tipo: "inteiro", minimo: 0, maximo: 1000000 };
  assert.equal(answerField("0", n, "valor_centavos"), 0);
  assert.equal(answerField("R$ 125,45", n, "valor_centavos"), 12545);
  assert.equal(answerField("25%", { ...n, maximo: 10000 }, "progresso_bp"), 2500);
  for (const v of ["", "1.234,56", "-1", "1e3"]) assert.throws(() => answerField(v, n, "valor_centavos"));
  assert.throws(() => answerField("2026-02-30", { tipo: "data" }, "prazo"));
  assert.equal(containsKey("sk-" + "A".repeat(30)), true);
});

test("migração atômica preserva legado e todas as edições seguintes usam o estado unificado", () => {
  const s = store(); const before = readBundle(s);
  s.setItem(STORAGE_KEY, JSON.stringify(before.vida)); s.setItem(READING_KEY, JSON.stringify(before.leitura));
  const next = structuredClone(before); next.vida.planos.push({ id: "p", titulo: "Plano sintético", atributo: "INT", porque: "Escolha", proximoPasso: "Passo", prazo: "", concluido: false });
  commitBundle(s, before, next);
  assert.equal(readLife(s).planos.length, 1); assert.deepEqual(JSON.parse(s.getItem(STORAGE_KEY)), before.vida);
  writeSlice(s, STORAGE_KEY, "vida", { ...readLife(s), tarefas: [{ id: "t", titulo: "Tarefa sintética", atributo: "INT", repetir: true, inicio: "2026-10-15" }] });
  assert.equal(readBundle(s).vida.tarefas.length, 1); assert.deepEqual(readReading(s), next.leitura);
  writeSlice(s, READING_KEY, "leitura", readReading(s)); assert.equal(readBundle(s).vida.planos.length, 1);
});

test("mudança concorrente ou falha de quota nunca aplica metade de um lote", () => {
  const s = store(); const before = readBundle(s), next = structuredClone(before);
  const changed = structuredClone(before); changed.vida.medidas.push({ id: "m", dia: "2026-10-15", app: "Exemplo", minutos: 0, origem: "usuario" });
  commitBundle(s, before, changed); assert.throws(() => commitBundle(s, before, next)); assert.deepEqual(readBundle(s), changed);
  const fail = { getItem: s.getItem, setItem() { throw new Error("quota"); } };
  assert.throws(() => commitBundle(fail, changed, before)); assert.deepEqual(readBundle(s), changed);
});

test("excluir um registro legado remove vínculos órfãos e backup não inclui outras chaves", () => {
  const s = store(), before = readBundle(s), b = structuredClone(before);
  b.vida.tarefas.push({ id: "t", titulo: "Exemplo", atributo: "INT", repetir: true, inicio: "2026-10-15" });
  b.caderno.assets.push({ id: "a", tipo: "fato", campos: { titulo: "Exemplo", descricao: "Fato sintético" } });
  b.caderno.relacoes.push({ de: { tipo: "tarefa", id: "t" }, para: { tipo: "fato", id: "a" }, tipo: "relacionado", porque: "Confirmado" });
  commitBundle(s, before, b); writeSlice(s, STORAGE_KEY, "vida", before.vida);
  assert.equal(readBundle(s).caderno.relacoes.length, 0);
  s.setItem("outra-chave", "SEGREDO_NAO_EXPORTAR");
  assert.equal(JSON.stringify(backupAll(s)).includes("SEGREDO_NAO_EXPORTAR"), false);
  s.setItem(CLIENT_STATE_KEY, "{broken"); assert.throws(() => readLife(s)); assert.throws(() => readReading(s));
});
