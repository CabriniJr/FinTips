import React, { useEffect, useRef, useState } from "react";
import { Icon } from "./icons.jsx";
import { PageHeading } from "./life.jsx";
import { hasNativeMotor, isAndroid, nativeMotor } from "./native-motor.js";
import { projectContext } from "./ai-projection.js";
import "./connect-ai.css";
import { ConnectRemote } from "./connect-remote.jsx";

const OPTIONS = [["rotina", "Rotina", "Evidência das metas escolhidas por você; sem nomes ou contagens."],
  ["planos", "Planos por área", "Somente o estado dos planos. Sem títulos, prazos ou motivos."],
  ["leitura", "Ritmo de leitura", "Estados do ritmo e origem dos registros. Sem livros, posições ou perfis."]];

function LegacyRevocations({ toast }) {
  const [links] = useState(() => {
    try {
      const v = JSON.parse(localStorage.getItem("fintips.ia.v1") || "[]");
      if (!Array.isArray(v) || v.length > 20) return null;
      return v.filter((l) => {
        if (!l || !/^[a-f0-9]{64}$/.test(l.revocation || "")) return false;
        const u = new URL(l.endpoint);
        return u.protocol === "https:" && u.origin === l.endpoint && !u.username && !u.password;
      });
    } catch { return null; }
  });
  if (links?.length === 0) return null;
  return <details className="life-card ai-connect"><summary>Autorizações do piloto remoto anterior</summary><p>Os códigos locais anteriores foram preservados. Esta ação abre o navegador para revogar aquele snapshot; o servidor local é independente.</p>
    {links === null ? <p>Não foi possível ler a lista anterior. Ela foi preservada.</p> : links.map((l, i) => <div key={i}><p>{l.endpoint}</p><button className="life-button" onClick={async () => {
      try { await nativeMotor("ia.abrir", { ...l, revoke: true }); toast("Confirme a revogação no navegador."); }
      catch { toast("Não foi possível solicitar a revogação. O código foi preservado."); }
    }}>Abrir revogação anterior</button></div>)}</details>;
}

