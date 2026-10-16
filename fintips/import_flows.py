"""Leitura conservadora do canal; não é o classificador financeiro completo.

Reutiliza os canais canônicos do Categorizer. Não examina origem/destino para
adivinhar Pix entre pessoas, contas próprias ou pagamentos. Sem identidade
local confirmada, esses lançamentos ficam pendentes.
"""
from functools import lru_cache
from hashlib import sha256
import json
from .categorize import Categorizer, norm

GROUPS = ("income", "expense", "savings_out", "savings_in", "refund", "pendente")
EXPECTED_SIGN = {"income": 1, "expense": -1, "savings_out": -1, "savings_in": 1, "refund": 1}


@lru_cache(maxsize=1)
def channel_rules():
    # A fonte única continua sendo rules/categories.yaml. Sem cópia de regras.
    return Categorizer().rules["canais"]


def rules_revision():
    data = json.dumps(channel_rules(), ensure_ascii=False, separators=(",", ":"))
    return sha256(data.encode()).hexdigest()


def import_group(memo: str, cents: int) -> str:
    target = norm(memo)
    rule = next((r for r in channel_rules() if target.startswith(norm(r["match"]))), None)
    if not rule or rule.get("canal", "other").startswith("pix"):
        return "pendente"
    flow = rule.get("fluxo")
    if flow not in EXPECTED_SIGN or cents == 0 or (1 if cents > 0 else -1) != EXPECTED_SIGN[flow]:
        return "pendente"
    return flow


def flow_summary(rows):
    # rows: mês, centavos, grupo. Nenhum texto/identificador entra na projeção.
    from .statement_context import safe
    def totals(data):
        return [dict(fluxo=group, transacoes=len(values),
                     entradas_centavos=safe(sum(v for v in values if v > 0)),
                     saidas_centavos=safe(-sum(v for v in values if v < 0)))
                for group in GROUPS if (values := [v for _, v, g in data if g == group])]
    return dict(schema_version=1, origem="heuristica", revisao_regras=rules_revision(),
                transacoes=len(rows), grupos=totals(rows),
                meses=[dict(mes=month, grupos=totals([r for r in rows if r[0] == month]))
                       for month in sorted({r[0] for r in rows})])


def validate_flow_summary(data):
    from .statement_context import safe
    import re
    if type(data) is not dict or set(data) != {"schema_version", "origem", "revisao_regras", "transacoes", "grupos", "meses"}:
        raise ValueError("fluxos inválidos")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1 or data["origem"] != "heuristica" or not re.fullmatch(r"[0-9a-f]{64}", data["revisao_regras"]):
        raise ValueError("revisão inválida")
    def groups(items):
        if type(items) is not list or len(items) > len(GROUPS):
            raise ValueError("grupos inválidos")
        seen = set()
        for item in items:
            if type(item) is not dict or set(item) != {"fluxo", "transacoes", "entradas_centavos", "saidas_centavos"} or item["fluxo"] not in GROUPS or item["fluxo"] in seen:
                raise ValueError("grupo inválido")
            seen.add(item["fluxo"])
            if any(safe(item[k]) < 0 for k in ("transacoes", "entradas_centavos", "saidas_centavos")) or not 1 <= item["transacoes"] <= 50000:
                raise ValueError("quantidade inválida")
            sign = EXPECTED_SIGN.get(item["fluxo"])
            if (sign == 1 and item["saidas_centavos"] != 0) or (sign == -1 and item["entradas_centavos"] != 0):
                raise ValueError("sinal inválido")
        return {g: tuple(next((r[k] for r in items if r["fluxo"] == g), 0) for k in ("transacoes", "entradas_centavos", "saidas_centavos")) for g in GROUPS}
    total = groups(data["grupos"])
    if not 0 <= safe(data["transacoes"]) <= 50000 or data["transacoes"] != sum(r[0] for r in total.values()) or type(data["meses"]) is not list or len(data["meses"]) > 1200:
        raise ValueError("contagem inválida")
    acc = {g: [0, 0, 0] for g in GROUPS}; previous = ""
    for month in data["meses"]:
        if type(month) is not dict or set(month) != {"mes", "grupos"} or type(month["mes"]) is not str or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month["mes"]) or month["mes"] <= previous:
            raise ValueError("mês inválido")
        previous = month["mes"]
        for g, values in groups(month["grupos"]).items():
            for i, n in enumerate(values): acc[g][i] = safe(acc[g][i] + n)
    if any(tuple(acc[g]) != total[g] for g in GROUPS):
        raise ValueError("totais incompatíveis")
    return data
