import React, { useEffect, useState } from "react";
import { ProjectionChart } from "./charts.jsx";
import { api, brl, brl0, mesLabel, pct, titulo } from "./lib.js";

function Panel({ titulo: t, hint, className = "c12", children }) {
  return (
    <section className={`panel ${className}`}>
      {t && <h2>{t}</h2>}
      {hint && <p className="hint">{hint}</p>}
      {children}
    </section>
  );
}

/* ====================================================================== PERFIL
 *
 * A tela inteira existe para manter visível a diferença entre o que os números
 * sugerem e o que alguém assinou. Por isso a sugestão nunca aparece sozinha:
 * vem sempre acompanhada da evidência que a sustenta e do rótulo "palpite".
 * Quem lê precisa poder discordar com o dado na mão.
 */
export function ProfileView({ ctx, reload, toast }) {
  const perfil = ctx.perfil;
  if (!perfil) return <div className="empty">perfil indisponível</div>;
  const cob = perfil.cobertura;

  return (
    <div className="grid">
      <Panel
        className="c12"
        titulo="Perfil financeiro"
        hint="Cinco eixos independentes. Perfil único seria horóscopo — descreveria todo mundo e não mudaria conta nenhuma."
      >
        <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
          <div className="score-head">
            <span className="score-num">{pct(cob.pct, 0)}</span>
            <span className="sub">
              {cob.assinados} de {cob.eixos} eixos assinados
            </span>
          </div>
          {perfil.divergencias.length > 0 && (
            <span className="tag declarado">
              {perfil.divergencias.length} divergência{perfil.divergencias.length > 1 ? "s" : ""}
            </span>
          )}
        </div>
        <div className="track" style={{ marginTop: 14 }}>
          <i style={{ width: `${Math.max(cob.pct, 0.8)}%`, background: "var(--ink)" }} />
        </div>
        <p className="hint" style={{ marginTop: 12, marginBottom: 0 }}>{cob.explicacao}.</p>
      </Panel>

      {perfil.eixos.map((e) => (
        <EixoCard key={e.eixo} eixo={e} reload={reload} toast={toast} />
      ))}

      <Panel
        className="c12"
        titulo="Indicadores que alimentam o casamento"
        hint="Os mesmos números das outras abas. Indicador ausente reprova o sinal em vez de casar por omissão."
      >
        <div className="scroll-x">
          <table>
            <thead>
              <tr><th>indicador</th><th className="num">valor</th></tr>
            </thead>
            <tbody>
              {Object.entries(perfil.indicadores).map(([k, v]) => (
                <tr key={k}>
                  <td className="mono" style={{ fontSize: 12 }}>{k}</td>
                  <td className="num">{v === null ? "—" : v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function EixoCard({ eixo, reload, toast }) {
  const [abrindo, setAbrindo] = useState(false);
  const [escolha, setEscolha] = useState(eixo.sugerido?.id || "");
  const [porque, setPorque] = useState("");
  const [nome, setNome] = useState("");
  const [descricao, setDescricao] = useState("");
  const [erro, setErro] = useState("");

  const assinado = eixo.assinado;
  const sug = eixo.sugerido;
  const personalizado = escolha === "personalizado";

  async function assinar(ev) {
    ev.preventDefault();
    setErro("");
    try {
      await api.assinarPerfil(eixo.eixo, {
        arquetipo: escolha,
        nome: personalizado ? nome : "",
        descricao: personalizado ? descricao : "",
        porque,
        origem: "usuario",
        confianca: 1,
      });
      setAbrindo(false);
      setPorque("");
      toast(`${eixo.nome.toLowerCase()} assinado`);
      reload();
    } catch (e) {
      setErro(e.message);
    }
  }

  return (
    <Panel className="c6" titulo={eixo.nome} hint={eixo.o_que_e}>
      {assinado ? (
        <>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
            <b style={{ fontSize: 16 }}>{assinado.nome}</b>
            <span className="tag contratual">{assinado.proveniencia.origem}</span>
          </div>
          {assinado.descricao && <p className="sub" style={{ margin: "6px 0 0" }}>{assinado.descricao}</p>}
          <p className="hint" style={{ marginTop: 10 }}>
            porque: {assinado.proveniencia.porque}
          </p>
          {eixo.diverge_da_sugestao && sug && (
            <div className="lever" style={{ marginTop: 12 }}>
              Os números sugeririam <b>{sug.nome}</b>. A assinatura vence — divergência
              costuma ser o extrato não contando a história toda.
            </div>
          )}
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn small" onClick={() => setAbrindo((v) => !v)}>rever</button>
            <button
              className="btn small"
              onClick={async () => {
                await api.esquecerPerfil(eixo.eixo);
                toast("traço removido");
                reload();
              }}
            >
              esquecer
            </button>
          </div>
        </>
      ) : sug ? (
        <>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
            <b style={{ fontSize: 16 }}>{sug.nome}</b>
            <span className="tag declarado">palpite · aderência {sug.aderencia}</span>
          </div>
          <p className="sub" style={{ margin: "6px 0 0" }}>{sug.descricao}</p>
          <p className="hint" style={{ marginTop: 10, marginBottom: 6 }}>o que isso muda: {sug.o_que_muda}</p>
          <ul className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)", paddingLeft: 18, margin: "8px 0 0" }}>
            {sug.evidencia.map((ev) => <li key={ev}>{ev}</li>)}
          </ul>
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn small primary" onClick={() => setAbrindo((v) => !v)}>assinar</button>
          </div>
        </>
      ) : (
        <>
          <b style={{ fontSize: 15 }}>Sem leitura</b>
          <p className="sub" style={{ margin: "6px 0 0" }}>{eixo.sem_leitura_porque}.</p>
          <p className="hint" style={{ marginTop: 8 }}>
            Estado honesto: o motor prefere não ter leitura a forçar o menos ruim.
          </p>
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn small" onClick={() => setAbrindo((v) => !v)}>assinar mesmo assim</button>
          </div>
        </>
      )}

      {abrindo && (
        <form onSubmit={assinar} style={{ borderTop: "1px solid var(--line-2)", paddingTop: 14, marginTop: 14 }}>
          <label className="field" style={{ marginBottom: 10 }}>
            arquétipo
            <select value={escolha} onChange={(ev) => setEscolha(ev.target.value)}>
              <option value="">escolha…</option>
              {eixo.candidatos.map((c) => (
                <option key={c.id} value={c.id}>{c.nome} — aderência {c.aderencia}</option>
              ))}
              <option value="personalizado">personalizado (nenhum me descreve)</option>
            </select>
          </label>
          {personalizado && (
            <div className="row" style={{ marginBottom: 10 }}>
              <label className="field">
                nome
                <input value={nome} onChange={(ev) => setNome(ev.target.value)} placeholder="Renda em blocos" />
              </label>
              <label className="field" style={{ flex: 1 }}>
                descrição
                <input
                  value={descricao}
                  onChange={(ev) => setDescricao(ev.target.value)}
                  placeholder="entra muito de três em três meses e nada no meio"
                />
              </label>
            </div>
          )}
          <label className="field" style={{ marginBottom: 12 }}>
            porque (obrigatório)
            <input
              value={porque}
              onChange={(ev) => setPorque(ev.target.value)}
              placeholder="o que você sabe que o extrato não mostra"
            />
          </label>
          {erro && <p className="hint" style={{ color: "var(--crit)" }}>{erro}</p>}
          <div className="row">
            <button className="btn primary" type="submit" disabled={!escolha || !porque.trim()}>
              assinar
            </button>
            <button className="btn" type="button" onClick={() => setAbrindo(false)}>cancelar</button>
          </div>
          <p className="hint" style={{ marginTop: 10, marginBottom: 0 }}>
            Assinar grava com origem <b>usuário</b> — quem está digitando é você. O casamento
            por número sozinho não assina nada.
          </p>
        </form>
      )}
    </Panel>
  );
}

/* =================================================================== PREVISÕES */
export function ForecastView({ ctx }) {
  const [cenario, setCenario] = useState("base");
  const [proj, setProj] = useState(ctx.projecao);
  const [meses, setMeses] = useState(12);

  useEffect(() => {
    api.projection(cenario, meses).then(setProj).catch(() => {});
  }, [cenario, meses]);

  if (!proj) return <div className="empty">sem projeção</div>;
  const p = proj.premissas;

  return (
    <div className="grid">
      <Panel
        className="c12"
        titulo="Projeção de caixa"
        hint="Repete como certo apenas o que foi definido como compromisso; o resto entra como média variável. Cenário conservador desconta a renda e infla o variável."
      >
        <div className="row" style={{ marginBottom: 14 }}>
          {["base", "conservador", "otimista"].map((c) => (
            <button
              key={c}
              className={`btn small ${c === cenario ? "primary" : ""}`}
              onClick={() => setCenario(c)}
            >
              {titulo(c)}
            </button>
          ))}
          <span style={{ width: 14 }} />
          {[6, 12, 24].map((m) => (
            <button
              key={m}
              className={`btn small ${m === meses ? "primary" : ""}`}
              onClick={() => setMeses(m)}
            >
              {m} meses
            </button>
          ))}
        </div>
        <ProjectionChart linhas={proj.linhas} reservaAlvo={proj.reserva.alvo} />
      </Panel>

      <Panel className="c5" titulo="Premissas" hint="A conta que sustenta a linha. Se uma premissa estiver errada, a projeção inteira está.">
        <div className="kpis">
          <div className="kpi"><div className="k">renda/mês</div><div className="v">{brl0(p.renda_mensal)}</div></div>
          <div className="kpi"><div className="k">fixo/mês</div><div className="v">{brl0(p.custo_fixo)}</div>
            <div className="n">{pct(p.fixo_pct_da_renda)} da renda</div></div>
          <div className="kpi"><div className="k">variável/mês</div><div className="v">{brl0(p.custo_variavel)}</div></div>
          <div className="kpi"><div className="k">sobra/mês</div><div className="v">{brl0(p.sobra_mensal)}</div></div>
        </div>
        <div className="lever" style={{ marginTop: 16 }}>
          Reserva alvo <b>{brl(proj.reserva.alvo)}</b>
          {proj.reserva.atingida_em
            ? <> — fecha em <b>{mesLabel(proj.reserva.atingida_em)}</b> neste cenário.</>
            : <> — não fecha dentro da janela de {meses} meses neste cenário.</>}
        </div>
      </Panel>

      <Panel className="c7" titulo="Quando cada meta fecha" hint="A mesma sobra atendendo a fila na ordem da prioridade.">
        {(proj.planos || []).length === 0 ? (
          <p className="hint" style={{ margin: 0 }}>Nenhum plano em aberto.</p>
        ) : (
        <div className="scroll-x">
          <table>
            <thead>
              <tr><th>plano</th><th className="num">falta ao fim</th><th className="num">conclui em</th></tr>
            </thead>
            <tbody>
              {(proj.planos || []).map((t) => (
                <tr key={t.id}>
                  <td>{t.nome}</td>
                  <td className="num">{brl0(t.falta_ao_fim)}</td>
                  <td className="num">{t.conclui_em ? mesLabel(t.conclui_em) : "fora da janela"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        )}
      </Panel>

      <Panel className="c12" titulo="Mês a mês" hint="Cada linha é conferível: renda menos fixo menos variável, e o que sobrou foi para onde.">
        <div className="scroll-x">
          <table>
            <thead>
              <tr>
                <th>mês</th><th className="num">renda</th><th className="num">fixo</th>
                <th className="num">variável</th><th className="num">sobra</th>
                <th className="num">para planos</th><th className="num">patrimônio</th>
              </tr>
            </thead>
            <tbody>
              {proj.linhas.map((l) => (
                <tr key={l.mes}>
                  <td className="mono">{mesLabel(l.mes)}</td>
                  <td className="num">{brl0(l.renda)}</td>
                  <td className="num">{brl0(l.custo_fixo)}</td>
                  <td className="num">{brl0(l.custo_variavel)}</td>
                  <td className="num">{brl0(l.sobra)}</td>
                  <td className="num">{brl0(l.aportes_em_planos)}</td>
                  <td className="num">{brl0(l.patrimonio_projetado)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

/* =================================================================== ALAVANCAS
 *
 * Note o que esta tela NÃO tem: nenhuma frase dizendo o que fazer. Cada cartão
 * é um número e o motor rodado de novo com ele. A leitura — se vale a pena, se
 * é viável, se já foi tentado — é da conversa com o agente, que sabe coisas que
 * o extrato não sabe.
 */
export function LeversView() {
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState(null);

  useEffect(() => {
    api.levers().then(setDados).catch((e) => setErro(e.message));
  }, []);

  if (erro) return <div className="empty">{erro}</div>;
  if (!dados) return <div className="empty">calculando…</div>;

  return (
    <div className="grid">
      <Panel
        className="c12"
        titulo="Alavancas"
        hint="O que muda cada número, e quanto — com o motor rodado de novo. Não são conselhos: o que vale a pena depende de coisas que o extrato não vê."
      >
        <p className="sub" style={{ margin: 0 }}>
          {dados.total} alavancas, ordenadas por <span className="marca">{dados.ordenado_por}</span>.
          Alavanca sem valor em reais não é a menos importante — é a que o motor
          não soube converter.
        </p>
      </Panel>

      {dados.alavancas.map((a) => (
        <LeverCard key={a.id} a={a} />
      ))}
    </div>
  );
}

/* Misturar unidades na mesma coluna é o jeito mais rápido de fazer alguém ler
   6 meses como R$ 6, ou 55 pontos como R$ 55. A exclusão vem primeiro de
   propósito: `meses_de_reserva_alvo` contém "alvo" mas conta meses. */
const NAO_DINHEIRO = /^(meses|pct|score|ganho|volatilidade|taxa|conclui|reserva_fecha)/;
const DINHEIRO = /(valor|custo|acumulado|invisivel|teto|falta|sobra)/;
const PORCENTO = /(^pct|_pct$|^taxa_)/;

function formatar(chave, valor) {
  if (NAO_DINHEIRO.test(chave)) return PORCENTO.test(chave) ? pct(valor) : valor;
  return DINHEIRO.test(chave) ? brl0(valor) : valor;
}

function LeverCard({ a }) {
  const entradas = Object.entries(a.efeito).filter(([, v]) => v !== null && v !== "");
  const numeros = entradas.filter(([, v]) => typeof v === "number");
  const textos = entradas.filter(([, v]) => typeof v === "string");

  return (
    <>
      <Panel className="c6" titulo={a.tipo}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
            <b style={{ fontSize: 15, flex: 1 }}>{a.titulo}</b>
          </div>
          <div className="score-head" style={{ marginTop: 10 }}>
            <span className="score-num" style={{ fontSize: 30 }}>
              {a.unidade.startsWith("BRL") ? brl0(a.numero) : a.numero}
            </span>
            <span className="eyebrow">
              {a.unidade === "BRL/mes" ? "por mês" : a.unidade === "BRL" ? "total" : a.unidade}
            </span>
          </div>

          {/* número e prosa não cabem na mesma tabela: a coluna numérica
              alinha à direita e sem quebra, o que destrói qualquer frase */}
          {numeros.length > 0 && (
            <table style={{ marginTop: 14 }}>
              <tbody>
                {numeros.map(([k, v]) => (
                  <tr key={k}>
                    <td
                      className="mono"
                      style={{ fontSize: 11.5, color: "var(--ink-3)", whiteSpace: "nowrap" }}
                    >
                      {k.replace(/_/g, " ")}
                    </td>
                    <td className="num">{formatar(k, v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {textos.map(([k, v]) => (
            <div className="lever" key={k} style={{ marginTop: 12, fontSize: 12.5 }}>
              <span className="eyebrow">{k.replace(/_/g, " ")}</span>
              <div style={{ marginTop: 4 }}>{v}</div>
            </div>
          ))}

        <details style={{ marginTop: 12 }}>
          <summary className="eyebrow" style={{ cursor: "pointer" }}>evidência</summary>
          <ul className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)", paddingLeft: 18 }}>
            {a.evidencia.map((ev) => <li key={ev}>{ev}</li>)}
          </ul>
        </details>
      </Panel>
    </>
  );
}
