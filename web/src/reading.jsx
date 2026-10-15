import React, { useCallback, useEffect, useState } from "react";
import { Icon } from "./icons.jsx";
import { Sheet, closeSheet } from "./life.jsx";
import { localDay, newId, shiftDay } from "./life-store.js";
import { READING_KEY, emptyReading, libreraPositions, mergeLibrera, readReading, validateReading } from "./reading-model.js";
import "./reading.css";
import { usePacing } from "./motor-hooks.js";
import { isAndroid } from "./native-motor.js";

const percent = (bp) => `${(bp / 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`;
const pp = (bp) => `${(bp / 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} p.p.`;
const dateLabel = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-BR");

function useReading() {
  const [initial] = useState(() => {
    try { return { data: readReading(localStorage), blocked: false }; }
    catch { return { data: emptyReading(), blocked: true }; }
  });
  const [state, setState] = useState(initial.data);
  const [blocked, setBlocked] = useState(initial.blocked);
  const [issue, setIssue] = useState(initial.blocked ? "Os registros de leitura não puderam ser lidos. Eles foram preservados; faça uma cópia local antes de recuperá-los." : "");
  const update = useCallback((transform) => {
    if (blocked) return false;
    try {
      const next = transform(readReading(localStorage));
      if (!validateReading(next)) throw new Error("estado inválido");
      localStorage.setItem(READING_KEY, JSON.stringify(next)); setState(next); setIssue(""); dispatchEvent(new Event("fintips:reading-changed")); return true;
    } catch { setIssue("Não foi possível salvar os registros de leitura no aparelho. A alteração não foi gravada."); return false; }
  }, [blocked]);
  useEffect(() => {
    const refresh = (e) => {
      if (e.key !== READING_KEY && e.key !== null) return;
      try { setState(readReading(localStorage)); setBlocked(false); setIssue(""); }
      catch { setBlocked(true); setIssue("Não foi possível ler os registros de leitura. A edição foi pausada para preservá-los."); }
    };
    addEventListener("storage", refresh); return () => removeEventListener("storage", refresh);
  }, []);
  return { state, update, issue, blocked };
}

function BookForm({ store, close, toast }) {
  const [title, setTitle] = useState("");
  const [progress, setProgress] = useState("0");
  const [days, setDays] = useState("3");
  const [deadline, setDeadline] = useState("");
  return <Sheet title="Um livro, um próximo capítulo" close={close}><form onSubmit={(e) => {
    e.preventDefault();
    const n = Number(progress); if (!title.trim() || progress === "" || !Number.isFinite(n) || n < 0 || n > 100) return;
    const book = { id: newId(), titulo: title.trim(), fonte: "usuario", chave: null, perfil: "",
      prazo: deadline, dias_semana: Number(days), observacoes: [{ dia: localDay(), progresso_bp: Math.round(n * 100), tempo_ms: Date.now(), origem: "usuario" }] };
    if (store.update((s) => ({ ...s, livros: [...s.livros, book] }))) { toast("Livro salvo no aparelho"); closeSheet(close); }
  }}>
    <label className="life-field">Título do livro<input autoFocus required maxLength={180} placeholder="O livro que você quer acompanhar" value={title} onChange={(e) => setTitle(e.target.value)}/></label>
    <label className="life-field">Porcentagem atual<input required type="number" inputMode="decimal" min="0" max="100" step="0.01" value={progress} onChange={(e) => setProgress(e.target.value)}/></label>
    <label className="life-field">Dias de leitura por semana<select value={days} onChange={(e) => setDays(e.target.value)}>{[1, 2, 3, 4, 5, 6, 7].map((d) => <option key={d} value={d}>{d} {d === 1 ? "dia" : "dias"}</option>)}</select></label>
    <label className="life-field">Prazo, se quiser<input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)}/></label>
    {store.issue && <p role="alert" className="form-error">{store.issue}</p>}
    <button className="life-button primary full" disabled={store.blocked}>Adicionar livro <Icon name="plus" size={18}/></button>
  </form></Sheet>;
}

