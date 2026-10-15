import React, { useCallback, useEffect, useRef, useState } from "react";
import { PageHeading } from "./life.jsx";
import { AREAS, localDay, newId } from "./life-store.js";
import { hasNativeMotor, isAndroid, nativeMotor } from "./native-motor.js";
import { CHAT_KEY, commitBundle, readBundle, readChat } from "./triagem-store.js";
import { stableJSON } from "./client-state.js";
import { inlineAnswer, inlineFields, splitIntents, correctionCandidates, containsKey, displayValue, makeDraft } from "./triagem-model.js";
import { Icon } from "./icons.jsx";
import "./triagem-chat.css";

async function contract(op, input = {}) {
  if (isAndroid()) return nativeMotor(op, input);
  const path = op.replace("triagem.", "");
  const r = await fetch(`/api/triagem/${path}`, { method: path === "catalogo" ? "GET" : "POST",
    headers: { "Content-Type": "application/json" }, ...(path === "catalogo" ? {} : { body: JSON.stringify(input) }) });
  if (!r.ok) throw new Error("A API local não confirmou o contrato. Seus registros foram preservados.");
  return r.json();
}
const initialChat = () => ({ schema_version: 1, messages: [], drafts: [], links: [], separate: [], cloudConsent: false, requests: 0 });
const turnSignature = (c) => { const user = [...c.messages].reverse().find((m) => m.role === "usuario"); return user?.id || user?.text || ""; };
function agentLinks(previous, result, links) {
  const map = new Map(previous.map((d, i) => [`${d.tipo}/${d.id}`, result[i] && { tipo: result[i].tipo, id: result[i].id }]));
  const all = links.map((r) => ({ ...r, de: map.get(`${r.de.tipo}/${r.de.id}`) || r.de, para: map.get(`${r.para.tipo}/${r.para.id}`) || r.para }));
  const resolved = all.filter((r, i) => stableJSON(r.de) !== stableJSON(r.para) && all.findIndex((x) => x.tipo === r.tipo && stableJSON(x.de) === stableJSON(r.de) && stableJSON(x.para) === stableJSON(r.para)) === i);
  if (resolved.length > 30) throw new Error("Há muitas conexões neste conjunto. Salve os registros atuais antes de continuar.");
  return resolved;
}
export function TriageChat({ toast }) {
  const [initial] = useState(() => { try { return { chat: readChat(localStorage) || initialChat() }; } catch (e) { return { chat: initialChat(), error: e.message }; } });
  const [chat, setChat] = useState(initial.chat), [catalog, setCatalog] = useState(null), [projection, setProjection] = useState(null);
  const [text, setText] = useState(""), [error, setError] = useState(initial.error || ""), [busy, setBusy] = useState(false), [aiBusy, setAiBusy] = useState(false);
  const [clarify, setClarify] = useState(null);
  const [agentQuestion, setAgentQuestion] = useState(initial.chat.agentQuestion || null), [agentDone, setAgentDone] = useState(Boolean(initial.chat.handledTurn));
  const [key, setKey] = useState({ configurada: false }), [editing, setEditing] = useState(null), [refresh, setRefresh] = useState(0);
  const [tab, setTab] = useState("conversa"), [showClear, setShowClear] = useState(false), [removing, setRemoving] = useState(null), [notebook, setNotebook] = useState(null);
  const activating = useRef(false);
  const generation = useRef(0), mounted = useRef(true), lastAPI = useRef(initial.chat.handledTurn || ""), end = useRef(null), input = useRef(null), chatRef = useRef(chat);
  chatRef.current = chat;
  const native = hasNativeMotor(), blocked = Boolean(initial.error), draftsKey = stableJSON(chat.drafts);
  const change = useCallback((fn) => { generation.current++; if (hasNativeMotor()) nativeMotor("triagem.cancelar").catch(() => {}); setEditing(null); setAgentQuestion(null); setAgentDone(false); setError(""); setChat((c) => ({ ...(typeof fn === "function" ? fn(c) : fn), agentQuestion: null })); }, []);
  useEffect(() => { contract("triagem.catalogo").then(setCatalog).catch((e) => setError(e.message)); }, []);
  useEffect(() => {
    if (blocked) return;
    try { localStorage.setItem(CHAT_KEY, JSON.stringify(chat)); } catch { setError("A conversa não pôde ser guardada. Confira o espaço; os registros existentes foram preservados."); }
  }, [chat, blocked]);
  useEffect(() => {
    const update = () => { generation.current++; setRefresh((v) => v + 1); };
    addEventListener("storage", update); addEventListener("fintips:reading-changed", update);
    return () => { removeEventListener("storage", update); removeEventListener("fintips:reading-changed", update); };
  }, []);
  useEffect(() => {
    let active = true; setProjection(null);
    try {
      const bundle = readBundle(localStorage); setNotebook(bundle);
      if (chat.drafts.length) contract("triagem.contexto", { bundle, rascunhos: chat.drafts, hoje: localDay() })
        .then((data) => { if (active) setProjection(data); }).catch((e) => { if (active) setError(e.message); });
    } catch (e) { setError(e.message); }
    return () => { active = false; };
  }, [draftsKey, refresh]);
  useEffect(() => {
    if (!native) return;
    const read = () => nativeMotor("triagem.chave_status").then((k) => { if (mounted.current) { setKey(k); if (k.configurada && activating.current) { activating.current = false; lastAPI.current = ""; setChat((c) => ({ ...c, cloudConsent: true })); } } }).catch(() => {});
    read(); addEventListener("fintips:chave-triagem", read); addEventListener("fintips:resume", read);
    return () => { removeEventListener("fintips:chave-triagem", read); removeEventListener("fintips:resume", read); };
  }, [native]);
  const askAPI = useCallback(async (manual = false) => {
    const current = chatRef.current;
    if (!projection || !current.drafts.length || !current.cloudConsent || !native || !key.configurada || aiBusy) return;
    // Uma consulta por turno da pessoa. Alterações feitas pelo agente não geram loops pagos.
    const signature = turnSignature(current);
    if (!manual && signature === lastAPI.current) return;
    lastAPI.current = signature;
    const ticket = generation.current; setAiBusy(true); setError("");
    setChat((c) => ({ ...c, requests: c.requests + 1 }));
    try {
      const result = await nativeMotor("triagem.organizar", { bundle: readBundle(localStorage), rascunhos: current.drafts, autorizado: true, hoje: localDay() });
      if (mounted.current && ticket === generation.current && chatRef.current.cloudConsent) {
        // O contrato nativo valida o lote inteiro antes de devolver referências restauradas.
        const links = agentLinks(current.drafts, result.rascunhos, [...current.links, ...result.relacoes]);
        setChat((c) => ({ ...c, drafts: result.rascunhos, links, handledTurn: signature, agentQuestion: result.pergunta }));
        setAgentQuestion(result.pergunta); setAgentDone(true);
      }
    } catch (e) { if (mounted.current && ticket === generation.current) {
      setError(e.message);
      const fallback = projection.publico.opcoes.find((o) => o.acao === "perguntar");
      if (fallback) setEditing({ index: Number(fallback.rascunho.split("_")[1]), field: fallback.campo });
    } }
    finally { if (mounted.current) setAiBusy(false); }
  }, [projection, native, key.configurada, aiBusy]);
  useEffect(() => { askAPI(); }, [projection, chat.cloudConsent, key.configurada, aiBusy]);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest", behavior: "auto" }); }, [chat.messages.length]);
  useEffect(() => () => { mounted.current = false; generation.current++; if (native) nativeMotor("triagem.cancelar").catch(() => {}); }, []);

  const option = projection?.publico.opcoes.find((o) => o.acao === "perguntar");
  const question = editing || agentQuestion || (!aiBusy && option ? { index: Number(option.rascunho.split("_")[1]), field: option.campo } : null);
  const currentDraft = question ? chat.drafts[question.index] : null;
  const spec = currentDraft && catalog?.tipos[currentDraft.tipo]?.campos[question.field];
  const ready = projection && projection.publico.rascunhos.every((d) => d.faltantes.length === 0);
  const appendDraft = (source, type) => {
    const d = makeDraft(source, type);
    if (catalog) d.campos = Object.fromEntries(Object.entries(d.campos).filter(([k]) => k in catalog.tipos[d.tipo].campos));
    return d;
  };
  const respond = (value = text, selected = null) => {
    if (busy || blocked || !catalog || !value.trim()) return;
    if (containsKey(value)) { setError("Use Adicionar chave OpenAI. A chave não deve ser escrita na conversa."); return; }
    try {
      const candidates = !question && chat.drafts.length ? correctionCandidates(value, chat.drafts) : [];
      if (!selected && candidates.length > 1) { setClarify({ text: value, ids: candidates.map((d) => d.id) }); return; }
      const target = selected || (candidates.length === 1 ? candidates[0].id : null);
      if (question && spec) {
        const parsed = inlineAnswer(value, spec, question.field, currentDraft.tipo);
        change((c) => ({ ...c, drafts: c.drafts.map((d, i) => i === question.index ? { ...d, campos: { ...d.campos, ...parsed } } : d),
          messages: [...c.messages, { role: "assistente", text: question.text || spec.rotulo }, { role: "usuario", text: value, id: newId() }].slice(-80) }));
      } else if (target) {
        const draft = chat.drafts.find((d) => d.id === target), fields = inlineFields(value, draft.tipo);
        if (!Object.keys(fields).length) {
          // Uma correção não compreendida nunca vira um registro novo silenciosamente.
          setEditing({ index: chat.drafts.indexOf(draft), field: "titulo" in draft.campos ? "titulo" : "rotulo" });
          setError("Me diga como você quer chamar esse registro. Os outros dados continuam guardados."); return;
        }
        change((c) => ({ ...c, drafts: c.drafts.map((d) => d.id === target ? { ...d, campos: { ...d.campos, ...fields } } : d), messages: [...c.messages, { role: "usuario", text: value, id: newId() }].slice(-80) }));
      } else {
        const lines = splitIntents(value);
        if (chat.drafts.length + lines.length > 20) throw new Error("Salve o que já organizei antes de acrescentar mais coisas.");
        change((c) => ({ ...c, drafts: [...c.drafts, ...lines.map((s) => appendDraft(s))], messages: [...c.messages, { role: "usuario", text: value, id: newId() }].slice(-80) }));
      }
      setClarify(null);
      setText("");
    } catch (e) { setError(e.message); }
  };
  const save = async () => {
    if (!ready || busy || blocked) return;
    setBusy(true); setError(""); const ticket = ++generation.current;
    if (native) nativeMotor("triagem.cancelar").catch(() => {});
    try {
      const before = readBundle(localStorage), id = newId(), selected = structuredClone(chat.drafts), rels = structuredClone(chat.links);
      const proposal = await contract("triagem.preparar", { bundle: before, rascunhos: selected, relacoes: rels, id });
      const result = await contract("triagem.aplicar", { bundle: before, proposta: proposal, confirmado: true, hoje: localDay(), tempo_ms: Date.now() });
      if (!mounted.current || ticket !== generation.current) throw new Error("A conversa mudou. Revise o lote antes de confirmar.");
      commitBundle(localStorage, before, result.bundle);
      change((c) => ({ ...c, drafts: [], links: [], separate: [], requests: 0, messages: [...c.messages, { role: "assistente", text: `Salvei ${selected.length} registro(s) e ${rels.length} vínculo(s). Pode continuar de onde parou ou me contar outro plano.` }].slice(-80) }));
      lastAPI.current = turnSignature(chatRef.current); toast(`${selected.length} registro(s) salvo(s) no aparelho`); setRefresh((v) => v + 1);
    } catch (e) { setError(e.message); }
    finally { if (mounted.current) setBusy(false); }
  };
  const linkOptions = projection?.publico.opcoes.filter((o) => o.acao === "correlacionar") || [];
  const metadata = (ref) => projection?.mapa_local[ref];
  const correlations = linkOptions.map((o) => ({ option: o, from: metadata(o.rascunho), to: metadata(o.alvo) }));
  const unresolvedDuplicate = correlations.some(({ from, to }) => from.tipo === to.tipo && from.titulo.trim().toLowerCase() === to.titulo.trim().toLowerCase() &&
    !chat.separate?.includes(from.id) && chat.drafts.some((d) => d.id === from.id && d.acao === "criar"));
  const localRecords = notebook?.caderno.assets || [];
  const titleFor = (ref) => {
    if (!notebook) return "Registro";
    const col = { tarefa: "tarefas", plano: "planos", medida: "medidas" }[ref.tipo];
    const a = col ? notebook.vida[col].find((a) => a.id === ref.id) : ref.tipo === "livro" ? notebook.leitura.livros.find((a) => a.id === ref.id) : notebook.caderno.assets.find((a) => a.id === ref.id && a.tipo === ref.tipo);
    return a?.titulo || a?.app || a?.campos.titulo || "Registro removido";
  };
  const updateExisting = (from, to) => { try {
    const c = chatRef.current;
    const b = readBundle(localStorage), type = from.tipo;
    const col = { tarefa: "tarefas", plano: "planos", medida: "medidas" }[type];
    const a = col ? b.vida[col].find((a) => a.id === to.id) : type === "livro" ? b.leitura.livros.find((a) => a.id === to.id) : b.caderno.assets.find((a) => a.id === to.id && a.tipo === type)?.campos;
    if (!a) throw new Error("Esse registro mudou. Tente novamente com a conversa atualizada.");
    const fields = Object.fromEntries(Object.entries(a).filter(([k, v]) => k in catalog.tipos[type].campos && v !== null));
    if (type === "medida") fields.rotulo = a.app;
    const next = c.drafts.map((d) => d.id === from.id ? { ...d, id: to.id, acao: "atualizar", campos: { ...fields, ...d.campos } } : d);
    change({ ...c, drafts: next, links: agentLinks(c.drafts, next, c.links) });
  } catch (e) { setError(e.message); } };
  const fieldRow = (d, index, field, s) => <div key={field}><dt>{s.rotulo}{s.obrigatorio && <span aria-label="obrigatório"> *</span>}</dt><dd>{d.campos[field] === undefined || d.campos[field] === "" || d.campos[field] === null ? <span className="triage-missing">{s.obrigatorio ? "Falta responder" : "Sem registro"}</span> : displayValue(field, d.campos[field])}<button className="text-button" disabled={busy} onClick={() => { generation.current++; setEditing({ index, field }); input.current?.focus(); }}>Ajustar</button></dd></div>;
  const present = (value) => value !== undefined && value !== null && value !== "";
  return <>
    <PageHeading code="06" overline="Você decide. Eu organizo." title="Conversa" description="Conte seus planos. Eu cuido dos registros e das conexões."/>
    <div className="triage-tabs" aria-label="Triagem e registros"><button aria-pressed={tab === "conversa"} onClick={() => setTab("conversa")}>Conversa</button><button aria-pressed={tab === "catalogo"} onClick={() => setTab("catalogo")}>Anotações <span>{localRecords.length}</span></button></div>
    {tab === "conversa" ? <>
      {(!key.configurada || !chat.cloudConsent) && <section className="triage-onboarding life-card">
        <span className="manual-tag">SEU ASSISTENTE</span><h2>Uma conversa, tudo organizado.</h2>
        <p>Eu preparo os registros e faço as conexões. Você responde só o que faltar, aqui mesmo.</p>
        <p className="form-hint">A OpenAI recebe valores e referências abstratas. Mensagens, nomes e origem/destino reais ficam no aparelho. A API é cobrada na sua conta.</p>
        <button className="life-button primary" disabled={!native || busy} onClick={() => {
          if (!key.configurada) { activating.current = true; nativeMotor("triagem.configurar_chave").catch((e) => { activating.current = false; setError(e.message); }); }
          else { lastAPI.current = ""; change((c) => ({ ...c, cloudConsent: true })); }
        }}>{key.configurada ? "Usar assistente" : "Conectar minha OpenAI"}</button>
        {!native && <p className="form-hint">A conexão segura está disponível no APK Android. Aqui você pode continuar com a preparação local.</p>}
      </section>}
      <section className="triage-thread" aria-label="Conversa de triagem" aria-live="polite">
        {!chat.messages.length && <div className="triage-bubble assistant"><span>FINTIPS / TRIAGEM LOCAL</span><p>O que você quer tirar da cabeça hoje? Me conte o que pretende fazer e o que está pegando.</p><small>Eu organizo por trás da conversa. Quando faltar uma decisão, pergunto aqui.</small></div>}
        {chat.messages.map((m, i) => <div key={i} className={`triage-bubble ${m.role === "usuario" ? "user" : "assistant"}`}><span>{m.role === "usuario" ? "VOCÊ" : "FINTIPS"}</span><p>{m.text}</p></div>)}
        {clarify && <div className="triage-bubble assistant"><span>UMA DECISÃO SUA</span><p>Essa mudança é sobre qual deles?</p><div className="triage-choices">{chat.drafts.filter((d) => clarify.ids.includes(d.id)).map((d) => <button className="life-button" key={d.id} onClick={() => respond(clarify.text, d.id)}>{d.campos.titulo || d.campos.rotulo}</button>)}</div></div>}
        {spec && <div className="triage-bubble assistant triage-current"><span>{agentDone ? "SÓ MAIS UMA COISA" : "VAMOS ENTENDER"}</span><p>{question.text || spec.rotulo}</p><small>Sobre: {currentDraft.campos.titulo || currentDraft.campos.rotulo || catalog.tipos[currentDraft.tipo].nome}</small>
          {spec.tipo === "opcao" && <div className="triage-choices">{spec.opcoes.map((v) => <button className="life-button" disabled={busy} key={v} onClick={() => respond(v)}>{AREAS.find((a) => a.id === v)?.nome || v}</button>)}</div>}
          {spec.tipo === "booleano" && <div className="triage-choices">{["Sim", "Não"].map((v) => <button className="life-button" key={v} disabled={busy} onClick={() => respond(v)}>{v}</button>)}</div>}
          {spec.tipo === "inteiro" && <small>{question.field.endsWith("_centavos") ? "Responda em reais, por exemplo 1500,50." : question.field === "progresso_bp" ? "Responda em porcentagem, por exemplo 25%." : `Entre ${spec.minimo} e ${spec.maximo}.`}</small>}
        </div>}
        {unresolvedDuplicate && !aiBusy && <div className="triage-bubble assistant"><span>COMO VOCÊ PREFERE?</span><p>Já existe um registro com esse nome. Quer atualizar ou manter separado?</p>{correlations.filter(({ from, to }) => from.tipo === to.tipo && from.titulo.trim().toLowerCase() === to.titulo.trim().toLowerCase()).map(({ from, to }, i) => <div className="triage-choices" key={i}><button className="life-button" onClick={() => updateExisting(from, to)}>Atualizar {to.titulo}</button><button className="text-button" onClick={() => change((c) => ({ ...c, separate: [...c.separate, from.id], drafts: c.drafts.map((d) => d.id === from.id ? { ...d, porque: "Registro separado por escolha explícita da pessoa na conversa." } : d) }))}>Manter separado</button></div>)}</div>}
        {aiBusy && <div className="triage-bubble assistant triage-working" role="status"><span>ORGANIZANDO</span><p>Preenchendo os registros e conectando as ideias<span className="triage-pulse">…</span></p><button className="text-button" onClick={() => { generation.current++; nativeMotor("triagem.cancelar").catch(() => {}); }}>Parar</button></div>}
        {ready && !spec && !aiBusy && <div className="triage-bubble assistant triage-ready"><span>{agentDone ? "DEIXEI ORGANIZADO" : "PREPARADO NO APARELHO"}</span>
          <ul>{chat.drafts.map((d) => <li key={d.id}><strong>{d.campos.titulo || d.campos.rotulo}</strong><small>{catalog?.tipos[d.tipo]?.nome}{d.campos.dias_semana ? ` · ${d.campos.dias_semana} dias por semana` : ""}{d.campos.progresso_bp !== undefined ? ` · ${displayValue("progresso_bp", d.campos.progresso_bp)} lido` : ""}{d.campos.valor_centavos !== undefined ? ` · ${displayValue("valor_centavos", d.campos.valor_centavos)}` : ""}</small></li>)}</ul>
          {!!chat.links.length && <p className="triage-link-count">↗ {chat.links.length} conexão(ões) preparada(s) entre os registros.</p>}
          <p>Está de acordo? Você também pode ajustar me contando abaixo.</p>
          <button className="life-button primary" disabled={busy || blocked || unresolvedDuplicate} onClick={save}>{busy ? "Guardando…" : "Está certo, salvar"}<Icon name="check" size={18}/></button>
        </div>}
        <div ref={end}/>
      </section>
      <form className="triage-composer" onSubmit={(e) => { e.preventDefault(); respond(); }}><label className="sr-only" htmlFor="triagem-mensagem">Mensagem de triagem</label>
        <textarea ref={input} id="triagem-mensagem" maxLength={4000} rows={3} inputMode={spec?.tipo === "inteiro" ? "decimal" : "text"} disabled={busy || blocked || !catalog} value={text} onChange={(e) => setText(e.target.value)} placeholder={spec ? "Responda do seu jeito…" : chat.drafts.length ? "Acrescente algo ou diga o que quer ajustar…" : "Quero organizar…"}/>
        <button className="life-button primary" type="submit" disabled={busy || blocked || !catalog || !text.trim()}>Enviar <Icon name="arrow" size={18}/></button>
      </form>
      {!!chat.drafts.length && <details className="triage-drafts" aria-label="Rascunhos para confirmar"><summary>Ver o que será guardado · {chat.drafts.length} registro(s)</summary>
        {chat.drafts.map((d, index) => <article className="life-card triage-draft" key={d.id}><div className="triage-draft-head"><span className="manual-tag">{d.acao === "atualizar" ? "Atualização" : "Rascunho local"}</span><button className="text-button" disabled={busy} onClick={() => change((c) => ({ ...c, drafts: c.drafts.filter((a) => a.id !== d.id), links: c.links.filter((r) => r.de.id !== d.id && r.para.id !== d.id) }))}>Remover rascunho</button></div>
          <h3>{d.campos.titulo || d.campos.rotulo || "Novo registro"}</h3><label className="triage-type">Tipo de registro<select aria-label={`Tipo do registro ${index + 1}`} disabled={busy || d.acao === "atualizar"} value={d.tipo} onChange={(e) => change((c) => ({ ...c, drafts: c.drafts.map((a, i) => i === index ? { ...appendDraft(a.campos.titulo || a.campos.rotulo || "", e.target.value), id: a.id } : a) }))}>{Object.entries(catalog?.tipos || {}).map(([id, s]) => <option key={id} value={id}>{s.nome}</option>)}</select></label>
          {catalog?.tipos[d.tipo]?.destino === "caderno" && <p className="form-hint">Vai para o catálogo local. Ainda não altera o cálculo financeiro nem cria registros de sensores.</p>}
          <dl>{Object.entries(catalog?.tipos[d.tipo]?.campos || {}).filter(([field, s]) => s.obrigatorio || present(d.campos[field])).map(([field, s]) => fieldRow(d, index, field, s))}</dl>
          {d.tipo === "livro" && !present(d.campos.progresso_bp) && <p className="form-hint">Sem posição de leitura informada. Não será registrada como 0%.</p>}
          <details><summary>Refinar com detalhes opcionais</summary><dl>{Object.entries(catalog?.tipos[d.tipo]?.campos || {}).filter(([field, s]) => !s.obrigatorio && !present(d.campos[field])).map(([field, s]) => fieldRow(d, index, field, s))}</dl></details>
        </article>)}
        {!!correlations.length && <div className="life-card triage-correlations"><h3>Conferir relações</h3><p>O aparelho encontrou semelhanças. Você decide se são a mesma coisa ou se existe um vínculo.</p>{correlations.map(({ option: o, from, to }) => {
          const chosen = chat.links.some((r) => r.de.id === from.id && r.para.id === to.id);
          return <div className="triage-relation" key={o.id}><p><strong>{from.titulo}</strong><span>↔</span><strong>{to.titulo}</strong></p>
            <button className="life-button" disabled={busy || chosen} onClick={() => change((c) => ({ ...c, links: [...c.links, { de: { tipo: from.tipo, id: from.id }, para: { tipo: to.tipo, id: to.id }, tipo: "relacionado", porque: "Vínculo confirmado pela pessoa na triagem local." }] }))}>{chosen ? "Vínculo confirmado" : "Relacionar"}</button>
            {from.tipo === to.tipo && <button className="text-button" disabled={busy} onClick={() => updateExisting(from, to)}>Atualizar o registro existente</button>}
            {from.tipo === to.tipo && !chat.separate?.includes(from.id) && <button className="text-button" disabled={busy} onClick={() => change((c) => ({ ...c, separate: [...(c.separate || []), from.id], drafts: c.drafts.map((d) => d.id === from.id ? { ...d, porque: "Registro separado por escolha explícita da pessoa na conversa." } : d) }))}>Manter como registro separado</button>}
          </div>;
        })}</div>}
        {unresolvedDuplicate && <p className="form-hint">Confirme se os registros com o mesmo título são duplicatas antes de salvar.</p>}
        <button className="life-button primary full triage-confirm" disabled={!ready || busy || blocked || unresolvedDuplicate} onClick={save}>{busy ? "Confirmando no aparelho…" : `Confirmar ${chat.drafts.length} registro(s)`}<Icon name="check" size={18}/></button>
        <p className="form-hint">A confirmação grava todo o lote de uma vez. Nada é criado por apenas conversar ou aceitar uma sugestão da IA.</p>
      </details>}
      <details className="life-card triage-settings"><summary><Icon name="lock" size={16}/> Conexão e detalhes</summary>
        <p>A conversa real fica no aparelho. O agente usa números, tipos, conceitos limitados e referências locais para preencher os contratos. Ainda depende de extração local limitada para interpretar sua mensagem; não é um modelo de linguagem embarcado.</p>
        <p className="form-hint">gpt-4.1-mini · store=false não significa retenção zero na OpenAI. Uma consulta por mensagem, sem repetição automática em falhas.</p>
        <div className="triage-actions"><button className="text-button" disabled={!native || busy} onClick={() => nativeMotor("triagem.configurar_chave").catch((e) => setError(e.message))}>{key.configurada ? "Trocar chave OpenAI" : "Adicionar chave OpenAI"}</button>
          {key.configurada && <button className="text-button" onClick={() => { change((c) => ({ ...c, cloudConsent: false })); nativeMotor("triagem.apagar_chave").then(setKey).catch((e) => setError(e.message)); }}>Apagar chave</button>}
          {chat.cloudConsent && <button className="text-button" onClick={() => { change((c) => ({ ...c, cloudConsent: false })); nativeMotor("triagem.cancelar").catch(() => {}); }}>Pausar assistência</button>}
          {chat.cloudConsent && key.configurada && projection && <button className="text-button" disabled={aiBusy} onClick={() => askAPI(true)}>Tentar organizar novamente</button>}
        </div>
      <details className="triage-contract-import"><summary>Integrar uma proposta por contrato</summary><p>Uma API ou agente local pode gerar o mesmo JSON de triagem. Importe a proposta para conferir aqui; a importação só cria rascunhos. O arquivo precisa usar o estado atual do aparelho.</p><label>Proposta de triagem em JSON<input type="file" accept=".json,application/json" disabled={busy || blocked || chat.drafts.length > 0} onChange={async (e) => {
        const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
        setBusy(true); setError(""); const ticket = ++generation.current;
        try {
          if (file.size > 1024 * 1024) throw new Error("A proposta deve ter até 1 MB.");
          const proposal = JSON.parse(await file.text()), before = readBundle(localStorage);
          const checked = await contract("triagem.preparar", { bundle: before, rascunhos: proposal.operacoes, relacoes: proposal.relacoes, id: proposal.id });
          if (stableJSON(checked) !== stableJSON(proposal)) throw new Error("A proposta não corresponde ao contrato ou ao estado atual. Gere uma revisão atualizada na API local.");
          if (!mounted.current || ticket !== generation.current) return;
          change((c) => ({ ...c, drafts: checked.operacoes, links: checked.relacoes, messages: [...c.messages, { role: "assistente", text: "Proposta importada para revisão no aparelho. Nenhum registro foi confirmado ainda." }].slice(-80) }));
        } catch { setError("Não foi possível importar a proposta. Confira o contrato e o estado atual; os registros foram preservados."); }
        finally { if (mounted.current) setBusy(false); }
      }}/></label><p className="form-hint">Confirme ou limpe o lote atual antes de importar outro. A cópia local contém dados pessoais; não publique esse arquivo.</p></details></details>
      <button className="text-button" disabled={busy || blocked} onClick={() => setShowClear(true)}>Nova conversa</button>
      {showClear && <div className="life-card" role="alertdialog" aria-label="Limpar conversa local"><p>Limpar as mensagens e os rascunhos desta conversa? Registros já confirmados permanecem.</p><button className="life-button" onClick={() => { if (native) nativeMotor("triagem.cancelar").catch(() => {}); change({ ...initialChat(), cloudConsent: chat.cloudConsent }); lastAPI.current = ""; setShowClear(false); }}>Limpar conversa</button><button className="text-button" onClick={() => setShowClear(false)}>Continuar aqui</button></div>}
    </> : <section className="triage-library"><p>Estes registros ficam no aparelho e podem ser relacionados a planos, tarefas e livros. Os contratos financeiros do catálogo ainda não alimentam a análise financeira do app.</p>
      {!localRecords.length && <div className="life-card"><h2>Um lugar para o que você descobrir</h2><p>Objetivos, decisões, fatos e outros registros confirmados na conversa aparecerão aqui.</p></div>}
      {localRecords.map((a) => <article className="life-card" key={`${a.tipo}/${a.id}`}><span className="manual-tag">{catalog?.tipos[a.tipo]?.nome || a.tipo}</span><h3>{a.campos.titulo}</h3><dl>{Object.entries(a.campos).map(([k, v]) => <div key={k}><dt>{catalog?.tipos[a.tipo]?.campos[k]?.rotulo || k}</dt><dd>{displayValue(k, v)}</dd></div>)}</dl><p className="form-hint">{a.proveniencia?.porque}</p><button className="life-button" disabled={busy} onClick={() => { change((c) => ({ ...c, drafts: [...c.drafts, { id: a.id, tipo: a.tipo, campos: { ...a.campos }, porque: "Atualização conversada e confirmada pela pessoa.", acao: "atualizar" }] })); setTab("conversa"); }}>Conversar sobre este registro</button><button className="text-button" disabled={busy || chat.drafts.some((d) => d.id === a.id && d.tipo === a.tipo)} onClick={() => setRemoving({ id: a.id, tipo: a.tipo })}>Remover registro</button></article>)}
      {!!notebook?.caderno.relacoes.length && <section className="life-card"><h3>Relações confirmadas</h3>{notebook.caderno.relacoes.map((r, i) => <p key={i}><strong>{titleFor(r.de)}</strong> → {r.tipo} → <strong>{titleFor(r.para)}</strong><br/>{r.porque}</p>)}</section>}
    </section>}
    {removing && <section className="life-card" role="alertdialog" aria-label="Remover registro local"><p>Remover este registro do catálogo e seus vínculos? Conversas e cópias locais são independentes.</p><button className="life-button" disabled={busy} onClick={async () => {
      setBusy(true); setError(""); ++generation.current;
      try {
        const before = readBundle(localStorage), next = structuredClone(before);
        next.caderno.assets = next.caderno.assets.filter((a) => a.id !== removing.id || a.tipo !== removing.tipo);
        next.caderno.relacoes = next.caderno.relacoes.filter((r) => ![r.de, r.para].some((a) => a.id === removing.id && a.tipo === removing.tipo));
        await contract("triagem.validar", { bundle: next }); commitBundle(localStorage, before, next);
        change((c) => ({ ...c, links: c.links.filter((r) => ![r.de, r.para].some((a) => a.id === removing.id && a.tipo === removing.tipo)) }));
        setRemoving(null); setRefresh((v) => v + 1); toast("Registro removido do aparelho");
      } catch (e) { setError(e.message); } finally { setBusy(false); }
    }}>Confirmar remoção</button><button className="text-button" disabled={busy} onClick={() => setRemoving(null)}>Manter registro</button></section>}
    {error && <p className="form-error triage-error" role="alert">{error}</p>}
    <p className="form-hint">Conversas e registros ficam no armazenamento privado do app. A cópia local em Contexto inclui vida, leitura, catálogo e conversa; não inclui a chave da API.</p>
  </>;
}
