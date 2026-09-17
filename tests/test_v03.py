"""Testes da inversão v0.3: proveniência, taxonomia, regras, contexto, triagem.

A propriedade que estes testes protegem é uma só: **o app não conclui nada
sozinho**. Heurística é sinal, decisão é do agente ou do usuário, e nada vira
número sem carregar quem decidiu.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fintips import mapping, report, triage as triage_mod  # noqa: E402
from fintips.commitments import CommitmentStore  # noqa: E402
from fintips.context import ContextStore  # noqa: E402
from fintips.contracts import AUTORIDADE, Condicao, Proveniencia  # noqa: E402
from fintips.taxonomy import Taxonomy  # noqa: E402
from fintips.workspace import Workspace  # noqa: E402

FIXTURE = Path(__file__).parent / "fixture.ofx"
TMP = Path("/tmp/fintips-v03")


def _ws() -> Workspace:
    if TMP.exists():
        shutil.rmtree(TMP)
    ws = Workspace.open(TMP)
    shutil.copy(FIXTURE, ws.extratos / "fixture.ofx")
    return ws


# --------------------------------------------------------------- proveniência

def test_autoridade_tem_ordem_e_heuristica_nao_e_verdade():
    assert AUTORIDADE["usuario"] > AUTORIDADE["agente"] > AUTORIDADE["importacao"] > AUTORIDADE["heuristica"]
    assert Proveniencia(origem="heuristica").e_verdade is False
    assert Proveniencia(origem="agente").e_verdade is True
    assert Proveniencia(origem="usuario").e_verdade is True


def test_heuristica_nao_sobrescreve_decisao_do_usuario():
    tax = Taxonomy(TMP / "tax.yaml")
    tax.criar("lazer", "Lazer do usuário",
              proveniencia=Proveniencia(origem="usuario", confianca=1.0, porque="ele disse"))
    tax.criar("lazer", "Lazer da heurística",
              proveniencia=Proveniencia(origem="heuristica", confianca=0.9, porque="palpite"))
    assert tax.get("lazer").nome == "Lazer do usuário"


def test_fato_de_menor_autoridade_nao_apaga_o_de_maior():
    loja = ContextStore(TMP / "ctx.yaml")
    loja.gravar("moradia.situacao", "aluguel",
                proveniencia=Proveniencia(origem="usuario", confianca=1.0, porque="afirmou"))
    loja.gravar("moradia.situacao", "com_familia",
                proveniencia=Proveniencia(origem="agente", confianca=0.6, porque="palpite meu"))
    assert loja.valor("moradia.situacao") == "aluguel"


# -------------------------------------------------------------------- regras

def test_regra_exige_condicao_e_efeito():
    loja = mapping.RuleStore(TMP / "regras.yaml")
    for quando, entao in [({}, {"categoria": "lazer"}), ({"canal": "pix"}, {})]:
        try:
            loja.criar(quando, entao)
            raise AssertionError(f"deveria recusar quando={quando} entao={entao}")
        except ValueError:
            pass


def test_regra_recusa_regex_invalida():
    loja = mapping.RuleStore(TMP / "regras2.yaml")
    try:
        loja.criar({"memo_casa": "(nao fecha"}, {"categoria": "lazer"})
        raise AssertionError("deveria recusar regex inválida")
    except ValueError:
        pass


def test_precedencia_autoridade_antes_de_especificidade():
    """Regra do usuário vence a do agente mesmo sendo menos específica."""
    ws = _ws()
    st = report.stores(ws)
    st["taxonomia"].criar("lazer", "Lazer", proveniencia=Proveniencia(origem="usuario", porque="t"))
    st["taxonomia"].criar("mercado", "Mercado", proveniencia=Proveniencia(origem="usuario", porque="t"))

    st["regras"].criar(
        {"canal": "debit_card", "valor_min": 1, "valor_max": 100},   # mais específica
        {"categoria": "mercado"},
        proveniencia=Proveniencia(origem="agente", confianca=0.9, porque="agente achou"),
    )
    st["regras"].criar(
        {"canal": "debit_card"},                                      # menos específica
        {"categoria": "lazer"},
        proveniencia=Proveniencia(origem="usuario", confianca=1.0, porque="usuário mandou"),
    )
    stmt = report.load_statement(ws, st)
    cartao = [t for t in stmt.transactions if t.channel == "debit_card"]
    assert cartao, "a fixture tem compras no débito"
    assert all(t.category == "lazer" for t in cartao)
    assert all(t.category_source == "usuario" for t in cartao)


def test_cobertura_distingue_decisao_de_palpite():
    ws = _ws()
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    antes = mapping.cobertura(stmt)
    assert antes["cobertura_pct"] == 0.0, "sem regras, tudo é palpite"

    st["taxonomia"].criar("lazer", "Lazer", proveniencia=Proveniencia(origem="usuario", porque="t"))
    st["regras"].criar({"canal": "debit_card"}, {"categoria": "lazer"},
                       proveniencia=Proveniencia(origem="usuario", confianca=1.0, porque="t"))
    stmt = report.load_statement(ws, st)
    assert mapping.cobertura(stmt)["cobertura_pct"] > 0


# -------------------------------------------------------------- compromissos

def test_custo_fixo_so_existe_quando_definido():
    ws = _ws()
    ctx = report.analyze(ws)
    assert ctx["estrutura_de_custo"]["comprometido_mes"] == 0.0
    assert ctx["custos_fixos"] == []
    # a detecção continua rodando, mas como candidato
    assert isinstance(ctx["candidatos_custo_fixo"], list)


def test_definir_custo_fixo_calcula_pelo_extrato():
    ws = _ws()
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    loja: CommitmentStore = st["compromissos"]
    item = loja.definir(
        "Transporte de rotina", "categoria", "transporte",
        metodo="mediana_meses_completos", natureza="rotina",
        proveniencia=Proveniencia(origem="usuario", confianca=1.0, porque="uso diário"),
        stmt=stmt,
    )
    assert item.valor_mensal > 0
    assert loja.total_mensal() == item.valor_mensal
    assert loja.por_natureza()["rotina"] == item.valor_mensal
    cats, _ = loja.coberturas()
    assert "transporte" in cats


def test_compromisso_sai_do_gasto_invisivel():
    ws = _ws()
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    antes = report.analyze(ws, st=st)["gastos_invisiveis"]["excluido_por_declaracao"]
    assert antes == []

    st["compromissos"].definir(
        "Transporte", "categoria", "transporte", valor_mensal=100.0,
        proveniencia=Proveniencia(origem="usuario", confianca=1.0, porque="rotina"),
    )
    depois = report.analyze(ws)["gastos_invisiveis"]["excluido_por_declaracao"]
    assert "transporte" in depois


# ------------------------------------------------------------------ triagem

def test_triagem_ordena_por_impacto_e_nao_repete_resolvido():
    ws = _ws()
    ctx = report.analyze(ws)
    itens = ctx["triagem"]["itens"]
    assert itens, "deveria haver itens em aberto"
    prioridades = [i["prioridade"] for i in itens if i["estado"] == "aberto"]
    assert prioridades == sorted(prioridades, reverse=True)
    assert all(i["porque_importa"] for i in itens), "todo item diz o que muda"

    alvo = itens[0]["id"]
    st = report.stores(ws)
    st["triagem"].resolver(alvo, {"o_que_foi_feito": "teste"})
    depois = report.analyze(ws)["triagem"]["itens"]
    assert alvo not in [i["id"] for i in depois]


def test_lacunas_do_nucleo_somem_ao_gravar_o_fato():
    ws = _ws()
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    from fintips.analysis import baseline

    loja: ContextStore = st["contexto"]
    lacunas = loja.lacunas(baseline(stmt))
    chaves = [l["chave"] for l in lacunas]
    assert "moradia.situacao" in chaves
    assert all(l["porque_importa"] for l in lacunas)

    loja.gravar("moradia.situacao", "aluguel",
                proveniencia=Proveniencia(origem="usuario", confianca=1.0, porque="afirmou"))
    assert "moradia.situacao" not in [l["chave"] for l in loja.lacunas(baseline(stmt))]


def test_fato_livre_convive_com_o_nucleo():
    """O híbrido: núcleo demarcado + especificidades sem mudar código."""
    loja = ContextStore(TMP / "ctx-livre.yaml")
    loja.gravar("transporte.reembolsado_pela_empresa", True,
                proveniencia=Proveniencia(origem="usuario", confianca=1.0, porque="RH reembolsa"))
    loja.gravar("reserva.alvo_meses", 3,
                proveniencia=Proveniencia(origem="usuario", confianca=1.0, porque="renda estável"))
    resumo = loja.resumo()
    assert resumo["nucleo"]["reserva.alvo_meses"] == 3
    assert resumo["especificos"]["transporte.reembolsado_pela_empresa"] is True
    assert resumo["cobertura"]["fatos_livres"] == 1


def test_chave_invalida_e_recusada():
    loja = ContextStore(TMP / "ctx-ruim.yaml")
    try:
        loja.gravar("chave com espaco", 1, proveniencia=Proveniencia(origem="usuario", porque="t"))
        raise AssertionError("deveria recusar chave com espaço")
    except ValueError:
        pass


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
