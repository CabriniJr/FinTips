"""Modelo canônico do FinTips.

Tudo que entra (OFX, CSV, futuro Open Finance) é normalizado para estas
estruturas antes de qualquer análise. O YAML gerado é a fonte de verdade
que o agente Claude lê.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

SCHEMA_VERSION = 1

# --------------------------------------------------------------------------
# Taxonomias
# --------------------------------------------------------------------------

# Como o dinheiro se moveu, do ponto de vista do patrimônio.
# É a distinção mais importante do motor: mandar dinheiro para o CDB NÃO é
# despesa, e transferência entre contas próprias não é nem receita nem gasto.
FLOWS = (
    "expense",      # saiu e não volta
    "income",       # entrou de fora (salário, rendimento, venda)
    "savings_out",  # conta -> investimento (aporte)
    "savings_in",   # investimento -> conta (resgate)
    "transfer",     # entre contas próprias / neutro
    "refund",       # estorno ou devolução de um gasto anterior
)

# Canal/instrumento usado.
CHANNELS = (
    "debit_card",
    "pix",
    "pix_qr",
    "pix_auto",
    "salary",
    "yield",
    "fixed_income",
    "fund",
    "fee",
    "transit_topup",
    "reversal",
    "other",
)

CATEGORIES = (
    "alimentacao",
    "mercado",
    "transporte",
    "moradia",
    "saude",
    "vestuario",
    "lazer",
    "educacao",
    "assinaturas",
    "servicos",
    "compras",
    "doacoes",
    "taxas",
    "viagem",
    "pessoas",
    "investimento",
    "renda",
    "outros",
)


def _dec(v: Any) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


@dataclass
class Transaction:
    id: str                      # FITID — chave de deduplicação entre extratos
    ts: datetime
    amount: Decimal              # negativo = saída
    memo_raw: str                # texto original do banco (fica local, nunca sai)
    channel: str = "other"
    flow: str = "expense"
    category: str = "outros"
    counterparty: str = ""       # normalizado
    counterparty_kind: str = ""  # merchant | person | institution | self
    city: str = ""
    tags: list[str] = field(default_factory=list)
    account_id: str = ""

    @property
    def day(self) -> date:
        return self.ts.date()

    @property
    def month(self) -> str:
        return self.ts.strftime("%Y-%m")

    def to_yaml_dict(self, *, include_raw: bool = False) -> dict:
        d = {
            "id": self.id,
            "data": self.ts.strftime("%Y-%m-%d"),
            "hora": self.ts.strftime("%H:%M"),
            "valor": float(self.amount),
            "fluxo": self.flow,
            "canal": self.channel,
            "categoria": self.category,
            "contraparte": self.counterparty,
            "tipo_contraparte": self.counterparty_kind,
        }
        if self.city:
            d["cidade"] = self.city
        if self.tags:
            d["tags"] = sorted(self.tags)
        if include_raw:
            d["memo"] = self.memo_raw
        return d


@dataclass
class Account:
    id_hash: str                 # hash do número da conta — nunca o número
    institution: str = ""
    bank_id: str = ""
    type: str = "CHECKING"
    currency: str = "BRL"


@dataclass
class Statement:
    account: Account
    period_start: date
    period_end: date
    ledger_balance: Decimal
    balance_as_of: date
    transactions: list[Transaction] = field(default_factory=list)
    source: str = ""             # ex.: "ofx:pagbank"

    def to_yaml_dict(self, *, include_raw: bool = False) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "gerado_em": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "origem": self.source,
            "conta": asdict(self.account),
            "periodo": {
                "inicio": self.period_start.isoformat(),
                "fim": self.period_end.isoformat(),
            },
            "saldo": {
                "conta": float(self.ledger_balance),
                "em": self.balance_as_of.isoformat(),
            },
            "transacoes": [
                t.to_yaml_dict(include_raw=include_raw) for t in self.transactions
            ],
        }

    def reconciles(self, opening: Decimal = Decimal("0")) -> tuple[bool, Decimal]:
        """Confere se saldo inicial + soma das transações == saldo declarado."""
        total = sum((t.amount for t in self.transactions), Decimal("0"))
        diff = (opening + total) - self.ledger_balance
        return abs(diff) < Decimal("0.01"), diff
