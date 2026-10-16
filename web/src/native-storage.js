// Autoridade Android; localStorage é usado apenas no navegador e como legado.
import { CLIENT_STATE_KEY } from "./client-state.js";
const CHAT = "fintips.triagem.chat.v1";
let installed = false;
const revisions = new Map();
export function stateRequest(method, input) {
  const bridge = globalThis.FinTipsState;
  if (!bridge || typeof bridge[method] !== "function") throw new Error("A guarda nativa não está disponível.");
  const response = JSON.parse(input === undefined ? bridge[method]() : bridge[method](JSON.stringify(input)));
  if (response.error) throw new Error(response.error);
  return response.result;
}
export const hasNativeStorage = () => installed;
export function installNativeStorage(snapshot) {
  if (!snapshot.bundle || !Number.isSafeInteger(snapshot.revisao_bundle)) throw new Error("Migração nativa inválida.");
  installed = true;
}
const nativeKey = (key) => key === CLIENT_STATE_KEY ? "bundle" : key === CHAT ? "chat" : null;
export const clientStorage = {
  getItem(key) {
    if (!installed) return globalThis.localStorage.getItem(key);
    const k = nativeKey(key);
    if (!k) return null; // o bundle nativo substitui as chaves legadas.
    const s = stateRequest("snapshot");
    revisions.set(k, s[`revisao_${k}`]);
    return s[k] === null ? null : JSON.stringify(s[k]);
  },
  setItem(key, value) {
    if (!installed) return globalThis.localStorage.setItem(key, value);
    const k = nativeKey(key);
    if (!k) throw new Error("Chave de guarda não reconhecida.");
    if (!revisions.has(k)) { const s=stateRequest("snapshot"); revisions.set(k,s[`revisao_${k}`]); }
    const s = stateRequest("salvar", { revisao: revisions.get(k), chave: k, valor: JSON.parse(value) });
    revisions.set(k,s[`revisao_${k}`]);
    if (k === "bundle") queueMicrotask(() => dispatchEvent(new StorageEvent("storage", { key: CLIENT_STATE_KEY })));
  },
};
