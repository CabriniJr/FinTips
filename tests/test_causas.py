"""Testes da camada de causa (v0.5).

A propriedade protegida aqui é a mais frágil de todas, porque é a que mais
parece automatizável: **causa não se deriva**. O extrato mostra que o dinheiro
saiu; nunca por quê. Se um dia alguém escrever `detectar_causas()`, estes
testes é que vão dizer que aquilo quebrou o produto, não um bug de cálculo.
"""

from __future__ import annotations

import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fintips import causes as causes_mod, report  # noqa: E402
from fintips.contracts import ATITUDES, Proveniencia  # noqa: E402
from fintips.workspace import Workspace  # noqa: E402

FIXTURE = Path(__file__).parent / "fixture.ofx"
TMP = Path("/tmp/fintips-causas")


def _ws() -> Workspace:
    if TMP.exists():
        shutil.rmtree(TMP)
    ws = Workspace.open(TMP)
    shutil.copy(FIXTURE, ws.extratos / "fixture.ofx")
    report.ingest(ws, ws.extratos / "fixture.ofx")
    return ws


def _loja(nome: str = "causas.yaml") -> causes_mod.CauseStore:
    return causes_mod.CauseStore(TMP / nome)


def _prov(origem: str = "usuario", porque: str = "a pessoa contou na conversa") -> Proveniencia:
    return Proveniencia(origem=origem, confianca=1.0, porque=porque)


def _valida(**extra):
    base = dict(
        efeito_tipo="categoria",
        efeito_ref="alimentacao",
        natureza="gatilho",
        enunciado="peço delivery nas noites que saio tarde do plantão",
        proveniencia=_prov(),
    )
    base.update(extra)
    return base


# ------------------------------------------------------------- não se deriva

def test_causa_nao_aceita_origem_derivada():
    _ws()
    loja = _loja("c1.yaml")
    for origem in ("heuristica", "importacao"):
        try:
            loja.gravar(**_valida(proveniencia=Proveniencia(origem=origem, confianca=0.99, porque="padrão claro")))
            raise AssertionError(f"origem '{origem}' não deveria poder afirmar causa")
        except ValueError:
            pass


def test_nao_existe_deteccao_de_causa_no_modulo():
    """Guarda explícita: se alguém adicionar detecção, este teste cai."""
    suspeitas = [n for n in dir(causes_mod) if "detect" in n.lower() or "inferir" in n.lower()]
    assert not suspeitas, f"detecção de causa não deve existir: {suspeitas}"


def test_causa_exige_porque_e_enunciado():
    _ws()
    loja = _loja("c2.yaml")
    try:
        loja.gravar(**_valida(proveniencia=Proveniencia(origem="usuario", porque="")))
        raise AssertionError("deveria exigir porque")
    except ValueError:
        pass
    try:
        loja.gravar(**_valida(enunciado="   "))
        raise AssertionError("causa sem enunciado é rótulo, deveria falhar")
    except ValueError:
        pass


def test_atitude_invalida_e_recusada():
    _ws()
    loja = _loja("c3.yaml")
    try:
        loja.gravar(**_valida(atitude="dar_um_jeito"))
        raise AssertionError("atitude fora do vocabulário deveria falhar")
    except ValueError:
        pass
    c = loja.gravar(**_valida(atitude="aceitar"))
    assert c.atitude == "aceitar"
    assert "aceitar" in ATITUDES


# ------------------------------------------------------------------ ciclo

def test_decidir_registra_atitude_depois():
    """Entender e decidir são momentos diferentes, às vezes com semanas entre eles."""
    _ws()
    loja = _loja("c4.yaml")
    c = loja.gravar(**_valida())
    assert c.atitude == "nenhuma"
    d = loja.decidir(c.id, "reduzir", "vou cozinhar no domingo para a semana")
    assert d.atitude == "reduzir"
    assert _loja("c4.yaml").causas[c.id].atitude == "reduzir"


def test_causa_vencida_sai_das_ativas():
    _ws()
    loja = _loja("c5.yaml")
    ontem = (date.today() - timedelta(days=1)).isoformat()
    c = loja.gravar(**_valida(revisar_em=ontem))
    assert c.vencida() is True
    assert c.id not in {x.id for x in loja.ativas()}
    assert c.id in {x.id for x in loja.vencidas()}


def test_agente_nao_derruba_causa_do_usuario():
    _ws()
    loja = _loja("c6.yaml")
    loja.gravar(**_valida(enunciado="é jornada dupla, não dá para cozinhar"))
    loja.gravar(**_valida(
        enunciado="parece preguiça de cozinhar",
        proveniencia=Proveniencia(origem="agente", confianca=0.9, porque="o padrão é noturno"),
    ))
    unica = list(loja.causas.values())[0]
    assert unica.proveniencia.origem == "usuario"
    assert "jornada dupla" in unica.enunciado


# -------------------------------------------------------------- correlação

def test_alvo_liga_causa_ao_dinheiro():
    _ws()
    loja = _loja("c7.yaml")
    c = loja.gravar(**_valida())
    assert c.alvo == "categoria:alimentacao"
    assert loja.por_alvo()["categoria:alimentacao"][0]["id"] == c.id
    assert loja.para("categoria", "alimentacao")[0].id == c.id


def test_cobertura_causal_comeca_em_zero_e_sobe():
    ws = _ws()
    stmt = report.load_statement(ws)
    st = report.stores(ws)
    report.enrich(ws, stmt, st)

    loja = _loja("c8.yaml")
    zero = loja.cobertura(stmt)
    assert zero["cobertura_pct"] == 0.0
    assert zero["com_causa"] == 0.0
    assert zero["maiores_sem_causa"], "deveria listar onde falta explicação"

    maior = zero["maiores_sem_causa"][0]["categoria"]
    loja.gravar(**_valida(efeito_ref=maior))
    depois = loja.cobertura(stmt)
    assert depois["cobertura_pct"] > 0
    assert depois["com_causa"] > 0
    assert maior not in [l["categoria"] for l in depois["maiores_sem_causa"]]


# ------------------------------------------------------------------ triagem

def test_triagem_cobra_causa_atitude_e_revisao():
    ws = _ws()
    ctx = report.analyze(ws)
    tipos = {i["tipo"] for i in ctx["triagem"]["itens"]}
    assert "causa_ausente" in tipos, "dinheiro sem explicação deveria entrar na fila"

    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    report.enrich(ws, stmt, st)
    cob = st["causas"].cobertura(stmt)
    alvo = cob["maiores_sem_causa"][0]["categoria"]

    st["causas"].gravar(**_valida(efeito_ref=alvo))           # sem atitude
    ctx2 = report.analyze(ws, st=st)
    tipos2 = {i["tipo"] for i in ctx2["triagem"]["itens"]}
    assert "causa_sem_atitude" in tipos2, "causa entendida e não decidida deveria voltar"

    ids = [c["id"] for c in ctx2["causas"]["itens"]]
    st["causas"].decidir(ids[0], "aceitar", "é o custo de trabalhar à noite")
    ctx3 = report.analyze(ws, st=st)
    assert "causa_sem_atitude" not in {i["tipo"] for i in ctx3["triagem"]["itens"]}


def test_contexto_unico_carrega_causas_e_cobertura():
    ws = _ws()
    ctx = report.analyze(ws)
    assert "causas" in ctx
    assert ctx["causas"]["cobertura"]["cobertura_pct"] == 0.0
    assert ctx["causas"]["itens"] == []
    assert ctx["causas"]["por_alvo"] == {}


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"ERRO {name}: {type(e).__name__}: {e}")
    raise SystemExit(1 if fails else 0)
