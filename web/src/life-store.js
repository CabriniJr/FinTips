// Estado exclusivamente no client. Não é enviado à API financeira ou ao MCP.
export const STORAGE_KEY = "fintips.vida.v1";
export const AREAS = [
  { id: "FOR", nome: "Força", detalhe: "Treino e resistência", cor: "#b85b41", icone: "strength" },
  { id: "AGI", nome: "Movimento", detalhe: "Caminhada e cardio", cor: "#467b68", icone: "movement" },
  { id: "VIT", nome: "Saúde", detalhe: "Sono e cuidado", cor: "#8b5886", icone: "heart" },
  { id: "INT", nome: "Estudos", detalhe: "Aprendizado e carreira", cor: "#5075aa", icone: "book" },
  { id: "FOC", nome: "Foco", detalhe: "Atenção e tempo", cor: "#8b7328", icone: "focus" },
  { id: "OURO", nome: "Finanças", detalhe: "Reserva e escolhas", cor: "#367c7a", icone: "wallet" },
];

export const emptyLife = () => ({ schema_version: 1, tarefas: [], registros: [], planos: [], medidas: [] });
export const localDay = (date = new Date()) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
export function newId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  // Prévia de celular em HTTP na rede local: randomUUID exige contexto seguro,
  // mas getRandomValues continua disponível. Não usar relógio como identidade.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

const isArea = (id) => AREAS.some((a) => a.id === id);
const text = (s) => typeof s === "string";
const day = (s) => text(s) && /^\d{4}-\d{2}-\d{2}$/.test(s) && localDay(new Date(`${s}T12:00:00`)) === s;
export function validateLife(value) {
  if (!value || value.schema_version !== 1 ||
      !["tarefas", "registros", "planos", "medidas"].every((key) => Array.isArray(value[key]))) return false;
  const ids = (items) => new Set(items.map((t) => t.id)).size === items.length;
  return ids(value.tarefas) && ids(value.planos) && ids(value.medidas) &&
    value.tarefas.every((t) => text(t.id) && text(t.titulo) && t.titulo.trim() && isArea(t.atributo) &&
      day(t.inicio) && typeof t.repetir === "boolean") &&
    value.registros.every((r) => text(r.tarefaId) && day(r.dia) && r.origem === "usuario" &&
      value.tarefas.some((t) => t.id === r.tarefaId)) &&
    new Set(value.registros.map((r) => `${r.tarefaId}/${r.dia}`)).size === value.registros.length &&
    value.planos.every((p) => text(p.id) && text(p.titulo) && p.titulo.trim() && isArea(p.atributo) &&
      text(p.porque) && text(p.proximoPasso) && (!p.prazo || day(p.prazo)) && typeof p.concluido === "boolean") &&
    value.medidas.every((m) => text(m.id) && day(m.dia) && text(m.app) && m.app.trim() &&
      Number.isInteger(m.minutos) && m.minutos >= 0 && m.minutos <= 1440 && m.origem === "usuario");
}

export function readLife(storage) {
  const raw = storage.getItem(STORAGE_KEY);
  if (!raw) return emptyLife();
  const parsed = JSON.parse(raw);
  if (!validateLife(parsed)) throw new Error("estado local inválido");
  return parsed;
}

export function tasksForDay(state, selectedDay) {
  return state.tarefas.filter((t) => t.repetir ? t.inicio <= selectedDay : t.inicio === selectedDay);
}
export const isDone = (state, taskId, selectedDay) =>
  state.registros.some((r) => r.tarefaId === taskId && r.dia === selectedDay);

export function toggleTask(state, taskId, selectedDay) {
  if (!tasksForDay(state, selectedDay).some((t) => t.id === taskId)) return state;
  const registros = isDone(state, taskId, selectedDay)
    ? state.registros.filter((r) => !(r.tarefaId === taskId && r.dia === selectedDay))
    : [...state.registros, { tarefaId: taskId, dia: selectedDay, origem: "usuario" }];
  return { ...state, registros };
}

export function removeTask(state, taskId) {
  return { ...state, tarefas: state.tarefas.filter((t) => t.id !== taskId),
    registros: state.registros.filter((r) => r.tarefaId !== taskId) };
}

export function dailyProgress(state, selectedDay, area) {
  const tasks = tasksForDay(state, selectedDay).filter((t) => !area || t.atributo === area);
  const done = tasks.filter((t) => isDone(state, t.id, selectedDay)).length;
  return { total: tasks.length, done, pct: tasks.length ? Math.round(done / tasks.length * 100) : 0 };
}

export function shiftDay(selectedDay, offset) {
  const date = new Date(`${selectedDay}T12:00:00`);
  date.setDate(date.getDate() + offset);
  return localDay(date);
}
