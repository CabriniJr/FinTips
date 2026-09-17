"""Alavancas: o que muda o número, e quanto.

Esta é a parte do motor que mais facilmente trairia o projeto inteiro, então
vale dizer o que ela **não** faz: não escreve dica, não recomenda corte, não
chama gasto de desnecessário. "Cortar streaming" é conselho; "assinaturas somam
R$ 78/mês, e tirar isso do variável antecipa a reserva em 2 meses" é conta.

Cada alavanca carrega:

- um **número**, na unidade em que ele existe (reais por mês, pontos de score);
- um **efeito**, que é o motor rodado de novo com aquela mudança — score
  recalculado pela mesma `score.compute`, projeção recalculada pela mesma
  `projection.project`. Nada de estimativa paralela;
- a **evidência**, com os números de origem, para a conta ser conferível.

A frase que amarra tudo isso — "você está pagando caro por conveniência" ou
"dá para viver com menos" — é do agente, que conversou com a pessoa. O motor
entrega a régua; quem interpreta tem contexto que nenhuma régua tem.
"""

from __future__ import annotations

import copy
from decimal import Decimal
from typing import Any

from . import projection, score as score_mod

Z = Decimal("0")

# Alvos das dimensões de score, os mesmos que `score.compute` usa para dar nota
# cheia. Ficam aqui explícitos porque a alavanca é justamente a distância até eles.
ALVO_TAXA_POUPANCA = 0.40
ALVO_MESES_RESERVA = 6.0
TETO_INVISIVEL_PCT = 0.15
ALVO_VOLATILIDADE = 0.20


def calcular(ctx: dict) -> dict:
    """Todas as alavancas do contexto atual, ordenadas por reais por mês.

    A ordenação é por dinheiro porque é a única unidade comparável entre
    alavancas de natureza diferente. Alavanca sem valor monetário direto
    (estabilidade, por exemplo) fica com `ordenacao: 0` e vai para o fim — o
    que não significa que importe menos, só que o motor não sabe convertê-la.
    """
    alavancas: list[dict] = []
    alavancas += _de_score(ctx)
    alavancas += _de_triagem(ctx)
    alavancas += _de_corte(ctx)
    alavancas += _de_planos(ctx)

    alavancas.sort(key=lambda a: a["ordenacao"], reverse=True)
    return {
        "alavancas": alavancas,
        "total": len(alavancas),
        "explicacao": (
            "cada alavanca é um número e o motor rodado de novo com ele. "
            "A leitura do que vale a pena é do agente, não do app"
        ),
        "ordenado_por": "impacto mensal em reais",
    }


