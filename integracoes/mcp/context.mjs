// Mesmo contrato da fronteira Kotlin. Qualquer campo fora da allowlist falha.
export const AREAS = ["FOR", "AGI", "VIT", "INT", "FOC", "OURO"];
export const READING_STATES = ["sem_dados", "desatualizado", "calibrando", "sem_avanco", "estimado", "no_fim"];
const object = (v) => v && typeof v === "object" && !Array.isArray(v);
const keys = (v, expected) => object(v) && Object.keys(v).length === expected.length && expected.every((k) => Object.hasOwn(v, k));
const orderedSubset = (v, choices) => Array.isArray(v) && JSON.stringify(v) === JSON.stringify(choices.filter((x) => v.includes(x)));
export function validateContext(c) {
  if (!object(c) || c.schema_version !== 1 || Object.keys(c).length < 2 ||
      Object.keys(c).some((k) => !["schema_version", "rotina", "planos", "leitura"].includes(k))) throw new Error("contexto inválido");
  for (const [key, field, choices] of [
    ["rotina", "evidencia", ["sem_metas", "sem_registro", "completa", "parcial"]],
    ["planos", "estado", ["sem_planos", "concluidos", "em_andamento", "misto"]],
  ]) if (Object.hasOwn(c, key)) {
    if (!Array.isArray(c[key]) || c[key].length !== AREAS.length || c[key].some((o, n) =>
      !keys(o, key === "rotina" ? ["area", field, "origem"] : ["area", field]) || o.area !== AREAS[n] ||
      !choices.includes(o[field]) || (key === "rotina" && o.origem !== "usuario"))) throw new Error("contexto inválido");
  }
  if (Object.hasOwn(c, "leitura")) {
    const r = c.leitura;
    if (!keys(r, ["estados", "fontes"]) || !orderedSubset(r.estados, READING_STATES) ||
        !orderedSubset(r.fontes, ["usuario", "librera"]) || (!r.estados.length !== !r.fontes.length)) throw new Error("contexto inválido");
  }
  return structuredClone(c);
}