export function ConnectAI({ life, toast, syncIssue }) {
  const [server, setServer] = useState(null);
  const [scopes, setScopes] = useState([]);
  const [snapshot, setSnapshot] = useState(null);
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [issue, setIssue] = useState("");
  const hydrated = useRef(false);
  const ready = hasNativeMotor();
  useEffect(() => { setSnapshot(null); setAck(false); }, [life.state, scopes]);
  useEffect(() => {
    const clear = () => { setSnapshot(null); setAck(false); };
    addEventListener("fintips:reading-changed", clear); addEventListener("storage", clear);
    return () => { removeEventListener("fintips:reading-changed", clear); removeEventListener("storage", clear); };
  }, []);
  useEffect(() => {
    if (!ready) return;
    let active = true;
    const refresh = () => nativeMotor("servidor.status").then((s) => {
      if (!active) return;
      setServer(s);
      if (!hydrated.current) { hydrated.current = true; if (s.ativo) setScopes(s.escopos); }
    }).catch(() => { if (active) setIssue("Não foi possível consultar o servidor local."); });
    refresh(); const id = setInterval(refresh, 3000);
    addEventListener("fintips:resume", refresh);
    return () => { active = false; clearInterval(id); removeEventListener("fintips:resume", refresh); };
  }, [ready]);
  const command = async (operation, input = {}) => {
    setBusy(true); setIssue("");
    try {
      const r = await nativeMotor(operation, input); setServer(r);
      dispatchEvent(new Event("fintips:mcp-state")); return r;
    } catch (e) { setIssue(e.message); throw e; }
    finally { setBusy(false); }
  };
  const select = async (id, checked) => {
    if (server?.ativo && !server.pausado) {
      try { await command("servidor.pausar", { sessao: server.sessao }); }
      catch { return; }
    }
    setScopes((s) => checked ? [...s, id] : s.filter((v) => v !== id));
  };
  const copy = async (operation, message) => {
    try { await nativeMotor(operation); toast(message); }
    catch { setIssue("Não foi possível copiar. Confira se o servidor está ativo."); }
  };
  return <>
    <PageHeading code="05.1" overline="Motor local · conexão MCP" title="Conectar IA" description="Seu celular calcula. Você autoriza os chats."/>
    <section className="privacy-card"><span className="privacy-icon"><Icon name="lock" size={24}/></span><div><h2>Servidor no seu celular</h2><p>O motor e os registros ficam neste aparelho. A conexão aos chats usa uma ponte HTTPS e somente os indicadores que você revisar e autorizar. Títulos e valores financeiros continuam privados.</p></div></section>
    <button className="life-button primary full" onClick={() => document.getElementById("conectar-chats")?.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" })}>Configurar ChatGPT e Claude<Icon name="arrow" size={18}/></button>
    <section className="life-card ai-connect"><div className="section-head"><h2>01 / Servidor local</h2><span className="manual-tag" role="status">{!ready ? isAndroid() ? "Atualize o WebView" : "APK Android necessário" : !server ? "Consultando…" : server.ativo ? server.pausado ? "Pausado para revisão" : server.teste_local === "ok" ? "MCP local verificado" : "Teste local pendente" : "Encerrado"}</span></div>
      <p>Inicie depois de escolher e revisar as áreas. Enquanto ativo, ele mantém uma notificação de controle e atualiza os indicadores autorizados ao usar o FinTips. Encerrar revoga o token e apaga o contexto da sessão.</p>
      {server?.ativo && <><pre className="ai-payload" aria-label="Endereço do servidor local">{server.endpoint}</pre><p className="motor-label">Somente 127.0.0.1 · sem acesso pela rede Wi-Fi · {server.contexto_disponivel ? "contexto disponível" : "contexto indisponível"}</p>
        <p role="status">{server.teste_local === "ok" ? "O app inicializou o MCP e consultou a ferramenta pelo socket deste celular." : "O funcionamento ainda não foi confirmado por uma consulta MCP local."}</p>
        <button className="life-button full" disabled={busy || server.pausado || !server.contexto_disponivel} onClick={() => command("servidor.verificar", { sessao: server.sessao }).then(() => toast("Teste MCP local aprovado. A conexão às contas de IA continua pendente.")).catch(() => {})}>Testar servidor neste celular</button>
        <p>Áreas autorizadas: {server.escopos.map((id) => OPTIONS.find(([k]) => k === id)?.[1]).join(", ")}.</p>
        <div className="local-mcp-actions"><button className="life-button" disabled={busy} onClick={() => copy("servidor.copiar_endereco", "Endereço local copiado")}>Copiar endereço</button><button className="life-button" disabled={busy} onClick={() => copy("servidor.copiar_token", "Token copiado. Cole apenas no cliente MCP autorizado.")}>Copiar token</button></div>
        <p>Configure o cliente local com o endereço acima e o token no header Authorization: Bearer. O token não aparece no contexto da IA e muda ao reiniciar o servidor.</p>
        <button className="life-button full" disabled={busy} onClick={() => command("servidor.encerrar").then(() => { setAck(false); setSnapshot(null); toast("Servidor encerrado e token revogado"); }).catch(() => {})}>Encerrar servidor</button>
        <button className="text-button" onClick={() => nativeMotor("servidor.notificacoes").catch(() => setIssue("Abra as configurações de notificações do Android."))}>Notificação de controle</button>
      </>}
      {server?.versao_app && <p className="motor-label">Build {server.versao_app} · Android API {server.android_sdk}</p>}
      {!ready && <p>{isAndroid() ? "O WebView deste Android não oferece o canal necessário. Atualize o Android System WebView e o Chrome pela loja, feche o FinTips e abra novamente." : "Instale o APK Android atual para usar o servidor local."}</p>}
    </section>
    <section className="life-card ai-connect"><div className="section-head"><h2>02 / Escolha o contexto</h2><Icon name="context"/></div>
      <p>Nenhuma área começa autorizada. Sem registro é ausência de evidência, não uma meta descumprida. Alterar a seleção pausa as consultas até você aplicar uma nova revisão.</p>
      <fieldset disabled={busy || life.blocked || !ready}><legend className="sr-only">Áreas disponíveis no servidor local</legend>{OPTIONS.map(([id, title, detail]) => <label className="ai-scope" key={id}><input type="checkbox" checked={scopes.includes(id)} onChange={(e) => select(id, e.target.checked)}/><span><strong>{title}</strong><small>{detail}</small></span></label>)}</fieldset>
      <button className="life-button full" disabled={!ready || !scopes.length || busy || life.blocked} onClick={async () => {
        setBusy(true); setIssue(""); setSnapshot(null); setAck(false);
        try { setSnapshot(await projectContext(life.state, scopes)); }
        catch (e) { setIssue(e.message); } finally { setBusy(false); }
      }}>{busy ? "Preparando no aparelho…" : "Revisar contexto local"}<Icon name="arrow" size={18}/></button>
    </section>
    {snapshot && <section className="life-card ai-connect"><div className="section-head"><h2>03 / Revise e autorize</h2><span className="manual-tag">Somente leitura</span></div>
      <p>Este é o formato integral consultável. As mesmas áreas serão recalculadas localmente ao usar o app. Sem atualização por uma hora, a ferramenta informa indisponibilidade. Encerrar ou pausar interrompe as consultas.</p>
      <pre className="ai-payload" tabIndex={0} aria-label="Conteúdo exato do contexto">{JSON.stringify(snapshot, null, 2)}</pre>
      <label className="ai-scope"><input type="checkbox" checked={ack} disabled={busy} onChange={(e) => setAck(e.target.checked)}/><span>Autorizo estas áreas no servidor local e a atualização dos indicadores ao usar o FinTips.</span></label>
      <button className="life-button primary full" disabled={!ack || busy || !ready || life.blocked} onClick={() => command("servidor.iniciar", { context: snapshot }).then(() => { setAck(false); setSnapshot(null); toast("Servidor MCP ativo neste celular"); }).catch(() => {})}>{server?.ativo ? "Aplicar áreas e retomar servidor" : "Iniciar servidor neste celular"}<Icon name="arrow" size={18}/></button>
    </section>}
    {(issue || syncIssue) && <p role="alert" className="form-error">{issue || syncIssue}</p>}
    <ConnectRemote life={life} server={server} toast={toast}/>
    <LegacyRevocations toast={toast}/>
  </>;
}
