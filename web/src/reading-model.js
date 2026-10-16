import { readSlice } from "./client-state.js";
import { localDay, newId } from "./life-store.js";

export const READING_KEY = "fintips.leitura.v1";
export const emptyReading = () => ({ schema_version: 1, livros: [] });
const ordinal = (d) => Date.parse(`${d}T00:00:00Z`) / 86400000;
export const validDay = (d) => typeof d === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d) &&
  Number.isFinite(ordinal(d)) && new Date(`${d}T00:00:00Z`).toISOString().slice(0, 10) === d;

// Replica fintips.reading.librera_positions. Nenhum trecho pt é mantido.
export function libreraPositions(data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("Formato de progresso não suportado.");
  const positions = []; let ignored = 0;
  for (const [key, record] of Object.entries(data)) {
    if (!key.trim() || key.includes("/") || key.includes("\\") || !record || typeof record !== "object" || Array.isArray(record) ||
      typeof record.p !== "number" || !Number.isFinite(record.p) || record.p < 0 || record.p > 1 ||
      !Number.isInteger(record.t) || record.t <= 0 || record.t > 8640000000000000) { ignored++; continue; }
    positions.push({ chave: key, progresso_bp: Math.floor(record.p * 10000 + .5), tempo_ms: record.t });
  }
  return { posicoes: positions, ignorados: ignored };
}

// Replica o cálculo Python/Kotlin. Porcentagens em centésimos de ponto percentual.
export function pacing(points, { today, deadline = null, reading_days = null }) {
  if (!validDay(today) || (deadline && !validDay(deadline)) ||
      (reading_days !== null && (!Number.isInteger(reading_days) || reading_days < 1 || reading_days > 7))) throw new Error("Plano de leitura inválido.");
  const seen = new Set();
  for (const p of points) {
    if (!validDay(p.dia) || p.dia > today || seen.has(p.dia) || !Number.isInteger(p.progresso_bp) || p.progresso_bp < 0 || p.progresso_bp > 10000) throw new Error("Observação de leitura inválida.");
    seen.add(p.dia);
  }
  const all = [...points].sort((a, b) => a.dia.localeCompare(b.dia));
  let recent = all.filter((p) => ordinal(today) - ordinal(p.dia) <= 28), reset = 0;
  for (let i = 1; i < recent.length; i++) if (recent[i].progresso_bp < recent[i - 1].progresso_bp) reset = i;
  recent = recent.slice(reset);
  const current = all.at(-1)?.progresso_bp ?? null;
  const span = recent.length >= 2 ? ordinal(recent.at(-1).dia) - ordinal(recent[0].dia) : 0;
  const gain = recent.length >= 2 ? recent.at(-1).progresso_bp - recent[0].progresso_bp : 0;
  const remaining = current !== null ? 10000 - current : null;
  const daysToTarget = deadline ? ordinal(deadline) - ordinal(today) : null;
  let projected = null, status;
  if (current === null) status = "sem_dados";
  else if (current === 10000) { status = "no_fim"; projected = 0; }
  else if (ordinal(today) - ordinal(all.at(-1).dia) > 7) status = "desatualizado";
  else if (recent.length < 2) status = "calibrando";
  else if (gain === 0) status = "sem_avanco";
  else { status = "estimado"; projected = Math.ceil(remaining * span / gain); }
  let needed = null, goal = null;
  if (remaining !== null && daysToTarget !== null && daysToTarget >= 0) {
    const available = Math.max(1, daysToTarget);
    needed = Math.ceil(remaining / available);
    if (reading_days !== null) goal = Math.ceil(remaining / Math.max(1, Math.ceil(available * reading_days / 7)));
  } else if (daysToTarget === null && reading_days !== null && status === "estimado") {
    goal = Math.ceil(gain * 7 / (span * reading_days));
  }
  return { estado: status, progresso_bp: current, amostras: recent.length, intervalo_dias: span,
    avanco_bp: gain, previsao_dias: projected, prazo_dias: daysToTarget, necessario_bp_dia: needed,
    meta_bp_sessao: goal, historico_reiniciado: reset > 0, preliminar: status === "estimado" && recent.length < 3 };
}

export function validateReading(s) {
  return s?.schema_version === 1 && Array.isArray(s.livros) && new Set(s.livros.map((b) => b.id)).size === s.livros.length &&
    s.livros.every((b) => typeof b.id === "string" && typeof b.titulo === "string" && b.titulo.trim() &&
      ["usuario", "librera"].includes(b.fonte) && typeof b.perfil === "string" &&
      (b.chave === null || typeof b.chave === "string") && (!b.prazo || validDay(b.prazo)) &&
      (b.dias_semana === null || (Number.isInteger(b.dias_semana) && b.dias_semana >= 1 && b.dias_semana <= 7)) &&
      Array.isArray(b.observacoes) && new Set(b.observacoes.map((p) => p.dia)).size === b.observacoes.length &&
      b.observacoes.every((p) => validDay(p.dia) && Number.isInteger(p.progresso_bp) && p.progresso_bp >= 0 && p.progresso_bp <= 10000 &&
        Number.isInteger(p.tempo_ms) && p.tempo_ms > 0 && ["usuario", "librera"].includes(p.origem)));
}

export function readReading(storage) {
  const raw = readSlice(storage, READING_KEY, "leitura");
  if (!raw) return emptyReading();
  const parsed = JSON.parse(raw);
  if (!validateReading(parsed)) throw new Error("Estado local de leitura inválido.");
  return parsed;
}

export function mergeLibrera(state, positions, profile, now = Date.now(), makeId = newId) {
  const next = structuredClone(state), today = localDay(new Date(now));
  let added = 0, updated = 0, ignored = 0;
  for (const p of positions) {
    const day = localDay(new Date(p.tempo_ms));
    if (!validDay(day) || day > today) { ignored++; continue; }
    let book = next.livros.find((b) => b.fonte === "librera" && b.chave === p.chave && b.perfil === profile);
    if (!book) {
      book = { id: makeId(), titulo: p.chave.replace(/\.[a-z0-9]+$/i, "").trim() || p.chave, fonte: "librera", chave: p.chave,
        perfil: profile, prazo: "", dias_semana: null, observacoes: [] };
      next.livros.push(book); added++;
    }
    const previous = book.observacoes.find((o) => o.dia === day);
    if (previous && (previous.origem === "usuario" || previous.tempo_ms >= p.tempo_ms)) continue;
    book.observacoes = [...book.observacoes.filter((o) => o.dia !== day),
      { dia: day, progresso_bp: p.progresso_bp, tempo_ms: p.tempo_ms, origem: "librera" }].sort((a, b) => a.dia.localeCompare(b.dia));
    updated++;
  }
  return { state: next, added, updated, ignored };
}
