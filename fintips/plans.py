"""Planos financeiros: cadastro, cruzamento com o extrato e viabilidade."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

from .categorize import norm
from .models import Statement

Z = Decimal("0")


@dataclass
class Plan:
    id: str
    nome: str
    tipo: str = "outro"          # viagem | compra | reserva | educacao | outro
    custo_alvo: Decimal = Z
    data_alvo: date | None = None
    prioridade: str = "media"    # alta | media | baixa
    aporte_mensal: Decimal = Z   # quanto você se comprometeu a guardar
    guardado: Decimal = Z        # quanto já separou para ESTE plano
    conta: str = ""              # onde o dinheiro está (ex.: "CDB")
    merchants: list[str] = field(default_factory=list)   # gastos que contam para o plano
    categorias: list[str] = field(default_factory=list)
    notas: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        alvo = d.get("data_alvo")
        if isinstance(alvo, str):
            alvo = date.fromisoformat(alvo)
        return cls(
            id=d["id"],
            nome=d.get("nome", d["id"]),
            tipo=d.get("tipo", "outro"),
            custo_alvo=Decimal(str(d.get("custo_alvo", 0))),
            data_alvo=alvo,
            prioridade=d.get("prioridade", "media"),
            aporte_mensal=Decimal(str(d.get("aporte_mensal", 0))),
            guardado=Decimal(str(d.get("guardado", 0))),
            conta=d.get("conta", ""),
            merchants=list(d.get("merchants", []) or []),
            categorias=list(d.get("categorias", []) or []),
            notas=d.get("notas", ""),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "tipo": self.tipo,
            "custo_alvo": float(self.custo_alvo),
            "data_alvo": self.data_alvo.isoformat() if self.data_alvo else None,
            "prioridade": self.prioridade,
            "aporte_mensal": float(self.aporte_mensal),
            "guardado": float(self.guardado),
            "conta": self.conta,
            "merchants": self.merchants,
            "categorias": self.categorias,
            "notas": self.notas,
        }


def load_plans(path: str | Path) -> list[Plan]:
    p = Path(path)
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return [Plan.from_dict(d) for d in (data.get("planos") or [])]


def save_plans(path: str | Path, plans: list[Plan]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        yaml.safe_dump(
            {"planos": [p.to_dict() for p in plans]},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def months_until(target: date | None, today: date | None = None) -> int | None:
    if not target:
        return None
    today = today or date.today()
    return max((target.year - today.year) * 12 + (target.month - today.month), 0)


def evaluate(plan: Plan, stmt: Statement, base: dict, *, today: date | None = None) -> dict:
    """Cruza o plano com o extrato: o que já foi gasto nele e se o ritmo fecha."""
    keys = [norm(m) for m in plan.merchants]
    cats = set(plan.categorias)
    gastos = [
        t
        for t in stmt.transactions
        if t.flow == "expense"
        and (
            (keys and any(k in norm(t.counterparty) for k in keys))
            or (cats and t.category in cats)
        )
    ]
    ja_gasto = sum((abs(t.amount) for t in gastos), Z)

    faltam = max(plan.custo_alvo - plan.guardado, Z)
    meses = months_until(plan.data_alvo, today)
    necessario = (faltam / meses).quantize(Decimal("0.01")) if meses else faltam
    sobra = Decimal(str(base.get("sobra_media_mes", 0)))
    capacidade = sobra if sobra > 0 else Z

    if faltam == 0:
        status, viavel = "concluido", True
    elif meses in (None, 0):
        status, viavel = ("pronto" if faltam <= 0 else "sem_prazo"), faltam <= capacidade
    elif necessario <= capacidade * Decimal("0.6"):
        status, viavel = "confortavel", True
    elif necessario <= capacidade:
        status, viavel = "apertado", True
    else:
        status, viavel = "inviavel_no_ritmo_atual", False

    meses_no_ritmo = (
        int((faltam / plan.aporte_mensal).to_integral_value(rounding="ROUND_CEILING"))
        if plan.aporte_mensal > 0 else None
    )

    return {
        "id": plan.id,
        "nome": plan.nome,
        "custo_alvo": float(plan.custo_alvo),
        "guardado": float(plan.guardado),
        "falta": float(faltam),
        "progresso_pct": float(round(plan.guardado / plan.custo_alvo * 100, 1)) if plan.custo_alvo else 0.0,
        "meses_ate_alvo": meses,
        "aporte_necessario_mes": float(necessario),
        "aporte_planejado_mes": float(plan.aporte_mensal),
        "capacidade_mensal_real": float(capacidade),
        "meses_no_ritmo_planejado": meses_no_ritmo,
        "status": status,
        "viavel": viavel,
        "ja_gasto_no_plano": float(ja_gasto),
        "compras_relacionadas": [
            {"data": t.day.isoformat(), "onde": t.counterparty, "valor": float(abs(t.amount))}
            for t in sorted(gastos, key=lambda x: x.ts, reverse=True)[:10]
        ],
    }


def evaluate_all(plans: list[Plan], stmt: Statement, base: dict, *, today: date | None = None) -> list[dict]:
    return [evaluate(p, stmt, base, today=today) for p in plans]
