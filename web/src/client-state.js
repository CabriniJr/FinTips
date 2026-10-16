// Uma gravação atômica quando a triagem une vida, leitura e catálogo.
// Chaves antigas continuam intactas; após a migração, todas as escritas usam a nova.
export const CLIENT_STATE_KEY = "fintips.client.v1";
export function readSlice(storage, legacyKey, section) {
  const raw = storage.getItem(CLIENT_STATE_KEY);
  if (raw === null) return storage.getItem(legacyKey);
  const b = JSON.parse(raw);
  if (b?.schema_version !== 1 || !b.vida || !b.leitura || !b.caderno || !b[section]) throw new Error("Estado unificado inválido.");
  return JSON.stringify(b[section]);
}
export function writeSlice(storage, legacyKey, section, value) {
  const raw = storage.getItem(CLIENT_STATE_KEY);
  if (raw === null) storage.setItem(legacyKey, JSON.stringify(value));
  else {
    const b = JSON.parse(raw);
    if (b?.schema_version !== 1 || !b.vida || !b.leitura || !b.caderno) throw new Error("Estado unificado inválido.");
    const next = { ...b, [section]: value };
    const exists = (ref) => {
      const col = { tarefa: "tarefas", plano: "planos", medida: "medidas" }[ref.tipo];
      if (col) return next.vida[col].some((a) => a.id === ref.id);
      if (ref.tipo === "livro") return next.leitura.livros.some((a) => a.id === ref.id);
      return next.caderno.assets.some((a) => a.id === ref.id && a.tipo === ref.tipo);
    };
    next.caderno = { ...next.caderno, relacoes: next.caderno.relacoes.filter((r) => exists(r.de) && exists(r.para)) };
    storage.setItem(CLIENT_STATE_KEY, JSON.stringify(next));
  }
}
export const stableJSON = (v) => JSON.stringify(v, (_, x) => x && typeof x === "object" && !Array.isArray(x)
  ? Object.fromEntries(Object.keys(x).sort().map((k) => [k, x[k]])) : x);
