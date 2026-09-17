"""Monta o pacote de análise que o agente Claude consome."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from . import analysis, plans as plans_mod, score as score_mod
from .categorize import Categorizer
from .models import Statement
from .parsers.ofx import parse_ofx
from .workspace import Workspace

Z = Decimal("0")


def ingest(ws: Workspace, ofx_path: str | Path) -> tuple[Statement, Path]:
    cfg = ws.config
    stmt = parse_ofx(ofx_path, salt=ws.salt)
    cat = Categorizer(
        aliases=cfg.get("apelidos") or {},
        my_names=cfg.get("meus_nomes") or [],
        salt=ws.salt,
        local_rules_path=ws.regras_locais_path,
    )
    cat.apply_all(stmt.transactions)

    name = f"{stmt.period_start:%Y%m%d}-{stmt.period_end:%Y%m%d}.yaml"
    out = ws.canonico / name
    out.write_text(
        yaml.safe_dump(
            stmt.to_yaml_dict(include_raw=bool(cfg.get("incluir_memo_bruto"))),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return stmt, out


def analyze(ws: Workspace, stmt: Statement) -> dict[str, Any]:
    cfg = ws.config
    base = analysis.baseline(stmt)
    months = analysis.monthly(stmt)
    invis = analysis.invisible_spending(stmt)
    recs = analysis.recurrences(stmt)
    outs = analysis.outliers(stmt)

    patr = ws.load_patrimonio()
    plan_list = plans_mod.load_plans(ws.planos_path)
    plan_results = plans_mod.evaluate_all(plan_list, stmt, base)

    total_guardado = Decimal(str(patr.get("total", 0)))
    sc = score_mod.compute(
        base, invis, plan_results, patrimonio_liquido=total_guardado
    )

    ok, diff = stmt.reconciles()
    return {
        "periodo": {
            "inicio": stmt.period_start.isoformat(),
            "fim": stmt.period_end.isoformat(),
            "transacoes": len(stmt.transactions),
        },
        "conciliacao": {"bate": ok, "diferenca": float(diff)},
        "saldo_conta": float(stmt.ledger_balance),
        "patrimonio": patr,
        "baseline": base,
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
        "por_categoria_total": _by_category(stmt),
        "recorrencias": [
            {
                "onde": r.counterparty,
                "categoria": r.category,
                "tipo": r.kind,
                "meses": r.months,
                "vezes": r.occurrences,
                "valor_tipico": float(r.median_amount),
                "custo_mensal": float(r.monthly_cost),
            }
            for r in recs[:25]
        ],
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
        "config": {"reserva_alvo_meses": cfg.get("reserva_alvo_meses", 6)},
    }


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
