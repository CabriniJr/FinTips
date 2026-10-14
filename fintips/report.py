"""Monta o contexto único que alimenta o painel, o agente e a triagem.

Ordem de montagem (importa, e é sempre esta):

1. parser            → transações cruas
2. heurística        → palpite do pacote, marcado como palpite
3. regras            → o que o agente/usuário decidiu, sobrescreve o palpite
4. entidades         → contrapartes agrupadas, cadência
5. compromissos      → custo fixo DEFINIDO (o detectado vira candidato)
6. análise           → baseline, mês a mês, invisível, score, planos, projeção
7. triagem           → o que ainda está em aberto, ordenado por impacto

Nenhuma métrica é recalculada em outro lugar. Se o número muda, muda para as
três interfaces ao mesmo tempo.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from . import analysis, causes as causes_mod, commitments, decisions, discovery, mapping
from . import plans as plans_mod
from . import profile as profile_mod, projection
from . import score as score_mod, taxonomy as tax_mod, triage
from .categorize import Categorizer
from .context import ContextStore
from .entities import build_counterparties
from .models import Statement
from .parsers.ofx import parse_ofx
from .workspace import Workspace

Z = Decimal("0")
CONTEXT_SCHEMA = 3


# --------------------------------------------------------------------------
# lojas
# --------------------------------------------------------------------------

def stores(ws: Workspace) -> dict[str, Any]:
    """Abre todas as lojas do workspace de uma vez."""
    tax = tax_mod.Taxonomy(ws.taxonomia_path)
    if len(tax.categorias) <= 1:
        # partida a frio: adota as sugestões do pacote marcadas como heurística,
        # para o motor ter onde pousar. A triagem vai pedir revisão delas.
        tax.adotar_sugestoes()
    return {
        "taxonomia": tax,
        "regras": mapping.RuleStore(ws.regras_path),
        "contexto": ContextStore(ws.contexto_path),
        "compromissos": commitments.CommitmentStore(ws.custos_fixos_path),
        "triagem": triage.TriageStore(ws.triagem_path),
        "perfil": profile_mod.PerfilStore(ws.perfil_path),
        "causas": causes_mod.CauseStore(ws.causas_path),
        "decisoes": decisions.DecisionStore(ws.decisoes_path),
    }


# --------------------------------------------------------------------------
# entrada
# --------------------------------------------------------------------------

def categorizer_for(ws: Workspace) -> Categorizer:
    cfg = ws.config
    return Categorizer(
        aliases=cfg.get("apelidos") or {},
        my_names=cfg.get("meus_nomes") or [],
        salt=ws.salt,
        local_rules_path=ws.regras_locais_path,
    )


def load_statement(ws: Workspace, st: dict | None = None) -> Statement:
    """Reprocessa o OFX mais recente. O YAML canônico é saída, não entrada."""
    files = sorted(ws.extratos.glob("*.ofx"))
    if not files:
        raise FileNotFoundError("nenhum extrato em data/extratos")
    st = st or stores(ws)
    stmt = parse_ofx(files[-1], salt=ws.salt)
    categorizer_for(ws).apply_all(stmt.transactions)      # piso: heurística
    mapping.aplicar(st["regras"], stmt)                   # decisões vencem o piso
    return stmt


def enrich(ws: Workspace, stmt: Statement, st: dict | None = None) -> list:
    """Entidades + confirmações antigas (v0.2), aplicadas antes dos agregados."""
    total_months = len({t.month for t in stmt.transactions}) or 1
    confirmations = discovery.load_confirmations(ws.contrapartes_path)
    cps = build_counterparties(stmt.transactions, total_months)
    discovery.apply_confirmations(cps, confirmations)
    discovery.apply_to_transactions(stmt, cps)
    cps = build_counterparties(stmt.transactions, total_months)
    return discovery.apply_confirmations(cps, confirmations)


def ingest(ws: Workspace, ofx_path: str | Path) -> tuple[Statement, Path]:
    cfg = ws.config
    st = stores(ws)
    stmt = parse_ofx(ofx_path, salt=ws.salt)
    categorizer_for(ws).apply_all(stmt.transactions)
    mapping.aplicar(st["regras"], stmt)
    enrich(ws, stmt, st)

    name = f"{stmt.period_start:%Y%m%d}-{stmt.period_end:%Y%m%d}.yaml"
    out = ws.canonico / name
    out.write_text(
        yaml.safe_dump(
            stmt.to_yaml_dict(include_raw=bool(cfg.get("incluir_memo_bruto"))),
            allow_unicode=True, sort_keys=False,
        ),
        encoding="utf-8",
    )
    # toda importação abre uma sessão de triagem
    ctx = analyze(ws, stmt, st)
    st["triagem"].abrir_sessao("importacao", ctx["triagem"]["resumo"]["abertos"])
    return stmt, out


# --------------------------------------------------------------------------
# contexto
# --------------------------------------------------------------------------

def analyze(ws: Workspace, stmt: Statement | None = None, st: dict | None = None) -> dict[str, Any]:
    st = st or stores(ws)
    stmt = stmt if stmt is not None else load_statement(ws, st)
    cps = enrich(ws, stmt, st)

    tax = st["taxonomia"]
    regras = st["regras"]
    contexto = st["contexto"]
    compromissos = st["compromissos"]

    base = analysis.baseline(stmt)
    months = analysis.monthly(stmt)
    month_keys = [m.month for m in months]
    meses_completos = base.get("meses_considerados") or month_keys
    outs = analysis.outliers(stmt)

    # custo fixo: o que está DEFINIDO manda; o detectado é só candidato
    definidos = compromissos.to_dicts()
    cats_cobertas, cps_cobertas = compromissos.coberturas()
    candidatos = []
    for f in discovery.detect_fixed_costs(stmt, cps, months=meses_completos):
        if f.key in cats_cobertas or f.key in cps_cobertas:
            continue
        d = f.to_dict()
        d["origem"] = "heuristica"
        d["aviso"] = "candidato detectado pelo padrão — ainda não é compromisso"
        candidatos.append(d)

    fixo_mes = Decimal(str(compromissos.total_mensal()))

    # gasto invisível ignora o que virou compromisso: transporte de trabalho não
    # é desperdício por ser pulverizado em recargas pequenas
    invis = analysis.invisible_spending(
        stmt, ignorar_categorias=cats_cobertas, ignorar_contrapartes=cps_cobertas
    )

    patr = ws.load_patrimonio()
    total_guardado = Decimal(str(patr.get("total", 0)))
    plan_list = plans_mod.load_plans(ws.planos_path)
    plan_results = plans_mod.evaluate_all(plan_list, stmt, base)

    reserva_alvo = contexto.valor("reserva.alvo_meses", ws.config.get("reserva_alvo_meses", 6))
    sc = score_mod.compute(base, invis, plan_results, patrimonio_liquido=total_guardado)

    despesa = Decimal(str(base.get("despesa_media_mes", 0)))
    por_natureza = compromissos.por_natureza()
    variavel = max(despesa - fixo_mes, Z)
    por_categoria = _by_category(stmt)

    ok, diff = stmt.reconciles()
    ctx: dict[str, Any] = {
        "schema_version": CONTEXT_SCHEMA,
        "periodo": {
            "inicio": stmt.period_start.isoformat(),
            "fim": stmt.period_end.isoformat(),
            "transacoes": len(stmt.transactions),
            "despesas": sum(1 for t in stmt.transactions if t.flow == "expense"),
        },
        "conciliacao": {"bate": ok, "diferenca": float(diff)},
        "saldo_conta": float(stmt.ledger_balance),
        "patrimonio": patr,
        "baseline": {**base, "reserva_alvo_meses": reserva_alvo},
        "score": sc,
        "meses": [
            {
                "mes": m.month,
                "renda": float(m.income),
                "despesa": float(m.expense),
                "aportes": float(m.savings_out),
                "resgates": float(m.savings_in),
                "estornos": float(m.refunds),
                "transferencias_liq": float(m.transfers_net),
                "sobra": float(m.net),
                "taxa_poupanca": m.savings_rate,
                "por_categoria": {k: float(v) for k, v in sorted(
                    m.by_category.items(), key=lambda kv: kv[1], reverse=True
                )},
            }
            for m in months
        ],
        "por_categoria_total": por_categoria,
        "taxonomia": tax.uso(por_categoria),
        "categorias_nao_revisadas": [c.to_dict() for c in tax.nao_revisadas()],
        "contrapartes": [c.to_dict() for c in cps],
        "regras": regras.to_dicts(),
        "cobertura_da_classificacao": mapping.cobertura(stmt),
        "custos_fixos": definidos,
        "candidatos_custo_fixo": candidatos,
        "estrutura_de_custo": {
            "por_natureza": por_natureza,
            "comprometido_mes": float(fixo_mes),
            "variavel_mes": float(variavel.quantize(Decimal("0.01"))),
            "despesa_mes": float(despesa),
            "comprometido_pct_despesa": round(float(fixo_mes / despesa * 100), 1) if despesa else 0.0,
            "comprometido_pct_renda": round(
                float(fixo_mes / Decimal(str(base["renda_media_mes"])) * 100), 1
            ) if base.get("renda_media_mes") else 0.0,
            "explicacao": (
                "só entra aqui o que foi DEFINIDO como compromisso. O que o motor "
                "apenas suspeita aparece em candidatos_custo_fixo e vai para a triagem"
            ),
        },
        "gastos_invisiveis": invis,
        "eventos_atipicos": [
            {
                "data": t.day.isoformat(),
                "onde": t.counterparty,
                "valor": float(t.amount),
                "fluxo": t.flow,
                "categoria": t.category,
            }
            for t in outs[:15]
        ],
        "planos": plan_results,
        "contexto": contexto.resumo(),
    }

    # o perfil lê o contexto já montado: sugestão por número + o que foi assinado
    ctx["perfil"] = profile_mod.montar(ctx, st["perfil"])

    ctx["causas"] = {
        "cobertura": st["causas"].cobertura(stmt),
        "itens": st["causas"].to_dicts(),
        "por_alvo": st["causas"].por_alvo(),
    }

    # decisões: o histórico não entra inteiro na análise — o que interessa aqui
    # é o que está em aberto e o que já se aprendeu. O detalhe sai por
    # `historico_de_decisoes`, que é onde ele é útil.
    ctx["decisoes"] = {
        "aprendizados": st["decisoes"].aprendizados(),
        "linha_do_tempo": st["decisoes"].linha_do_tempo()[:12],
        "abertas": [d.to_dict() for d in st["decisoes"].abertas()],
    }

    ctx["projecao"] = projection.project(
        baseline=ctx["baseline"],
        fixed_monthly=fixo_mes,
        saldo_conta=stmt.ledger_balance,
        patrimonio=total_guardado,
        planos=plan_results,
        meses=12,
    )

    itens = triage.construir(
        stmt, cps,
        base=base,
        ctx_store=contexto,
        custos_fixos=definidos,
        candidatos_fixos=candidatos,
        store=st["triagem"],
        causas=st["causas"],
        decisoes=st["decisoes"],
        fallback=tax_mod.FALLBACK,
    )
    ctx["triagem"] = {
        "resumo": triage.resumo(itens),
        "itens": [i.to_dict() for i in itens],
        "ultima_sessao": st["triagem"].sessoes[-1] if st["triagem"].sessoes else None,
    }
    return ctx


def _by_category(stmt: Statement) -> dict[str, float]:
    acc: dict[str, Decimal] = {}
    for t in stmt.transactions:
        if t.flow != "expense":
            continue
        acc[t.category] = acc.get(t.category, Z) + abs(t.amount)
    return {k: float(v) for k, v in sorted(acc.items(), key=lambda kv: kv[1], reverse=True)}


def save_report(ws: Workspace, data: dict, name: str = "analise.yaml") -> Path:
    out = ws.relatorios / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return out


# --------------------------------------------------------------------------
# a análise vista pelo agente
# --------------------------------------------------------------------------

# Blocos que o contexto completo carrega inteiros e que o agente quase nunca
# usa inteiros: cada um tem ferramenta própria que devolve o detalhe. O valor
# é o nome dessa ferramenta — nenhum bloco sai daqui sem dizer por onde voltar.
DETALHE_EM = {
    "perfil": "perfil",
    "taxonomia": "listar_taxonomia",
    "categorias_nao_revisadas": "listar_taxonomia",
    "contrapartes": "investigar",
    "triagem": "triagem",
    "projecao": "projecao",
    "causas": "listar_causas",
    "decisoes": "listar_decisoes",
    "regras": "listar_regras",
}


def para_agente(ctx: dict[str, Any], *, topo: int = 8) -> dict[str, Any]:
    """O contexto único, cortado para caber numa conversa.

    `analyze()` continua devolvendo tudo — é a fonte única, e o painel, o CLI e
    o relatório em disco dependem disso. O corte acontece só na fronteira do
    agente, e por um motivo prático: a análise de um fixture de nove transações
    já passa de 12 mil tokens, e cresce com o extrato. O agente gastava a
    janela inteira antes da primeira pergunta, recebendo por precaução catálogo
    de arquétipo, taxonomia com proveniência e projeção mês a mês.

    A regra aqui é a mesma do dossiê: **resumo com ponteiro, nunca resumo que
    esconde**. Todo bloco cortado diz quantos itens existem e qual ferramenta
    devolve o resto. Um agente que recebe "12 contrapartes" e o nome da
    ferramenta busca o detalhe quando precisa; um que recebe as três maiores
    sem saber que existem doze passa a supor — e supor é exatamente o que este
    projeto existe para não fazer.
    """
    out = {k: v for k, v in ctx.items() if k not in DETALHE_EM}

    out["perfil"] = _perfil_curto(ctx.get("perfil") or {})
    out["taxonomia"] = _taxonomia_curta(ctx.get("taxonomia") or [])
    out["contrapartes"] = _contrapartes_curtas(ctx.get("contrapartes") or [], topo)
    out["triagem"] = _triagem_curta(ctx.get("triagem") or {}, topo)
    out["projecao"] = _projecao_curta(ctx.get("projecao") or {})
    out["causas"] = _causas_curtas(ctx.get("causas") or {})
    out["decisoes"] = _decisoes_curtas(ctx.get("decisoes") or {})

    nao_revisadas = ctx.get("categorias_nao_revisadas") or []
    out["categorias_nao_revisadas"] = {
        "quantas": len(nao_revisadas),
        "ids": [c["id"] for c in nao_revisadas],
        "detalhe_em": DETALHE_EM["categorias_nao_revisadas"],
    }

    regras = ctx.get("regras") or []
    out["regras"] = {"quantas": len(regras), "detalhe_em": DETALHE_EM["regras"]}

    out["como_ler"] = (
        "resumo com ponteiro: cada bloco cortado traz `quantas` e `detalhe_em` "
        "com a ferramenta que devolve o resto. Se a resposta depender do que "
        "não está aqui, chame a ferramenta — não suponha"
    )
    return out


def _perfil_curto(perfil: dict) -> dict:
    """Os cinco eixos sem o catálogo: o que foi assinado, e o que é palpite."""
    eixos = []
    for e in perfil.get("eixos") or []:
        assinado, sugerido = e.get("assinado"), e.get("sugerido")
        eixos.append({
            "eixo": e.get("eixo"),
            "assinado": (
                {"arquetipo": assinado["nome"],
                 "porque": assinado["proveniencia"]["porque"]}
                if assinado else None
            ),
            # a evidência do palpite fica de fora de propósito: ela é longa e
            # serve para conversar sobre o eixo, que é o que `perfil` faz
            "sugerido": (
                {"arquetipo": sugerido["nome"], "aderencia": sugerido["aderencia"]}
                if sugerido else None
            ),
        })
    return {
        "cobertura": perfil.get("cobertura"),
        "eixos": eixos,
        "divergencias": perfil.get("divergencias"),
        "detalhe_em": DETALHE_EM["perfil"],
    }


def _taxonomia_curta(taxonomia: list[dict]) -> dict:
    """Só o que tem dinheiro em cima. Categoria sem uso não muda resposta."""
    em_uso = [
        {"id": c["id"], "nome": c["nome"], "total_no_periodo": c.get("total_no_periodo")}
        for c in taxonomia if c.get("em_uso")
    ]
    em_uso.sort(key=lambda c: abs(c["total_no_periodo"] or 0), reverse=True)
    return {
        "quantas": len(taxonomia),
        "em_uso": em_uso,
        "detalhe_em": DETALHE_EM["taxonomia"],
    }


def _contrapartes_curtas(cps: list[dict], topo: int) -> dict:
    maiores = sorted(cps, key=lambda c: abs(c.get("custo_mensal") or 0), reverse=True)
    return {
        "quantas": len(cps),
        "maiores": [
            {"id": c["id"], "nome": c["nome"], "categoria": c.get("categoria"),
             "custo_mensal": c.get("custo_mensal"), "cadencia": c.get("cadencia"),
             "transacoes": c.get("transacoes")}
            for c in maiores[:topo]
        ],
        "detalhe_em": DETALHE_EM["contrapartes"],
    }


def _triagem_curta(triagem: dict, topo: int) -> dict:
    itens = triagem.get("itens") or []
    return {
        "resumo": triagem.get("resumo"),
        "primeiros": [
            {"id": i["id"], "tipo": i["tipo"], "titulo": i["titulo"],
             "prioridade": i["prioridade"], "porque_importa": i["porque_importa"]}
            for i in itens[:topo]
        ],
        "quantos": len(itens),
        "detalhe_em": DETALHE_EM["triagem"],
    }


def _projecao_curta(projecao: dict) -> dict:
    """O destino e a reserva; o mês a mês é do gráfico, não da conversa."""
    linhas = projecao.get("linhas") or []
    return {
        "cenario": projecao.get("cenario"),
        "premissas": projecao.get("premissas"),
        "reserva": projecao.get("reserva"),
        "planos": projecao.get("planos"),
        "primeiro_mes": linhas[0] if linhas else None,
        "ultimo_mes": linhas[-1] if linhas else None,
        "meses_projetados": len(linhas),
        "detalhe_em": DETALHE_EM["projecao"],
    }


def _causas_curtas(causas: dict) -> dict:
    itens = causas.get("itens") or []
    return {
        "cobertura": causas.get("cobertura"),
        "quantas": len(itens),
        "detalhe_em": DETALHE_EM["causas"],
    }


def _decisoes_curtas(decisoes: dict) -> dict:
    abertas = decisoes.get("abertas") or []
    return {
        "aprendizados": decisoes.get("aprendizados"),
        "abertas": [
            {"id": d["id"], "titulo": d["titulo"], "pergunta": d["pergunta"],
             "alternativas": [a["nome"] for a in d["alternativas"]]}
            for d in abertas
        ],
        "detalhe_em": DETALHE_EM["decisoes"],
    }
