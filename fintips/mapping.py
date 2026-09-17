"""Motor de regras.

O agente escreve regras; o app as aplica de forma determinística e reproduzível.
Duas execuções sobre o mesmo extrato e o mesmo conjunto de regras produzem
exatamente o mesmo resultado — condição para que o número possa ser auditado.

Precedência, em ordem: autoridade da proveniência (usuário > agente >
importação > heurística), depois especificidade da condição, depois confiança.
Uma regra do usuário sempre vence uma heurística, por mais específica que a
heurística seja.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .categorize import norm
from .contracts import Condicao, Efeito, Proveniencia, Regra, agora, novo_id, valida_regex
from .entities import canonical_name, slug
from .models import Statement, Transaction

RULES_SCHEMA = 1


class RuleStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.regras: list[Regra] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        self.regras = [Regra.from_dict(d) for d in (data.get("regras") or [])]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": RULES_SCHEMA,
                    "atualizado_em": agora(),
                    "regras": [r.to_dict() for r in self.regras],
                },
                allow_unicode=True, sort_keys=False,
            ),
            encoding="utf-8",
        )

    # -------------------------------------------------------------- escrita
    def criar(
        self,
        quando: dict,
        entao: dict,
        *,
        proveniencia: Proveniencia | None = None,
        nota: str = "",
        regra_id: str = "",
    ) -> Regra:
        cond = Condicao.from_dict(quando)
        if cond.vazia():
            raise ValueError("condição vazia: uma regra sem `quando` casaria com tudo")
        valida_regex(cond.memo_casa)
        efeito = Efeito.from_dict(entao)
        if not (efeito.categoria or efeito.fluxo or efeito.marcar or efeito.rotulo):
            raise ValueError("efeito vazio: a regra não faria nada")

        rid = regra_id or novo_id("r", str(sorted(quando.items())), str(sorted(entao.items())))
        regra = Regra(
            id=rid, quando=cond, entao=efeito,
            proveniencia=proveniencia or Proveniencia(origem="agente", confianca=0.8),
            nota=nota,
        )
        self.regras = [r for r in self.regras if r.id != rid] + [regra]
        self.save()
        return regra

    def remover(self, regra_id: str) -> bool:
        antes = len(self.regras)
        self.regras = [r for r in self.regras if r.id != regra_id]
        if len(self.regras) != antes:
            self.save()
            return True
        return False

    def desativar(self, regra_id: str) -> bool:
        for r in self.regras:
            if r.id == regra_id:
                r.ativa = False
                self.save()
                return True
        return False

    # -------------------------------------------------------------- leitura
    def ativas(self) -> list[Regra]:
        return sorted(
            [r for r in self.regras if r.ativa],
            key=lambda r: r.prioridade(), reverse=True,
        )

    def to_dicts(self) -> list[dict]:
        return [r.to_dict() for r in sorted(self.regras, key=lambda r: r.prioridade(), reverse=True)]


# --------------------------------------------------------------------------
# aplicação
# --------------------------------------------------------------------------

def casa(regra: Regra, tx: Transaction) -> bool:
    c = regra.quando
    if c.contraparte_id and slug(canonical_name(tx.counterparty or "")) != c.contraparte_id:
        return False
    if c.contraparte_contem and norm(c.contraparte_contem) not in norm(tx.counterparty or ""):
        return False
    if c.memo_casa and not re.search(c.memo_casa, tx.memo_raw or "", re.I):
        return False
    if c.canal and tx.channel != c.canal:
        return False
    if c.fluxo and tx.flow != c.fluxo:
        return False
    if c.categoria_atual and tx.category != c.categoria_atual:
        return False
    valor = abs(float(tx.amount))
    if c.valor_min is not None and valor < c.valor_min:
        return False
    if c.valor_max is not None and valor > c.valor_max:
        return False
    if c.dias_semana and tx.ts.weekday() not in c.dias_semana:
        return False
    if c.hora_min is not None and tx.ts.hour < c.hora_min:
        return False
    if c.hora_max is not None and tx.ts.hour > c.hora_max:
        return False
    return True


def aplicar(store: RuleStore, stmt: Statement) -> dict:
    """Aplica as regras sobre as transações já classificadas pela heurística.

    A classificação anterior não é apagada: ela vira o piso, com proveniência
    'heuristica'. Cada transação sai daqui sabendo quem decidiu o que ela é.
    """
    regras = store.ativas()
    aplicadas: dict[str, int] = {}
    tocadas = 0

    for tx in stmt.transactions:
        for regra in regras:                       # já vêm em ordem de precedência
            if not casa(regra, tx):
                continue
            e = regra.entao
            if e.categoria:
                tx.category = e.categoria
            if e.fluxo:
                tx.flow = e.fluxo
            for tag in e.marcar:
                if tag not in tx.tags:
                    tx.tags.append(tag)
            if e.rotulo:
                tx.counterparty = e.rotulo
            tx.category_source = regra.proveniencia.origem
            tx.category_confidence = regra.proveniencia.confianca
            tx.rule_id = regra.id
            aplicadas[regra.id] = aplicadas.get(regra.id, 0) + 1
            tocadas += 1
            break                                   # a primeira (mais forte) vence

    return {
        "regras_ativas": len(regras),
        "transacoes_tocadas": tocadas,
        "por_regra": aplicadas,
        "sem_regra": len(stmt.transactions) - tocadas,
    }


def cobertura(stmt: Statement) -> dict:
    """Quanto do dinheiro está classificado por decisão e quanto por palpite."""
    total = por_decisao = por_palpite = 0.0
    for tx in stmt.transactions:
        if tx.flow != "expense":
            continue
        v = abs(float(tx.amount))
        total += v
        if tx.category_source in ("usuario", "agente"):
            por_decisao += v
        else:
            por_palpite += v
    return {
        "despesa_total": round(total, 2),
        "classificado_por_decisao": round(por_decisao, 2),
        "classificado_por_heuristica": round(por_palpite, 2),
        "cobertura_pct": round(por_decisao / total * 100, 1) if total else 0.0,
    }
