import React, { useEffect, useRef, useState } from "react";
import { nativeMotor, hasNativeMotor } from "./native-motor.js";
import { projectContext } from "./ai-projection.js";
import { Icon } from "./icons.jsx";

const AREAS = [["rotina", "Rotina"], ["planos", "Planos por área"], ["leitura", "Ritmo de leitura"]];
const LABEL = { chatgpt: "ChatGPT", claude: "Claude" };
const PHASE = { aguardando_ia: "Aguardando retorno à IA", autorizado: "OAuth concluído", consulta_recebida: "Consulta recebida do conector" };
const STATE = { conectando: "Conectando", online: "Ponte online", reconectando: "Reconectando", encerrado: "Desconectada", erro_de_protocolo: "Protocolo recusado", credencial_ou_protocolo_recusado: "Reconecte a ponte" };
export function ConnectRemote({ life, server, toast }) {
  const [bridge, setBridge] = useState(null), [origin, setOrigin] = useState(""), [invite, setInvite] = useState("");
  const [allowBridge, setAllowBridge] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [code, setCode] = useState(""), [info, setInfo] = useState(null), [scopes, setScopes] = useState([]), [snapshot, setSnapshot] = useState(null), [ack, setAck] = useState(false);
  const alert = useRef(null), ready = hasNativeMotor(), online = bridge?.estado === "online";
  const available = server?.ativo && !server.pausado && server.contexto_disponivel && !life.blocked;
  const normalized = code.replace(/[\s-]/g, "").toUpperCase();
  useEffect(() => {
    if (!ready) return;
    let active = true;
    const refresh = () => nativeMotor("ponte.status").then((s) => { if (active) setBridge(s); }).catch(() => {});
    refresh(); const timer = setInterval(refresh, 3000); addEventListener("fintips:resume", refresh);
    return () => { active = false; clearInterval(timer); removeEventListener("fintips:resume", refresh); };
  }, [ready]);
  const allowedKey = JSON.stringify(server?.escopos || []);
  useEffect(() => { const allowed = JSON.parse(allowedKey); setScopes((s) => s.filter((v) => allowed.includes(v))); }, [allowedKey]);
  useEffect(() => { setSnapshot(null); setAck(false); }, [life.state, scopes, server?.sessao]);
  useEffect(() => { setInfo(null); setSnapshot(null); setAck(false); }, [code]);
  useEffect(() => {
    const clear = () => { setSnapshot(null); setAck(false); };
    addEventListener("fintips:reading-changed", clear); addEventListener("storage", clear);
    return () => { removeEventListener("fintips:reading-changed", clear); removeEventListener("storage", clear); };
  }, []);
  useEffect(() => { if (error) alert.current?.scrollIntoView({ block: "nearest", behavior: "auto" }); }, [error]);
  const run = async (op, input = {}) => {
    setBusy(true); setError("");
    try { return await nativeMotor(op, input); } catch (e) { setError(e.message); throw e; } finally { setBusy(false); }
  };
  return <section id="conectar-chats" className="life-card ai-connect"><div className="section-head"><h2>04 / Conectar aos chats</h2><span className="manual-tag" role="status">{bridge?.ativo ? STATE[bridge.estado] || "Conexão pendente" : "Não conectados"}</span></div>
    <p>Um endpoint MCP para ChatGPT e Claude, atendido pelo celular. A ponte HTTPS encaminha as consultas; somente os indicadores revisados saem do aparelho. Registros completos e credenciais de fontes ficam locais.</p>
    {!server?.ativo && <p className="form-hint">Primeiro escolha as áreas, revise e inicie o servidor local acima.</p>}
    {!bridge?.ativo ? <form onSubmit={(e) => {
      e.preventDefault();
      run("ponte.iniciar", { origem: origin.trim(), convite: invite.trim() }).then((s) => { setBridge(s); setInvite(""); setAllowBridge(false); toast("Conexão com a ponte iniciada"); }).catch(() => {});
    }}><fieldset disabled={!ready || !available || busy}>
      <label>Endereço HTTPS da ponte<input type="url" required value={origin} onChange={(e) => { setOrigin(e.target.value); setAllowBridge(false); }} placeholder="https://ponte.seu-dominio.example" autoCapitalize="none" autoComplete="off"/></label>
      <label>Convite privado da ponte<input type="password" required value={invite} onChange={(e) => setInvite(e.target.value)} autoComplete="off" minLength={43} maxLength={64}/></label>
      <p className="form-hint">A hospedagem fornece o endereço e o convite. Esta build não tem destino externo predefinido. O convite não é o token MCP do telefone.</p>
      <label className="ai-scope"><input type="checkbox" checked={allowBridge} onChange={(e) => setAllowBridge(e.target.checked)}/><span>Autorizo este aparelho a se conectar à ponte HTTPS informada. Cada chat ainda precisa da minha autorização abaixo.</span></label>
      <button className="life-button primary full" type="submit" disabled={!allowBridge || ![43, 64].includes(invite.trim().length)}>Conectar ponte<Icon name="arrow" size={18}/></button>
    </fieldset></form> : <>
      <pre className="ai-payload" aria-label="Endpoint MCP para ChatGPT e Claude">{bridge.origem}/mcp</pre>
      <div className="local-mcp-actions"><button className="life-button" disabled={busy} onClick={() => run("ponte.copiar_endpoint").then(() => toast("Endpoint MCP copiado")).catch(() => {})}>Copiar endpoint MCP</button><button className="life-button" disabled={busy} onClick={() => run("ponte.encerrar").then((s) => { setBridge(s); setInfo(null); setSnapshot(null); toast("Ponte encerrada; acesso revogado no aparelho"); }).catch(() => {})}>Desconectar ponte</button></div>
      <ol className="form-hint"><li>Na configuração de conectores da IA, adicione o endereço acima. Selecione OAuth com registro dinâmico.</li><li>Inicie a autorização. A página FinTips mostra um código de 12 caracteres.</li><li>Informe o código aqui, revise as áreas e autorize. Volte à janela da IA para concluir o OAuth.</li></ol>
      <div className="local-mcp-actions">{["chatgpt", "claude"].map((id) => <button key={id} className="life-button" onClick={() => run("ponte.abrir_cliente", { provedor: id }).catch(() => {})}>Abrir {LABEL[id]}</button>)}</div>
      <form onSubmit={(e) => { e.preventDefault(); run("ponte.consultar", { codigo: normalized }).then(setInfo).catch(() => {}); }}><fieldset disabled={busy || !online || !available}>
        <label>Código exibido pela autorização da IA<input value={code} onChange={(e) => setCode(e.target.value)} maxLength={16} autoCapitalize="characters" autoComplete="off" placeholder="ABCD-EFGH-JKLM"/></label>
        <button className="life-button full" type="submit" disabled={!/^[A-Z2-7]{12}$/.test(normalized)}>Conferir autorização</button>
      </fieldset></form>
      {info && <div className="remote-consent"><h3>Autorizar {LABEL[info.provider]}</h3><p>Retorno OAuth para <strong>{info.callback_host}</strong>. Escolha somente as áreas que este conector pode consultar. Nenhuma começa selecionada.</p>
        <fieldset disabled={busy || !available || !online}><legend className="sr-only">Áreas autorizadas para este chat</legend>{AREAS.filter(([id]) => server?.escopos?.includes(id)).map(([id, title]) => <label className="ai-scope" key={id}><input type="checkbox" checked={scopes.includes(id)} onChange={(e) => setScopes((s) => e.target.checked ? [...s, id] : s.filter((v) => v !== id))}/><span>{title}</span></label>)}</fieldset>
        <button className="life-button full" disabled={busy || !scopes.length || !available || !online} onClick={async () => {
          setBusy(true); setError(""); setSnapshot(null); setAck(false);
          try { setSnapshot(await projectContext(life.state, scopes)); } catch (e) { setError(e.message); } finally { setBusy(false); }
        }}>Revisar contexto para {LABEL[info.provider]}</button>
        {snapshot && <><pre className="ai-payload" aria-label="Contexto permitido a este conector">{JSON.stringify(snapshot, null, 2)}</pre>
          <p>O chat poderá consultar atualizações dessas mesmas áreas enquanto o serviço estiver ativo. Fonte inválida, pausa ou contexto vencido não devolvem uma cópia antiga. Indicadores reduzidos ainda revelam sua rotina.</p>
          <label className="ai-scope"><input type="checkbox" checked={ack} disabled={busy} onChange={(e) => setAck(e.target.checked)}/><span>Autorizo {LABEL[info.provider]} a consultar estas áreas por esta ponte.</span></label>
          <button className="life-button primary full" disabled={!ack || busy || !available || !online} onClick={() => run("ponte.autorizar", { codigo: normalized, provedor: info.provider, context: snapshot }).then((s) => { setBridge(s); setCode(""); setScopes([]); toast("Autorizado no FinTips. Volte à janela da IA para concluir."); }).catch(() => {})}>Autorizar {LABEL[info.provider]}<Icon name="arrow" size={18}/></button>
        </>}
        <button className="text-button" disabled={busy} onClick={() => run("ponte.negar", { codigo: normalized }).then(() => { setCode(""); toast("Autorização recusada"); }).catch(() => {})}>Recusar esta autorização</button>
      </div>}
      <div className="remote-grants">{bridge.autorizacoes?.map((g) => <div className="remote-grant" key={g.id}><h3>{LABEL[g.provedor]}</h3><p>{PHASE[g.estado] || "Autorização pendente"}</p><p className="form-hint">{g.escopos.map((v) => AREAS.find(([id]) => id === v)?.[1]).join(" · ")}</p><button className="text-button" disabled={busy} onClick={() => run("ponte.revogar", { id: g.id }).then(setBridge).catch(() => {})}>Revogar {LABEL[g.provedor]}</button></div>)}</div>
      {!bridge.autorizacoes?.length && <p>Nenhum chat autorizado nesta sessão.</p>}
    </>}
    {error && <p ref={alert} role="alert" className="form-error">{error}</p>}
    <a className="text-button" href="/NOTICE-ponte.txt">Licenças dos componentes da conexão</a>
    <p className="form-hint">Conectar a ponte não conclui a autorização nas contas. O estado OAuth e uma consulta recebida aparecem por conector. Encerrar o serviço revoga o acesso no aparelho. Reiniciar o processo exige nova sessão; esta versão não persiste credenciais.</p>
  </section>;
}
