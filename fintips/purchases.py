"""Consultor de compras.

Você manda uma intenção ("fone X, R$ 1.800, quero em novembro") e o motor
devolve o que é calculável: impacto no caixa, custo em meses de aporte,
atraso que causa em cada plano, sinais de arrependimento tirados do SEU
histórico e os cenários de estratégia. O Claude escreve a recomendação em
cima disso — mas os números não são opinião.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from .categorize import norm
from .models import Statement, Transaction

Z = Decimal("0")


@dataclass
class PurchaseIntent:
    item: str
    preco: Decimal
    categoria: str = "compras"
    urgencia: str = "media"          # alta | media | baixa
    quando: date | None = None       # quando você quer ter o item
    parcelas_possiveis: int = 1
    juros_parcelamento: float = 0.0  # % ao mês; 0 = sem juros
    substitui: str = ""              # o que essa compra substitui, se substitui
    notas: str = ""
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "PurchaseIntent":
        q = d.get("quando")
        if isinstance(q, str):
            q = date.fromisoformat(q)
        return cls(
            item=d["item"],
            preco=Decimal(str(d["preco"])),
            categoria=d.get("categoria", "compras"),
            urgencia=d.get("urgencia", "media"),
            quando=q,
            parcelas_possiveis=int(d.get("parcelas_possiveis", 1)),
            juros_parcelamento=float(d.get("juros_parcelamento", 0.0)),
            substitui=d.get("substitui", ""),
            notas=d.get("notas", ""),
            tags=list(d.get("tags", []) or []),
        )


def _category_history(stmt: Statement, categoria: str, keywords: Iterable[str] = ()) -> list[Transaction]:
    keys = [norm(k) for k in keywords if k]
    out = []
    for t in stmt.transactions:
        if t.flow != "expense":
            continue
        if t.category == categoria or (keys and any(k in norm(t.counterparty) for k in keys)):
            out.append(t)
    return out


def regret_signals(intent: PurchaseIntent, stmt: Statement, base: dict) -> dict:
    """Sinais de arrependimento — todos derivados do seu próprio histórico."""
    hist = _category_history(stmt, intent.categoria, intent.tags)
    ultimos_60 = [
        t for t in hist if t.day >= (stmt.period_end - timedelta(days=60))
    ]
    grandes_recentes = [t for t in ultimos_60 if abs(t.amount) >= intent.preco * Decimal("0.5")]

    estornos = [
        t for t in stmt.transactions
        if t.flow == "refund" and abs(t.amount) >= Decimal("50")
    ]

    despesa_mes = Decimal(str(base.get("despesa_media_mes", 0) or 0))
    ticket_medio = (
        Decimal(str(statistics.median([float(abs(t.amount)) for t in hist])))
        if hist else Z
    )
    multiplo = float(intent.preco / ticket_medio) if ticket_medio > 0 else None

    sinais: list[str] = []
    if grandes_recentes:
        sinais.append(
            f"{len(grandes_recentes)} compra(s) de porte parecido na mesma categoria nos últimos 60 dias"
        )
    if multiplo and multiplo > 10:
        sinais.append(f"preço é {multiplo:.0f}x o seu ticket típico nessa categoria")
    if despesa_mes > 0 and intent.preco > despesa_mes:
        sinais.append("o item custa mais que um mês inteiro da sua despesa média")
    if intent.urgencia == "alta" and not intent.substitui:
        sinais.append("marcada como urgente sem substituir nada — típico de compra por impulso")
    if len(estornos) >= 3:
        sinais.append(f"{len(estornos)} estornos/devoluções no período (histórico de compra revertida)")

    risco = min(100, 20 * len(sinais))
    return {
        "risco_arrependimento": risco,
        "sinais": sinais,
        "compras_semelhantes_recentes": [
            {"data": t.day.isoformat(), "onde": t.counterparty, "valor": float(abs(t.amount))}
            for t in sorted(grandes_recentes, key=lambda x: x.ts, reverse=True)[:5]
        ],
        "ticket_medio_categoria": float(ticket_medio),
    }


def scenarios(intent: PurchaseIntent, base: dict, saldo_disponivel: Decimal) -> list[dict]:
    sobra = Decimal(str(base.get("sobra_media_mes", 0) or 0))
    out: list[dict] = []

    # 1. À vista agora
    out.append({
        "estrategia": "a_vista_agora",
        "custo_total": float(intent.preco),
        "impacto_caixa_imediato": float(intent.preco),
        "saldo_apos": float(saldo_disponivel - intent.preco),
        "viavel": saldo_disponivel >= intent.preco,
        "observacao": "sem juros; derruba a liquidez imediata",
    })

    # 2. Juntar e comprar depois
    meses = int((intent.preco / sobra).to_integral_value(rounding="ROUND_CEILING")) if sobra > 0 else None
    out.append({
        "estrategia": "juntar_e_comprar",
        "custo_total": float(intent.preco),
        "meses_necessarios": meses,
        "aporte_mensal": float(sobra) if sobra > 0 else 0.0,
        "viavel": meses is not None,
        "observacao": (
            f"no ritmo atual de sobra, o item se paga em {meses} mês(es) sem tocar na reserva"
            if meses else "sobra mensal atual não financia a compra"
        ),
    })

    # 3. Parcelado
    if intent.parcelas_possiveis > 1:
        n = intent.parcelas_possiveis
        i = Decimal(str(intent.juros_parcelamento)) / 100
        if i > 0:
            fator = (i * (1 + i) ** n) / ((1 + i) ** n - 1)
            parcela = (intent.preco * fator).quantize(Decimal("0.01"))
        else:
            parcela = (intent.preco / n).quantize(Decimal("0.01"))
        total = parcela * n
        out.append({
            "estrategia": "parcelado",
            "parcelas": n,
            "valor_parcela": float(parcela),
            "custo_total": float(total),
            "custo_do_credito": float(total - intent.preco),
            "pct_da_sobra_mensal": float(round(parcela / sobra * 100, 1)) if sobra > 0 else None,
            "viavel": sobra > parcela,
            "observacao": "compromete sobra futura; só vale se o dinheiro parado render mais que o juro",
        })
    return out


def plan_impact(intent: PurchaseIntent, plan_results: list[dict], base: dict) -> list[dict]:
    """Quanto essa compra atrasa cada plano ativo."""
    sobra = Decimal(str(base.get("sobra_media_mes", 0) or 0))
    out = []
    for r in plan_results:
        if r.get("status") == "concluido":
            continue
        aporte = Decimal(str(r.get("aporte_necessario_mes") or 0))
        atraso = float(intent.preco / aporte) if aporte > 0 else None
        out.append({
            "plano": r.get("nome"),
            "atraso_em_meses": round(atraso, 1) if atraso else None,
            "folga_apos_compra": float(sobra - aporte) if aporte else float(sobra),
            "conflito": bool(atraso and atraso >= 1 and r.get("status") in ("apertado", "inviavel_no_ritmo_atual")),
        })
    return out


def evaluate(
    intent: PurchaseIntent,
    stmt: Statement,
    base: dict,
    plan_results: list[dict],
    *,
    saldo_conta: Decimal | float = 0,
    reserva_alvo_meses: float = 6.0,
    patrimonio: Decimal | float = 0,
) -> dict:
    saldo = Decimal(str(saldo_conta))
    patr = Decimal(str(patrimonio))
    despesa = Decimal(str(base.get("despesa_media_mes", 0) or 0))
    sobra = Decimal(str(base.get("sobra_media_mes", 0) or 0))

    reserva_alvo = despesa * Decimal(str(reserva_alvo_meses))
    excedente = patr + saldo - reserva_alvo  # o que dá pra gastar sem furar a reserva

    regret = regret_signals(intent, stmt, base)
    cen = scenarios(intent, base, saldo + patr)
    impacto_planos = plan_impact(intent, plan_results, base)

    custo_em_meses = float(intent.preco / sobra) if sobra > 0 else None
    fura_reserva = intent.preco > excedente

    if fura_reserva and (custo_em_meses or 0) > 3:
        veredito = "nao_agora"
    elif regret["risco_arrependimento"] >= 60:
        veredito = "espere_30_dias"
    elif fura_reserva:
        veredito = "juntar_antes"
    elif any(p["conflito"] for p in impacto_planos):
        veredito = "escolha_entre_plano_e_compra"
    elif (custo_em_meses or 0) <= 1:
        veredito = "pode_comprar"
    else:
        veredito = "cabe_com_planejamento"

    prudencia = max(
        0,
        100
        - regret["risco_arrependimento"]
        - (25 if fura_reserva else 0)
        - (15 if any(p["conflito"] for p in impacto_planos) else 0),
    )

    return {
        "item": intent.item,
        "preco": float(intent.preco),
        "veredito": veredito,
        "score_prudencia": prudencia,
        "custo_em_meses_de_sobra": round(custo_em_meses, 2) if custo_em_meses else None,
        "reserva": {
            "alvo_meses": reserva_alvo_meses,
            "alvo_valor": float(reserva_alvo.quantize(Decimal("0.01"))),
            "excedente_disponivel": float(excedente.quantize(Decimal("0.01"))),
            "compra_fura_reserva": fura_reserva,
        },
        "arrependimento": regret,
        "estrategias": cen,
        "impacto_nos_planos": impacto_planos,
        "melhor_estrategia": _best(cen, fura_reserva, regret["risco_arrependimento"]),
    }


def _best(cen: list[dict], fura_reserva: bool, risco: int) -> str:
    viaveis = [c for c in cen if c.get("viavel")]
    if not viaveis:
        return "juntar_e_comprar"
    if risco >= 60:
        return "juntar_e_comprar"      # tempo é o melhor filtro de impulso
    if fura_reserva:
        return "juntar_e_comprar"
    a_vista = next((c for c in viaveis if c["estrategia"] == "a_vista_agora"), None)
    parcelado = next((c for c in viaveis if c["estrategia"] == "parcelado"), None)
    if parcelado and parcelado.get("custo_do_credito", 0) == 0 and a_vista:
        return "parcelado"             # sem juros, mantém liquidez rendendo
    return a_vista["estrategia"] if a_vista else viaveis[0]["estrategia"]
