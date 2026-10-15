import React, { useState } from "react";
import { nativeMotor, hasNativeMotor } from "./native-motor.js";
import { brl, dataBR } from "./lib.js";
import { Icon } from "./icons.jsx";
import { PageHeading } from "./life.jsx";

export function NativeFinance() {
  const [file, setFile] = useState(null), [opening, setOpening] = useState("");
  const [result, setResult] = useState(null), [busy, setBusy] = useState(false), [issue, setIssue] = useState("");
  return <><PageHeading code="03" overline="Motor embarcado" title="Finanças" description="Primeiro confira os dados. Depois, tome decisões."/>
    <section className="life-card ai-connect"><div className="section-head"><h2>Conferir um extrato OFX</h2><Icon name="wallet"/></div>
      <p>O parser Kotlin já roda no aparelho. Este fluxo confere o saldo; ainda não classifica gastos, calcula score financeiro ou salva um histórico. O arquivo é lido em memória e não é enviado ao MCP.</p>
      <form onSubmit={async (e) => {
        e.preventDefault(); if (!file || busy) return;
        setBusy(true); setIssue(""); setResult(null);
        try {
          if (file.size > 1024 * 1024) throw new Error("Use um arquivo OFX de até 1 MB.");
          if (!/^-?\d{1,12}([.,]\d{1,2})?$/.test(opening)) throw new Error("Informe o saldo anterior em reais, com até duas casas decimais.");
          setResult(await nativeMotor("extrato.conferir", { ofx: await file.text(), saldo_inicial: opening }));
        } catch (e) { setIssue(e.message); } finally { setBusy(false); }
      }}>
        <label className="life-field">Arquivo no aparelho<input required disabled={busy} type="file" accept=".ofx,.qfx" onChange={(e) => { setFile(e.target.files?.[0] || null); setResult(null); }}/></label>
        <label className="life-field">Saldo imediatamente anterior ao período (R$)<input required disabled={busy} inputMode="decimal" placeholder="Ex.: 1250,00" value={opening} onChange={(e) => { setOpening(e.target.value); setResult(null); }}/></label>
        <button className="life-button primary full" disabled={busy || !file || !opening || !hasNativeMotor()}>{busy ? "Conferindo no aparelho…" : "Conferir com o motor Kotlin"}</button>
      </form>
      {!hasNativeMotor() && <p role="status">Atualize o Android System WebView para acessar o motor. Seus registros foram preservados.</p>}
      {issue && <p role="alert" className="form-error">{issue}</p>}
      {result && <div className="native-result" role="status"><strong>{result.conciliado ? "Saldo conferido" : "Há uma diferença"}</strong><span>{result.transacoes} transações · {dataBR(result.inicio)} a {dataBR(result.fim)}</span><span>Saldo declarado: {brl(result.saldo_centavos / 100)}</span><span>Diferença: {brl(result.diferenca_centavos / 100)}</span><small>Conferência aritmética do arquivo e do saldo informado. Não confirma categorias ou origem das movimentações.</small></div>}
    </section></>;
}
