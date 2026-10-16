import { hasNativeStorage } from "./native-storage.js";
import { clientStorage } from "./native-storage.js";
import { nativeMotor } from "./native-motor.js";
import { localDay, tasksForDay, isDone } from "./life-store.js";
import { readReading } from "./reading-model.js";

// Nenhum título, texto, arquivo ou valor financeiro atravessa esta fronteira.
export async function projectContext(state, scopes) {
  if (hasNativeStorage()) return nativeMotor("estado.contexto", { scopes });
  const today = localDay();
  const front = await nativeMotor("vida.frentes", { today, tasks: tasksForDay(state, today).map((t) => ({ id: t.id, area: t.atributo, done: isDone(state, t.id, today) })) });
  const books = scopes.includes("leitura") ? readReading(clientStorage).livros : [];
  const reading = [];
  for (const b of books) {
    const r = await nativeMotor("leitura.ritmo", { today, points: b.observacoes.map(({ dia, progresso_bp }) => ({ dia, progresso_bp })), deadline: b.prazo || null, reading_days: b.dias_semana });
    const last = [...b.observacoes].sort((a, b) => a.dia.localeCompare(b.dia)).at(-1);
    reading.push({ state: r.estado, source: last?.origem || b.fonte });
  }
  return nativeMotor("ia.contexto", { fronts: front.fronts.map(({ area, total, done }) => ({ area, total, done })),
    plans: scopes.includes("planos") ? state.planos.map((p) => ({ area: p.atributo, done: p.concluido })) : [], reading, scopes });
}
