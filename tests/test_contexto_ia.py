"""Projeção explícita; escopos, tipos e evidência não viram texto livre."""
import pytest
from fintips.ai_context import AREAS, project_context


def args():
    return dict(fronts=[{"area": a, "total": 0, "done": 0} for a in AREAS], plans=[], reading=[], scopes=[])


def test_nenhum_escopo_e_ativado_por_padrao():
    assert project_context(**args()) == {"schema_version": 1}


def test_ausencia_de_meta_e_ausencia_de_registro_sao_estados_distintos():
    i = args()
    i["fronts"][0].update(total=2)
    i["fronts"][1].update(total=2, done=1)
    i["fronts"][2].update(total=2, done=2)
    i["scopes"] = ["rotina"]
    assert [f["evidencia"] for f in project_context(**i)["rotina"]] == [
        "sem_registro", "parcial", "completa", "sem_metas", "sem_metas", "sem_metas"]


@pytest.mark.parametrize("field,value", [
    ("scopes", ["nome"]), ("scopes", ["rotina", "rotina"]), ("fronts", []),
    ("plans", [{"area": "texto livre", "done": False}]),
    ("plans", [{"area": "FOR", "done": "false"}]),
    ("reading", [{"state": "texto livre", "source": "usuario"}]),
    ("reading", [{"state": "estimado", "source": "sensor"}]),
])
def test_entradas_fora_do_contrato_sao_recusadas(field, value):
    i = args(); i[field] = value
    with pytest.raises(ValueError):
        project_context(**i)


@pytest.mark.parametrize("total,done", [(True, 0), (2, False), (2, 3), (-1, 0), (10001, 0)])
def test_contagem_nao_aceita_booleano_ou_fora_da_base(total, done):
    i = args(); i["fronts"][0].update(total=total, done=done)
    with pytest.raises(ValueError):
        project_context(**i)
