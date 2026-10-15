import { CLIENT_STATE_KEY, stableJSON } from "./client-state.js";
import { readLife, validateLife } from "./life-store.js";
import { readReading, validateReading } from "./reading-model.js";
export const CHAT_KEY = "fintips.triagem.chat.v1";
export const emptyNotebook = () => ({ schema_version: 1, assets: [], relacoes: [], aplicacoes: [] });
export function readBundle(storage) {
  const raw = storage.getItem(CLIENT_STATE_KEY);
  const b = raw === null ? { schema_version: 1, vida: readLife(storage), leitura: readReading(storage), caderno: emptyNotebook() } : JSON.parse(raw);
  if (b?.schema_version !== 1 || !validateLife(b.vida) || !validateReading(b.leitura) || b.caderno?.schema_version !== 1 ||
      !["assets", "relacoes", "aplicacoes"].every((k) => Array.isArray(b.caderno[k])) ||
      !b.caderno.assets.every((a) => typeof a.id === "string" && typeof a.tipo === "string" && a.campos && typeof a.campos === "object" && !Array.isArray(a.campos)) ||
      !b.caderno.relacoes.every((r) => r.de && r.para && typeof r.tipo === "string" && typeof r.porque === "string")) throw new Error("Seus registros locais precisam de revisão. Eles foram preservados.");
  return b;
}
export function commitBundle(storage, before, next) {
  if (stableJSON(readBundle(storage)) !== stableJSON(before)) throw new Error("Seus registros mudaram. Revise a proposta atualizada antes de salvar.");
  if (!validateLife(next.vida) || !validateReading(next.leitura) || next.caderno?.schema_version !== 1) throw new Error("Proposta local inválida.");
  // setItem é a única mutação: falha de quota não deixa metade de um lote gravado.
  storage.setItem(CLIENT_STATE_KEY, JSON.stringify(next));
  if (typeof dispatchEvent === "function") {
    dispatchEvent(new StorageEvent("storage", { key: null }));
    dispatchEvent(new Event("fintips:reading-changed"));
    dispatchEvent(new Event("fintips:triagem-changed"));
  }
}
export function readChat(storage) {
  const raw = storage.getItem(CHAT_KEY);
  if (!raw) return null;
  const c = JSON.parse(raw);
  if (c?.schema_version !== 1 || !Array.isArray(c.messages) || !Array.isArray(c.drafts) || !Array.isArray(c.links) ||
      (c.handledTurn !== undefined && (typeof c.handledTurn !== "string" || c.handledTurn.length > 5000)) ||
      (c.agentQuestion !== undefined && c.agentQuestion !== null && (!Number.isInteger(c.agentQuestion.index) || c.agentQuestion.index < 0 || c.agentQuestion.index >= c.drafts.length || typeof c.agentQuestion.field !== "string" || (c.agentQuestion.text !== undefined && (typeof c.agentQuestion.text !== "string" || c.agentQuestion.text.length > 5000)))) ||
      c.messages.length > 80 || c.drafts.length > 20 || c.links.length > 30 ||
      !Array.isArray(c.separate) || !c.separate.every((v) => typeof v === "string") || typeof c.cloudConsent !== "boolean" ||
      !Number.isInteger(c.requests) || c.requests < 0 || c.requests > 1000000 ||
      !c.drafts.every((d) => typeof d.id === "string" && typeof d.tipo === "string" && d.campos && typeof d.campos === "object" && !Array.isArray(d.campos) && typeof d.porque === "string" && ["criar", "atualizar"].includes(d.acao)) ||
      !c.messages.every((m) => ["usuario", "assistente"].includes(m.role) && typeof m.text === "string" && m.text.length <= 5000))
    throw new Error("A conversa local não pôde ser lida. Faça uma cópia antes de recuperá-la.");
  return c;
}
export function backupAll(storage) {
  try { return { tipo: "fintips_backup", schema_version: 2, bundle: readBundle(storage), conversa: readChat(storage) }; }
  catch { return { tipo: "fintips_recuperacao", schema_version: 1, originais: Object.fromEntries([CLIENT_STATE_KEY, "fintips.vida.v1", "fintips.leitura.v1", CHAT_KEY].map((k) => [k, storage.getItem(k)])) }; }
}