function ImportForm({ store, close, toast }) {
  const [file, setFile] = useState(null);
  const [profile, setProfile] = useState("principal");
  const [busy, setBusy] = useState(false);
  const [issue, setIssue] = useState("");
  return <Sheet title="Progresso do Librera" close={close}>
    <p className="sheet-description">Selecione uma cópia local de <b>app-Progress.json</b>, dentro do perfil do Librera. O arquivo é lido neste aparelho, sem upload.</p>
    <form onSubmit={async (e) => {
      e.preventDefault(); if (!file || !profile.trim() || busy) return;
      setBusy(true); setIssue("");
      try {
        if (file.size > 2 * 1024 * 1024) { setIssue("Escolha um arquivo de progresso de até 2 MB."); return; }
        const parsed = libreraPositions(JSON.parse(await file.text()));
        if (!parsed.posicoes.length) { setIssue("Não há posições com porcentagem e data válidas neste arquivo. Use app-Progress.json; formatos antigos podem precisar de atualização no Librera."); return; }
        let result;
        const saved = store.update((s) => { result = mergeLibrera(s, parsed.posicoes, profile.trim()); return result.state; });
        if (saved) { toast(`${result.updated} posições atualizadas · ${parsed.ignorados + result.ignored} ignoradas`); closeSheet(close); }
      } catch { setIssue("Não foi possível ler esse arquivo de progresso. Nenhum dado foi enviado ou alterado."); }
      finally { setBusy(false); }
    }}>
      <label className="life-field">Arquivo de progresso<input type="file" accept=".json,application/json" required onChange={(e) => setFile(e.target.files?.[0] || null)}/></label>
      <label className="life-field">Perfil do Librera<input value={profile} required maxLength={100} onChange={(e) => setProfile(e.target.value)}/></label>
      <p className="reading-caption">Use o mesmo perfil ao reimportar. Perfis diferentes ficam separados, inclusive quando o nome do livro é igual.</p>
      {(issue || store.issue) && <p className="form-error" role="alert">{issue || store.issue}</p>}
      <button className="life-button primary full" disabled={busy || store.blocked || !file}>{busy ? "Lendo no aparelho…" : "Importar progresso local"}</button>
    </form>
    <p className="reading-caption">A sincronização direta com a nuvem ainda não está conectada. O arquivo guarda a última posição; o histórico começa a se formar com as próximas atualizações.</p>
  </Sheet>;
}

function ProgressForm({ book, store, close, toast }) {
  const last = [...book.observacoes].sort((a, b) => a.dia.localeCompare(b.dia)).at(-1);
  const [progress, setProgress] = useState(String((last?.progresso_bp || 0) / 100));
  const [day, setDay] = useState(localDay());
  return <Sheet title="Onde você está na leitura?" close={close}><p className="sheet-description">Uma posição por dia. Este registro é informado por você e prevalece sobre uma importação do mesmo dia.</p>
    <form onSubmit={(e) => {
      e.preventDefault(); const n = Number(progress);
      if (progress === "" || !Number.isFinite(n) || n < 0 || n > 100 || !day || day > localDay()) return;
      if (store.update((s) => ({ ...s, livros: s.livros.map((b) => b.id !== book.id ? b : { ...b, observacoes: [...b.observacoes.filter((p) => p.dia !== day),
        { dia: day, progresso_bp: Math.round(n * 100), tempo_ms: Date.now(), origem: "usuario" }].sort((a, b) => a.dia.localeCompare(b.dia)) }) }))) { toast("Posição registrada no aparelho"); closeSheet(close); }
    }}>
      <label className="life-field">Porcentagem de leitura<input autoFocus required type="number" inputMode="decimal" min="0" max="100" step="0.01" value={progress} onChange={(e) => setProgress(e.target.value)}/></label>
      <label className="life-field">Dia da posição<input type="date" required max={localDay()} value={day} onChange={(e) => setDay(e.target.value)}/></label>
      {store.issue && <p role="alert" className="form-error">{store.issue}</p>}
      <button className="life-button primary full" disabled={store.blocked}>Salvar posição <Icon name="check" size={18}/></button>
    </form></Sheet>;
}

function PaceForm({ book, store, close, toast }) {
  const [title, setTitle] = useState(book.titulo);
  const [days, setDays] = useState(String(book.dias_semana || 3));
  const [deadline, setDeadline] = useState(book.prazo || "");
  return <Sheet title="Um ritmo que cabe na sua vida" close={close}><p className="sheet-description">Você escolhe a frequência e o prazo. A previsão usa as posições que já foram registradas.</p>
    <form onSubmit={(e) => {
      e.preventDefault();
      if (!title.trim()) return;
      if (store.update((s) => ({ ...s, livros: s.livros.map((b) => b.id === book.id ? { ...b, titulo: title.trim(), dias_semana: Number(days), prazo: deadline } : b) }))) { toast("Plano de leitura atualizado"); closeSheet(close); }
    }}>
      <label className="life-field">Título no FinTips<input required maxLength={180} value={title} onChange={(e) => setTitle(e.target.value)}/></label>
      <label className="life-field">Dias de leitura por semana<select value={days} onChange={(e) => setDays(e.target.value)}>{[1, 2, 3, 4, 5, 6, 7].map((d) => <option key={d} value={d}>{d} {d === 1 ? "dia" : "dias"}</option>)}</select></label>
      <label className="life-field">Prazo de leitura<input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)}/></label>
      {store.issue && <p role="alert" className="form-error">{store.issue}</p>}
      <button className="life-button primary full" disabled={store.blocked}>Ajustar ritmo <Icon name="check" size={18}/></button>
    </form></Sheet>;
}

