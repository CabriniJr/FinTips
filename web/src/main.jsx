import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./lib.js";
import { ForecastView, LeversView, ProfileView } from "./profile.jsx";
import { TriageView } from "./triage.jsx";
import { Data, Fixed, Overview, Plans, Spending } from "./views.jsx";
import { LifeAreas, LifePlans, PageHeading, PhoneContext, Today, useLocalLife } from "./life.jsx";
import { AREAS, localDay } from "./life-store.js";
import { Icon } from "./icons.jsx";
import "./styles.css";
import "./mobile.css";
import "./instrument.css";

const FINANCE = [["visao", "Panorama"], ["perfil", "Perfil"], ["triagem", "Triagem"],
  ["gastos", "Gastos"], ["fixos", "Compromissos"], ["planos", "Metas"],
  ["previsoes", "Previsões"], ["alavancas", "Alavancas"], ["dados", "Dados"]];
const NAV = [["hoje", "Hoje", "today"], ["vida", "Vida", "life"], ["visao", "Finanças", "wallet"],
  ["projetos", "Planos", "plans"], ["contexto", "Contexto", "context"]];
function route() {
  const [page, area] = location.hash.slice(1).split("/");
  const known = [...NAV, ...FINANCE].some(([id]) => id === page);
  return { page: known ? page : "hoje", area: AREAS.some((a) => a.id === area) ? area : "FOR" };
}

function FinanceEmpty({ erro, reload, toast }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [issue, setIssue] = useState("");
  if (location.hostname === "appassets.androidplatform.net") {
    return <section className="life-card finance-empty"><span className="empty-icon"><Icon name="wallet" size={30}/></span>
      <h2>Finanças em preparação</h2><p>As finanças ainda não estão disponíveis neste APK de avaliação. Você já pode registrar tarefas, planos de vida e o progresso dos livros.</p>
    </section>;
  }
  return <section className="life-card finance-empty"><span className="empty-icon"><Icon name="wallet" size={30}/></span>
    <h2>Vamos conhecer suas finanças?</h2><p>Importe um extrato para ver seus gastos, sua reserva e o efeito das escolhas. Suas outras áreas já podem ser usadas.</p>
    <form onSubmit={async (e) => {
      e.preventDefault(); if (!file || busy) return;
      setBusy(true); setIssue("");
      try { const result = await api.import(file); toast(`${result.transacoes} transações importadas`); reload(); }
      catch (error) { setIssue(error.message); }
      finally { setBusy(false); }
    }}><label className="life-field">Extrato OFX<input type="file" accept=".ofx,.qfx" onChange={(e) => setFile(e.target.files?.[0] || null)}/></label>
      <button className="life-button primary full" disabled={!file || busy}>{busy ? "Importando…" : "Importar no motor local"}</button>
    </form><p className="finance-local-note">A importação financeira usa o motor rodando no próprio aparelho.</p>
    {issue && <p role="alert" className="form-error">{issue}</p>}
    <details><summary>Conexão com o motor</summary><p>{erro}</p><button className="life-button" onClick={reload}>Tentar novamente</button></details>
  </section>;
}