# --------------------------------------------------------------------------
# score: quanto falta em cada dimensão, e quantos pontos isso vale
# --------------------------------------------------------------------------
def _de_score(ctx: dict) -> list[dict]:
    base = ctx.get("baseline") or {}
    sc = ctx.get("score") or {}
    invis = ctx.get("gastos_invisiveis") or {}
    planos = ctx.get("planos") or []
    patrimonio = float((ctx.get("patrimonio") or {}).get("total", 0) or 0)
    atual = float(sc.get("score", 0) or 0)

    renda = float(base.get("renda_media_mes", 0) or 0)
    despesa = float(base.get("despesa_media_mes", 0) or 0)
    taxa = float(base.get("taxa_poupanca_media", 0) or 0)
    out: list[dict] = []

    def _recalcula(nova_base=None, novo_invis=None, novo_patrimonio=None) -> float:
        r = score_mod.compute(
            nova_base or base,
            novo_invis or invis,
            planos,
            patrimonio_liquido=novo_patrimonio if novo_patrimonio is not None else patrimonio,
        )
        return float(r["score"])

    # -------- poupança: subir a sobra até a taxa de nota cheia
    if renda > 0 and taxa < ALVO_TAXA_POUPANCA:
        falta_mes = round((ALVO_TAXA_POUPANCA - taxa) * renda, 2)
        nova = dict(base, taxa_poupanca_media=ALVO_TAXA_POUPANCA,
                    despesa_media_mes=max(renda * (1 - ALVO_TAXA_POUPANCA), 0),
                    sobra_media_mes=renda * ALVO_TAXA_POUPANCA)
        depois = _recalcula(nova_base=nova)
        out.append(_alavanca(
            id="score-poupanca",
            tipo="score",
            alvo="poupanca",
            titulo="Sobra mensal que falta para a nota cheia de poupança",
            numero=falta_mes,
            unidade="BRL/mes",
            efeito={
                "taxa_poupanca_agora": round(taxa * 100, 1),
                "taxa_poupanca_alvo": round(ALVO_TAXA_POUPANCA * 100, 1),
                "score_agora": atual,
                "score_depois": depois,
                "ganho_de_score": round(depois - atual, 1),
            },
            evidencia=[
                f"renda média {renda:.2f}/mês",
                f"despesa média {despesa:.2f}/mês",
                f"taxa de poupança observada {taxa * 100:.1f}%",
            ],
            ordenacao=falta_mes,
        ))

    # -------- reserva: quanto falta guardar para cobrir os meses-alvo
    alvo_meses = float(base.get("reserva_alvo_meses", ALVO_MESES_RESERVA) or ALVO_MESES_RESERVA)
    if despesa > 0:
        alvo_valor = despesa * alvo_meses
        falta = round(max(alvo_valor - patrimonio, 0), 2)
        if falta > 0:
            depois = _recalcula(novo_patrimonio=alvo_valor)
            sobra = float(base.get("sobra_media_mes", 0) or 0)
            out.append(_alavanca(
                id="score-reserva",
                tipo="score",
                alvo="reserva",
                titulo="Valor que falta para a reserva cobrir os meses-alvo",
                numero=falta,
                unidade="BRL",
                efeito={
                    "meses_de_reserva_agora": round(patrimonio / despesa, 1),
                    "meses_de_reserva_alvo": alvo_meses,
                    "meses_no_ritmo_atual": round(falta / sobra, 1) if sobra > 0 else None,
                    "score_agora": atual,
                    "score_depois": depois,
                    "ganho_de_score": round(depois - atual, 1),
                },
                evidencia=[
                    f"patrimônio {patrimonio:.2f}",
                    f"despesa média {despesa:.2f}/mês",
                    f"alvo de {alvo_meses:g} meses = {alvo_valor:.2f}",
                ],
                # o que entra na fila é o esforço mensal, não o total
                ordenacao=round(falta / 12, 2),
            ))

    # -------- vazamentos: o excedente de gasto invisível sobre o teto
    invis_mes = (
        float((invis.get("taxas_e_seguros") or {}).get("por_mes", 0) or 0)
        + float((invis.get("micro_gastos") or {}).get("por_mes", 0) or 0)
    )
    if despesa > 0 and invis_mes > despesa * TETO_INVISIVEL_PCT:
        excedente = round(invis_mes - despesa * TETO_INVISIVEL_PCT, 2)
        novo_invis = copy.deepcopy(invis)
        alvo_mes = despesa * TETO_INVISIVEL_PCT
        fator = alvo_mes / invis_mes if invis_mes else 0
        for chave in ("taxas_e_seguros", "micro_gastos"):
            if chave in novo_invis:
                novo_invis[chave] = dict(
                    novo_invis[chave],
                    por_mes=round(float(novo_invis[chave].get("por_mes", 0) or 0) * fator, 2),
                )
        depois = _recalcula(novo_invis=novo_invis)
        out.append(_alavanca(
            id="score-vazamentos",
            tipo="score",
            alvo="vazamentos",
            titulo="Gasto invisível acima do teto de 15% da despesa",
            numero=excedente,
            unidade="BRL/mes",
            efeito={
                "invisivel_agora": round(invis_mes, 2),
                "teto": round(alvo_mes, 2),
                "score_agora": atual,
                "score_depois": depois,
                "ganho_de_score": round(depois - atual, 1),
            },
            evidencia=[
                f"taxas e seguros {(invis.get('taxas_e_seguros') or {}).get('por_mes', 0)}/mês",
                f"micro-gastos {(invis.get('micro_gastos') or {}).get('por_mes', 0)}/mês",
                f"despesa média {despesa:.2f}/mês",
            ],
            ordenacao=excedente,
        ))

    # -------- estabilidade: sem tradução em reais, e o motor diz isso
    vol = float(base.get("volatilidade_despesa", 0) or 0)
    if vol > ALVO_VOLATILIDADE:
        nova = dict(base, volatilidade_despesa=ALVO_VOLATILIDADE, meses_no_vermelho=0)
        depois = _recalcula(nova_base=nova)
        out.append(_alavanca(
            id="score-estabilidade",
            tipo="score",
            alvo="estabilidade",
            titulo="Variação do gasto mensal acima da faixa de nota cheia",
            numero=round(vol - ALVO_VOLATILIDADE, 3),
            unidade="coeficiente",
            efeito={
                "volatilidade_agora": vol,
                "volatilidade_alvo": ALVO_VOLATILIDADE,
                "meses_no_vermelho": int(base.get("meses_no_vermelho", 0) or 0),
                "score_agora": atual,
                "score_depois": depois,
                "ganho_de_score": round(depois - atual, 1),
                "conversao_em_reais": (
                    "não existe: volatilidade é dispersão entre meses, não um valor a cortar"
                ),
            },
            evidencia=[
                f"volatilidade observada {vol}",
                f"meses considerados: {', '.join(base.get('meses_considerados') or [])}",
            ],
            ordenacao=0.0,
        ))

    return out


