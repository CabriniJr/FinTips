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

from . import analysis, commitments, discovery, mapping, plans as plans_mod
from . import projection, score as score_mod, taxonomy as tax_mod, triage
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
