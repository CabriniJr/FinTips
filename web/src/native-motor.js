// Canal assíncrono limitado à origem local do APK; nenhum fetch/servidor.
const pending = new Map();
let connected;
let sequence = 0;
export const isAndroid = () => globalThis.location?.hostname === "appassets.androidplatform.net";
export const hasNativeMotor = () => isAndroid() && typeof globalThis.FinTipsMotor?.postMessage === "function";

export function nativeMotor(operation, input = {}) {
  if (!hasNativeMotor()) return Promise.reject(new Error("O motor embarcado exige este APK e um Android System WebView atualizado."));
  const bridge = globalThis.FinTipsMotor;
  if (connected !== bridge) {
    connected = bridge;
    bridge.onmessage = ({ data }) => {
      let reply;
      try { reply = JSON.parse(data); } catch { return; }
      const request = pending.get(reply.id);
      if (!request) return;
      pending.delete(reply.id); clearTimeout(request.timer);
      if (reply.error) request.reject(new Error(reply.error)); else request.resolve(reply.result);
    };
  }
  return new Promise((resolve, reject) => {
    const id = String(++sequence);
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(operation.startsWith("triagem.") ? "TRIAGEM-08: A consulta não confirmou a resposta a tempo. Continue localmente ou tente mais tarde." : operation.startsWith("ponte.") ? "PONTE-05: A conexão não confirmou a ação a tempo. Confira o estado antes de tentar novamente." : operation.startsWith("servidor.") ? "MCP-05: O servidor não confirmou a ação a tempo. Confira o estado antes de tentar novamente." : "O motor não respondeu. Tente novamente.")); }, ["triagem.sugerir", "triagem.organizar"].includes(operation) ? 55000 : operation.startsWith("ponte.") ? 45000 : 20000);
    pending.set(id, { resolve, reject, timer });
    try { bridge.postMessage(JSON.stringify({ id, operation, input })); }
    catch { clearTimeout(timer); pending.delete(id); reject(new Error("Não foi possível acessar o motor embarcado.")); }
  });
}
