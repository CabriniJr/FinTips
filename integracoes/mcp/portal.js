// Nenhum script, fonte, analytics ou domínio externo.
import { validateContext } from "./context.mjs";
const status = document.getElementById("status");
async function post(path, value) {
  const r = await fetch(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(value), credentials: "omit", cache: "no-store", redirect: "error" });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || "Não foi possível concluir.");
  return data;
}
const oauth = document.getElementById("oauth");
if (oauth) {
  let attempts = 0;
  const poll = async () => {
    try {
      if (++attempts > 155) throw new Error("Solicitação expirada. Reinicie na IA.");
      const r = await post("/api/poll", { poll: oauth.dataset.poll });
      if (r.redirect) { location.replace(r.redirect); return; }
      setTimeout(poll, 2000);
    } catch (e) { status.textContent = e.message; }
  };
  poll();
} else {
  let generation = 0;
  const receive = () => {
    // Reabrir a mesma aba pode mudar só o fragmento, sem recarregar o módulo.
    const raw = location.hash.slice(1), current = ++generation;
    history.replaceState(null, "", location.pathname);
    const section = document.getElementById("link"), button = document.getElementById("confirm");
    section.hidden = true; button.disabled = false; button.onclick = null;
    status.textContent = "Inicie o vínculo na IA e continue pelo app FinTips.";
    if (!raw) return;
    try {
      const payload = JSON.parse(decodeURIComponent(raw));
      if (JSON.stringify(payload).length > 12000) throw new Error();
      if (!payload || typeof payload !== "object" || typeof payload.revocation !== "string" || !/^[a-f0-9]{64}$/.test(payload.revocation)) throw new Error();
      if (payload.revoke === true) {
        if (Object.keys(payload).sort().join(",") !== "revocation,revoke") throw new Error();
      } else {
        if (Object.keys(payload).sort().join(",") !== "code,context,revocation" || typeof payload.code !== "string" || !/^[A-Z2-7]{12}$/.test(payload.code)) throw new Error();
        validateContext(payload.context);
      }
      section.hidden = false;
      document.getElementById("operation").textContent = payload.revoke ? "Revogar este vínculo e apagar o snapshot deste servidor." : "Este é o contexto enviado ao servidor após sua confirmação. A IA poderá consultá-lo durante uma hora.";
      document.getElementById("context").textContent = payload.revoke ? "A IA deixará de conseguir consultar o snapshot. Mensagens já recebidas pela IA não são apagadas." : JSON.stringify(payload.context, null, 2);
      button.textContent = payload.revoke ? "Revogar e apagar" : "Autorizar por uma hora";
      status.textContent = "Confira o domínio na barra do navegador antes de confirmar.";
      button.onclick = async () => {
        button.disabled = true;
        try {
          await post(payload.revoke ? "/api/revoke" : "/api/link", payload.revoke ? { revocation: payload.revocation } : payload);
          if (current !== generation) return;
          section.hidden = true;
          status.textContent = payload.revoke ? "Vínculo revogado neste servidor. Você pode voltar ao app." : "Contexto autorizado por uma hora. Volte à janela da IA para concluir a conexão.";
        } catch (e) { if (current === generation) { status.textContent = e.message; button.disabled = false; } }
      };
    } catch { status.textContent = "Pedido inválido. Reabra esta página pelo app."; }
  };
  receive();
  addEventListener("hashchange", receive);
}
