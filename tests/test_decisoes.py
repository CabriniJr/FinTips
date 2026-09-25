"""Testes da camada de decisão (v0.6).

O cenário que guia o módulo inteiro é o do celular quebrado: uma pergunta
pontual, duas ou três saídas com custos e prazos diferentes, uma escolha feita
sob condições específicas, e um desfecho que só se conhece meses depois.

Três propriedades importam mais que o resto, e são as que estes testes
protegem:

- **decisão não se deriva** — como a causa, ela nasce de `agente` ou `usuario`.
  O extrato mostra R$ 2.500 numa loja de eletrônicos; ele não sabe se foi troca
  planejada, emergência ou presente para outra pessoa.
- **as alternativas descartadas sobrevivem** — é metade do valor do registro, e
  a parte que qualquer implementação ingênua joga fora ao guardar só a escolha.
- **o instantâneo congela** — decisão julgada pelos números de hoje é injusta
  com quem decidiu com os números de então.
"""

from __future__ import annotations

import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fintips import decisions as dec_mod, purchases, report, triage  # noqa: E402
from fintips.contracts import Alternativa, Proveniencia  # noqa: E402
from fintips.workspace import Workspace  # noqa: E402

FIXTURE = Path(__file__).parent / "fixture.ofx"
TMP = Path("/tmp/fintips-decisoes")

CELULAR = [
    {"nome": "consertar", "custo": 700, "horizonte_meses": 8,
     "consequencia": "aparelho volta, sem garantia de placa",
     "descartada_porque": "assistência não cobre a placa, que é o que quebrou"},
    {"nome": "comprar novo", "custo": 2500, "horizonte_meses": 36,
     "consequencia": "some a reserva de dois meses, e resolve por três anos"},
    {"nome": "usar o antigo", "custo": 0, "horizonte_meses": 3,
     "consequencia": "sem custo agora, mas a bateria não passa da tarde",
     "descartada_porque": "não aguenta o dia de trabalho"},
]


def _ws() -> Workspace:
    if TMP.exists():
        shutil.rmtree(TMP)
    ws = Workspace.open(TMP)
    shutil.copy(FIXTURE, ws.extratos / "fixture.ofx")
    report.ingest(ws, ws.extratos / "fixture.ofx")
    return ws


def _loja(ws: Workspace | None = None) -> dec_mod.DecisionStore:
    return dec_mod.DecisionStore((ws.root if ws else TMP) / "data" / "decisoes.yaml")


def _prov(origem: str = "usuario", porque: str = "o celular caiu e parou de carregar") -> Proveniencia:
    return Proveniencia(origem=origem, confianca=1.0, porque=porque)


def _abrir(loja, **kw):
    campos = dict(
        titulo="Celular quebrou", situacao="caiu na terça, tela e carregamento",
        pergunta="consertar, trocar ou aguentar?", tipo="troca",
        alternativas=CELULAR, proveniencia=_prov(),
        ligacoes=["categoria:eletronicos"],
    )
    campos.update(kw)
    return loja.abrir(**campos)


# --------------------------------------------------------------------------
# a propriedade central: o app não inventa decisão
# --------------------------------------------------------------------------

def test_decisao_nao_se_deriva_dos_dados():
    loja = _loja(_ws())
    for origem in ("heuristica", "importacao"):
        try:
            _abrir(loja, proveniencia=Proveniencia(origem=origem, confianca=1.0, porque="x"))
        except ValueError as e:
            assert "agente" in str(e), e
        else:
            raise AssertionError(f"origem '{origem}' não deveria abrir decisão")


def test_nao_existe_deteccao_de_decisao_no_modulo():
    fonte = Path(dec_mod.__file__).read_text(encoding="utf-8")
    for proibido in ("def detectar", "def inferir_decis", "def deduzir"):
        assert proibido not in fonte, (
            f"'{proibido}' apareceu em decisions.py — decisão não se deriva do extrato"
        )


def test_uma_alternativa_so_nao_e_decisao():
    loja = _loja(_ws())
    try:
        _abrir(loja, alternativas=[CELULAR[0]])
    except ValueError as e:
        assert "duas" in str(e), e
    else:
        raise AssertionError("aceitou decisão com uma alternativa só")


# --------------------------------------------------------------------------
# o que o registro precisa preservar
# --------------------------------------------------------------------------

def test_alternativa_descartada_sobrevive_com_o_motivo():
    loja = _loja(_ws())
    d = _abrir(loja)
    loja.escolher(d.id, "comprar novo", "o conserto não cobria a placa")

    precedente = _loja().semelhantes("celular")[0]
    descartadas = {a["nome"]: a["descartada_porque"] for a in precedente["descartou"]}
    assert "consertar" in descartadas, "a alternativa descartada sumiu do precedente"
    assert "placa" in descartadas["consertar"], descartadas
    assert "usar o antigo" in descartadas, "só a primeira descartada foi guardada"


