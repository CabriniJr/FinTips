import test from "node:test";
import assert from "node:assert/strict";
import { STORAGE_KEY, dailyProgress, emptyLife, isDone, localDay, readLife,
  removeTask, shiftDay, tasksForDay, toggleTask, validateLife } from "./life-store.js";

const daily = { id: "daily", titulo: "Ler", atributo: "INT", inicio: "2026-10-14", repetir: true };
const once = { id: "once", titulo: "Organizar", atributo: "FOC", inicio: "2026-10-14", repetir: false };
const sample = () => ({ ...emptyLife(), tarefas: [daily, once] });

test("tarefa diária reaparece amanhã; conclusão permanece no dia registrado", () => {
  const done = toggleTask(sample(), daily.id, "2026-10-14");
  assert.equal(isDone(done, daily.id, "2026-10-14"), true);
  assert.equal(isDone(done, daily.id, "2026-10-15"), false);
  assert.deepEqual(tasksForDay(done, "2026-10-15"), [daily]);
  assert.deepEqual(tasksForDay(done, "2026-10-13"), []);
  assert.equal(done.registros[0].origem, "usuario");
});

test("desmarcar uma tarefa não apaga cumprimento de outros dias", () => {
  let state = toggleTask(sample(), daily.id, "2026-10-14");
  state = toggleTask(state, daily.id, "2026-10-15");
  state = toggleTask(state, daily.id, "2026-10-14");
  assert.equal(isDone(state, daily.id, "2026-10-14"), false);
  assert.equal(isDone(state, daily.id, "2026-10-15"), true);
});

test("tarefa pontual e dia anterior ao início não recebem registros", () => {
  const state = sample();
  assert.equal(toggleTask(state, once.id, "2026-10-15"), state);
  assert.equal(toggleTask(state, daily.id, "2026-10-13"), state);
  assert.equal(toggleTask(state, "missing", "2026-10-14"), state);
});

test("progresso é calculado com tarefas reais e separado por área", () => {
  const state = toggleTask(sample(), daily.id, "2026-10-14");
  assert.deepEqual(dailyProgress(state, "2026-10-14"), { total: 2, done: 1, pct: 50 });
  assert.deepEqual(dailyProgress(state, "2026-10-14", "INT"), { total: 1, done: 1, pct: 100 });
  assert.deepEqual(dailyProgress(state, "2026-10-14", "VIT"), { total: 0, done: 0, pct: 0 });
});

test("remoção limpa somente os registros da tarefa removida", () => {
  const done = toggleTask(toggleTask(sample(), daily.id, "2026-10-14"), once.id, "2026-10-14");
  const removed = removeTask(done, daily.id);
  assert.deepEqual(removed.tarefas, [once]);
  assert.deepEqual(removed.registros, [{ tarefaId: once.id, dia: "2026-10-14", origem: "usuario" }]);
  assert.equal(validateLife(removed), true);
});

test("estado inválido é recusado sem sobrescrever o armazenamento", () => {
  for (const raw of ["{broken", JSON.stringify({ ...emptyLife(), schema_version: 2 }),
    JSON.stringify({ ...sample(), tarefas: [daily, daily] }),
    JSON.stringify({ ...sample(), registros: [{ tarefaId: "missing", dia: "2026-10-14", origem: "usuario" }] })]) {
    const storage = { getItem(key) { if (key === "fintips.client.v1") return null; assert.equal(key, STORAGE_KEY); return raw; },
      setItem() { assert.fail("dados inválidos não podem ser sobrescritos"); } };
    assert.throws(() => readLife(storage));
  }
});

test("medida manual zero é válida; dado ausente e registro presumido são recusados", () => {
  const state = { ...emptyLife(), medidas: [{ id: "m", dia: "2026-10-14", app: "Leitor", minutos: 0, origem: "usuario" }] };
  assert.equal(validateLife(state), true);
  for (const minutes of [null, -1, 1441, 1.5]) assert.equal(validateLife({ ...state, medidas: [{ ...state.medidas[0], minutos: minutes }] }), false);
  assert.equal(validateLife({ ...state, medidas: [{ ...state.medidas[0], origem: "sensor" }] }), false);
  assert.equal(validateLife({ ...sample(), registros: [{ tarefaId: daily.id, dia: "2026-10-14", origem: "presumido" }] }), false);
});

test("datas impossíveis e duplicatas de cumprimento não são aceitas", () => {
  assert.equal(validateLife({ ...sample(), tarefas: [{ ...daily, inicio: "2026-02-30" }] }), false);
  const done = toggleTask(sample(), daily.id, "2026-10-14");
  assert.equal(validateLife({ ...done, registros: [...done.registros, ...done.registros] }), false);
});

test("o calendário usa data local e atravessa virada de mês e ano", () => {
  assert.equal(localDay(new Date(2026, 9, 14, 0, 1)), "2026-10-14");
  assert.equal(shiftDay("2026-12-31", 1), "2027-01-01");
  assert.equal(shiftDay("2026-03-01", -1), "2026-02-28");
  assert.equal(shiftDay("2024-03-01", -1), "2024-02-29");
});
