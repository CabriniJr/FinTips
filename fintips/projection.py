"""Projeção de caixa.

Separar custo fixo de variável só vale a pena se alguém usar a separação. É
aqui: o fixo é repetido como compromisso, o variável entra como média com
folga, os planos consomem a sobra na ordem da prioridade, e cada meta ganha uma
data provável de conclusão — que é a pergunta que o usuário realmente faz.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

Z = Decimal("0")

CENARIOS = {
    "base": {"renda": 1.00, "variavel": 1.00},
    "conservador": {"renda": 0.90, "variavel": 1.15},
    "otimista": {"renda": 1.05, "variavel": 0.90},
}


def _add_months(d: date, n: int) -> date:
    y, m = divmod((d.year * 12 + d.month - 1) + n, 12)
    return date(y, m + 1, 1)


@dataclass
class PlanTrack:
    id: str
    nome: str
    falta: Decimal
    prioridade: str
    aporte: Decimal
    concluido_em: str | None = None


def project(
    *,
    baseline: dict,
    fixed_monthly: Decimal | float,
    saldo_conta: Decimal | float,
    patrimonio: Decimal | float,
    planos: list[dict],
    meses: int = 12,
    cenario: str = "base",
    inicio: date | None = None,
) -> dict:
    fator = CENARIOS.get(cenario, CENARIOS["base"])
    renda = Decimal(str(baseline.get("renda_media_mes", 0))) * Decimal(str(fator["renda"]))
    despesa_total = Decimal(str(baseline.get("despesa_media_mes", 0)))
    fixo = Decimal(str(fixed_monthly))
    variavel = max(despesa_total - fixo, Z) * Decimal(str(fator["variavel"]))

    inicio = inicio or date.today()
    caixa = Decimal(str(saldo_conta))
    guardado = Decimal(str(patrimonio)) - caixa

    tracks = [
        PlanTrack(
            id=p["id"],
            nome=p["nome"],
            falta=Decimal(str(p.get("falta", 0))),
            prioridade=p.get("prioridade", "media"),
            aporte=Decimal(str(p.get("aporte_planejado_mes") or p.get("aporte_necessario_mes") or 0)),
        )
        for p in planos
        if p.get("status") != "concluido"
    ]
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    tracks.sort(key=lambda t: ordem.get(t.prioridade, 1))

    linhas = []
    for i in range(meses):
        mes = _add_months(inicio, i)
        sobra = renda - fixo - variavel
        destinado = Z
        for t in tracks:
            if t.falta <= 0:
                continue
            disponivel = max(sobra - destinado, Z)
            aporte = min(t.aporte if t.aporte > 0 else disponivel, disponivel, t.falta)
            if aporte <= 0:
                continue
            t.falta -= aporte
            destinado += aporte
            if t.falta <= 0 and not t.concluido_em:
                t.concluido_em = mes.strftime("%Y-%m")

        livre = sobra - destinado
        guardado += destinado + max(livre, Z)
        caixa += min(livre, Z)  # só um mês negativo mexe no caixa
        linhas.append(
            {
                "mes": mes.strftime("%Y-%m"),
                "renda": float(renda.quantize(Decimal("0.01"))),
                "custo_fixo": float(fixo.quantize(Decimal("0.01"))),
                "custo_variavel": float(variavel.quantize(Decimal("0.01"))),
                "sobra": float(sobra.quantize(Decimal("0.01"))),
                "aportes_em_planos": float(destinado.quantize(Decimal("0.01"))),
                "patrimonio_projetado": float((guardado + caixa).quantize(Decimal("0.01"))),
            }
        )

    reserva_alvo = (fixo + variavel) * Decimal(str(baseline.get("reserva_alvo_meses", 6)))
    mes_reserva = next(
        (l["mes"] for l in linhas if Decimal(str(l["patrimonio_projetado"])) >= reserva_alvo),
        None,
    )

    return {
        "cenario": cenario,
        "premissas": {
            "renda_mensal": float(renda.quantize(Decimal("0.01"))),
            "custo_fixo": float(fixo.quantize(Decimal("0.01"))),
            "custo_variavel": float(variavel.quantize(Decimal("0.01"))),
            "sobra_mensal": float((renda - fixo - variavel).quantize(Decimal("0.01"))),
            "fixo_pct_da_renda": round(float(fixo / renda * 100), 1) if renda else 0.0,
        },
        "linhas": linhas,
        "planos": [
            {
                "id": t.id,
                "nome": t.nome,
                "falta_ao_fim": float(max(t.falta, Z)),
                "conclui_em": t.concluido_em,
            }
            for t in tracks
        ],
        "reserva": {
            "alvo": float(reserva_alvo.quantize(Decimal("0.01"))),
            "atingida_em": mes_reserva,
        },
    }


def all_scenarios(**kwargs) -> dict:
    kwargs.pop("cenario", None)
    return {nome: project(cenario=nome, **kwargs) for nome in CENARIOS}
