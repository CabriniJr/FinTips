import React from "react";
import { brl } from "./lib.js";

const LABELS = {
  income: "Recebimentos identificados", expense: "Pagamentos identificados",
  savings_out: "Aplicações", savings_in: "Resgates", refund: "Estornos e devoluções", pendente: "A revisar",
};
const group = (data, flow) => data.grupos.find((g) => g.fluxo === flow);
const money = (n) => brl(n / 100);

function Value({ data, flow }) {
  const row = group(data, flow);
  const value = flow === "expense" || flow === "savings_out" ? row?.saidas_centavos : row?.entradas_centavos;
  return <div><dt>{LABELS[flow]}</dt><dd>{money(value || 0)}</dd><small>{row?.transacoes || 0} movimentações</small></div>;
}

/** Só apresenta a separação calculada no motor; não classifica pelo React. */
export function FinancialFlows({ data }) {
  if (!data) return <p className="finance-evidence" role="status">A separação dos fluxos não está disponível nesta versão do motor.</p>;
  const pending = group(data, "pendente");
  return <div className="financial-flows" aria-label="Separação dos fluxos financeiros">
    <h3>O que entrou e o que foi pago</h3>
    <p className="form-hint">Identificação inicial pelo tipo de lançamento. Aplicações, resgates e estornos ficam separados. Pix sem contexto suficiente permanece a revisar.</p>
    <dl className="finance-totals finance-primary"><Value data={data} flow="income"/><Value data={data} flow="expense"/></dl>
    {!!pending && <aside className="finance-pending" aria-label="Movimentações a revisar"><h3>{pending.transacoes} movimentações a revisar</h3>
      <p>Entradas {money(pending.entradas_centavos)} · Saídas {money(pending.saidas_centavos)}</p>
      <p className="form-hint">Fora dos recebimentos e pagamentos identificados. Um Pix pode ser renda, pagamento ou transferência; o extrato sozinho não resolve essa diferença.</p>
    </aside>}
    <h3>Investimentos e devoluções</h3>
    <dl className="finance-totals"><Value data={data} flow="savings_out"/><Value data={data} flow="savings_in"/><Value data={data} flow="refund"/></dl>
    <p className="form-hint">Aplicar é mover seu dinheiro para um investimento; resgatar é trazê-lo de volta. Esses movimentos não são consumo ou nova renda. Sem a análise completa, estes números ainda não determinam renda total, despesa total, reserva ou score.</p>
    <details><summary>Fluxos por mês</summary><div className="finance-flow-months">{data.meses.map((month) => <section key={month.mes}><h4>{month.mes}</h4><dl>{month.grupos.map((row) => <div key={row.fluxo}><dt>{LABELS[row.fluxo]}</dt><dd>{row.fluxo === "pendente" ? <>Entradas {money(row.entradas_centavos)} · Saídas {money(row.saidas_centavos)}</> : money(row.fluxo === "expense" || row.fluxo === "savings_out" ? row.saidas_centavos : row.entradas_centavos)}</dd></div>)}</dl></section>)}</div></details>
  </div>;
}
