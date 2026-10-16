import { readBundle, readChat } from "./triagem-store.js";
import { installNativeStorage, stateRequest } from "./native-storage.js";

export function bootstrapStorage() {
  if (location.hostname !== "appassets.androidplatform.net" || !globalThis.FinTipsState) return;
  const status = stateRequest("status");
  const snapshot = status.existe ? stateRequest("snapshot") : stateRequest("inicializar", {
    bundle: readBundle(globalThis.localStorage), chat: readChat(globalThis.localStorage),
  });
  // A confirmação só vem depois da validação/gravação atômica no Android.
  // O legado não é apagado nem recebe as novas escritas.
  installNativeStorage(snapshot);
}
