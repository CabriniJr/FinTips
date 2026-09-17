"""Descoberta: o que o extrato ensina sobre o usuário a cada importação.

Três trabalhos:
1. Propor categoria para contrapartes que nenhuma regra conheceu.
2. Separar custo fixo de custo variável — inclusive quando o fixo é um monte
   de lançamentos pequenos na mesma categoria (transporte é o caso clássico).
3. Guardar o que o usuário confirmou, para nunca perguntar duas vezes.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import yaml

from .categorize import norm
from .entities import Counterparty, FixedCost, canonical_name, slug
from .models import Statement

Z = Decimal("0")

# Pistas fracas: só entram quando nenhuma regra casou, e sempre com confiança
# baixa o bastante para virar pergunta em vez de virar verdade.
HINTS: dict[str, tuple[str, ...]] = {
    "alimentacao": ("REST", "LANCH", "BAR", "CAFE", "PIZZ", "SUSHI", "GRILL", "BURG",
                    "PASTEL", "SORVE", "GELAT", "DOCER", "CONFEIT", "EMPOR", "CANTIN"),
    "mercado": ("MERC", "SUPER", "ATACAD", "HORTI", "QUITAND", "ACOUGU", "PADAR"),
    "transporte": ("TRANS", "MOBIL", "TARIF", "BILHET", "METRO", "TREM", "ONIBUS",
                   "TAXI", "ESTACION", "PARK", "POSTO", "COMBUST", "AUTO"),
    "saude": ("DROG", "FARM", "CLIN", "MEDIC", "ODONT", "LAB", "SAUDE", "HOSPIT"),
    "vestuario": ("MODA", "CALCAD", "SPORT", "ESPORT", "STORE", "OUTDOOR", "TRILHA"),
    "lazer": ("CINE", "TEATR", "SHOW", "EVENT", "CLUB", "PARQUE", "MUSE", "LIVR"),
    "educacao": ("CURSO", "ESCOL", "FACUL", "ENSINO", "EDUC", "LIVRAR"),
    "servicos": ("SERV", "MANUT", "OFICIN", "LAVAND", "SALAO", "BARBE"),
    "moradia": ("ALUGU", "CONDOM", "ENERG", "ELETRO", "SABESP", "AGUA", "GAS",
                "INTERNET", "TELEFON", "VIVO", "CLARO", "TIM ", "NET "),
}


@dataclass
class Proposal:
    """Uma pergunta fechada para o usuário: 'isto é disto?'"""

    counterparty_id: str
    display: str
    suggested: str
    confidence: float
    rationale: str
    alternatives: list[str] = field(default_factory=list)
    n_tx: int = 0
    total: Decimal = Z
    monthly: Decimal = Z
    cadence: str = "esporadico"
    sample: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.counterparty_id,
            "nome": self.display,
            "sugestao": self.suggested,
            "confianca": round(self.confidence, 2),
            "porque": self.rationale,
            "alternativas": self.alternatives,
            "transacoes": self.n_tx,
            "total": float(self.total),
            "custo_mensal": float(self.monthly),
            "cadencia": self.cadence,
            "exemplos": self.sample,
        }


# --------------------------------------------------------------------------
# confirmações
# --------------------------------------------------------------------------

def load_confirmations(path: str | Path) -> dict[str, dict]:
    p = Path(path)
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data.get("contrapartes") or {}


def save_confirmations(path: str | Path, data: dict[str, dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(
            {"schema_version": 1, "contrapartes": data},
            allow_unicode=True,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def confirm(
    path: str | Path,
    counterparty_id: str,
    *,
    category: str,
    fixed: bool | None = None,
    label: str = "",
    note: str = "",
) -> dict:
    """Grava a decisão do usuário. É isto que faz o sistema parar de perguntar."""
    data = load_confirmations(path)
    entry = data.get(counterparty_id, {})
    entry["categoria"] = category
    entry["origem"] = "confirmado"
    if fixed is not None:
        entry["fixo"] = bool(fixed)
    if label:
        entry["rotulo"] = label
    if note:
        entry["nota"] = note
    data[counterparty_id] = entry
    save_confirmations(path, data)
    return entry


def apply_confirmations(
    cps: list[Counterparty], confirmations: dict[str, dict]
) -> list[Counterparty]:
    for c in cps:
        conf = confirmations.get(c.id)
        if not conf:
            continue
        c.category = conf.get("categoria", c.category)
        c.source = "confirmado"
        c.confidence = 1.0
        if "fixo" in conf:
            c.fixed = bool(conf["fixo"])
        if conf.get("rotulo"):
            c.display = conf["rotulo"]
        if conf.get("nota"):
            c.note = conf["nota"]
    return cps


def apply_to_transactions(stmt: Statement, cps: list[Counterparty]) -> None:
    """Propaga categoria confirmada de volta para as transações."""
    by_id = {c.id: c for c in cps if c.source == "confirmado"}
    for t in stmt.transactions:
        if not t.counterparty:
            continue
        c = by_id.get(slug(canonical_name(t.counterparty)))
        if c:
            t.category = c.category


# --------------------------------------------------------------------------
# propostas
# --------------------------------------------------------------------------

def _tokens(name: str) -> set[str]:
    return {w for w in norm(name).split() if len(w) >= 4}


def propose(cps: list[Counterparty], *, fallback: str = "outros") -> list[Proposal]:
    """Para cada contraparte sem categoria, a melhor hipótese e o porquê."""
    known = [c for c in cps if c.category != fallback and c.kind == "merchant"]
    out: list[Proposal] = []

    for c in cps:
        if c.category != fallback or c.kind not in ("merchant", "institution"):
            continue
        n = norm(c.display)

        # 1. vizinho mais próximo entre o que já está categorizado
        best, best_score = None, 0.0
        for k in known:
            shared = _tokens(c.display) & _tokens(k.display)
            if shared:
                score = len(shared) / max(len(_tokens(c.display)), 1)
                if score > best_score:
                    best, best_score = k, score
        if best and best_score >= 0.5:
            out.append(_mk(c, best.category, 0.55 + 0.3 * best_score,
                           f"parecido com {best.display}, que é {best.category}"))
            continue

        # 2. pista fraca no nome
        hit = next(
            ((cat, frag) for cat, frags in HINTS.items() for frag in frags if frag in n),
            None,
        )
        if hit:
            cat, frag = hit
            out.append(_mk(c, cat, 0.5, f"o nome contém “{frag.strip()}”"))
            continue

        # 3. nada no nome: a cadência ainda diz algo
        if c.cadence == "assinatura":
            out.append(_mk(c, "assinaturas", 0.45,
                           f"cobra {c.median_amount} quase todo mês, no dia {c.typical_day}"))
        elif c.cadence == "fixo_de_uso":
            out.append(_mk(c, fallback, 0.2,
                           f"{c.n_tx} compras pequenas em {len(c.months)} meses — parece rotina, mas de quê?"))
        else:
            out.append(_mk(c, fallback, 0.15, "nenhuma regra casou"))

    out.sort(key=lambda p: (-float(p.monthly), -p.n_tx))
    return out


def _mk(c: Counterparty, cat: str, conf: float, why: str) -> Proposal:
    alts = [x for x in ("alimentacao", "mercado", "transporte", "lazer", "compras",
                        "servicos", "saude", "assinaturas") if x != cat][:5]
    return Proposal(
        counterparty_id=c.id,
        display=c.display,
        suggested=cat,
        confidence=conf,
        rationale=why,
        alternatives=alts,
        n_tx=c.n_tx,
        total=c.total,
        monthly=c.monthly_cost,
        cadence=c.cadence,
        sample=c.aliases[:3],
    )


# --------------------------------------------------------------------------
# custo fixo
# --------------------------------------------------------------------------

def _cv(values: list[float]) -> float:
    """Coeficiente de variação: 0 = idêntico todo mês."""
    if len(values) < 2:
        return 0.0
    m = statistics.fmean(values)
    return statistics.pstdev(values) / m if m else 1.0


def detect_fixed_costs(
    stmt: Statement,
    cps: list[Counterparty],
    *,
    months: list[str],
    declared: dict[str, float] | None = None,
) -> list[FixedCost]:
    """Separa o gasto previsível do gasto solto, em duas naturezas diferentes.

    - **contratual**: assinatura, seguro, tarifa. Valor conhecido, data conhecida,
      só sai se você cancelar.
    - **rotina**: uma categoria inteira que se repete com pouca variação, mesmo
      pulverizada em lançamentos pequenos. Transporte público é o exemplo: dez
      recargas de R$ 5 a R$ 20 por mês somam tão previsivelmente quanto um
      boleto — e tratá-las como "gasto invisível" é errado, porque não são
      desperdício, são o custo de ir trabalhar.

    A distinção importa porque o contratual se corta com um cancelamento e a
    rotina só muda com mudança de vida. Misturar os dois produz conselho ruim.

    `months` deve conter apenas meses COMPLETOS: um mês pela metade derruba a
    média e faz uma despesa estável parecer volátil.
    """
    declared = declared or {}
    n_months = max(len(months), 1)
    contratuais: list[FixedCost] = []

    # 1. contraparte com cara de compromisso
    for c in cps:
        if c.kind == "person" or c.category == "investimento":
            continue
        if "expense" not in (c.flows or ["expense"]):
            continue
        if c.fixed or c.cadence == "assinatura":
            contratuais.append(
                FixedCost(
                    id=f"cp:{c.id}",
                    label=c.display,
                    scope="contraparte",
                    key=c.id,
                    kind="contratual",
                    category=c.category,
                    monthly=c.median_amount if c.cadence == "assinatura" else c.monthly_cost,
                    confidence=0.9 if c.source == "confirmado" else 0.7,
                    source="confirmado" if c.source == "confirmado" else "detectado",
                    evidence=[
                        f"{c.n_tx} cobranças em {len(c.months)} meses",
                        f"valor típico R$ {c.median_amount}"
                        + (f", por volta do dia {c.typical_day}" if c.typical_day else ""),
                    ],
                )
            )

    # 2. categoria que se comporta como rotina previsível
    por_cat: dict[str, dict[str, Decimal]] = {}
    n_por_cat: dict[str, int] = {}
    for t in stmt.transactions:
        if t.flow != "expense" or t.month not in months:
            continue
        por_cat.setdefault(t.category, {})
        por_cat[t.category][t.month] = por_cat[t.category].get(t.month, Z) + abs(t.amount)
        n_por_cat[t.category] = n_por_cat.get(t.category, 0) + 1

    rotinas: list[FixedCost] = []
    for cat, by_month in por_cat.items():
        if cat in ("investimento", "pessoas"):
            continue
        vals = [float(by_month.get(m, 0)) for m in months]
        presentes = [v for v in vals if v > 0]
        if len(presentes) < n_months or n_months < 2:
            continue                      # tem que estar em TODOS os meses completos
        cv = _cv(presentes)
        if cv > 0.35:
            continue
        if n_por_cat[cat] / n_months < 2:
            continue                      # rotina é frequente, não uma compra por mês
        mediana = Decimal(str(statistics.median(presentes))).quantize(Decimal("0.01"))
        if mediana < Decimal("20"):
            continue
        # desconta o que já está contado como contratual dentro da categoria
        ja_contado = sum(
            (f.monthly for f in contratuais if f.category == cat), Z
        )
        liquido = max(mediana - ja_contado, Z)
        if liquido < Decimal("20"):
            continue
        rotinas.append(
            FixedCost(
                id=f"cat:{cat}",
                label=f"{cat} (rotina)",
                scope="categoria",
                key=cat,
                kind="rotina",
                category=cat,
                monthly=liquido,
                confidence=round(max(0.4, 1 - cv), 2),
                variation=cv,
                evidence=[
                    f"presente nos {len(presentes)} meses completos",
                    f"{n_por_cat[cat]} lançamentos, ~{n_por_cat[cat] // n_months} por mês",
                    f"variação mensal de apenas {cv * 100:.0f}%",
                ],
            )
        )

    out = contratuais + rotinas

    # 3. o que o usuário declarou vence a detecção
    for key, value in declared.items():
        scope, _, k = key.partition(":")
        out = [f for f in out if f.key != k]
        out.append(
            FixedCost(
                id=key,
                label=k,
                scope="categoria" if scope == "cat" else "contraparte",
                key=k,
                kind="declarado",
                category=k if scope == "cat" else "outros",
                monthly=Decimal(str(value)),
                confidence=1.0,
                source="declarado",
                evidence=["informado por você"],
            )
        )

    return sorted(out, key=lambda f: f.monthly, reverse=True)


def fixed_total(costs: list[FixedCost]) -> Decimal:
    return sum((f.monthly for f in costs), Z).quantize(Decimal("0.01"))