function PositionChart({ observations }) {
  // Datas determinam a distância horizontal. Não inventar avanço entre amostras.
  const points = observations.slice(-14);
  if (points.length < 2) return null;
  const ordinal = (d) => Date.parse(`${d}T00:00:00Z`) / 86400000;
  const start = ordinal(points[0].dia), span = ordinal(points.at(-1).dia) - start;
  const x = (p) => 34 + (ordinal(p.dia) - start) / span * 238;
  const y = (p) => 92 - p.progresso_bp / 10000 * 76;
  return <figure className="reading-chart"><figcaption>Posições observadas · últimas {points.length}</figcaption>
    <svg viewBox="0 0 286 118" role="img" aria-label="Evolução da posição de leitura. Consulte os valores em Ver posições registradas.">
      {[0, 50, 100].map((n) => <g key={n}><line className="chart-grid" x1="34" x2="272" y1={92 - n * .76} y2={92 - n * .76}/><text x="1" y={95 - n * .76}>{n}%</text></g>)}
      <polyline key={points.map((p) => `${p.dia}/${p.progresso_bp}`).join(";")} pathLength="1" className="chart-path" points={points.map((p) => `${x(p)},${y(p)}`).join(" ")}/>
      {points.map((p) => <circle key={p.dia} className="chart-point" cx={x(p)} cy={y(p)} r="3"/>)}
      <text x="34" y="112">{dateLabel(points[0].dia).slice(0, 5)}</text><text x="272" y="112" textAnchor="end">{dateLabel(points.at(-1).dia).slice(0, 5)}</text>
    </svg>
  </figure>;
}

function BookCard({ book, store, onProgress, onPace, onRemove }) {
  const today = localDay();
  const observations = [...book.observacoes].sort((a, b) => a.dia.localeCompare(b.dia));
  const calculation = usePacing(observations, { today, deadline: book.prazo || null, reading_days: book.dias_semana });
  if (calculation.error) return <article className="reading-book"><h3>{book.titulo}</h3><p role="alert" className="form-error">{calculation.error}</p></article>;
  if (calculation.loading) return <article className="reading-book"><h3>{book.titulo}</h3><p role="status">Calculando no aparelho…</p></article>;
  const r = calculation.data;
  const last = observations.at(-1);
  const demanding = r.estado === "estimado" && r.prazo_dias !== null && r.prazo_dias >= 0 &&
    (10000 - r.progresso_bp) * r.intervalo_dias > r.avanco_bp * Math.max(1, r.prazo_dias);
  return <article className="reading-book">
    <div className="section-head"><span className="manual-tag">{last?.origem === "librera" ? "Posição do Librera" : "Informado por você"}</span>
      <strong className="reading-percent">{r.progresso_bp === null ? "—" : percent(r.progresso_bp)}</strong><button className="icon-button" disabled={store.blocked} aria-label={`Excluir livro ${book.titulo}`} onClick={onRemove}><Icon name="trash" size={17}/></button></div>
    <h3>{book.titulo}</h3><div className="reading-track"><i style={{ width: `${(r.progresso_bp || 0) / 100}%` }}/></div>
    {last && <p className="reading-caption">Última posição de {dateLabel(last.dia)} · {book.fonte === "librera" ? `perfil ${book.perfil}` : "registro local"}</p>}
    <PositionChart observations={observations}/>
    <div className="reading-pacing">
      {isAndroid() && <small className="motor-label">Motor Kotlin · cálculo no aparelho</small>}
      {r.estado === "estimado" ? <><span className="eyebrow">{r.preliminar ? "Primeira estimativa" : "Seu ritmo observado"}</span>
        <strong>{pp(r.avanco_bp / r.intervalo_dias)} por dia de calendário</strong>
        <p>Nesse ritmo, o fim fica em aproximadamente <b>{r.previsao_dias} dias</b>, por volta de {dateLabel(shiftDay(today, r.previsao_dias))}.</p>
        <small>{r.amostras} posições em {r.intervalo_dias} dias. Os intervalos incluem dias sem atualização; não medimos sessões ou compreensão.</small></>
        : <p>{({ calibrando: "Mais uma posição em outro dia já permite uma primeira estimativa do ritmo.", desatualizado: "A última posição tem mais de sete dias. Atualize antes de usar uma previsão.",
          sem_avanco: "As posições observadas não avançaram. Vamos esperar uma nova atualização antes de projetar.", no_fim: "A posição está no fim do livro. Isso não marca automaticamente uma tarefa como concluída.", sem_dados: "Ainda não há posição registrada." })[r.estado]}</p>}
      {r.historico_reiniciado && <p>Você voltou para uma posição anterior. O ritmo usa só o trecho do histórico depois desse recuo.</p>}
    </div>
    {r.meta_bp_sessao !== null && <div className="reading-goal"><Icon name="book" size={18}/><div><strong>{pp(r.meta_bp_sessao)} por dia de leitura</strong><small>{book.dias_semana} dias por semana · {book.prazo ? `prazo ${dateLabel(book.prazo)}` : "distribuição do ritmo observado"}</small></div></div>}
    {demanding && <p className="reading-warning">Esse prazo pede um ritmo maior que o observado. Ajuste o prazo ou a frequência para comparar alternativas.</p>}
    {r.prazo_dias !== null && r.prazo_dias < 0 && <p className="reading-warning">O prazo passou. Você pode escolher uma nova data sem perder seu histórico.</p>}
    <details className="reading-history"><summary>Ver posições registradas ({observations.length})</summary>
      <ul>{[...observations].reverse().map((p) => <li key={p.dia}><span>{dateLabel(p.dia)}</span><b>{percent(p.progresso_bp)}</b><small>{p.origem === "librera" ? "Librera" : "Você"}</small></li>)}</ul>
    </details>
    <div className="reading-actions"><button className="life-button" disabled={store.blocked} onClick={onProgress}>Registrar posição</button><button className="text-button" disabled={store.blocked} onClick={onPace}>Ajustar ritmo <Icon name="arrow" size={16}/></button></div>
  </article>;
}

