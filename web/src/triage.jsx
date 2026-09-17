import React, { useState } from "react";
import { api, brl, brl0, titulo } from "./lib.js";

/* A tela de triagem existe para uma coisa: transformar o que está em aberto em
   decisão registrada. Ela não decide nada sozinha — mostra a evidência, o que
   muda, e quem decidiu o quê. O caminho rico é conversar com o agente; aqui
   ficam as decisões simples e a visão do que falta. */

const ROTULO_TIPO = {
  contraparte_nova: "contraparte nova",
  classificacao_fraca: "classificado por palpite",
  candidato_custo_fixo: "candidato a compromisso",
  custo_fixo_derivou: "compromisso derivou",
  fato_ausente: "falta contexto",
  fato_vencido: "contexto vencido",
  evento_sem_explicacao: "evento sem explicação",
};

const COR_TIPO = {
  fato_ausente: "var(--s1)",
  fato_vencido: "var(--s4)",
  contraparte_nova: "var(--s3)",
  classificacao_fraca: "var(--s4)",
  candidato_custo_fixo: "var(--s3)",
  custo_fixo_derivou: "var(--crit)",
  evento_sem_explicacao: "var(--ink-3)",
};

function Panel({ titulo: t, hint, className = "c12", children }) {
  return (
    <section className={`panel ${className}`}>
      {t && <h2>{t}</h2>}
      {hint && <p className="hint">{hint}</p>}
      {children}
    </section>
  );
}

function ItemDeTriagem({ item, categorias, reload, toast }) {
  const [aberto, setAberto] = useState(false);
  const [categoria, setCategoria] = useState("");
  const [valor, setValor] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const ev = item.evidencia || {};

  async function executar(fn, descricao) {
    setOcupado(true);
    try {
      await fn();
      await api.resolverItem(item.id, descricao);
      toast(descricao);
      reload();
    } catch (e) {
      toast("falhou: " + e.message);
    } finally {
      setOcupado(false);
    }
  }

  const classificar = () =>
    executar(
      () =>
        api.definirRegra({
          quando: { contraparte_id: ev.contraparte_id },
          entao: { categoria },
          porque: "classificado pelo usuário no painel",
          origem: "usuario",
          confianca: 1.0,
        }),
      `${item.titulo.split(" —")[0]} → ${categoria}`
    );

  const virarCompromisso = () =>
    executar(
      () =>
        api.definirCustoFixo({
          rotulo: ev.rotulo || item.titulo,
          base_tipo: ev.escopo === "contraparte" ? "contraparte" : "categoria",
          base_ref: ev.chave,
          valor_mensal: Number(valor) || ev.por_mes,
          natureza: ev.natureza || "rotina",
          porque: "confirmado pelo usuário no painel",
          origem: "usuario",
          confianca: 1.0,
        }),
      `${ev.chave} virou compromisso`
    );

  const gravarFato = (v) =>
    executar(
      () =>
        api.gravarFato({
          chave: ev.chave,
          valor: v,
          porque: "respondido pelo usuário no painel",
          origem: "usuario",
          confianca: 1.0,
        }),
      `${ev.chave} = ${v}`
    );

  return (
    <div className="question" style={{ borderLeft: `3px solid ${COR_TIPO[item.tipo] || "var(--line)"}` }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="eyebrow">{ROTULO_TIPO[item.tipo] || item.tipo}</span>
        <span className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)" }}>
          {brl0(item.impacto_mensal)}/mês · {brl0(item.impacto_anual)}/ano
        </span>
      </div>
      <div className="q">{item.titulo}</div>
      <div className="why">{item.porque_importa}</div>

      {item.tipo === "contraparte_nova" && (
        <div className="row">
          <select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
            <option value="">escolher categoria…</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>{c.nome}</option>
            ))}
          </select>
          <button className="btn small primary" disabled={!categoria || ocupado} onClick={classificar}>
            classificar
          </button>
        </div>
      )}

      {item.tipo === "candidato_custo_fixo" && (
        <div className="row">
          <input type="number" placeholder={String(ev.por_mes ?? "")} value={valor}
            style={{ width: 120 }} onChange={(e) => setValor(e.target.value)} />
          <button className="btn small primary" disabled={ocupado} onClick={virarCompromisso}>
            é compromisso
          </button>
          <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
            detectado por padrão — confirme só se for mesmo previsível
          </span>
        </div>
      )}

      {(item.tipo === "fato_ausente" || item.tipo === "fato_vencido") && (
        <div className="opts">
          {(ev.opcoes || []).map((o) => (
            <button key={o} disabled={ocupado} onClick={() => gravarFato(o)}>
              {o.replace(/_/g, " ")}
            </button>
          ))}
          {(!ev.opcoes || ev.opcoes.length === 0) && (
            <div className="row">
              <input style={{ flex: 1 }} value={valor} placeholder={ev.o_que_e}
                onChange={(e) => setValor(e.target.value)} />
              <button className="btn primary" disabled={!valor || ocupado}
                onClick={() => gravarFato(valor)}>gravar</button>
            </div>
          )}
        </div>
      )}

      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn small" onClick={() => setAberto(!aberto)}>
          {aberto ? "ocultar evidência" : "ver evidência"}
        </button>
        <button className="btn small" disabled={ocupado}
          onClick={() => executar(async () => {}, "adiado")}>
          adiar
        </button>
        {item.tipo === "evento_sem_explicacao" && (
          <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
            pergunte ao agente: ele grava a explicação como fato
          </span>
        )}
      </div>
      {aberto && (
        <pre className="mono" style={{
          fontSize: 11.5, background: "var(--card)", border: "1px solid var(--line-2)",
          borderRadius: 8, padding: 10, marginTop: 10, overflowX: "auto",
        }}>{JSON.stringify(ev, null, 2)}</pre>
      )}
    </div>
  );
}

