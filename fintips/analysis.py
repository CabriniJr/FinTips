"""Análise do extrato: fluxo mensal, recorrências, gastos invisíveis, outliers."""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from .models import Statement, Transaction

Z = Decimal("0")


def _sum(txs: Iterable[Transaction]) -> Decimal:
    return sum((t.amount for t in txs), Z)


@dataclass
class MonthSummary:
    month: str
    income: Decimal = Z
    expense: Decimal = Z          # positivo = quanto saiu
    savings_out: Decimal = Z
    savings_in: Decimal = Z
    transfers_net: Decimal = Z
    refunds: Decimal = Z
    by_category: dict[str, Decimal] = field(default_factory=dict)

    @property
    def net(self) -> Decimal:
        return self.income - self.expense + self.refunds

    @property
    def savings_rate(self) -> float:
        """Quanto da renda sobrou (aporte líquido + saldo não gasto)."""
        if self.income <= 0:
            return 0.0
        return float(round(self.net / self.income, 4))


@dataclass
class Recurrence:
    counterparty: str
    category: str
    months: list[str]
    occurrences: int
    median_amount: Decimal
    monthly_cost: Decimal
    kind: str  # assinatura | recorrente | sangria


def monthly(stmt: Statement) -> list[MonthSummary]:
    buckets: dict[str, MonthSummary] = {}
    for t in stmt.transactions:
        m = buckets.setdefault(t.month, MonthSummary(month=t.month))
        amt = abs(t.amount)
        if t.flow == "income":
            m.income += amt
        elif t.flow == "expense":
            m.expense += amt
            m.by_category[t.category] = m.by_category.get(t.category, Z) + amt
        elif t.flow == "savings_out":
            m.savings_out += amt
        elif t.flow == "savings_in":
            m.savings_in += amt
        elif t.flow == "refund":
            m.refunds += amt
        elif t.flow == "transfer":
            m.transfers_net += t.amount
    return [buckets[k] for k in sorted(buckets)]


def full_months(stmt: Statement) -> list[MonthSummary]:
    """Descarta meses parciais das pontas — eles distorcem qualquer média."""
    months = monthly(stmt)
    if len(months) <= 2:
        return months
    out = months
    if stmt.period_start.day > 1:
        out = out[1:]
    if stmt.period_end.day < 26:
        out = out[:-1]
    return out or months


def recurrences(stmt: Statement, *, min_months: int = 3) -> list[Recurrence]:
    """Contrapartes que reaparecem mês após mês — o custo fixo real."""
    groups: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
    for t in stmt.transactions:
        if t.flow != "expense" or not t.counterparty:
            continue
        groups[(t.counterparty, t.category)].append(t)

    n_months = max(len({t.month for t in stmt.transactions}), 1)
    out: list[Recurrence] = []
    for (party, cat), txs in groups.items():
        months = sorted({t.month for t in txs})
        if len(months) < min_months:
            continue
        amounts = sorted(abs(t.amount) for t in txs)
        med = Decimal(str(statistics.median(amounts)))
        total = sum(amounts, Z)
        spread = (max(amounts) - min(amounts)) / med if med else Decimal("9")
        per_month = len(txs) / len(months)
        if spread <= Decimal("0.15") and per_month <= 1.4:
            kind = "assinatura"       # mesmo valor, uma vez por mês
        elif per_month >= 3:
            kind = "sangria"          # muitas compras pequenas, sempre no mesmo lugar
        else:
            kind = "recorrente"
        out.append(
            Recurrence(
                counterparty=party,
                category=cat,
                months=months,
                occurrences=len(txs),
                median_amount=med,
                monthly_cost=(total / n_months).quantize(Decimal("0.01")),
                kind=kind,
            )
        )
    return sorted(out, key=lambda r: r.monthly_cost, reverse=True)


def invisible_spending(stmt: Statement) -> dict:
    """Gasto que não dói na hora mas soma no mês.

    Três fontes: taxas e seguros, micro-débitos (<= R$30) e sangrias
    (mesmo estabelecimento, várias vezes por mês).
    """
    n_months = max(len({t.month for t in stmt.transactions}), 1)
    fees = [t for t in stmt.transactions if t.category == "taxas" and t.flow == "expense"]
    micro = [t for t in stmt.transactions if "micro" in t.tags and t.flow == "expense"]
    bleeds = [r for r in recurrences(stmt) if r.kind == "sangria"]

    total_expense = _sum([t for t in stmt.transactions if t.flow == "expense"])
    micro_total = sum((abs(t.amount) for t in micro), Z)
    fee_total = sum((abs(t.amount) for t in fees), Z)

    return {
        "taxas_e_seguros": {
            "total": float(fee_total),
            "por_mes": float((fee_total / n_months).quantize(Decimal("0.01"))),
            "ocorrencias": len(fees),
            "itens": sorted({t.counterparty or t.memo_raw[:40] for t in fees}),
        },
        "micro_gastos": {
            "total": float(micro_total),
            "por_mes": float((micro_total / n_months).quantize(Decimal("0.01"))),
            "ocorrencias": len(micro),
            "ticket_medio": float(
                (micro_total / len(micro)).quantize(Decimal("0.01"))
            ) if micro else 0.0,
            "pct_da_despesa": float(
                round(micro_total / abs(total_expense) * 100, 1)
            ) if total_expense else 0.0,
        },
        "sangrias": [
            {
                "onde": r.counterparty,
                "categoria": r.category,
                "vezes": r.occurrences,
                "por_mes": float(r.monthly_cost),
                "ticket_medio": float(r.median_amount),
            }
            for r in bleeds[:10]
        ],
        "custo_fixo_estimado_mes": float(
            sum(
                (r.monthly_cost for r in recurrences(stmt) if r.kind == "assinatura"),
                Z,
            )
        ),
    }


def outliers(stmt: Statement, *, k: Decimal = Decimal("4")) -> list[Transaction]:
    """Eventos atípicos (compra grande, repasse pontual) que não podem entrar
    na linha de base de consumo."""
    values = [abs(t.amount) for t in stmt.transactions if t.flow in ("expense", "transfer")]
    if len(values) < 8:
        return []
    med = Decimal(str(statistics.median(values)))
    limit = med * k if med else Decimal("500")
    return sorted(
        [
            t
            for t in stmt.transactions
            if t.flow in ("expense", "transfer") and abs(t.amount) > max(limit, Decimal("500"))
        ],
        key=lambda t: abs(t.amount),
        reverse=True,
    )


def baseline(stmt: Statement) -> dict:
    """Números que todo o resto do motor usa como referência."""
    months = full_months(stmt)
    if not months:
        months = monthly(stmt)
    incomes = [m.income for m in months]
    expenses = [m.expense for m in months]
    avg_income = sum(incomes, Z) / len(months)
    avg_expense = sum(expenses, Z) / len(months)
    exp_f = [float(e) for e in expenses]
    volatility = (
        statistics.pstdev(exp_f) / statistics.fmean(exp_f) if len(exp_f) > 1 and statistics.fmean(exp_f) else 0.0
    )
    return {
        "meses_considerados": [m.month for m in months],
        "renda_media_mes": float(avg_income.quantize(Decimal("0.01"))),
        "despesa_media_mes": float(avg_expense.quantize(Decimal("0.01"))),
        "sobra_media_mes": float((avg_income - avg_expense).quantize(Decimal("0.01"))),
        "taxa_poupanca_media": float(
            round((avg_income - avg_expense) / avg_income, 4)
        ) if avg_income else 0.0,
        "volatilidade_despesa": round(volatility, 3),
        "meses_no_vermelho": sum(1 for m in months if m.net < 0),
    }
