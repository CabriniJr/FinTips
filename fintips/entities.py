"""Objetos derivados da importação.

Um extrato é uma lista de eventos. O que serve para decidir é o que se repete:
quem são as contrapartes, quais gastos são fixos, o que é assinatura e o que é
consumo solto. Estas entidades são geradas a cada importação e guardadas com id
estável, para que confirmações e apelidos sobrevivam ao próximo extrato.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Iterable

from .models import Transaction

Z = Decimal("0")
ENTITIES_SCHEMA = 1

# Cadências, da mais previsível para a menos.
CADENCES = (
    "assinatura",     # mesmo valor, uma vez por mês, quase todo mês
    "fixo_de_uso",    # muitas vezes por mês, todo mês (transporte, mercado de rua)
    "recorrente",     # aparece em vários meses, valor variável
    "esporadico",     # poucos meses
    "unico",          # uma vez só
)

SOURCES = ("regra_publica", "regra_local", "proposta", "confirmado", "declarado")

# Sufixos de loja/terminal que variam sem mudar o estabelecimento.
_STORE_SUFFIX = re.compile(
    r"(?:[-\s]*(?:LJ|LOJA|FIL|UN)\s*\d+|\*\d{3,}|\s+\d{3,}|\s+[IVX]{1,4})$", re.I
)
_ACQUIRER_CODE = re.compile(r"^([A-Z0-9 ]+?)\s*\*\s*(.+)$")


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    return t or "sem-nome"


def canonical_name(raw: str) -> str:
    """Junta variações do mesmo estabelecimento.

    "Gelato Roma-LJ0046" e "-LJ0084" viram um só; "EMV CMT*144318981" vira
    "EMV CMT"; nomes de pessoa e pseudônimos passam intactos.
    """
    name = raw.strip()
    if name.startswith("PF:") or not name:
        return name
    m = _ACQUIRER_CODE.match(name.upper())
    if m and re.fullmatch(r"[\d\s.-]+", m.group(2)):
        name = m.group(1)
    prev = None
    while prev != name:
        prev = name
        name = _STORE_SUFFIX.sub("", name).strip(" -.*")
    return re.sub(r"\s{2,}", " ", name) or raw.strip()


@dataclass
class Counterparty:
    id: str
    display: str
    kind: str                       # merchant | person | institution | self
    category: str
    source: str = "proposta"
    confidence: float = 0.5
    aliases: list[str] = field(default_factory=list)
    first_seen: date | None = None
    last_seen: date | None = None
    n_tx: int = 0
    total: Decimal = Z
    months: list[str] = field(default_factory=list)
    median_amount: Decimal = Z
    cadence: str = "esporadico"
    typical_day: int | None = None
    fixed: bool = False
    note: str = ""
    flows: list[str] = field(default_factory=list)      # expense, income, transfer...
    channels: list[str] = field(default_factory=list)   # salary, pix, debit_card...

    @property
    def monthly_cost(self) -> Decimal:
        n = max(len(self.months), 1)
        return (self.total / n).quantize(Decimal("0.01"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.display,
            "tipo": self.kind,
            "categoria": self.category,
            "origem": self.source,
            "confianca": round(self.confidence, 2),
            "apelidos": sorted(set(self.aliases)),
            "primeira_vez": self.first_seen.isoformat() if self.first_seen else None,
            "ultima_vez": self.last_seen.isoformat() if self.last_seen else None,
            "transacoes": self.n_tx,
            "total": float(self.total),
            "meses": self.months,
            "valor_tipico": float(self.median_amount),
            "custo_mensal": float(self.monthly_cost),
            "cadencia": self.cadence,
            "dia_tipico": self.typical_day,
            "fixo": self.fixed,
            "nota": self.note,
            "fluxos": self.flows,
            "canais": self.channels,
        }


@dataclass
class FixedCost:
    """Um compromisso mensal previsível.

    Pode ser de uma contraparte (assinatura do Google) ou de uma categoria
    inteira (transporte: dez recargas pequenas por mês que, somadas, são tão
    previsíveis quanto uma mensalidade).
    """

    id: str
    label: str
    scope: str                       # contraparte | categoria
    key: str
    monthly: Decimal
    confidence: float
    kind: str = "rotina"             # contratual | rotina | declarado
    source: str = "detectado"        # detectado | confirmado | declarado
    variation: float = 0.0           # coeficiente de variação entre meses
    evidence: list[str] = field(default_factory=list)
    category: str = "outros"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rotulo": self.label,
            "escopo": self.scope,
            "natureza": self.kind,
            "chave": self.key,
            "categoria": self.category,
            "por_mes": float(self.monthly),
            "por_ano": float((self.monthly * 12).quantize(Decimal("0.01"))),
            "confianca": round(self.confidence, 2),
            "origem": self.source,
            "variacao_mensal": round(self.variation, 3),
            "evidencia": self.evidence,
        }


def _median(values: Iterable[Decimal]) -> Decimal:
    vals = [float(v) for v in values]
    return Decimal(str(statistics.median(vals))) if vals else Z


def build_counterparties(txs: list[Transaction], total_months: int) -> list[Counterparty]:
    """Agrupa transações por contraparte canônica e classifica a cadência."""
    groups: dict[str, list[Transaction]] = {}
    names: dict[str, set[str]] = {}
    for t in txs:
        if not t.counterparty:
            continue
        canon = canonical_name(t.counterparty)
        key = slug(canon)
        groups.setdefault(key, []).append(t)
        names.setdefault(key, set()).add(t.counterparty)

    out: list[Counterparty] = []
    for key, items in groups.items():
        items.sort(key=lambda t: t.ts)
        months = sorted({t.month for t in items})
        amounts = [abs(t.amount) for t in items]
        med = _median(amounts)
        spread = float((max(amounts) - min(amounts)) / med) if med else 9.0
        per_month = len(items) / max(len(months), 1)
        coverage = len(months) / max(total_months, 1)

        if len(items) == 1:
            cadence = "unico"
        elif coverage >= 0.6 and per_month <= 1.4 and spread <= 0.2:
            cadence = "assinatura"
        elif coverage >= 0.6 and per_month >= 2:
            cadence = "fixo_de_uso"
        elif len(months) >= 3:
            cadence = "recorrente"
        else:
            cadence = "esporadico"

        days = [t.day.day for t in items]
        typical_day = int(statistics.median(days)) if cadence == "assinatura" else None

        canon = canonical_name(items[0].counterparty)
        out.append(
            Counterparty(
                id=key,
                display=canon,
                kind=items[0].counterparty_kind or "merchant",
                category=items[0].category,
                first_seen=items[0].day,
                last_seen=items[-1].day,
                n_tx=len(items),
                total=sum(amounts, Z),
                months=months,
                median_amount=med,
                cadence=cadence,
                typical_day=typical_day,
                aliases=sorted(n for n in names[key] if n != canon),
                fixed=cadence == "assinatura",
                flows=sorted({t.flow for t in items}),
                channels=sorted({t.channel for t in items}),
            )
        )
    return sorted(out, key=lambda c: c.total, reverse=True)
