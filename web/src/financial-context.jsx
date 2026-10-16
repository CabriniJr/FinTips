import React, { useEffect, useState } from "react";
import { isAndroid, nativeMotor } from "./native-motor.js";
import { dataBR } from "./lib.js";

/** Leitura do mesmo depósito nativo; nenhuma cópia financeira no localStorage. */
export function FinancialContextCard() {
  const [context, setContext] = useState(null), [issue, setIssue] = useState("");
  useEffect(() => {
    if (!isAndroid()) return;
    let ended = false, sequence = 0;
    const read = async () => {
      const ticket = ++sequence;
      try { const data = await nativeMotor("extrato.contexto"); if (!ended && ticket === sequence) { setContext(data); setIssue(""); } }
      catch { if (!ended && ticket === sequence) { setContext(null); setIssue("O histórico financeiro não pôde ser lido. As fontes foram preservadas."); } }
    };
    const events = ["fintips:finance-changed", "fintips:resume", "focus"];
    events.forEach((e) => addEventListener(e, read)); read();
    return () => { ended = true; events.forEach((e) => removeEventListener(e, read)); };
  }, []);
  if (!isAndroid()) return null;
  return <section className="life-card" aria-label="Contexto financeiro registrado"><span className="manual-tag">EXTRATOS / CONTEXTO LOCAL</span>
    {issue ? <p role="alert">{issue}</p> : context ? context.estado === "importado" ? <><h2>{context.transacoes} movimentações disponíveis</h2><p>{context.arquivos} extrato(s) · {dataBR(context.inicio)} a {dataBR(context.fim)}. A API do assistente recebe valores e períodos, com aplicações, resgates, estornos e movimentos pendentes separados; a conciliação e a cobertura seguem sinalizadas.</p></> : <><h2>Seu contexto financeiro começa pelo extrato</h2><p>Registre um OFX para disponibilizar suas movimentações ao assistente.</p></> : <p role="status">Consultando o contexto financeiro no aparelho…</p>}
    <a className="life-button" href="#visao">{context?.estado === "importado" ? "Ver extratos registrados" : "Abrir Finanças"}</a>
  </section>;
}