function App() {
  const life = useLocalLife();
  const [current, setCurrent] = useState(route);
  const [day, setDay] = useState(localDay);
  const [ctx, setCtx] = useState(null);
  const [financeError, setFinanceError] = useState("");
  const [loading, setLoading] = useState(false);
  const [toastMsg, setToastMsg] = useState(null);
  const timer = useRef(null);
  const financeiro = FINANCE.some(([id]) => id === current.page);
  const carregar = useCallback(() => {
    setLoading(true); setFinanceError("");
    api.context().then((data) => setCtx(data)).catch((e) => setFinanceError(e.message))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    const change = () => { setCurrent(route()); window.scrollTo({ top: 0, behavior: "instant" }); };
    addEventListener("hashchange", change);
    return () => removeEventListener("hashchange", change);
  }, []);
  useEffect(() => { if (financeiro && !ctx && !loading && !financeError) carregar(); }, [financeiro, ctx, loading, financeError, carregar]);
  useEffect(() => {
    let lastDay = localDay();
    const refreshDay = () => { const next = localDay(); if (next !== lastDay) { setDay((d) => d === lastDay ? next : d); lastDay = next; } };
    const id = setInterval(refreshDay, 30000);
    addEventListener("focus", refreshDay);
    return () => { clearInterval(id); removeEventListener("focus", refreshDay); };
  }, []);
  const toast = useCallback((msg) => {
    clearTimeout(timer.current); setToastMsg(msg);
    timer.current = setTimeout(() => setToastMsg(null), 3600);
  }, []);
  useEffect(() => () => clearTimeout(timer.current), []);
  const ir = useCallback((id) => { location.hash = id; setCurrent(route()); }, []);
  const openArea = (id) => ir(`vida/${id}`);
  const financialProps = { ctx, reload: carregar, toast, ir };
  const views = { visao: Overview, perfil: ProfileView, triagem: TriageView, gastos: Spending,
    fixos: Fixed, planos: Plans, previsoes: ForecastView, alavancas: LeversView, dados: Data };
  const FinancialView = views[current.page];
  return <div className="app mobile-app">
    <a className="skip-link" href="#conteudo" onClick={(e) => { e.preventDefault(); document.getElementById("conteudo").focus(); }}>Ir para o conteúdo</a>
    <header className="life-topbar"><div className="life-topbar-in"><a className="life-brand" href="#hoje" aria-label="FinTips, início"><span className="brand-mark" aria-hidden="true">FT</span><span>fintips<small>uma vida em perspectiva</small></span></a>
      <span className="local-indicator"><Icon name="lock" size={14}/><span>No seu aparelho</span></span>
    </div></header>
    <main id="conteudo" tabIndex={-1} className="life-main">
      {life.issue && <div className="storage-alert" role="alert"><Icon name="lock" size={19}/><div>{life.issue}<button className="text-button" onClick={() => ir("contexto")}>Abrir cópia local</button></div></div>}
      {current.page === "hoje" && <Today life={life} selectedDay={day} setDay={setDay} ir={ir} openArea={openArea} toast={toast}/>}
      {current.page === "vida" && <LifeAreas life={life} selectedDay={day} areaId={current.area} setArea={openArea} toast={toast} ir={ir}/>}
      {current.page === "projetos" && <LifePlans life={life} toast={toast} ir={ir}/>}
      {current.page === "contexto" && <PhoneContext life={life} toast={toast}/>}
      {financeiro && <div className="finance-content"><PageHeading code="03" overline="Reserva, escolhas e metas" title="Finanças" description="Entenda o presente. Abra espaço para seus planos."/>
        <div className="finance-tabs" aria-label="Seções financeiras">{FINANCE.map(([id, label]) => <button key={id} aria-pressed={current.page === id} onClick={() => ir(id)}>{label}{id === "triagem" && ctx?.triagem?.resumo?.abertos > 0 && <span className="finance-count">{ctx.triagem.resumo.abertos}</span>}</button>)}</div>
        {loading && <div className="loading-card" role="status">Organizando suas finanças…</div>}
        {!loading && financeError && <FinanceEmpty erro={financeError} reload={carregar} toast={toast}/>}
        {!loading && !financeError && ctx && FinancialView && <FinancialView {...financialProps}/>}
      </div>}
      <footer className="life-footer"><Icon name="lock" size={13}/><span>Seu contexto começa com você.</span></footer>
    </main>
    <nav className="bottom-nav" aria-label="Navegação principal"><div>{NAV.map(([id, label, icon]) => {
      const active = id === "visao" ? financeiro : current.page === id;
      return <a key={id} href={`#${id}`} aria-current={active ? "page" : undefined}><Icon name={icon} size={23}/><span>{label}</span></a>;
    })}</div></nav>
    {toastMsg && <div className="life-toast" role="status">{toastMsg}</div>}
  </div>;
}

createRoot(document.getElementById("root")).render(<App/>);