# --------------------------------------------------------------------------
# triagem: o custo mensal de deixar uma decisão em aberto
# --------------------------------------------------------------------------
def _de_triagem(ctx: dict) -> list[dict]:
    itens = ((ctx.get("triagem") or {}).get("itens")) or []
    despesa = float((ctx.get("baseline") or {}).get("despesa_media_mes", 0) or 0)
    out = []
    for item in itens:
        if item.get("estado") != "aberto":
            continue
        impacto = abs(float(item.get("impacto_mensal", 0) or 0))
        if impacto <= 0:
            continue
        out.append(_alavanca(
            id=f"triagem-{item['id']}",
            tipo="triagem",
            alvo=item.get("tipo", ""),
            titulo=item.get("titulo", ""),
            numero=round(impacto, 2),
            unidade="BRL/mes",
            efeito={
                "custo_anual_de_nao_decidir": round(impacto * 12, 2),
                "pct_da_despesa": round(impacto / despesa * 100, 1) if despesa else None,
                "o_que_muda": item.get("porque_importa", ""),
            },
            evidencia=[f"{k}: {v}" for k, v in (item.get("evidencia") or {}).items()] or [
                f"item de triagem {item['id']}"
            ],
            ordenacao=round(impacto, 2),
        ))
    return out[:10]


# --------------------------------------------------------------------------
# corte: o efeito de tirar N reais do variável, medido na projeção
# --------------------------------------------------------------------------
def _de_corte(ctx: dict) -> list[dict]:
    """Não escolhe o que cortar — mede o que um corte faria.

    O valor testado não é arbitrário: é o gasto invisível mensal, que já é o
    dinheiro que sai sem decisão consciente. Se não houver, não há alavanca.
    """
    invis = ctx.get("gastos_invisiveis") or {}
    corte = round(
        float((invis.get("taxas_e_seguros") or {}).get("por_mes", 0) or 0)
        + float((invis.get("micro_gastos") or {}).get("por_mes", 0) or 0),
        2,
    )
    if corte <= 0:
        return []

    proj_agora = ctx.get("projecao") or {}
    antes = (proj_agora.get("reserva") or {}).get("atingida_em")

    base = dict(ctx.get("baseline") or {})
    despesa = float(base.get("despesa_media_mes", 0) or 0)
    if despesa <= corte:
        return []
    renda = float(base.get("renda_media_mes", 0) or 0)
    base["despesa_media_mes"] = despesa - corte
    base["sobra_media_mes"] = float(base.get("sobra_media_mes", 0) or 0) + corte
    if renda:
        base["taxa_poupanca_media"] = round((renda - base["despesa_media_mes"]) / renda, 4)

    depois_proj = projection.project(
        baseline=base,
        fixed_monthly=Decimal(str((ctx.get("estrutura_de_custo") or {}).get("comprometido_mes", 0) or 0)),
        saldo_conta=Decimal(str(ctx.get("saldo_conta", 0) or 0)),
        patrimonio=Decimal(str((ctx.get("patrimonio") or {}).get("total", 0) or 0)),
        planos=ctx.get("planos") or [],
        meses=len(proj_agora.get("linhas") or []) or 12,
    )
    depois = (depois_proj.get("reserva") or {}).get("atingida_em")

    return [_alavanca(
        id="corte-invisivel",
        tipo="projecao",
        alvo="reserva",
        titulo="Efeito na projeção de tirar o gasto invisível do variável",
        numero=corte,
        unidade="BRL/mes",
        efeito={
            "reserva_fecha_agora_em": antes,
            "reserva_fecha_depois_em": depois,
            "meses_antecipados": _meses_entre(depois, antes),
            "sobra_depois": round(float(base.get("sobra_media_mes", 0) or 0), 2),
            "acumulado_em_12_meses": round(corte * 12, 2),
        },
        evidencia=[
            f"gasto invisível {corte:.2f}/mês",
            f"despesa média {despesa:.2f}/mês",
            "mesma projection.project que a aba de previsões usa",
        ],
        ordenacao=corte,
    )]


