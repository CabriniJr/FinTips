import React, { useState, useCallback } from "react";
import { brl, brl0, mesLabel } from "./lib.js";

/* Um tooltip só, compartilhado por todos os gráficos. */
function useTip() {
  const [tip, setTip] = useState(null);
  const bind = useCallback(
    (text) => ({
      onPointerEnter: (e) => setTip({ text, x: e.clientX, y: e.clientY }),
      onPointerMove: (e) => setTip((t) => (t ? { ...t, x: e.clientX, y: e.clientY } : t)),
      onPointerLeave: () => setTip(null),
    }),
    []
  );
  const node = tip ? (
    <div
      className="tt"
      style={{ left: Math.min(tip.x + 12, window.innerWidth - 180), top: Math.max(tip.y - 46, 8) }}
    >
      {tip.text}
    </div>
  ) : null;
  return [bind, node];
}

/* ------------------------------------------------- fluxo mensal: barras + linha */
export function FlowChart({ meses }) {
  const [bind, tip] = useTip();
  if (!meses?.length) return null;
  const W = 760, H = 300, mL = 56, mR = 12, mT = 14, mB = 34;
  const iw = W - mL - mR, ih = H - mT - mB;
  const max = Math.max(...meses.flatMap((m) => [m.renda, m.despesa, m.sobra])) * 1.1 || 1;
  const y = (v) => mT + ih - (v / max) * ih;
  const bw = iw / meses.length;
  const step = max > 6000 ? 2000 : 1000;
  const ticks = [];
  for (let v = 0; v <= max; v += step) ticks.push(v);
  const pts = meses.map((m, i) => [mL + i * bw + bw / 2, y(m.sobra)]);

  return (
    <>
      <div className="legend">
        <span><i className="swatch" style={{ background: "var(--s1)" }} />Renda</span>
        <span><i className="swatch" style={{ background: "var(--s2)" }} />Despesa</span>
        <span><i className="swatch line" style={{ background: "var(--s3)" }} />Sobra</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Renda, despesa e sobra por mês">
        {ticks.map((v) => (
          <g key={v}>
            <line className="gridline" x1={mL} x2={mL + iw} y1={y(v)} y2={y(v)} />
            <text className="tick" x={mL - 9} y={y(v) + 3.5} textAnchor="end">{v / 1000}k</text>
          </g>
        ))}
        {meses.map((m, i) => {
          const cx = mL + i * bw, pad = bw * 0.17, gap = 2, bar = (bw - pad * 2 - gap) / 2;
          return (
            <g key={m.mes}>
              <rect x={cx + pad} y={y(m.renda)} width={bar} height={Math.max(mT + ih - y(m.renda), 1)}
                rx="4" fill="var(--s1)" {...bind(`${mesLabel(m.mes)}\nrenda: ${brl(m.renda)}`)} />
              <rect x={cx + pad + bar + gap} y={y(m.despesa)} width={bar}
                height={Math.max(mT + ih - y(m.despesa), 1)} rx="4" fill="var(--s2)"
                {...bind(`${mesLabel(m.mes)}\ndespesa: ${brl(m.despesa)}`)} />
              <text className="axis-lab" x={cx + bw / 2} y={H - 12} textAnchor="middle">
                {mesLabel(m.mes)}
              </text>
            </g>
          );
        })}
        <path d={"M" + pts.map((p) => p.join(" ")).join(" L ")} fill="none"
          stroke="var(--s3)" strokeWidth="2" strokeLinejoin="round" />
        {pts.map(([px, py], i) => (
          <g key={i}>
            <circle cx={px} cy={py} r="5.5" fill="var(--s3)" stroke="var(--card)" strokeWidth="2" />
            <text className="axis-lab" x={px} y={py - 14} textAnchor="middle" fill="var(--ink-2)">
              {brl0(meses[i].sobra).replace("R$ ", "")}
            </text>
            <circle cx={px} cy={py} r="14" fill="transparent"
              {...bind(`${mesLabel(meses[i].mes)}\nsobra: ${brl(meses[i].sobra)}`)} />
          </g>
        ))}
      </svg>
      {tip}
    </>
  );
}

/* ------------------------------------------------------- barras horizontais */
export function HBars({ data, color = "var(--s1)", max: maxIn, format = brl0, height = 30 }) {
  const [bind, tip] = useTip();
  if (!data?.length) return null;
  const W = 520, lab = 130, mR = 92;
  const H = data.length * height + 8;
  const max = maxIn || Math.max(...data.map((d) => d.valor)) || 1;
  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} role="img">
        {data.map((d, i) => {
          const yy = i * height + 6;
          const bw = (d.valor / max) * (W - lab - mR);
          return (
            <g key={d.rotulo}>
              <text className="axis-lab" x={lab - 10} y={yy + 13} textAnchor="end">{d.rotulo}</text>
              <rect x={lab} y={yy + 2} width={Math.max(bw, 2)} height="16" rx="4"
                fill={d.cor || color} opacity={d.opacidade ?? 1}
                {...bind(`${d.rotulo}: ${brl(d.valor)}${d.nota ? "\n" + d.nota : ""}`)} />
              <text className="axis-lab" x={lab + bw + 9} y={yy + 14.5} fill="var(--ink-2)">
                {format(d.valor)}
              </text>
            </g>
          );
        })}
      </svg>
      {tip}
    </>
  );
}

/* --------------------------------------------- barra empilhada de estrutura
   Genérica de propósito: as naturezas de custo são nomeadas por quem define o
   compromisso, não por uma lista fixa no código. */