/* Itens que dependem de conversa não viram formulário: viram uma linha com o
   contexto que o agente precisa para perguntar. Empilhar 29 cartões idênticos
   seria fingir que tudo se resolve com um clique. */
const RESOLVE_AQUI = new Set([
  "contraparte_nova", "candidato_custo_fixo", "fato_ausente", "fato_vencido",
]);

function LinhaCompacta({ item, reload, toast }) {
  const [ocupado, setOcupado] = useState(false);
  return (
    <tr>
      <td>
        {item.titulo}
        <div style={{ fontSize: 11.5, color: "var(--ink-3)" }}>
          {ROTULO_TIPO[item.tipo] || item.tipo}
        </div>
      </td>
      <td className="num">{brl0(item.impacto_mensal)}/mês</td>
      <td className="num">
        <button className="btn small" disabled={ocupado} onClick={async () => {
          setOcupado(true);
          try {
            await api.resolverItem(item.id, "adiado no painel", true);
            toast("adiado"); reload();
          } finally { setOcupado(false); }
        }}>adiar</button>
      </td>
    </tr>
  );
}

export function TriageView({ ctx, reload, toast }) {
  const t = ctx.triagem || { resumo: {}, itens: [] };
  const categorias = (ctx.taxonomia || []).filter((c) => c.id !== "outros");
  const contexto = ctx.contexto || {};
  const cob = contexto.cobertura || {};
  const clas = ctx.cobertura_da_classificacao || {};
  const [filtro, setFiltro] = useState("");
  const [mostrar, setMostrar] = useState(6);

  const todos = filtro ? t.itens.filter((i) => i.tipo === filtro) : t.itens;
  const acionaveis = todos.filter((i) => RESOLVE_AQUI.has(i.tipo));
  const conversaveis = todos.filter((i) => !RESOLVE_AQUI.has(i.tipo));

  return (
    <div className="grid">
      <Panel className="c8" titulo="Decisões que você fecha aqui"
        hint="Ordenadas pelo custo mensal de deixar em aberto. Uma decisão registrada vale para todos os extratos futuros.">
        <div className="row" style={{ marginBottom: 12 }}>
          <button className={`btn small ${filtro === "" ? "primary" : ""}`} onClick={() => setFiltro("")}>
            tudo ({t.resumo.abertos || 0})
          </button>
          {Object.entries(t.resumo.por_tipo || {}).map(([tipo, n]) => (
            <button key={tipo} className={`btn small ${filtro === tipo ? "primary" : ""}`}
              onClick={() => setFiltro(tipo)}>
              {ROTULO_TIPO[tipo] || tipo} ({n})
            </button>
          ))}
        </div>
        {acionaveis.length === 0
          ? <p className="hint">Nada em aberto para este filtro.</p>
          : acionaveis.slice(0, mostrar).map((i) => (
              <ItemDeTriagem key={i.id} item={i} categorias={categorias} reload={reload} toast={toast} />
            ))}
        {acionaveis.length > mostrar && (
          <button className="btn" style={{ marginTop: 12 }} onClick={() => setMostrar(mostrar + 6)}>
            mostrar mais {Math.min(6, acionaveis.length - mostrar)} de {acionaveis.length - mostrar}
          </button>
        )}

        {conversaveis.length > 0 && (
          <div style={{ marginTop: 26 }}>
            <div className="eyebrow">Precisam de conversa</div>
            <p className="hint" style={{ marginTop: 4 }}>
              Um clique não resolve: o que estes itens precisam é de explicação — foi único ou
              vai se repetir, é compromisso ou coincidência. Pergunte ao agente, que investiga
              e grava a resposta com a evidência.
            </p>
            <div className="scroll-x">
              <table>
                <thead>
                  <tr><th>O quê</th><th className="num">Impacto</th><th /></tr>
                </thead>
                <tbody>
                  {conversaveis.map((i) => (
                    <LinhaCompacta key={i.id} item={i} reload={reload} toast={toast} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Panel>

      <Panel className="c4" titulo="Quanto já se sabe"
        hint="Nada aqui é verdade sem origem declarada.">
        <div className="eyebrow">Contexto do usuário</div>
        <div className="track" style={{ height: 10, margin: "8px 0" }}>
          <i style={{ width: `${cob.cobertura_pct || 0}%`, background: "var(--s1)" }} />
        </div>
        <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 14 }}>
          {cob.nucleo_conhecido || 0}/{cob.nucleo_total || 0} do núcleo ·{" "}
          {cob.fatos_livres || 0} fatos específicos
        </div>

        <div className="eyebrow">Classificação por decisão</div>
        <div className="track" style={{ height: 10, margin: "8px 0" }}>
          <i style={{ width: `${clas.cobertura_pct || 0}%`, background: "var(--s3)" }} />
        </div>
        <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>
          {clas.cobertura_pct || 0}% do dinheiro classificado por decisão;
          o resto é palpite do pacote
        </div>

        <table style={{ marginTop: 16 }}>
          <tbody>
            {Object.entries(contexto.nucleo || {}).map(([k, v]) => (
              <tr key={k}>
                <td style={{ fontSize: 12 }}>{k}</td>
                <td className="num" style={{ color: v == null ? "var(--ink-3)" : "var(--ink)" }}>
                  {v == null ? "—" : String(v).replace(/_/g, " ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {Object.keys(contexto.especificos || {}).length > 0 && (
          <>
            <div className="eyebrow" style={{ marginTop: 16 }}>Específicos desta pessoa</div>
            <table>
              <tbody>
                {Object.entries(contexto.especificos).map(([k, v]) => (
                  <tr key={k}>
                    <td style={{ fontSize: 12 }}>{k}</td>
                    <td className="num">{String(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Panel>

      <Panel className="c7" titulo="Taxonomia"
        hint="As categorias pertencem a você. '?' marca o que veio da lista sugerida e ninguém revisou.">
        <div className="scroll-x">
          <table>
            <thead>
              <tr><th>Categoria</th><th>Origem</th><th className="num">No período</th></tr>
            </thead>
            <tbody>
              {(ctx.taxonomia || []).filter((c) => c.em_uso || c.total_no_periodo > 0).map((c) => (
                <tr key={c.id}>
                  <td>
                    {c.nome}
                    {!["usuario", "agente"].includes(c.proveniencia.origem) && (
                      <span style={{ color: "var(--ink-3)" }}> ?</span>
                    )}
                    {c.descricao && (
                      <div style={{ fontSize: 11.5, color: "var(--ink-3)" }}>{c.descricao}</div>
                    )}
                  </td>
                  <td><span className="tag">{c.proveniencia.origem}</span></td>
                  <td className="num">{brl(c.total_no_periodo)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel className="c5" titulo="Regras vigentes"
        hint="O que o agente e você decidiram. Mais específica e de maior autoridade vence.">
        {(ctx.regras || []).length === 0
          ? <p className="hint">Nenhuma regra ainda — tudo classificado por heurística.</p>
          : (ctx.regras || []).map((r) => (
              <div key={r.id} style={{
                padding: "10px 0", borderTop: "1px solid var(--line-2)", fontSize: 12.5,
              }}>
                <div className="mono" style={{ fontSize: 11.5 }}>
                  {JSON.stringify(r.quando)} → {JSON.stringify(r.entao)}
                </div>
                <div style={{ color: "var(--ink-3)", marginTop: 4 }}>
                  {r.proveniencia.porque}
                </div>
                <div className="row" style={{ marginTop: 6 }}>
                  <span className="tag">{r.proveniencia.origem}</span>
                  <button className="btn small" onClick={async () => {
                    await api.removerRegra(r.id); toast("regra removida"); reload();
                  }}>remover</button>
                </div>
              </div>
            ))}
      </Panel>
    </div>
  );
}