def test_custo_por_mes_de_uso_compara_prazos_diferentes():
    # é a conta que decide a troca e que ninguém faz de cabeça:
    # R$ 700 por 8 meses custam mais por mês que R$ 2.500 por 36.
    consertar = Alternativa(nome="consertar", custo=700, horizonte_meses=8)
    novo = Alternativa(nome="novo", custo=2500, horizonte_meses=36)
    assert consertar.custo_por_mes_de_uso == 87.5, consertar.custo_por_mes_de_uso
    assert novo.custo_por_mes_de_uso == 69.44, novo.custo_por_mes_de_uso
    assert consertar.custo_por_mes_de_uso > novo.custo_por_mes_de_uso

    # sem horizonte declarado o motor não inventa vida útil
    assert Alternativa(nome="x", custo=700).custo_por_mes_de_uso is None


def test_plano_mensal_entra_no_custo_do_horizonte():
    # um plano de celular de R$ 90/mês por 36 meses custa mais que o aparelho
    com_plano = Alternativa(nome="com plano", custo=0, custo_mensal=90, horizonte_meses=36)
    assert com_plano.custo_no_horizonte == 3240.0, com_plano.custo_no_horizonte


def test_instantaneo_congela_os_numeros_da_epoca():
    ws = _ws()
    ctx = report.analyze(ws)
    loja = _loja(ws)
    d = _abrir(loja, instantaneo=dec_mod.instantaneo_de(ctx))

    assert d.instantaneo["sobra_media_mes"] == ctx["baseline"]["sobra_media_mes"]
    assert d.instantaneo["em"] == date.today().isoformat()
    # o instantâneo tem que trazer o score de verdade: um snapshot que grava
    # None em silêncio não serve para julgar a escolha depois
    assert d.instantaneo["score"] == ctx["score"]["score"], d.instantaneo
    assert d.instantaneo["reserva_meses"] == ctx["score"]["indicadores"]["meses_de_reserva"]

    # e continua valendo o de então, mesmo que a análise mude depois
    relido = _loja(ws).decisoes[d.id]
    assert relido.instantaneo["sobra_media_mes"] == ctx["baseline"]["sobra_media_mes"]
    assert "no dia da decisão" in relido.instantaneo["nota"]


# --------------------------------------------------------------------------
# o ciclo: abrir, escolher, saber no que deu
# --------------------------------------------------------------------------

def test_escolher_exige_alternativa_que_existe():
    loja = _loja(_ws())
    d = _abrir(loja)
    try:
        loja.escolher(d.id, "financiar em 24x", "pareceu melhor")
    except ValueError as e:
        assert "não está entre as alternativas" in str(e), e
    else:
        raise AssertionError("aceitou escolha que não estava na mesa")


def test_desfecho_so_existe_depois_da_escolha():
    loja = _loja(_ws())
    d = _abrir(loja)
    try:
        loja.registrar_desfecho(d.id, "funcionou")
    except ValueError as e:
        assert "ainda não foi tomada" in str(e), e
    else:
        raise AssertionError("registrou desfecho de decisão em aberto")


def test_cedo_para_saber_nao_fecha_a_decisao():
    loja = _loja(_ws())
    d = _abrir(loja)
    loja.escolher(d.id, "comprar novo", "resolvia por três anos")
    loja.registrar_desfecho(d.id, "cedo_para_saber", "comprei semana passada")

    relida = loja.decisoes[d.id]
    assert relida.status == "decidida", "cedo_para_saber não pode fechar a decisão"
    assert not relida.aprendeu, "veredito provisório não pode virar aprendizado"
    assert relida.id in {x.id for x in loja.sem_desfecho(date.today() + timedelta(days=200))}


def test_substituir_preserva_a_decisao_anterior():
    loja = _loja(_ws())
    antiga = _abrir(loja)
    loja.escolher(antiga.id, "consertar", "era o mais barato agora")
    nova = _abrir(loja, titulo="Celular quebrou de novo",
                  situacao="o conserto durou seis semanas", substitui=antiga.id)

    relida = loja.decisoes[antiga.id]
    assert relida.status == "substituida", relida.status
    assert relida.substituida_por == nova.id
    assert antiga.id in loja.decisoes, "a decisão substituída sumiu do histórico"


# --------------------------------------------------------------------------
# histórico: decidir a próxima com o que se aprendeu na anterior
# --------------------------------------------------------------------------

def test_precedente_aparece_na_proxima_decisao_parecida():
    loja = _loja(_ws())
    d = _abrir(loja)
    loja.escolher(d.id, "consertar", "não tinha R$ 2.500 naquele mês")
    loja.registrar_desfecho(d.id, "arrependi", "durou seis semanas e gastei de novo")

    achados = loja.semelhantes("celular novo", tipo="troca",
                               ligacoes=["categoria:eletronicos"])
    assert achados, "o precedente óbvio não foi encontrado"
    assert achados[0]["deu_em"] == "arrependi"
    assert achados[0]["porque"] == "não tinha R$ 2.500 naquele mês"
    assert "numeros_da_epoca" in achados[0], "precedente sem as condições da época"
    assert "precedente, não regra" in achados[0]["como_usar"]


