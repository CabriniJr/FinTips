"""As seis frentes como contexto de decisão financeira.

O que estes testes protegem não é cálculo — é a fronteira entre o que o motor
calcula e o que ele não tem o direito de concluir. Toda vez que um deles
quebrar, o app terá começado a opinar no lugar da pessoa.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from fintips.life import (
    ATRIBUTOS,
    Missao,
    RegistroDeMissao,
    Vida,
    carregar,
    cobertura_de_evidencia,
    contexto_de_compra,
    contexto_de_planos,
    estado_diario,
    forca_dos_atributos,
    registrar,
)

HOJE = date(2026, 10, 14)

SEM_TELA = Missao(
    id="foc-sem-video-curto",
    titulo="Sem vídeo curto",
    atributo="FOC",
    cadencia="diaria",
    como_medir="tempo de tela em zero",
    sensor_possivel=True,
    porque="corte total, sem moderação — força de vontade sozinha já falhou",
    colide_com=["tablet", "celular", "streaming"],
)

LEITURA = Missao(
    id="int-leitura",
    titulo="Leitura",
    atributo="INT",
    cadencia="diaria",
)

APORTE = Missao(
    id="ouro-aporte-do-mes",
    titulo="Aporte do mês",
    atributo="OURO",
    cadencia="mensal",
    como_medir="transferido nas datas combinadas",
    valor_mensal=Decimal("1000"),
)


def reg(missao, dia, origem, medida=""):
    return RegistroDeMissao(missao.id, date(2026, 10, dia), origem, medida)


# ------------------------------------------------------------ proveniência


def test_presumido_nunca_conta_como_cumprido():
    # O app supor que você treinou não é você ter treinado.
    assert not reg(LEITURA, 14, "presumido").conta_como_cumprido
    for origem in ("agente", "sensor", "usuario"):
        assert reg(LEITURA, 14, origem).conta_como_cumprido


def test_sensor_vence_agente_e_pessoa_vence_sensor():
    from fintips.life import ORIGENS_DO_REGISTRO as O

    assert O["sensor"] > O["agente"]     # medida vale mais que interpretação
    assert O["usuario"] > O["sensor"]    # quem mede não entende contexto


def test_origem_invalida_falha_em_vez_de_virar_presumido():
    with pytest.raises(ValueError, match="origem 'palpite' não existe"):
        RegistroDeMissao.from_dict({"missao_id": "x", "dia": "2026-10-14", "origem": "palpite"})


# ---------------------------------------------------------------- sequência


def test_hoje_vazio_nao_quebra_sequencia_e_recorde_sobrevive_a_recaida():
    registros = [reg(SEM_TELA, d, "sensor") for d in (1, 2, 3, 4, 5, 6, 7, 9, 10)]
    e = estado_diario(SEM_TELA, registros, date(2026, 10, 11))
    assert e["sequencia"] == 2, "o dia de hoje ainda não acabou"
    assert e["recorde"] == 7, "zerar o recorde transformaria um tropeço em perda total"


def test_registro_presumido_abre_buraco_na_sequencia():
    registros = [
        reg(LEITURA, 11, "usuario"),
        reg(LEITURA, 12, "presumido"),
        reg(LEITURA, 13, "usuario"),
        reg(LEITURA, 14, "usuario"),
    ]
    assert estado_diario(LEITURA, registros, HOJE)["sequencia"] == 2


# ---------------------------------------------------------------- atributos


def test_as_seis_frentes_aparecem_mesmo_vazias():
    # Frente sem missão é informação: mostra o que a pessoa não treina.
    f = forca_dos_atributos([SEM_TELA], [], HOJE)
    assert [x["atributo"] for x in f] == list(ATRIBUTOS)
    assert next(x for x in f if x["atributo"] == "OURO")["missoes"] == 0


def test_cobertura_separa_medida_de_memoria():
    c = cobertura_de_evidencia([SEM_TELA, LEITURA], [reg(SEM_TELA, 14, "sensor", "0 min")])
    assert c["missoes_ativas"] == 2
    assert c["mensuraveis_por_aparelho"] == 1
    assert c["com_medida_registrada"] == 1
    assert c["pct_medido"] == 50.0


# ------------------------------------------------- a ponte com o dinheiro


def test_colisao_existe_so_porque_a_pessoa_declarou():
    """O centro do módulo: o motor não decide que tablet é vício."""
    vida = Vida(missoes=[SEM_TELA, LEITURA, APORTE])
    ctx = contexto_de_compra(vida, item="Tablet S11", preco=Decimal("2500"), hoje=HOJE)

    foc = [m for m in ctx["missoes_em_jogo"] if m["atributo"] == "FOC"]
    assert len(foc) == 1
    assert foc[0]["colisao_declarada"] == "tablet"
    assert "a pessoa declarou" in foc[0]["por_que_entra_aqui"]
    assert "força de vontade" in foc[0]["porque_da_missao"]

    # A leitura não colide com nada, e não entra — o motor não varre frentes
    # procurando o que possa parecer relacionado.
    assert "int-leitura" not in [m["missao"] for m in ctx["missoes_em_jogo"]]


def test_sem_declaracao_nao_ha_colisao_nem_que_a_palavra_bata():
    sem_colisao = Missao(
        id="foc-sem-video-curto", titulo="Sem vídeo curto",
        atributo="FOC", cadencia="diaria",
    )
    vida = Vida(missoes=[sem_colisao])
    ctx = contexto_de_compra(vida, item="Tablet S11", preco=Decimal("2500"), hoje=HOJE)
    assert ctx["missoes_em_jogo"] == []


def test_missao_de_dinheiro_entra_sempre():
    vida = Vida(missoes=[APORTE])
    ctx = contexto_de_compra(vida, item="Cafeteira", preco=Decimal("200"), hoje=HOJE)
    assert [m["missao"] for m in ctx["missoes_em_jogo"]] == ["ouro-aporte-do-mes"]
    assert "toda compra disputa" in ctx["missoes_em_jogo"][0]["por_que_entra_aqui"]


def test_preco_traduzido_em_meses_de_aporte():
    vida = Vida(missoes=[APORTE])
    ctx = contexto_de_compra(vida, item="Tablet", preco=Decimal("2500"), hoje=HOJE)
    assert ctx["custo_em_aportes"]["meses_de_aporte"] == 2.5


def test_sem_valor_mensal_nao_ha_traducao_inventada():
    sem_valor = Missao(id="ouro-x", titulo="Aporte", atributo="OURO", cadencia="mensal")
    ctx = contexto_de_compra(Vida(missoes=[sem_valor]), item="X", preco=Decimal("100"), hoje=HOJE)
    assert ctx["custo_em_aportes"] is None


# -------------------------------------------------- a regra que ela assinou


def _vida_com_regra(tmp_path: Path) -> Vida:
    p = tmp_path / "missoes.yaml"
    p.write_text(yaml.safe_dump({
        "missoes": [APORTE.to_dict()],
        "regras": [{
            "id": "espera-antes-de-comprar",
            "tipo": "espera_antes_de_comprar",
            "acima_de": 300,
            "dias": 30,
            "porque": "lista de desejos e 30 dias — impulso é o padrão a quebrar",
        }],
    }, allow_unicode=True), encoding="utf-8")
    return carregar(p)


def test_regra_declarada_aplica_acima_do_limite(tmp_path):
    vida = _vida_com_regra(tmp_path)
    ctx = contexto_de_compra(vida, item="Tablet", preco=Decimal("2500"), hoje=HOJE)
    r = ctx["regra_declarada"]
    assert r["aplica"] is True
    assert r["liberada_em"] == "2026-11-13"
    assert "lista de desejos" in r["porque_ela_escreveu"]


def test_regra_declarada_nao_aplica_abaixo_do_limite(tmp_path):
    vida = _vida_com_regra(tmp_path)
    ctx = contexto_de_compra(vida, item="Livro", preco=Decimal("90"), hoje=HOJE)
    assert ctx["regra_declarada"]["aplica"] is False
    assert ctx["regra_declarada"]["liberada_em"] is None


def test_regra_sem_porque_e_recusada(tmp_path):
    p = tmp_path / "missoes.yaml"
    p.write_text(yaml.safe_dump({"regras": [{
        "id": "espera", "tipo": "espera_antes_de_comprar", "acima_de": 300, "dias": 30,
    }]}, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="sem `porque`"):
        carregar(p)


def test_tipo_de_regra_desconhecido_quebra_em_vez_de_ser_ignorado(tmp_path):
    # Regra ignorada em silêncio é pior que regra inexistente: a pessoa pensa
    # que o app está aplicando algo que ele nunca leu.
    p = tmp_path / "missoes.yaml"
    p.write_text(yaml.safe_dump({"regras": [{
        "id": "x", "tipo": "proibir_tudo", "porque": "porque sim",
    }]}, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="não é suportado"):
        carregar(p)


# -------------------------------------------------------------- carregamento


def test_atributo_fora_das_seis_frentes_e_recusado():
    with pytest.raises(ValueError, match="atributo 'XP' não existe"):
        Missao.from_dict({"id": "x", "atributo": "XP", "cadencia": "diaria"})


def test_cadencia_inexistente_e_recusada():
    # Dentista a cada 6 meses não cabe: ou entra no enum, ou não existe.
    with pytest.raises(ValueError, match="cadência 'semestral' não existe"):
        Missao.from_dict({"id": "x", "atributo": "VIT", "cadencia": "semestral"})


def test_registro_de_missao_fora_do_catalogo_e_recusado(tmp_path):
    m = tmp_path / "missoes.yaml"
    m.write_text(yaml.safe_dump({"missoes": [LEITURA.to_dict()]}, allow_unicode=True), encoding="utf-8")
    r = tmp_path / "registros.jsonl"
    r.write_text(json.dumps({"missao_id": "fantasma", "dia": "2026-10-14", "origem": "usuario"}) + "\n",
                 encoding="utf-8")
    with pytest.raises(ValueError, match="não está no catálogo"):
        carregar(m, r)


def test_ausencia_de_catalogo_nao_e_erro(tmp_path):
    vida = carregar(tmp_path / "nao-existe.yaml", tmp_path / "nada.jsonl")
    assert vida.vazia
    assert vida.registros == []


def test_registro_e_append_e_nao_reescrita(tmp_path):
    p = tmp_path / "registros.jsonl"
    registrar(p, reg(LEITURA, 13, "usuario"))
    registrar(p, reg(LEITURA, 14, "sensor", "30 min"))
    linhas = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 2, "registro é histórico; append só sabe crescer"
    assert json.loads(linhas[0])["dia"] == "2026-10-13"


def test_o_exemplo_do_pacote_carrega():
    # Se o molde que acompanha o pacote não carrega, ninguém consegue começar.
    vida = carregar(Path("fintips/rules/exemplo-missoes.yaml"))
    assert len(vida.missoes) >= 10
    assert len(vida.regras) == 1
    assert any(m.colide_com for m in vida.missoes)
    assert any(m.valor_mensal for m in vida.missoes)


# -------------------------------------------------------------- com planos


def test_aporte_declarado_confrontado_com_os_planos():
    vida = Vida(missoes=[APORTE])
    planos = [
        {"nome": "Viagem", "aporte_necessario_mes": 400, "status": "no_ritmo"},
        {"nome": "Reserva", "aporte_necessario_mes": 300, "status": "apertado"},
        {"nome": "Antigo", "aporte_necessario_mes": 900, "status": "concluido"},
    ]
    c = contexto_de_planos(vida, planos)
    assert c["exigido_pelos_planos_mes"] == 700.0   # concluído não conta
    assert c["folga_mensal"] == 300.0
    assert c["planos_cabem_no_aporte"] is True


def test_sem_missao_de_aporte_o_motor_diz_que_nao_sabe():
    c = contexto_de_planos(Vida(), [{"nome": "X", "aporte_necessario_mes": 100}])
    assert c["missao_de_aporte"] is None
    assert "nenhuma missão de aporte" in c["nota"]


# ------------------------------- a compra avaliada com as seis frentes


def _cenario_de_compra(tmp_path, *, com_vida: bool, preco=2500):
    """Avalia a mesma compra com e sem catálogo de missões."""
    import shutil

    from fintips import purchases, report
    from fintips.workspace import Workspace

    raiz = tmp_path / ("com" if com_vida else "sem")
    ws = Workspace.open(raiz)
    shutil.copy(Path(__file__).parent / "fixture.ofx", ws.extratos / "fixture.ofx")
    report.ingest(ws, ws.extratos / "fixture.ofx")
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    report.enrich(ws, stmt, st)
    ctx = report.analyze(ws, stmt=stmt, st=st)

    vida = None
    if com_vida:
        ws.missoes_path.write_text(yaml.safe_dump({
            "missoes": [SEM_TELA.to_dict(), APORTE.to_dict()],
            "regras": [{
                "id": "espera-antes-de-comprar",
                "tipo": "espera_antes_de_comprar",
                "acima_de": 300, "dias": 30,
                "porque": "lista de desejos e 30 dias — impulso é o padrão a quebrar",
            }],
        }, allow_unicode=True), encoding="utf-8")
        vida = carregar(ws.missoes_path, ws.registros_path)

    intent = purchases.PurchaseIntent(
        item="Tablet S11", preco=Decimal(str(preco)), categoria="compras",
    )
    return purchases.evaluate(
        intent, stmt, ctx["baseline"], ctx["planos"],
        saldo_conta=ctx["saldo_conta"],
        patrimonio=ctx["patrimonio"].get("total", 0),
        vida=vida, hoje=HOJE,
    )


def test_a_regra_dela_muda_o_veredito_e_vai_nomeada(tmp_path):
    """A única coisa do contexto de vida com direito de mexer no veredito.

    E ela mexe porque é decisão que a pessoa já tomou, não leitura do motor
    sobre o histórico dela. Por isso vai nomeada, com o `porque` ao lado: a
    conversa cita a regra dela, nunca um conselho do app.
    """
    r = _cenario_de_compra(tmp_path, com_vida=True, preco=2500)
    assert r["veredito"] == "espere_30_dias"
    aplicada = r["regra_declarada_aplicada"]
    assert aplicada["regra"] == "espera-antes-de-comprar"
    assert "lista de desejos" in aplicada["porque_ela_escreveu"]
    assert aplicada["liberada_em"] == "2026-11-13"


def test_abaixo_do_limite_a_regra_nao_interfere(tmp_path):
    r = _cenario_de_compra(tmp_path, com_vida=True, preco=150)
    assert "regra_declarada_aplicada" not in r


def test_o_resto_do_contexto_de_vida_nao_mexe_em_numero(tmp_path):
    """Colisão, sequência e meses de aporte informam; não decidem.

    Comparado abaixo do limite da regra, para isolar: o que varia entre os
    dois lados é só a presença do contexto, nunca a conta.
    """
    com = _cenario_de_compra(tmp_path, com_vida=True, preco=150)
    sem = _cenario_de_compra(tmp_path, com_vida=False, preco=150)

    assert com["veredito"] == sem["veredito"]
    assert com["score_prudencia"] == sem["score_prudencia"]
    assert com["reserva"] == sem["reserva"]
    assert com["melhor_estrategia"] == sem["melhor_estrategia"]

    # Sem catálogo a resposta não ganha chave nenhuma: quem não usa a camada
    # recebe exatamente a forma que recebia antes dela existir.
    assert "contexto_de_vida" not in sem
    assert com["contexto_de_vida"]["missoes_em_jogo"]


def test_sem_catalogo_o_bloco_de_vida_nem_aparece(tmp_path):
    r = _cenario_de_compra(tmp_path, com_vida=False)
    assert "contexto_de_vida" not in r
    assert "regra_declarada_aplicada" not in r


# ------------------------------------------------- a API que o painel usa


def _cliente(tmp_path, *, com_missoes=True):
    import importlib
    import os
    import shutil

    os.environ["FINTIPS_ROOT"] = str(tmp_path / "ws")
    from fastapi.testclient import TestClient

    from fintips import api, report
    from fintips.workspace import Workspace

    importlib.reload(api)
    ws = Workspace.open(tmp_path / "ws")
    shutil.copy(Path(__file__).parent / "fixture.ofx", ws.extratos / "fixture.ofx")
    report.ingest(ws, ws.extratos / "fixture.ofx")
    if com_missoes:
        ws.missoes_path.write_text(yaml.safe_dump({
            "missoes": [SEM_TELA.to_dict(), LEITURA.to_dict(), APORTE.to_dict()],
        }, allow_unicode=True), encoding="utf-8")
    return TestClient(api.app), ws


def test_api_devolve_as_seis_barras(tmp_path):
    cliente, _ = _cliente(tmp_path)
    r = cliente.get("/api/life")
    assert r.status_code == 200
    d = r.json()
    assert [f["atributo"] for f in d["frentes"]] == list(ATRIBUTOS)
    assert {m["missao"] for m in d["missoes_do_dia"]} == {"foc-sem-video-curto", "int-leitura"}


def test_api_sem_catalogo_diz_onde_criar(tmp_path):
    cliente, ws = _cliente(tmp_path, com_missoes=False)
    d = cliente.get("/api/life").json()
    assert d["sem_missoes_cadastradas"] is True
    assert d["molde"].endswith("exemplo-missoes.yaml")


def test_api_registra_e_devolve_o_estado(tmp_path):
    cliente, _ = _cliente(tmp_path)
    r = cliente.post("/api/life/log", json={
        "missao_id": "foc-sem-video-curto", "origem": "sensor", "medida": "0 min",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["conta_como_cumprido"] is True
    assert d["estado"]["sequencia"] == 1


def test_api_recusa_origem_invalida_e_missao_fantasma(tmp_path):
    cliente, _ = _cliente(tmp_path)
    assert cliente.post("/api/life/log", json={
        "missao_id": "foc-sem-video-curto", "origem": "palpite",
    }).status_code == 422
    assert cliente.post("/api/life/log", json={
        "missao_id": "nao-existe", "origem": "usuario",
    }).status_code == 404


def test_api_registro_presumido_grava_mas_nao_conta(tmp_path):
    # Grava porque o histórico é dela; não conta porque suposição não é feito.
    cliente, _ = _cliente(tmp_path)
    d = cliente.post("/api/life/log", json={
        "missao_id": "int-leitura", "origem": "presumido",
    }).json()
    assert d["conta_como_cumprido"] is False
    assert d["estado"]["sequencia"] == 0


# --------------------------------- o catálogo viajando para o aparelho


def test_exportar_para_aparelho_manda_dinheiro_como_texto():
    # Valor que passa por float volta diferente, e aqui ele atravessa a
    # fronteira entre dois motores.
    from fintips.life import exportar_para_aparelho

    d = exportar_para_aparelho(Vida(missoes=[APORTE, SEM_TELA]))
    aporte = next(m for m in d["missoes"] if m["id"] == APORTE.id)
    assert aporte["valor_mensal"] == "1000.00"
    assert isinstance(aporte["valor_mensal"], str)
    tela = next(m for m in d["missoes"] if m["id"] == SEM_TELA.id)
    assert tela["valor_mensal"] is None
    assert tela["colide_com"] == ["tablet", "celular", "streaming"]


def test_o_historico_do_aparelho_volta_para_o_workspace():
    from fintips.life import importar_do_aparelho

    linhas = "\n".join([
        json.dumps({"missao_id": "int-leitura", "dia": "2026-10-13", "origem": "usuario"}),
        json.dumps({"missao_id": "foc-sem-video-curto", "dia": "2026-10-14",
                    "origem": "sensor", "medida": "0 min"}),
    ])
    vindos = importar_do_aparelho(linhas, {"int-leitura", "foc-sem-video-curto"})
    assert len(vindos) == 2
    assert vindos[1].origem == "sensor"
    assert vindos[1].medida == "0 min"


def test_historico_do_aparelho_com_missao_desconhecida_e_recusado():
    from fintips.life import importar_do_aparelho

    with pytest.raises(ValueError, match="não está no catálogo"):
        importar_do_aparelho(
            json.dumps({"missao_id": "fantasma", "dia": "2026-10-14", "origem": "usuario"}),
            {"int-leitura"},
        )


def test_o_exemplo_do_pacote_exporta_sem_dado_pessoal():
    """Quem trabalha na tela precisa de dado, e não do workspace de ninguém."""
    from fintips.life import carregar, exportar_para_aparelho

    vida = carregar(Path("fintips/rules/exemplo-missoes.yaml"))
    d = exportar_para_aparelho(vida)
    assert len(d["missoes"]) >= 10
    assert d["schema_version"] == 1
    # tem o que a tela precisa exercitar: as duas pontas e a regra
    assert any(m["valor_mensal"] for m in d["missoes"])
    assert any(m["colide_com"] for m in d["missoes"])
    assert len(d["regras"]) == 1
