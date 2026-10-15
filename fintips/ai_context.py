"""Projeção mínima para IA. Nunca recebe textos livres, identificadores ou valores.

As faixas são vocabulário de compartilhamento, não um score de vida. A pessoa
escolhe as áreas. Ausência de evidência não significa meta descumprida.
"""
from __future__ import annotations

AREAS = ("FOR", "AGI", "VIT", "INT", "FOC", "OURO")
READING_STATES = ("sem_dados", "desatualizado", "calibrando", "sem_avanco", "estimado", "no_fim")


def _plan_state(items: list[dict]) -> str:
    if not items:
        return "sem_planos"
    if all(p["done"] for p in items):
        return "concluidos"
    return "misto" if any(p["done"] for p in items) else "em_andamento"


def project_context(*, fronts: list[dict], plans: list[dict], reading: list[dict],
                    scopes: list[str]) -> dict:
    allowed = {"rotina", "planos", "leitura"}
    if len(set(scopes)) != len(scopes) or not set(scopes) <= allowed:
        raise ValueError("escopo inválido")
    if len(fronts) != len(AREAS) or {f["area"] for f in fronts} != set(AREAS):
        raise ValueError("frentes inválidas")
    for f in fronts:
        if (type(f["total"]) is not int or type(f["done"]) is not int or
                not 0 <= f["done"] <= f["total"] <= 10000):
            raise ValueError("contagem inválida")
    for p in plans:
        if p["area"] not in AREAS or type(p["done"]) is not bool:
            raise ValueError("plano inválido")
    for r in reading:
        if r["state"] not in READING_STATES or r["source"] not in ("usuario", "librera"):
            raise ValueError("leitura inválida")
    result = {"schema_version": 1}
    if "rotina" in scopes:
        result["rotina"] = [{"area": area, "evidencia": (
            "sem_metas" if f["total"] == 0 else "sem_registro" if f["done"] == 0
            else "completa" if f["done"] == f["total"] else "parcial"),
            "origem": "usuario"} for area in AREAS for f in fronts if f["area"] == area]
    if "planos" in scopes:
        result["planos"] = [{"area": area, "estado": _plan_state([p for p in plans if p["area"] == area])}
                            for area in AREAS]
    if "leitura" in scopes:
        result["leitura"] = {
            "estados": [s for s in READING_STATES if any(r["state"] == s for r in reading)],
            "fontes": [s for s in ("usuario", "librera") if any(r["source"] == s for r in reading)],
        }
    return result
