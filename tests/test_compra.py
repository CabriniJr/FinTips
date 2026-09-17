"""Testes da compra lida à luz do perfil e das causas.

O cenário que estes testes protegem é o que o produto promete: a pessoa diz
"quero comprar um tablet", o agente carrega o contexto e responde com o que
sabe sobre *ela* — não só com o saldo.

A propriedade que não pode quebrar: contexto pessoal informa, nunca decide. O
veredito continua saindo da conta (reserva, planos, arrependimento). Se um
traço de perfil começar a mudar veredito sozinho, o motor voltou a opinar.
"""

from __future__ import annotations

import shutil
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fintips import purchases, report  # noqa: E402
from fintips.contracts import Proveniencia  # noqa: E402
from fintips.workspace import Workspace  # noqa: E402

FIXTURE = Path(__file__).parent / "fixture.ofx"
TMP = Path("/tmp/fintips-compra-test")


def _cenario(*, assinar=None, causa=None):
    if TMP.exists():
        shutil.rmtree(TMP)
    ws = Workspace.open(TMP)
    shutil.copy(FIXTURE, ws.extratos / "fixture.ofx")
    report.ingest(ws, ws.extratos / "fixture.ofx")
    st = report.stores(ws)
    if assinar:
        eixo, arq, porque = assinar
        st["perfil"].assinar(eixo, arq, proveniencia=Proveniencia(origem="usuario", porque=porque))
    if causa:
        st["causas"].gravar(
            efeito_tipo="categoria", efeito_ref=causa["ref"], natureza=causa["natureza"],
            enunciado=causa["enunciado"], atitude=causa.get("atitude", "nenhuma"),
            proveniencia=Proveniencia(origem="usuario", porque="contado na conversa"),
        )
    stmt = report.load_statement(ws, st)
    report.enrich(ws, stmt, st)
    ctx = report.analyze(ws, stmt=stmt, st=st)
    return ws, stmt, ctx


def _avaliar(ctx, stmt, *, item="Tablet S11", preco=4200, categoria="compras"):
    intent = purchases.PurchaseIntent(
        item=item, preco=Decimal(str(preco)), categoria=categoria,
    )
    return purchases.evaluate(
        intent, stmt, ctx["baseline"], ctx["planos"],
        saldo_conta=ctx["saldo_conta"],
        patrimonio=ctx["patrimonio"].get("total", 0),
        reserva_alvo_meses=float(ctx["baseline"].get("reserva_alvo_meses", 6)),
        perfil=ctx.get("perfil"),
        causas=(ctx.get("causas") or {}).get("itens"),
    )


# --------------------------------------------------- contexto não vira veredito

def test_perfil_e_causa_nao_mudam_o_veredito():
    """A conta é a conta. Perfil e causa dizem o que reler, não o que decidir."""
    _, stmt_sem, ctx_sem = _cenario()
    sem = _avaliar(ctx_sem, stmt_sem)

    _, stmt_com, ctx_com = _cenario(
        assinar=("renda", "variavel", "sou PJ"),
        causa={"ref": "compras", "natureza": "gatilho",
               "enunciado": "compro eletrônico quando fecho um projeto grande"},
    )
    com = _avaliar(ctx_com, stmt_com)

    assert sem["veredito"] == com["veredito"]
    assert sem["score_prudencia"] == com["score_prudencia"]
    assert sem["reserva"] == com["reserva"]


def test_sem_perfil_assinado_o_motor_avisa():
    _, stmt, ctx = _cenario()
    cp = _avaliar(ctx, stmt)["contexto_pessoal"]
    assert cp["sem_perfil_assinado"] is True
    assert cp["tracos_aplicados"] == []


# ------------------------------------------------------------------- perfil

def test_traco_assinado_traz_o_que_reler_e_o_porque():
    _, stmt, ctx = _cenario(assinar=("renda", "variavel", "sou PJ, fecho por projeto"))
    cp = _avaliar(ctx, stmt)["contexto_pessoal"]
    traco = cp["tracos_aplicados"][0]
    assert traco["eixo"] == "renda"
    assert traco["porque_foi_assinado"] == "sou PJ, fecho por projeto"
    assert "pior mês" in traco["o_que_muda"]
    # o texto descreve o cálculo, nunca a ação
    for proibido in ("não compre", "evite", "recomendamos", "você deveria"):
        assert proibido not in traco["o_que_muda"].lower()


def test_leitura_alternativa_nao_substitui_o_alvo_declarado():
    """Renda variável sugere reserva maior — ao lado da original, nunca no lugar."""
    _, stmt, ctx = _cenario(assinar=("renda", "variavel", "sou PJ"))
    res = _avaliar(ctx, stmt)
    alt = res["contexto_pessoal"]["leitura_alternativa_da_reserva"]
    assert alt is not None
    assert alt["reserva_alvo_meses"] == 9.0
    assert res["reserva"]["alvo_meses"] == 6.0, "o alvo declarado foi trocado por baixo do pano"
    assert alt["reserva_alvo_valor"] > res["reserva"]["alvo_valor"]


def test_traco_sem_efeito_mapeado_nao_inventa_leitura():
    _, stmt, ctx = _cenario(assinar=("fase", "acumulacao", "junto todo mês"))
    cp = _avaliar(ctx, stmt)["contexto_pessoal"]
    assert cp["tracos_aplicados"] == [], "arquétipo sem efeito mapeado não deve gerar texto"


# ------------------------------------------------------------------- causas

def test_causa_da_categoria_e_acionada_com_as_palavras_dela():
    frase = "compro eletrônico quando fecho um projeto grande, é meu jeito de comemorar"
    _, stmt, ctx = _cenario(causa={"ref": "compras", "natureza": "gatilho", "enunciado": frase})
    cp = _avaliar(ctx, stmt, categoria="compras")["contexto_pessoal"]
    assert len(cp["causas_acionadas"]) == 1
    c = cp["causas_acionadas"][0]
    assert c["nas_palavras_dela"] == frase
    assert c["natureza"] == "gatilho"
    assert "frase dela" in c["como_usar"]


def test_causa_de_outra_categoria_nao_e_acionada():
    _, stmt, ctx = _cenario(causa={"ref": "alimentacao", "natureza": "necessidade",
                                   "enunciado": "almoço fora todo dia útil"})
    cp = _avaliar(ctx, stmt, categoria="compras")["contexto_pessoal"]
    assert cp["causas_acionadas"] == []


def test_causa_aceita_vira_pedido_de_nao_cobrar():
    """Se a pessoa já decidiu aceitar, voltar a cobrar é o jeito de perdê-la."""
    _, stmt, ctx = _cenario(causa={
        "ref": "compras", "natureza": "compensacao", "atitude": "aceitar",
        "enunciado": "é o único luxo que eu me dou no ano",
    })
    c = _avaliar(ctx, stmt, categoria="compras")["contexto_pessoal"]["causas_acionadas"][0]
    assert c["ja_decidido"] is True
    assert "não transforme isso em cobrança" in c["como_usar"]


def test_contexto_pessoal_declara_que_nao_decide():
    _, stmt, ctx = _cenario(assinar=("renda", "variavel", "sou PJ"))
    cp = _avaliar(ctx, stmt)["contexto_pessoal"]
    assert "nenhum destes itens muda o veredito" in cp["nota"]


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
