"""Custos fixos DEFINIDOS.

A diferença com `discovery.candidatos_custo_fixo` é a coisa toda: lá é o motor
notando um padrão; aqui é alguém afirmando um compromisso. Só o que está aqui
entra na projeção como custo fixo e sai do relatório de gasto invisível.

O agente define; o usuário confirma; o app aplica e recalcula.
"""

from __future__ import annotations

import statistics
from decimal import Decimal
from pathlib import Path

import yaml

from .contracts import CustoFixo, Proveniencia, agora, novo_id
from .models import Statement

COMMITMENTS_SCHEMA = 1
Z = Decimal("0")

BASES = ("categoria", "contraparte", "regra", "valor")
METODOS = ("declarado", "mediana_meses_completos", "media")


class CommitmentStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.itens: dict[str, CustoFixo] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        for d in data.get("custos_fixos") or []:
            self.itens[d["id"]] = CustoFixo.from_dict(d)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": COMMITMENTS_SCHEMA,
                    "atualizado_em": agora(),
                    "custos_fixos": [c.to_dict() for c in self.ativos() + self.inativos()],
                },
                allow_unicode=True, sort_keys=False,
            ),
            encoding="utf-8",
        )

    # -------------------------------------------------------------- escrita
    def definir(
        self,
        rotulo: str,
        base_tipo: str,
        base_ref: str,
        *,
        valor_mensal: float | None = None,
        metodo: str = "declarado",
        natureza: str = "rotina",
        proveniencia: Proveniencia | None = None,
        stmt: Statement | None = None,
        meses_completos: list[str] | None = None,
        custo_id: str = "",
    ) -> CustoFixo:
        if base_tipo not in BASES:
            raise ValueError(f"base_tipo deve ser um de {BASES}")
        if metodo not in METODOS:
            raise ValueError(f"metodo deve ser um de {METODOS}")

        if valor_mensal is None:
            if stmt is None:
                raise ValueError("sem valor_mensal é preciso passar o extrato para calcular")
            valor_mensal = observado(stmt, base_tipo, base_ref, meses_completos, metodo)
            if valor_mensal is None:
                raise ValueError(
                    f"não há lançamentos suficientes de {base_tipo}={base_ref} para calcular"
                )

        cid = custo_id or novo_id("fx", base_tipo, base_ref)
        item = CustoFixo(
            id=cid, rotulo=rotulo, base_tipo=base_tipo, base_ref=base_ref,
            valor_mensal=float(valor_mensal), metodo=metodo, natureza=natureza,
            proveniencia=proveniencia or Proveniencia(origem="agente", confianca=0.85),
        )
        self.itens[cid] = item
        self.save()
        return item

    def remover(self, custo_id: str) -> bool:
        if custo_id in self.itens:
            del self.itens[custo_id]
            self.save()
            return True
        return False

    def desativar(self, custo_id: str) -> bool:
        if custo_id in self.itens:
            self.itens[custo_id].ativo = False
            self.save()
            return True
        return False

    # -------------------------------------------------------------- leitura
    def ativos(self) -> list[CustoFixo]:
        return sorted([c for c in self.itens.values() if c.ativo],
                      key=lambda c: c.valor_mensal, reverse=True)

    def inativos(self) -> list[CustoFixo]:
        return [c for c in self.itens.values() if not c.ativo]

    def to_dicts(self) -> list[dict]:
        return [c.to_dict() for c in self.ativos()]

    def total_mensal(self) -> float:
        return round(sum(c.valor_mensal for c in self.ativos()), 2)

    def por_natureza(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for c in self.ativos():
            out[c.natureza] = round(out.get(c.natureza, 0) + c.valor_mensal, 2)
        return out

    def coberturas(self) -> tuple[set[str], set[str]]:
        """Categorias e contrapartes já contabilizadas como compromisso."""
        cats = {c.base_ref for c in self.ativos() if c.base_tipo == "categoria"}
        cps = {c.base_ref for c in self.ativos() if c.base_tipo == "contraparte"}
        return cats, cps


def observado(
    stmt: Statement,
    base_tipo: str,
    base_ref: str,
    meses: list[str] | None = None,
    metodo: str = "mediana_meses_completos",
) -> float | None:
    """Quanto a base realmente gastou por mês, a partir do extrato."""
    por_mes: dict[str, float] = {}
    for t in stmt.transactions:
        if t.flow != "expense":
            continue
        if meses and t.month not in meses:
            continue
        chave = {
            "categoria": t.category,
            "contraparte": t.counterparty,
            "regra": t.rule_id,
        }.get(base_tipo)
        if chave != base_ref:
            continue
        por_mes[t.month] = por_mes.get(t.month, 0) + abs(float(t.amount))
    if not por_mes:
        return None
    vals = list(por_mes.values())
    if metodo == "media":
        return round(sum(vals) / len(vals), 2)
    return round(float(statistics.median(vals)), 2)
