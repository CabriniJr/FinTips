"""Score financeiro 0–100.

Cinco dimensões, pesos explícitos, tudo rastreável: cada ponto tem uma
fórmula visível. Nada de número mágico saído do LLM.
"""

from __future__ import annotations

from decimal import Decimal

Z = Decimal("0")

WEIGHTS = {
    "poupanca": 30,     # quanto da renda sobra
    "reserva": 25,      # meses de despesa cobertos pelo que está guardado
    "estabilidade": 15, # previsibilidade do gasto mensal
    "vazamentos": 10,   # peso dos gastos invisíveis
    "planos": 20,       # aderência às metas cadastradas
}


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _band(score: float) -> str:
    if score >= 85:
        return "excelente"
    if score >= 70:
        return "bom"
    if score >= 55:
        return "razoavel"
    if score >= 40:
        return "atencao"
    return "critico"


def compute(
    base: dict,
    invisible: dict,
    plan_results: list[dict],
    *,
    patrimonio_liquido: Decimal | float = 0,
) -> dict:
    patrimonio = Decimal(str(patrimonio_liquido))
    despesa = Decimal(str(base.get("despesa_media_mes", 0) or 0))
    renda = Decimal(str(base.get("renda_media_mes", 0) or 0))

    # 1. Taxa de poupança — 20% já é saudável, 40%+ é teto da nota.
    taxa = float(base.get("taxa_poupanca_media", 0) or 0)
    p_poupanca = _clamp(taxa / 0.40) * WEIGHTS["poupanca"]

    # 2. Reserva de emergência — 6 meses de despesa = nota cheia.
    meses_reserva = float(patrimonio / despesa) if despesa > 0 else 0.0
    p_reserva = _clamp(meses_reserva / 6.0) * WEIGHTS["reserva"]

    # 3. Estabilidade — volatilidade de 0 é ótima, 50%+ zera; mês no vermelho pune.
    vol = float(base.get("volatilidade_despesa", 0) or 0)
    p_estab = _clamp(1 - vol / 0.5) * WEIGHTS["estabilidade"]
    vermelhos = int(base.get("meses_no_vermelho", 0) or 0)
    p_estab *= max(0.0, 1 - 0.25 * vermelhos)

    # 4. Vazamentos — invisível acima de 15% da despesa zera a dimensão.
    invis_mes = (
        Decimal(str(invisible.get("taxas_e_seguros", {}).get("por_mes", 0)))
        + Decimal(str(invisible.get("micro_gastos", {}).get("por_mes", 0)))
    )
    pct_invis = float(invis_mes / despesa) if despesa > 0 else 0.0
    p_vaz = _clamp(1 - pct_invis / 0.15) * WEIGHTS["vazamentos"]

    # 5. Planos — média de aderência; sem plano cadastrado, metade da nota.
    if plan_results:
        aderencias = []
        for r in plan_results:
            nec = r.get("aporte_necessario_mes") or 0
            cap = r.get("capacidade_mensal_real") or 0
            if r.get("status") == "concluido":
                aderencias.append(1.0)
            elif nec <= 0:
                aderencias.append(0.5)
            else:
                aderencias.append(_clamp(cap / nec))
        p_planos = (sum(aderencias) / len(aderencias)) * WEIGHTS["planos"]
    else:
        p_planos = WEIGHTS["planos"] * 0.5

    partes = {
        "poupanca": round(p_poupanca, 1),
        "reserva": round(p_reserva, 1),
        "estabilidade": round(p_estab, 1),
        "vazamentos": round(p_vaz, 1),
        "planos": round(p_planos, 1),
    }
    total = round(sum(partes.values()), 1)

    return {
        "score": total,
        "faixa": _band(total),
        "dimensoes": [
            {
                "nome": k,
                "pontos": partes[k],
                "maximo": WEIGHTS[k],
                "pct": round(partes[k] / WEIGHTS[k] * 100),
            }
            for k in WEIGHTS
        ],
        "indicadores": {
            "taxa_poupanca": round(taxa * 100, 1),
            "meses_de_reserva": round(meses_reserva, 1),
            "volatilidade_despesa": round(vol, 3),
            "gasto_invisivel_mes": float(invis_mes),
            "gasto_invisivel_pct_despesa": round(pct_invis * 100, 1),
            "renda_media_mes": float(renda),
            "despesa_media_mes": float(despesa),
        },
        "proximo_ponto": _next_lever(partes),
    }


def _next_lever(partes: dict[str, float]) -> str:
    gaps = {k: WEIGHTS[k] - v for k, v in partes.items()}
    alvo = max(gaps, key=gaps.get)
    dicas = {
        "poupanca": "aumentar a sobra mensal: o maior ganho de score está em guardar mais do que entra",
        "reserva": "engordar a reserva até cobrir 6 meses de despesa",
        "estabilidade": "reduzir a variação do gasto entre meses — orçamento por categoria",
        "vazamentos": "cortar taxas, seguros e micro-gastos recorrentes",
        "planos": "ajustar prazo ou aporte dos planos para caberem na capacidade real",
    }
    return dicas[alvo]