def test_historico_vazio_nao_inventa_precedente():
    loja = _loja(_ws())
    assert loja.semelhantes("celular") == []
    ap = loja.aprendizados()
    assert ap["decisoes_registradas"] == 0
    assert ap["cobertura_de_desfecho_pct"] == 0.0


def test_aprendizado_sai_de_desfecho_declarado_e_nao_do_extrato():
    loja = _loja(_ws())
    for i, veredito in enumerate(("arrependi", "funcionou")):
        d = _abrir(loja, titulo=f"Troca {i}")
        loja.escolher(d.id, "comprar novo", "porque sim")
        loja.registrar_desfecho(d.id, veredito)

    ap = loja.aprendizados()
    assert ap["por_tipo"]["troca"]["taxa_arrependimento_pct"] == 50.0, ap["por_tipo"]
    assert len(ap["arrependimentos"]) == 1
    assert "não deduz arrependimento do extrato" in ap["explicacao"]


def test_compra_recebe_os_precedentes_sem_mudar_o_veredito():
    ws = _ws()
    loja = _loja(ws)
    d = _abrir(loja, tipo="compra")
    loja.escolher(d.id, "comprar novo", "queria a câmera")
    loja.registrar_desfecho(d.id, "arrependi", "usei a câmera duas vezes")

    ctx = report.analyze(ws)
    stmt = report.load_statement(ws)
    intent = purchases.PurchaseIntent(item="celular novo", preco=2500, categoria="eletronicos")
    args = dict(saldo_conta=stmt.ledger_balance, patrimonio=0)

    sem = purchases.evaluate(intent, stmt, ctx["baseline"], ctx["planos"], **args)
    com = purchases.evaluate(
        intent, stmt, ctx["baseline"], ctx["planos"],
        precedentes=loja.semelhantes("celular novo eletronicos", tipo="compra",
                                     ligacoes=["categoria:eletronicos"]),
        aprendizados=loja.aprendizados(), **args)

    assert com["veredito"] == sem["veredito"], (
        "precedente mudou o veredito calculado — ele informa a conversa, não o motor"
    )
    assert com["score_prudencia"] == sem["score_prudencia"]
    assert com["precedentes"]["quantas"] == 1
    assert com["precedentes"]["arrependimentos_parecidos"] == 1
    assert com["precedentes"]["o_que_perguntar"], "não sobrou nada para perguntar"
    assert sem["precedentes"]["sem_historico"] is True


# --------------------------------------------------------------------------
# a fila: o que a triagem cobra
# --------------------------------------------------------------------------

def test_triagem_cobra_decisao_aberta_e_desfecho():
    ws = _ws()
    loja = _loja(ws)
    aberta = _abrir(loja)
    decidida = _abrir(loja, titulo="Notebook velho")
    loja.escolher(decidida.id, "comprar novo", "o antigo não liga mais")
    # empurra a decisão para trás no tempo, para cobrar o desfecho
    loja.decisoes[decidida.id].decidido_em = (
        date.today() - timedelta(days=200)).isoformat() + "T12:00:00"
    loja.save()

    ctx = report.analyze(ws)
    tipos = {i["tipo"]: i for i in ctx["triagem"]["itens"]}

    assert "decisao_aberta" in tipos, "decisão em aberto não entrou na fila"
    assert aberta.id in tipos["decisao_aberta"]["evidencia"]["decisao_id"]
    assert "decisao_sem_desfecho" in tipos, "ninguém cobrou o que deu na decisão tomada"
    assert tipos["decisao_sem_desfecho"]["evidencia"]["escolheu"] == "comprar novo"


def test_decisao_aberta_pesa_mais_que_pendencia_de_dado():
    # é a única fila em que a pessoa está esperando para agir; o resto é o
    # motor esperando dados.
    from fintips.contracts import ItemDeTriagem

    def item(tipo):
        return ItemDeTriagem(id=tipo, tipo=tipo, titulo="x", impacto_mensal=100,
                             porque_importa="")

    decisao, fato = item("decisao_aberta"), item("fato_ausente")
    assert decisao.prioridade > fato.prioridade, (decisao.prioridade, fato.prioridade)


def test_analise_publica_decisoes_sem_derramar_o_historico():
    ws = _ws()
    loja = _loja(ws)
    for i in range(20):
        _abrir(loja, titulo=f"Decisão {i}")

    bloco = report.analyze(ws)["decisoes"]
    assert len(bloco["linha_do_tempo"]) == 12, "a análise carregou o histórico inteiro"
    assert bloco["aprendizados"]["decisoes_registradas"] == 20


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
