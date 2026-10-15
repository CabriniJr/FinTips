import React, { useEffect, useState } from "react";
import { Icon } from "./icons.jsx";
import { PageHeading } from "./life.jsx";
import { localDay, tasksForDay, isDone } from "./life-store.js";
import { readReading } from "./reading-model.js";
import { hasNativeMotor, nativeMotor } from "./native-motor.js";
import "./connect-ai.css";

const KEY = "fintips.ia.v1";
const OPTIONS = [["rotina", "Rotina", "Evidência das metas escolhidas por você; sem nomes ou contagens."],
  ["planos", "Planos por área", "Somente se há planos em andamento ou concluídos. Sem títulos, prazos ou motivos."],
  ["leitura", "Ritmo de leitura", "Estados do ritmo e origem dos registros. Sem livros, posições ou perfis."]];
export function connectorOrigin(value) {
  const url = new URL(value.trim());
  if (url.protocol !== "https:" || url.username || url.password || !["", "/"].includes(url.pathname) || url.search || url.hash) throw new Error("Use apenas a origem HTTPS do seu conector, sem /mcp, caminhos ou credenciais.");
  return url.origin;
}
function readLinks() {
  const v = JSON.parse(localStorage.getItem(KEY) || "[]");
  if (!Array.isArray(v) || v.length > 20 || v.some((l) => !l || connectorOrigin(l.endpoint) !== l.endpoint || !/^[a-f0-9]{64}$/.test(l.revocation))) throw new Error("Lista de vínculos inválida. Ela foi preservada.");
  return v;
}
const makeSecret = () => [...crypto.getRandomValues(new Uint8Array(32))].map((v) => v.toString(16).padStart(2, "0")).join("");

async function project(state, scopes) {
  const today = localDay();
  const front = await nativeMotor("vida.frentes", { today, tasks: tasksForDay(state, today).map((t) => ({ id: t.id, area: t.atributo, done: isDone(state, t.id, today) })) });
  const books = scopes.includes("leitura") ? readReading(localStorage).livros : [];
  const reading = [];
  // Sequencial para não enfileirar milhares de mensagens no WebView.
  for (const b of books) {
    const r = await nativeMotor("leitura.ritmo", { today, points: b.observacoes.map(({ dia, progresso_bp }) => ({ dia, progresso_bp })), deadline: b.prazo || null, reading_days: b.dias_semana });
    const last = [...b.observacoes].sort((a, b) => a.dia.localeCompare(b.dia)).at(-1);
    reading.push({ state: r.estado, source: last?.origem || b.fonte });
  }
  return nativeMotor("ia.contexto", { fronts: front.fronts.map(({ area, total, done }) => ({ area, total, done })),
    plans: scopes.includes("planos") ? state.planos.map((p) => ({ area: p.atributo, done: p.concluido })) : [], reading, scopes });
}

