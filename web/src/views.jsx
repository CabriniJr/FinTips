import React, { useEffect, useState } from "react";
import { CostStack, FlowChart, HBars, ProjectionChart, ScoreBars } from "./charts.jsx";
import { api, brl, brl0, dataBR, mesLabel, pct, titulo } from "./lib.js";

function Panel({ titulo: t, hint, className = "c12", children }) {
  return (
    <section className={`panel ${className}`}>
      {t && <h2>{t}</h2>}
      {hint && <p className="hint">{hint}</p>}
      {children}
    </section>
  );
}

/* ================================================================ VISÃO GERAL */
export function Overview({ ctx, ir }) {
  const { score, baseline: b, estrutura_de_custo: est } = ctx;
  const tri = ctx.triagem?.resumo || {};
  const clas = ctx.cobertura_da_classificacao || {};
  const kpis = [
    ["Taxa de poupança", pct(score.indicadores.taxa_poupanca), "da renda sobra por mês"],
    ["Reserva", `${String(score.indicadores.meses_de_reserva).replace(".", ",")} meses`, "de despesa cobertos"],
    ["Sobra média", brl0(b.sobra_media_mes), "por mês"],
    ["Comprometido", brl0(est.comprometido_mes), `${pct(est.comprometido_pct_renda)} da renda`],
    ["Invisível", brl0(score.indicadores.gasto_invisivel_mes), `${pct(score.indicadores.gasto_invisivel_pct_despesa)} da despesa`],
    ["Despesa média", brl0(b.despesa_media_mes), `${ctx.periodo.transacoes} lançamentos`],
  ];

  return (
    <div className="grid">
      {tri.abertos > 0 && (
        <section className="panel c12" style={{ borderColor: "var(--s4)" }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div>
              <div className="eyebrow">Triagem</div>
              <div style={{ fontSize: 14.5, marginTop: 4 }}>
                <b>{tri.abertos}</b> decisões em aberto, somando{" "}
                <b className="mono">{brl0(tri.impacto_mensal_em_aberto)}/mês</b> de dinheiro
                que ainda está classificado por palpite ou sem contexto.
              </div>
              <div style={{ fontSize: 12.5, color: "var(--ink-3)", marginTop: 4 }}>
                {clas.cobertura_pct || 0}% da despesa está classificada por decisão sua ou do agente.
              </div>
            </div>
            <button className="btn primary" onClick={() => ir("triagem")}>abrir triagem</button>
          </div>
        </section>
      )}

      <Panel className="c7" titulo="Score financeiro"
        hint="Cinco dimensões com peso explícito. A barra mostra quanto dos pontos possíveis foi conquistado.">
        <div className="score-head">
          <div className="score-num">{String(score.score).replace(".", ",")}</div>
          <div className="mono" style={{ color: "var(--ink-3)" }}>/ 100</div>
          <div className="faixa">{score.faixa}</div>
        </div>
        <ScoreBars dimensoes={score.dimensoes} />
        <div className="lever"><b>Maior ganho agora:</b> {score.proximo_ponto}.</div>
      </Panel>

      <Panel className="c5" titulo="Indicadores"
        hint="Médias dos meses completos — meses parciais das pontas ficam de fora.">
        <div className="kpis">
          {kpis.map(([k, v, n]) => (
            <div className="kpi" key={k}>
              <div className="k">{k}</div>
              <div className="v">{v}</div>
              <div className="n">{n}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel className="c12" titulo="Estrutura de custo"
        hint="As naturezas são nomeadas por quem define o compromisso — não há lista fixa no código.">
        <CostStack porNatureza={est.por_natureza} variavel={est.variavel_mes}
          explicacao={est.explicacao} />
      </Panel>

      <Panel className="c12" titulo="Fluxo mês a mês"
        hint="Renda e despesa não incluem aporte, resgate nem transferência entre contas suas — por isso a sobra é real.">
        <FlowChart meses={ctx.meses} />
      </Panel>
    </div>
  );
}

/* =================================================================== GASTOS */
export function Spending({ ctx }) {
  const [filtro, setFiltro] = useState({ mes: "", categoria: "", q: "" });
  const [txs, setTxs] = useState(null);

  useEffect(() => {
    let vivo = true;
    api.transactions({ ...filtro, fluxo: "expense", limite: 120 })
      .then((d) => vivo && setTxs(d))
      .catch(() => vivo && setTxs({ total: 0, transacoes: [] }));
    return () => { vivo = false; };
  }, [filtro]);

  const nomes = Object.fromEntries((ctx.taxonomia || []).map((c) => [c.id, c.nome]));
  const cats = Object.entries(ctx.por_categoria_total).slice(0, 10).map(([k, v], i) => ({
    rotulo: nomes[k] || titulo(k), valor: v,
    cor: i === 0 ? "var(--s2)" : "var(--s1)", opacidade: i === 0 ? 1 : 1 - i * 0.06,
  }));

  const cps = (ctx.contrapartes || []).filter((c) => c.fluxos?.includes("expense")).slice(0, 12);

  return (
    <div className="grid">
      <Panel className="c6" titulo="Para onde o dinheiro foi" hint="Despesa acumulada no período, por categoria.">
        <HBars data={cats} />
      </Panel>

      <Panel className="c6" titulo="Contrapartes" hint="Variações do mesmo estabelecimento já vêm agrupadas.">
        <div className="scroll-x">
          <table>
            <thead>
              <tr><th>Onde</th><th>Cadência</th><th className="num">Vezes</th><th className="num">Por mês</th></tr>
            </thead>
            <tbody>
              {cps.map((c) => (
                <tr key={c.id}>
                  <td>{c.nome}{c.apelidos?.length > 0 && (
                    <div style={{ fontSize: 11, color: "var(--ink-3)" }}>
                      {c.apelidos.length} variação(ões) agrupada(s)
                    </div>)}
                  </td>
                  <td><span className={`tag ${c.cadencia}`}>{c.cadencia.replace(/_/g, " ")}</span></td>
                  <td className="num">{c.transacoes}</td>
                  <td className="num">{brl(c.custo_mensal)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel className="c12" titulo="Transações"
        hint="A coluna origem mostra quem decidiu a categoria: heurística é palpite do pacote.">
        <div className="row" style={{ marginBottom: 12 }}>
          <select value={filtro.mes} onChange={(e) => setFiltro({ ...filtro, mes: e.target.value })}>
            <option value="">todos os meses</option>
            {ctx.meses.map((m) => <option key={m.mes} value={m.mes}>{mesLabel(m.mes)}</option>)}
          </select>
          <select value={filtro.categoria} onChange={(e) => setFiltro({ ...filtro, categoria: e.target.value })}>
            <option value="">todas as categorias</option>
            {Object.keys(ctx.por_categoria_total).map((c) => (
              <option key={c} value={c}>{nomes[c] || titulo(c)}</option>
            ))}
          </select>
          <input placeholder="buscar contraparte" value={filtro.q}
            onChange={(e) => setFiltro({ ...filtro, q: e.target.value })} />
          {txs && <span style={{ color: "var(--ink-3)", fontSize: 12.5 }}>{txs.total} resultado(s)</span>}
        </div>
        <div className="scroll-x">
          <table>
            <thead>
              <tr><th>Data</th><th>Contraparte</th><th>Categoria</th><th>Origem</th><th className="num">Valor</th></tr>
            </thead>
            <tbody>
              {(txs?.transacoes || []).map((t) => (
                <tr key={t.id}>
                  <td className="num" style={{ textAlign: "left" }}>{dataBR(t.data)}</td>
                  <td>{t.contraparte}</td>
                  <td>{nomes[t.categoria] || titulo(t.categoria)}</td>
                  <td>
                    <span className="tag" style={{
                      color: ["usuario", "agente"].includes(t.origem_categoria) ? "var(--s3)" : "var(--ink-3)",
                    }}>{t.origem_categoria}</span>
                  </td>
                  <td className="num" style={{ color: t.valor < 0 ? "var(--crit)" : "var(--good)" }}>
                    {brl(t.valor)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

/* ============================================================ COMPROMISSOS */
export function Fixed({ ctx, reload, toast }) {
  const definidos = ctx.custos_fixos || [];
  const candidatos = ctx.candidatos_custo_fixo || [];
  const inv = ctx.gastos_invisiveis || {};
  const anual = definidos.reduce((s, f) => s + f.valor_anual, 0);

  return (
    <div className="grid">
      <Panel className="c7" titulo="Compromissos definidos"
        hint="Só o que alguém afirmou entra aqui — e só isto a projeção repete como certo.">
        {definidos.length === 0 ? (
          <p className="hint">
            Nenhum compromisso definido. O motor detecta padrões, mas não decide por você:
            os candidatos estão ao lado.
          </p>
        ) : (
          <div className="scroll-x">
            <table>
              <thead>
                <tr><th>O quê</th><th>Natureza</th><th>Origem</th><th className="num">Por mês</th><th className="num">Por ano</th><th /></tr>
              </thead>
              <tbody>
                {definidos.map((f) => (
                  <tr key={f.id}>
                    <td>
                      {f.rotulo}
                      <div style={{ fontSize: 11.5, color: "var(--ink-3)" }}>
                        {f.base.tipo}: {f.base.ref} · {f.proveniencia.porque}
                      </div>
                    </td>
                    <td><span className="tag rotina">{f.natureza}</span></td>
                    <td><span className="tag">{f.proveniencia.origem}</span></td>
                    <td className="num">{brl(f.valor_mensal)}</td>
                    <td className="num" style={{ color: "var(--ink-3)" }}>{brl0(f.valor_anual)}</td>
                    <td className="num">
                      <button className="btn small" onClick={async () => {
                        await api.removerCustoFixo(f.id); toast("compromisso removido"); reload();
                      }}>remover</button>
                    </td>
                  </tr>
                ))}
                <tr>
                  <td><b>Total</b></td><td /><td />
                  <td className="num"><b>{brl(ctx.estrutura_de_custo.comprometido_mes)}</b></td>
                  <td className="num"><b>{brl0(anual)}</b></td><td />
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel className="c5" titulo="Candidatos detectados"
        hint="Padrão previsível encontrado pelo motor. É hipótese, não conclusão — confirme na triagem.">
        {candidatos.length === 0
          ? <p className="hint">Nenhum candidato no momento.</p>
          : candidatos.map((c) => (
              <div key={c.id} style={{
                padding: "11px 13px", borderRadius: 8, background: "var(--card-2)",
                border: "1px dashed var(--line)", marginBottom: 10,
              }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <b style={{ fontSize: 13 }}>{titulo(c.rotulo)}</b>
                  <span className="mono" style={{ fontSize: 13 }}>{brl0(c.por_mes)}/mês</span>
                </div>
                <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 4 }}>
                  {(c.evidencia || []).join(" · ")}
                </div>
              </div>
            ))}
      </Panel>

      <Panel className="c6" titulo="Gastos invisíveis"
        hint="O que não dói na hora. O que virou compromisso sai daqui — rotina não é desperdício.">
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {[
            ["Micro-gastos", `${inv.micro_gastos?.ocorrencias || 0} compras de até R$ 30 · ticket ${brl(inv.micro_gastos?.ticket_medio || 0)}`, inv.micro_gastos?.por_mes || 0],
            ["Taxas e seguros", `${inv.taxas_e_seguros?.ocorrencias || 0} cobranças automáticas`, inv.taxas_e_seguros?.por_mes || 0],
            ...(inv.sangrias || []).map((s) => [s.onde, `${s.vezes}× no período · ticket ${brl(s.ticket_medio)}`, s.por_mes]),
          ].map(([t, sub, m]) => (
            <div key={t} style={{
              display: "flex", justifyContent: "space-between", gap: 12, padding: "11px 13px",
              borderRadius: 8, background: "var(--card-2)", border: "1px solid var(--line-2)",
            }}>
              <div style={{ fontSize: 13 }}>
                {t}<div style={{ color: "var(--ink-3)", fontSize: 11.5 }}>{sub}</div>
              </div>
              <div style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                <div className="mono" style={{ fontWeight: 600 }}>{brl0(m)}/mês</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--warn)" }}>{brl0(m * 12)} ao ano</div>
              </div>
            </div>
          ))}
        </div>
        {(inv.excluido_por_declaracao || []).length > 0 && (
          <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 12 }}>
            fora da conta por decisão sua: {inv.excluido_por_declaracao.join(", ")}
          </div>
        )}
      </Panel>

      <Panel className="c6" titulo="Eventos atípicos"
        hint="Movimentos grandes e pontuais, fora da linha de base até alguém explicar o que foram.">
        <div className="scroll-x">
          <table>
            <thead><tr><th>Data</th><th>Contraparte</th><th>Fluxo</th><th className="num">Valor</th></tr></thead>
            <tbody>
              {(ctx.eventos_atipicos || []).slice(0, 10).map((e, i) => (
                <tr key={i}>
                  <td className="num" style={{ textAlign: "left" }}>{dataBR(e.data)}</td>
                  <td>{e.onde}</td>
                  <td><span className="tag">{e.fluxo}</span></td>
                  <td className="num" style={{ color: e.valor < 0 ? "var(--crit)" : "var(--good)" }}>{brl(e.valor)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

/* ================================================= PLANOS, PROJEÇÃO, COMPRA */
export function Plans({ ctx, reload, toast }) {
  const [cenario, setCenario] = useState("base");
  const [proj, setProj] = useState(ctx.projecao);
  const [novo, setNovo] = useState({ nome: "", custo_alvo: "", data_alvo: "", aporte_mensal: "", prioridade: "media" });
  const [compra, setCompra] = useState({ item: "", preco: "", parcelas_possiveis: 1, urgencia: "media" });
  const [veredito, setVeredito] = useState(null);

  useEffect(() => { api.projection(cenario).then(setProj).catch(() => {}); }, [cenario]);

  async function salvarPlano(e) {
    e.preventDefault();
    if (!novo.nome || !novo.custo_alvo) return;
    await api.savePlan({
      id: novo.nome.toLowerCase().normalize("NFD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
      nome: novo.nome, custo_alvo: Number(novo.custo_alvo),
      data_alvo: novo.data_alvo || null, aporte_mensal: Number(novo.aporte_mensal || 0),
      prioridade: novo.prioridade, tipo: "outro",
    });
    setNovo({ nome: "", custo_alvo: "", data_alvo: "", aporte_mensal: "", prioridade: "media" });
    toast("plano salvo");
    reload();
  }

  async function avaliar(e) {
    e.preventDefault();
    if (!compra.item || !compra.preco) return;
    setVeredito(await api.purchase({
      ...compra, preco: Number(compra.preco),
      parcelas_possiveis: Number(compra.parcelas_possiveis),
    }));
  }

  return (
    <div className="grid">
      <Panel className="c12" titulo="Projeção de caixa"
        hint="Repete como certo apenas o que foi definido como compromisso; o resto entra como média variável.">
        <div className="row" style={{ marginBottom: 12 }}>
          {["base", "conservador", "otimista"].map((c) => (
            <button key={c} className={`btn small ${c === cenario ? "primary" : ""}`} onClick={() => setCenario(c)}>
              {titulo(c)}
            </button>
          ))}
          {proj && (
            <span style={{ color: "var(--ink-3)", fontSize: 12.5, marginLeft: 6 }}>
              sobra {brl0(proj.premissas.sobra_mensal)}/mês · fixo {pct(proj.premissas.fixo_pct_da_renda)} da renda
              {proj.reserva.atingida_em && ` · reserva completa em ${mesLabel(proj.reserva.atingida_em)}`}
            </span>
          )}
        </div>
        {proj && <ProjectionChart linhas={proj.linhas} reservaAlvo={proj.reserva.alvo} />}
      </Panel>

      <Panel className="c7" titulo="Planos" hint="Meta cruzada com o extrato: o que já foi gasto nela conta como execução.">
        {(ctx.planos || []).length === 0 && <p className="hint">Nenhum plano cadastrado.</p>}
        {(ctx.planos || []).map((p) => (
          <div key={p.id} style={{ marginBottom: 18 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b>{p.nome}</b>
              <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>{p.status.replace(/_/g, " ")}</span>
            </div>
            <div className="track" style={{ margin: "8px 0 6px", height: 10 }}>
              <i style={{ width: `${Math.max(p.progresso_pct, 1.5)}%`, background: "var(--s3)" }} />
            </div>
            <div className="row mono" style={{ justifyContent: "space-between", fontSize: 12, color: "var(--ink-3)" }}>
              <span>{brl0(p.guardado)} de {brl0(p.custo_alvo)}</span>
              <span>{p.meses_ate_alvo} meses · precisa {brl0(p.aporte_necessario_mes)}/mês · pode {brl0(p.capacidade_mensal_real)}</span>
            </div>
            {p.ja_gasto_no_plano > 0 && (
              <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 4 }}>
                já gasto no plano: {brl(p.ja_gasto_no_plano)}
              </div>
            )}
            <div className="row" style={{ marginTop: 8 }}>
              <button className="btn small" onClick={async () => {
                await api.deletePlan(p.id); toast("plano removido"); reload();
              }}>remover</button>
            </div>
          </div>
        ))}
        <form onSubmit={salvarPlano} style={{ borderTop: "1px solid var(--line-2)", paddingTop: 14, marginTop: 6 }}>
          <div className="row">
            <label className="field">nome<input value={novo.nome} onChange={(e) => setNovo({ ...novo, nome: e.target.value })} placeholder="Trekking Patagônia" /></label>
            <label className="field">custo (R$)<input type="number" value={novo.custo_alvo} onChange={(e) => setNovo({ ...novo, custo_alvo: e.target.value })} /></label>
            <label className="field">data alvo<input type="date" value={novo.data_alvo} onChange={(e) => setNovo({ ...novo, data_alvo: e.target.value })} /></label>
            <label className="field">aporte/mês<input type="number" value={novo.aporte_mensal} onChange={(e) => setNovo({ ...novo, aporte_mensal: e.target.value })} /></label>
            <label className="field">prioridade
              <select value={novo.prioridade} onChange={(e) => setNovo({ ...novo, prioridade: e.target.value })}>
                <option value="alta">alta</option><option value="media">média</option><option value="baixa">baixa</option>
              </select>
            </label>
            <button className="btn primary" type="submit" style={{ alignSelf: "flex-end" }}>adicionar</button>
          </div>
        </form>
      </Panel>

      <Panel className="c5" titulo="Vale a pena comprar?"
        hint="O motor calcula; a decisão continua sua. Nada aqui é recomendação de investimento.">
        <form onSubmit={avaliar}>
          <div className="row">
            <label className="field" style={{ flex: 1 }}>item<input value={compra.item} onChange={(e) => setCompra({ ...compra, item: e.target.value })} placeholder="Monitor 27 QHD" /></label>
            <label className="field">preço<input type="number" value={compra.preco} onChange={(e) => setCompra({ ...compra, preco: e.target.value })} /></label>
            <label className="field">parcelas<input type="number" min="1" value={compra.parcelas_possiveis} onChange={(e) => setCompra({ ...compra, parcelas_possiveis: e.target.value })} /></label>
          </div>
          <button className="btn primary" type="submit" style={{ marginTop: 10 }}>avaliar</button>
        </form>
        {veredito && (
          <div style={{ marginTop: 14 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b className="mono">{veredito.veredito.replace(/_/g, " ")}</b>
              <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>prudência {veredito.score_prudencia}/100</span>
            </div>
            <div style={{ fontSize: 12.5, color: "var(--ink-2)", margin: "8px 0" }}>
              custa {veredito.custo_em_meses_de_sobra ? `${String(veredito.custo_em_meses_de_sobra).replace(".", ",")} mês(es)` : "—"} da sua sobra ·
              {veredito.reserva.compra_fura_reserva ? " fura a reserva" : " cabe sem tocar na reserva"}
            </div>
            {veredito.arrependimento.sinais.length > 0 && (
              <ul style={{ fontSize: 12.5, color: "var(--ink-3)", paddingLeft: 18, margin: "6px 0" }}>
                {veredito.arrependimento.sinais.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            )}
            <div className="scroll-x">
              <table>
                <thead><tr><th>Estratégia</th><th className="num">Custo</th><th>Observação</th></tr></thead>
                <tbody>
                  {veredito.estrategias.map((e) => (
                    <tr key={e.estrategia}>
                      <td>{e.estrategia.replace(/_/g, " ")}{e.estrategia === veredito.melhor_estrategia && <span className="tag rotina" style={{ marginLeft: 6 }}>melhor</span>}</td>
                      <td className="num">{brl0(e.custo_total)}</td>
                      <td style={{ color: "var(--ink-3)", fontSize: 12 }}>{e.observacao}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

/* ================================================================== DADOS */
export function Data({ ctx, reload, toast }) {
  const [pos, setPos] = useState(ctx.patrimonio?.posicoes || []);
  const [arquivo, setArquivo] = useState(null);

  async function salvar() {
    await api.holdings(pos.map((p) => ({ ...p, valor: Number(p.valor) })));
    toast("patrimônio atualizado");
    reload();
  }
  async function importar() {
    if (!arquivo) return;
    const r = await api.import(arquivo);
    toast(`${r.transacoes} transações · ${r.triagem.abertos} itens na triagem`);
    setArquivo(null);
    reload();
  }

  return (
    <div className="grid">
      <Panel className="c6" titulo="Patrimônio" hint="Saldos e posições que o extrato não enxerga.">
        {pos.map((p, i) => (
          <div className="row" key={i} style={{ marginBottom: 8 }}>
            <input value={p.nome} onChange={(e) => { const n = [...pos]; n[i] = { ...p, nome: e.target.value }; setPos(n); }} />
            <input type="number" value={p.valor} style={{ width: 130 }}
              onChange={(e) => { const n = [...pos]; n[i] = { ...p, valor: e.target.value }; setPos(n); }} />
          </div>
        ))}
        <div className="row">
          <button className="btn small" onClick={() => setPos([...pos, { nome: "", tipo: "conta", valor: 0, liquidez: "imediata" }])}>
            + posição
          </button>
          <button className="btn small primary" onClick={salvar}>salvar</button>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>
            total {brl(ctx.patrimonio?.total || 0)}
          </span>
        </div>
      </Panel>

      <Panel className="c6" titulo="Importar extrato"
        hint="Toda importação abre uma sessão de triagem com o que mudou.">
        <div className="row">
          <input type="file" accept=".ofx,.qfx" onChange={(e) => setArquivo(e.target.files?.[0] || null)} />
          <button className="btn small primary" onClick={importar} disabled={!arquivo}>importar</button>
        </div>
        <p className="hint" style={{ marginTop: 10 }}>
          O arquivo fica em data/extratos e nunca sai desta máquina.
          Período atual: {dataBR(ctx.periodo.inicio)} a {dataBR(ctx.periodo.fim)} ·{" "}
          {ctx.periodo.transacoes} transações
          {ctx.conciliacao.bate ? " · concilia com o saldo" : ` · divergência de ${brl(ctx.conciliacao.diferenca)}`}.
        </p>
      </Panel>
    </div>
  );
}