const CORES = ["var(--s1)", "var(--s3)", "var(--s4)", "var(--s2)"];

export function CostStack({ porNatureza = {}, variavel = 0, explicacao = "" }) {
  const partes = [
    ...Object.entries(porNatureza).map(([k, v], i) => ({
      k, v, c: CORES[i % CORES.length], definido: true,
    })),
    { k: "não comprometido", v: variavel, c: "var(--ink-3)", definido: false },
  ].filter((p) => p.v > 0);
  const total = partes.reduce((s, p) => s + p.v, 0) || 1;

  if (partes.length === 1 && !partes[0].definido) {
    return (
      <div style={{ fontSize: 13, color: "var(--ink-2)" }}>
        Nenhum compromisso definido ainda: os {brl0(variavel)}/mês de despesa estão
        todos como variável. Enquanto ninguém decidir o que é compromisso, a
        projeção trata tudo como escolha mensal.
        <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 6 }}>{explicacao}</div>
      </div>
    );
  }

  return (
    <div>
      <div className="stack">
        {partes.map((p) => (
          <i key={p.k} title={`${p.k}: ${brl(p.v)}`}
            style={{ width: `${(p.v / total) * 100}%`, minWidth: 3, background: p.c,
                     opacity: p.definido ? 1 : 0.35 }} />
        ))}
      </div>
      <div className="bar-legend">
        {partes.map((p) => (
          <div className="item" key={p.k}>
            <i className="swatch" style={{ background: p.c, opacity: p.definido ? 1 : 0.35 }} />
            <div>
              <b>{brl0(p.v)}</b>{" "}
              <span style={{ color: "var(--ink-3)" }}>
                {p.k} · {Math.round((p.v / total) * 100)}%
              </span>
            </div>
          </div>
        ))}
      </div>
      {explicacao && (
        <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 10 }}>{explicacao}</div>
      )}
    </div>
  );
}

/* ------------------------------------------------------ projeção de caixa */
export function ProjectionChart({ linhas, reservaAlvo }) {
  const [bind, tip] = useTip();
  if (!linhas?.length) return null;
  const W = 760, H = 260, mL = 58, mR = 14, mT = 16, mB = 32;
  const iw = W - mL - mR, ih = H - mT - mB;
  const max = Math.max(...linhas.map((l) => l.patrimonio_projetado), reservaAlvo || 0) * 1.1 || 1;
  const x = (i) => mL + (i / Math.max(linhas.length - 1, 1)) * iw;
  const y = (v) => mT + ih - (v / max) * ih;
  const d = linhas.map((l, i) => `${i ? "L" : "M"} ${x(i)} ${y(l.patrimonio_projetado)}`).join(" ");
  const area = `${d} L ${x(linhas.length - 1)} ${mT + ih} L ${mL} ${mT + ih} Z`;
  const step = max > 60000 ? 20000 : max > 30000 ? 10000 : 5000;
  const ticks = [];
  for (let v = 0; v <= max; v += step) ticks.push(v);

  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Patrimônio projetado">
        {ticks.map((v) => (
          <g key={v}>
            <line className="gridline" x1={mL} x2={mL + iw} y1={y(v)} y2={y(v)} />
            <text className="tick" x={mL - 9} y={y(v) + 3.5} textAnchor="end">{v / 1000}k</text>
          </g>
        ))}
        {reservaAlvo > 0 && (
          <g>
            <line x1={mL} x2={mL + iw} y1={y(reservaAlvo)} y2={y(reservaAlvo)}
              stroke="var(--s4)" strokeWidth="1.5" strokeDasharray="5 4" />
            <text className="axis-lab" x={mL + iw - 6} y={y(reservaAlvo) - 7} textAnchor="end" fill="var(--s4)">
              reserva alvo {brl0(reservaAlvo)}
            </text>
          </g>
        )}
        <path d={area} fill="var(--s1)" opacity="0.12" />
        <path d={d} fill="none" stroke="var(--s1)" strokeWidth="2" strokeLinejoin="round" />
        {linhas.map((l, i) => (
          <g key={l.mes}>
            <circle cx={x(i)} cy={y(l.patrimonio_projetado)} r="3.5" fill="var(--s1)" />
            <circle cx={x(i)} cy={y(l.patrimonio_projetado)} r="14" fill="transparent"
              {...bind(`${mesLabel(l.mes)}\npatrimônio: ${brl(l.patrimonio_projetado)}\nsobra: ${brl(l.sobra)}\naporte: ${brl(l.aportes_em_planos)}`)} />
            {i % Math.ceil(linhas.length / 6) === 0 && (
              <text className="axis-lab" x={x(i)} y={H - 10} textAnchor="middle">{mesLabel(l.mes)}</text>
            )}
          </g>
        ))}
      </svg>
      {tip}
    </>
  );
}

/* ------------------------------------------------------- barras do score */
export function ScoreBars({ dimensoes }) {
  const rot = {
    poupanca: "Poupança", reserva: "Reserva", estabilidade: "Estabilidade",
    vazamentos: "Vazamentos", planos: "Planos",
  };
  const cor = (p) => (p >= 75 ? "var(--good)" : p >= 45 ? "var(--warn)" : "var(--crit)");
  return (
    <div className="dims">
      {dimensoes.map((d) => (
        <div className="dim" key={d.nome}>
          <div>{rot[d.nome] || d.nome}</div>
          <div className="track"><i style={{ width: `${d.pct}%`, background: cor(d.pct) }} /></div>
          <div className="val">{String(d.pontos).replace(".", ",")} / {d.maximo}</div>
        </div>
      ))}
    </div>
  );
}