export function ConnectAI({ life, toast }) {
  const [endpoint, setEndpoint] = useState("");
  const [code, setCode] = useState("");
  const [scopes, setScopes] = useState([]);
  const [snapshot, setSnapshot] = useState(null);
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [issue, setIssue] = useState("");
  const [links, setLinks] = useState(() => { try { return readLinks(); } catch { return null; } });
  const [opened, setOpened] = useState(false);
  const [forget, setForget] = useState(null);
  useEffect(() => { setSnapshot(null); setAck(false); }, [life.state, scopes]);
  useEffect(() => { setAck(false); }, [endpoint, code]);
  const ready = hasNativeMotor();
  const review = async () => {
    setBusy(true); setIssue(""); setOpened(false); setSnapshot(null); setAck(false);
    try { setSnapshot(await project(life.state, scopes)); }
    catch (e) { setIssue(e.message); }
    finally { setBusy(false); }
  };
  const open = async () => {
    setBusy(true); setIssue("");
    try {
      const origin = connectorOrigin(endpoint);
      const normalized = code.toUpperCase().replaceAll("-", "").replaceAll(" ", "");
      if (!/^[A-Z2-7]{12}$/.test(normalized)) throw new Error("Digite o código de 12 caracteres exibido pela autorização da IA.");
      const record = { endpoint: origin, revocation: makeSecret() };
      const previous = readLinks();
      if (previous.length >= 20) throw new Error("O limite de 20 tentativas foi alcançado. Seus códigos de revogação foram preservados.");
      // A chave precisa sobreviver mesmo se o processo fechar ao abrir o navegador.
      const next = [...previous, record]; localStorage.setItem(KEY, JSON.stringify(next)); setLinks(next);
      await nativeMotor("ia.abrir", { endpoint: origin, code: normalized, revocation: record.revocation, context: snapshot });
      setOpened(true); setAck(false); setCode("");
      toast("Continue a confirmação no navegador.");
    } catch (e) { setIssue(e.message); }
    finally { setBusy(false); }
  };
  return <>
    <PageHeading code="05.1" overline="Um contexto · duas IAs" title="Conectar IA" description="O motor fica com você. O contexto atravessa por escolha sua."/>
    <section className="privacy-card"><span className="privacy-icon"><Icon name="lock" size={24}/></span><div><h2>O mesmo MCP no ChatGPT e no Claude</h2><p>O servidor recebe apenas os indicadores reduzidos que você revisar. Extratos, nomes, títulos, motivos e registros completos continuam no aparelho. Esses indicadores ainda revelam aspectos da sua rotina.</p></div></section>
    <section className="life-card ai-connect">
      <div className="section-head"><h2>01 / Prepare a conexão</h2><span className="manual-tag">Piloto · snapshot</span></div>
      <p>Cadastre <code>https://seu-servidor/mcp</code> como conector personalizado na IA e inicie a autorização. Use a mesma origem HTTPS abaixo e o código exibido na página de autorização. A disponibilidade depende da sua conta na IA.</p>
      <p>Este APK não traz um servidor público configurado. O serviço MCP está no repositório e precisa ser hospedado antes do vínculo.</p>
      <label className="life-field">Endereço do conector<input type="url" autoComplete="off" placeholder="https://seu-servidor" value={endpoint} onChange={(e) => setEndpoint(e.target.value)} disabled={busy}/></label>
      <label className="life-field">Código da autorização<input autoComplete="off" autoCapitalize="characters" spellCheck="false" maxLength={20} placeholder="XXXX-XXXX-XXXX" value={code} onChange={(e) => setCode(e.target.value)} disabled={busy}/></label>
    </section>
    <section className="life-card ai-connect">
      <div className="section-head"><h2>02 / Escolha o contexto</h2><Icon name="context"/></div>
      <p>As áreas começam desmarcadas. Sem registro significa ausência de evidência; não é uma meta descumprida. Não há acesso automático à sua rotina.</p>
      <fieldset disabled={busy || life.blocked || !ready}><legend className="sr-only">Áreas compartilhadas com a IA</legend>
        {OPTIONS.map(([id, title, detail]) => <label className="ai-scope" key={id}><input type="checkbox" checked={scopes.includes(id)} onChange={(e) => setScopes((s) => e.target.checked ? [...s, id] : s.filter((v) => v !== id))}/><span><strong>{title}</strong><small>{detail}</small></span></label>)}
      </fieldset>
      {!ready && <p role="status">Este fluxo usa o motor do APK Android. Instale a versão atual e mantenha o Android System WebView atualizado.</p>}
      <button className="life-button full" disabled={!ready || !scopes.length || busy || life.blocked} onClick={review}>{busy ? "Preparando no aparelho…" : "Revisar exatamente o que será enviado"}<Icon name="arrow" size={18}/></button>
    </section>
    {snapshot && <section className="life-card ai-connect"><div className="section-head"><h2>03 / Revise e autorize</h2><span className="manual-tag">Somente leitura</span></div>
      <p>Este é o conteúdo integral do snapshot. Após confirmar no navegador, a IA poderá consultá-lo por uma hora. Para atualizar, revise um novo snapshot e autorize novamente.</p>
      <pre className="ai-payload" tabIndex={0} aria-label="Conteúdo exato do contexto">{JSON.stringify(snapshot, null, 2)}</pre>
      <label className="ai-scope"><input type="checkbox" checked={ack} disabled={busy} onChange={(e) => setAck(e.target.checked)}/><span>Revisei o contexto e o domínio. Quero abrir a confirmação no navegador.</span></label>
      <button className="life-button primary full" disabled={!ack || busy || !endpoint.trim() || !code.trim() || links === null} onClick={open}>Continuar vínculo MCP <Icon name="arrow" size={18}/></button>
    </section>}
    {issue && <p role="alert" className="form-error">{issue}</p>}
    {opened && <p className="ai-status" role="status">Abertura solicitada ao navegador. Confirme lá e volte à janela do ChatGPT ou Claude. O app não verifica a conclusão externa.</p>}
    <section className="life-card ai-connect"><h2>Controle das autorizações</h2><p>A revogação apaga o snapshot do servidor e bloqueia novas consultas. Não apaga mensagens que a IA já recebeu. Reiniciar o servidor ou vencer uma hora também encerra o acesso.</p>
      {links === null ? <p role="alert">Não foi possível ler os códigos locais de revogação. Eles foram preservados.</p> : !links.length ? <p>Nenhuma tentativa de vínculo iniciada neste aparelho.</p> : <ul className="ai-links">{links.map((l, n) => <li key={l.revocation}><strong>Tentativa {n + 1}</strong><span>{l.endpoint}</span><button className="life-button" disabled={busy || !ready} onClick={async () => {
        setBusy(true); setIssue("");
        try { await nativeMotor("ia.abrir", { ...l, revoke: true }); toast("Confirme a revogação no navegador."); }
        catch (e) { setIssue(e.message); } finally { setBusy(false); }
      }}>Abrir revogação</button>{forget !== l.revocation ? <button className="text-button" disabled={busy} onClick={() => setForget(l.revocation)}>Limpar código desta tentativa</button> : <div><p>Remover o código local não revoga o servidor. Faça isso somente depois de confirmar a revogação no navegador ou o vencimento do snapshot.</p><button className="life-button" disabled={busy} onClick={() => {
        try { const next = readLinks().filter((v) => v.revocation !== l.revocation); localStorage.setItem(KEY, JSON.stringify(next)); setLinks(next); setForget(null); }
        catch { setIssue("Não foi possível remover o código local. A lista foi preservada."); }
      }}>Já encerrei o acesso; apagar código local</button><button className="text-button" onClick={() => setForget(null)}>Cancelar</button></div>}</li>)}</ul>}
    </section>
  </>;
}
