import React, { useCallback, useEffect, useRef, useState } from "react";
import { nativeMotor, hasNativeMotor } from "./native-motor.js";
import { brl, dataBR } from "./lib.js";
import { FinancialFlows } from "./financial-flows.jsx";
import { Icon } from "./icons.jsx";
import { PageHeading } from "./life.jsx";
import "./native-finance.css";

export function NativeFinance({ toast }) {
  const [file, setFile] = useState(null), [opening, setOpening] = useState("");
  const [state, setState] = useState(null), [busy, setBusy] = useState(true), [issue, setIssue] = useState("");
  const [receipt, setReceipt] = useState(null), [removing, setRemoving] = useState(null);
  const seq = useRef(0), mounted = useRef(true), fileInput = useRef(null);
  const load = useCallback(async () => {
    const ticket = ++seq.current;
    try { const data = await nativeMotor("extrato.estado"); if (mounted.current && ticket === seq.current) { setState(data); setIssue(""); } }
    catch (e) { if (mounted.current && ticket === seq.current) setIssue(e.message); }
    finally { if (mounted.current && ticket === seq.current) setBusy(false); }
  }, []);
  useEffect(() => { load(); return () => { mounted.current = false; ++seq.current; }; }, [load]);
  useEffect(() => { if (busy) return; addEventListener("fintips:resume", load); return () => removeEventListener("fintips:resume", load); }, [load, busy]);
  const ctx = state?.contexto;
  const changed = (next) => { setState(next); dispatchEvent(new Event("fintips:finance-changed")); };
  return <><PageHeading code="03" overline="Contexto financeiro no aparelho" title="Finanças" description="Seus extratos alimentam o contexto das suas decisões."/>
    {receipt && <div className="native-result" role="status"><strong>{receipt.duplicado ? "Este extrato já estava registrado" : "Extrato registrado no aparelho"}</strong><span>{receipt.novas_transacoes} nova(s) transação(ões). {receipt.contexto.transacoes} no histórico, sem duplicar arquivos sobrepostos.</span><small>O resumo financeiro fica disponível para a API do assistente. Origem/destino reais e arquivo bruto permanecem locais.</small></div>}
    {ctx?.estado === "importado" && <section className="life-card finance-snapshot" aria-label="Contexto dos extratos registrados">
      <span className="manual-tag">EXTRATOS REGISTRADOS</span><h2>{ctx.transacoes} movimentações no contexto</h2>
      <p>{ctx.contas} conta(s) · {ctx.arquivos} arquivo(s) · {dataBR(ctx.inicio)} a {dataBR(ctx.fim)}</p>
      <FinancialFlows data={state.fluxos}/>
      <details className="finance-gross"><summary>Conferir movimento bruto da conta</summary><p className="form-hint">Soma de todos os créditos e débitos, incluindo investimentos, Pix e estornos. Serve para conferir o arquivo; não é renda, consumo ou saldo disponível.</p>
        <dl className="finance-totals"><div><dt>Créditos brutos</dt><dd>{brl(ctx.entradas_centavos / 100)}</dd></div><div><dt>Débitos brutos</dt><dd>{brl(ctx.saidas_centavos / 100)}</dd></div><div><dt>Variação no período</dt><dd>{brl(ctx.liquido_centavos / 100)}</dd></div></dl>
        <div className="finance-months">{ctx.meses.map((m) => <div key={m.mes}><strong>{m.mes}</strong><span>{m.transacoes} movimentações</span><span>Créditos {brl(m.entradas_centavos / 100)}</span><span>Débitos {brl(m.saidas_centavos / 100)}</span></div>)}</div>
      </details>
      {!!ctx.conciliacao.nao_conferidos && <p className="finance-evidence">{ctx.conciliacao.nao_conferidos} extrato(s) sem conferência do saldo inicial.</p>}
      {!!ctx.conciliacao.divergentes && <p className="form-error">{ctx.conciliacao.divergentes} extrato(s) com diferença na conciliação. A fonte foi preservada com essa ressalva.</p>}
      <a className="life-button" href="#conversa">Conversar sobre meus planos <Icon name="arrow" size={18}/></a>

    </section>}
    <section className="life-card ai-connect"><div className="section-head"><h2>{ctx?.arquivos ? "Adicionar extrato" : "Registrar meu primeiro extrato"}</h2><Icon name="wallet"/></div>
      <p>Escolha um OFX. O arquivo fica no armazenamento privado do app e continua registrado depois de fechar ou atualizar. Ao usar o assistente pela API, ele recebe valores e períodos com investimentos, estornos e movimentos pendentes separados, sem banco, conta, memo ou contraparte real.</p>
      <form onSubmit={async (e) => {
        e.preventDefault(); if (!file || busy) return;
        setBusy(true); setIssue(""); setReceipt(null); const ticket = ++seq.current;
        try {
          if (file.size > 1024 * 1024) throw new Error("Use um arquivo OFX de até 1 MB.");
          const value = opening.trim();
          if (value && !/^-?\d{1,12}([.,]\d{1,2})?$/.test(value)) throw new Error("Informe o saldo anterior em reais, com até duas casas decimais, ou deixe em branco.");
          const next = await nativeMotor("extrato.importar", { ofx: await file.text(), saldo_inicial: value || null });
          if (!mounted.current || ticket !== seq.current) return;
          changed(next); setReceipt(next); setFile(null); setOpening(""); if (fileInput.current) fileInput.current.value = "";
          toast?.(next.duplicado ? "Extrato já registrado. Histórico preservado." : "Extrato registrado no contexto financeiro");
        } catch (e) { if (mounted.current && ticket === seq.current) setIssue(e.message); }
        finally { if (mounted.current && ticket === seq.current) setBusy(false); }
      }}>
        <label className="life-field">Extrato OFX no aparelho<input ref={fileInput} required disabled={busy} type="file" accept=".ofx,.qfx" onChange={(e) => { setFile(e.target.files?.[0] || null); setReceipt(null); }}/></label>
        <details><summary>Conferir também o saldo — opcional</summary><label className="life-field">Saldo imediatamente anterior ao período (R$)<input disabled={busy} inputMode="decimal" placeholder="Ex.: 1250,00" value={opening} onChange={(e) => setOpening(e.target.value)}/></label><p className="form-hint">Não precisa saber esse valor para registrar o extrato. Sem ele, a conciliação fica como não conferida.</p></details>
        <button className="life-button primary full" disabled={busy || !file || !hasNativeMotor()}>{busy ? "Lendo no aparelho…" : "Importar e registrar contexto"}</button>
      </form>
      {!hasNativeMotor() && <p role="status">Atualize o Android System WebView para acessar o motor. Seus registros foram preservados.</p>}
      {issue && <><p role="alert" className="form-error">{issue} Seus extratos anteriores foram preservados. Use um OFX de uma conta, em reais.</p>{!state && <button className="life-button" onClick={() => nativeMotor("extrato.exportar").catch((e) => setIssue(e.message))}>Salvar cópia para recuperação</button>}</>}
    </section>
    {!!state?.fontes.length && <section className="life-card finance-sources"><h2>Fontes registradas</h2><p className="form-hint">Até 20 arquivos, 1 MB cada e 16 MB no total. Arquivos repetidos não criam outra fonte.</p>
      {state.fontes.map((f, i) => <article key={f.ref}><div><span className="manual-tag">EXTRATO {i + 1}</span><h3>{dataBR(f.inicio)} a {dataBR(f.fim)}</h3><p>{f.transacoes} movimentações · {Number.isSafeInteger(f.saldo_centavos) ? `saldo declarado ${brl(f.saldo_centavos / 100)}` : "saldo não informado"}</p><small>{f.conciliacao === "conferido" ? "Saldo conferido" : f.conciliacao === "divergente" ? `Diferença de ${brl(f.diferenca_centavos / 100)}` : "Saldo inicial não informado"}</small></div><button className="text-button" disabled={busy} onClick={() => setRemoving(f.ref)}>Remover</button></article>)}
      <button className="life-button" disabled={busy} onClick={() => nativeMotor("extrato.exportar").catch((e) => setIssue(e.message))}>Salvar cópia dos extratos</button><p className="form-hint">Cópia privada em Downloads/FinTips, com os arquivos originais. Contém dados bancários; guarde no aparelho. A cópia de Vida/Leitura não inclui estes extratos.</p>
      <p className="form-hint">Conector MCP legado ainda não inclui este resumo financeiro. A fonte está no app e disponível para a API do assistente.</p>
    </section>}
    {removing && <section className="life-card" role="alertdialog" aria-label="Remover extrato do contexto"><p>Remover esta fonte do histórico local e recalcular o contexto? Você poderá importar o OFX novamente.</p><button className="life-button" disabled={busy} onClick={async () => {
      const ticket = ++seq.current; setBusy(true); setIssue("");
      try { const next = await nativeMotor("extrato.remover", { ref: removing }); if (mounted.current && ticket === seq.current) { changed(next); setRemoving(null); setReceipt(null); } }
      catch (e) { if (mounted.current && ticket === seq.current) setIssue(e.message); }
      finally { if (mounted.current && ticket === seq.current) setBusy(false); }
    }}>Remover fonte</button><button className="text-button" disabled={busy} onClick={() => setRemoving(null)}>Manter</button></section>}
  </>;
}