export function ReadingTracker({ toast }) {
  const store = useReading();
  const [mode, setMode] = useState(null);
  const [bookId, setBookId] = useState(null);
  const [undo, setUndo] = useState(null);
  const selected = store.state.livros.find((b) => b.id === bookId);
  const open = (m, b) => { setUndo(null); setMode(m); setBookId(b?.id || null); };
  const close = () => setMode(null);
  const backup = () => {
    try {
      const raw = localStorage.getItem(READING_KEY) || JSON.stringify(store.state);
      const url = URL.createObjectURL(new Blob([raw], { type: "application/json" }));
      const link = document.createElement("a"); link.href = url; link.download = `fintips-leitura-${localDay()}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast("Cópia local dos livros criada. Guarde-a com cuidado.");
    } catch { toast("Não foi possível criar a cópia dos registros."); }
  };
  return <section className="life-card reading-card" aria-label="Leitura e ritmo">
    <div className="section-head"><h2>Seu próximo capítulo</h2><Icon name="book" size={22}/></div>
    <p className="reading-intro">Acompanhe o avanço nos livros e encontre um ritmo que cabe na semana.</p>
    <div className="reading-toolbar"><button className="life-button primary" disabled={store.blocked} onClick={() => open("new")}><Icon name="plus" size={17}/> Adicionar livro</button>
      <button className="life-button" disabled={store.blocked} onClick={() => open("import")}>Importar Librera</button></div>
    {store.issue && <p className="form-error" role="alert">{store.issue}</p>}
    {!store.state.livros.length ? <div className="reading-empty"><Icon name="book" size={32}/><h3>Progresso que conta uma história</h3><p>Adicione um livro ou importe a posição do Librera. A previsão aparece quando houver histórico, não no primeiro registro.</p></div>
      : store.state.livros.map((b) => <BookCard key={b.id} book={b} store={store} onProgress={() => open("progress", b)} onPace={() => open("pace", b)} onRemove={() => {
        if (store.update((s) => ({ ...s, livros: s.livros.filter((item) => item.id !== b.id) }))) setUndo(b);
      }}/>)}
    {undo && <div className="undo-row" role="status"><span>Livro removido.</span><button className="text-button" onClick={() => {
      if (store.update((s) => ({ ...s, livros: [...s.livros.filter((b) => b.id !== undo.id && !(undo.fonte === "librera" && b.fonte === "librera" && b.chave === undo.chave && b.perfil === undo.perfil)), undo] }))) setUndo(null);
    }}>Desfazer</button></div>}
    <div className="reading-local"><Icon name="lock" size={14}/><span>Títulos e histórico ficam no aparelho.</span><button className="text-button" onClick={backup}>Cópia local</button></div>
    {mode === "new" && <BookForm store={store} close={close} toast={toast}/>}
    {mode === "import" && <ImportForm store={store} close={close} toast={toast}/>}
    {mode === "progress" && selected && <ProgressForm book={selected} store={store} close={close} toast={toast}/>}
    {mode === "pace" && selected && <PaceForm book={selected} store={store} close={close} toast={toast}/>}
  </section>;
}
