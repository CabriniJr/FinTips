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


def project_bundle(bundle: dict, scopes: list[str], today: str) -> dict:
    """Mesmo contrato v1, agora derivado da autoridade canônica sem WebView."""
    from .reading import pacing
    tasks=[t for t in bundle['vida']['tarefas'] if t['inicio'] <= today and (t['repetir'] or t['inicio']==today)]
    done={r['tarefaId'] for r in bundle['vida']['registros'] if r['dia']==today}
    fronts=[dict(area=a,total=sum(t['atributo']==a for t in tasks),done=sum(t['atributo']==a and t['id'] in done for t in tasks)) for a in AREAS]
    plans=[dict(area=p['atributo'],done=p['concluido']) for p in bundle['vida']['planos']]
    reading=[]
    for b in bundle['leitura']['livros'] if 'leitura' in scopes else []:
        result=pacing([dict(dia=p['dia'],progresso_bp=p['progresso_bp']) for p in b['observacoes']],today=today,deadline=b['prazo'] or None,reading_days=b['dias_semana'])
        last=max(b['observacoes'],key=lambda o:o['dia'],default=None)
        reading.append(dict(state=result['estado'],source=last['origem'] if last else b['fonte']))
    return project_context(fronts=fronts,plans=plans,reading=reading,scopes=scopes)
