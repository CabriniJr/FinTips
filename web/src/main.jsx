import React, { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, brl, dataBR } from "./lib.js";
import { ForecastView, LeversView, ProfileView } from "./profile.jsx";
import { TriageView } from "./triage.jsx";
import { Data, Fixed, Overview, Plans, Spending } from "./views.jsx";
import "./styles.css";

const ABAS = [
  ["visao", "Visão geral"],
  ["perfil", "Perfil"],
  ["triagem", "Triagem"],
  ["gastos", "Gastos"],
  ["fixos", "Compromissos"],
  ["planos", "Planos"],
  ["previsoes", "Previsões"],
  ["alavancas", "Alavancas"],
  ["dados", "Dados"],
];

function App() {
  const [ctx, setCtx] = useState(null);
  const [erro, setErro] = useState(null);
  const [aba, setAba] = useState(() => location.hash.slice(1) || "visao");
  const [toastMsg, setToastMsg] = useState(null);

  const carregar = useCallback(() => {
    api.context().then((c) => { setCtx(c); setErro(null); }).catch((e) => setErro(e.message));
  }, []);

  useEffect(carregar, [carregar]);
  useEffect(() => {
    const h = () => setAba(location.hash.slice(1) || "visao");
    addEventListener("hashchange", h);
    return () => removeEventListener("hashchange", h);
  }, []);

  const toast = useCallback((msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 2800);
  }, []);

  const ir = useCallback((id) => {
    location.hash = id;
    setAba(id);
  }, []);

  if (erro) {
    return (
      <div className="empty">
        <h1>Sem extrato ainda</h1>
        <p>{erro}</p>
        <p className="mono" style={{ fontSize: 13 }}>fintips ingest extrato.ofx</p>
      </div>
    );
  }
  if (!ctx) return <div className="empty">carregando…</div>;

  const props = { ctx, reload: carregar, toast, ir };
  const pendentes = ctx.triagem?.resumo?.abertos || 0;

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-in">
          <div className="brand">
            FinTips <small>{dataBR(ctx.periodo.inicio)} – {dataBR(ctx.periodo.fim)}</small>
          </div>
          <div className="mono" style={{ fontSize: 12.5, color: "var(--ink-3)" }}>
            em conta {brl(ctx.saldo_conta)} · total {brl(ctx.patrimonio?.total || 0)}
          </div>
          <nav>
            {ABAS.map(([id, rotulo]) => (
              <button key={id} aria-current={aba === id} onClick={() => ir(id)}>
                {rotulo}
                {id === "triagem" && pendentes > 0 && <span className="badge-n">{pendentes}</span>}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main>
        {aba === "visao" && <Overview {...props} />}
        {aba === "perfil" && <ProfileView {...props} />}
        {aba === "triagem" && <TriageView {...props} />}
        {aba === "gastos" && <Spending {...props} />}
        {aba === "fixos" && <Fixed {...props} />}
        {aba === "planos" && <Plans {...props} />}
        {aba === "previsoes" && <ForecastView {...props} />}
        {aba === "alavancas" && <LeversView {...props} />}
        {aba === "dados" && <Data {...props} />}
      </main>

      {toastMsg && <div className="toast">{toastMsg}</div>}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