# --------------------------------------------------------------------------
# planos: o efeito de mudar a ordem de prioridade
# --------------------------------------------------------------------------
def _de_planos(ctx: dict) -> list[dict]:
    """Prioridade é alavanca: a mesma sobra fecha metas diferentes primeiro."""
    planos = [p for p in (ctx.get("planos") or []) if p.get("status") != "concluido"]
    if len(planos) < 2:
        return []

    proj_agora = ctx.get("projecao") or {}
    quando_agora = {p["id"]: p.get("conclui_em") for p in (proj_agora.get("planos") or [])}
    meses = len(proj_agora.get("linhas") or []) or 12
    comum = dict(
        baseline=ctx.get("baseline") or {},
        fixed_monthly=Decimal(str((ctx.get("estrutura_de_custo") or {}).get("comprometido_mes", 0) or 0)),
        saldo_conta=Decimal(str(ctx.get("saldo_conta", 0) or 0)),
        patrimonio=Decimal(str((ctx.get("patrimonio") or {}).get("total", 0) or 0)),
        meses=meses,
    )

    out = []
    for p in planos:
        if quando_agora.get(p["id"]):
            continue  # já fecha dentro da janela; priorizar não é a pergunta
        priorizado = [
            dict(q, prioridade="alta" if q["id"] == p["id"] else "baixa") for q in planos
        ]
        proj = projection.project(planos=priorizado, **comum)
        depois = next(
            (t.get("conclui_em") for t in proj.get("planos") or [] if t["id"] == p["id"]), None
        )
        if not depois:
            continue
        out.append(_alavanca(
            id=f"plano-{p['id']}",
            tipo="plano",
            alvo=p["id"],
            titulo=f"Efeito de priorizar o plano {p.get('nome', p['id'])}",
            numero=round(float(p.get("aporte_necessario_mes") or 0), 2),
            unidade="BRL/mes",
            efeito={
                "conclui_em_agora": quando_agora.get(p["id"]),
                "conclui_em_priorizado": depois,
                "falta": round(float(p.get("falta", 0) or 0), 2),
                "custo": "as outras metas da fila atrasam na mesma proporção",
            },
            evidencia=[
                f"prioridade atual: {p.get('prioridade', 'media')}",
                f"falta {float(p.get('falta', 0) or 0):.2f}",
                f"janela da projeção: {meses} meses",
            ],
            ordenacao=round(float(p.get("aporte_necessario_mes") or 0), 2),
        ))
    return out


# --------------------------------------------------------------------------
def _alavanca(**kw: Any) -> dict:
    """Forma única de alavanca. `origem` é sempre `importacao`: derivado dos
    seus dados, portanto ainda não é verdade sobre nada."""
    kw.setdefault("origem", "importacao")
    return kw


def _meses_entre(depois: str | None, antes: str | None) -> int | None:
    """Quantos meses um marco foi antecipado. None quando falta uma das pontas."""
    if not depois or not antes:
        return None
    try:
        ay, am = (int(x) for x in antes.split("-"))
        dy, dm = (int(x) for x in depois.split("-"))
    except ValueError:
        return None
    return (ay * 12 + am) - (dy * 12 + dm)
