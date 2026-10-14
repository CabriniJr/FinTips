"""O plano decomposto: correlação declarada, agenda, score e reajuste.

Estes testes protegem três fronteiras, e nenhuma delas é de cálculo:

- a IA **propõe** a estrutura; a agenda só aceita o que foi assinado;
- o reajuste existe e **custa** — senão o score vira enfeite;
- laço que a conversa não declarou não é descoberto pelo motor.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from fintips.life import Missao, RegistroDeMissao, Vida
from fintips.objetivos import (
    Check,
    Objetivo,
    ObjetivoStore,
    agenda,
    aplicar_reajuste,
    carregar_checks,
    checks_de_hoje,
    contexto_de_perfil,
    correlacionar,
    cumprimento,
    exportar_para_aparelho,
    gauges,
    importar_do_aparelho,
    marcar,
    reajuste_proposto,
    score_do_objetivo,
    situacao_da_etapa,
    status_do_objetivo,
)

HOJE = date(2026, 10, 14)


def cert(**extra) -> dict:
    """Um objetivo com a forma do caso real: cursos, prova e custo."""
    d = {
        "id": "cert-nuvem",
        "titulo": "Certificação de plataforma em nuvem",
        "porque": "é o que falta para pleitear a vaga sênior no ano que vem",
        "comecou_em": "2026-09-01",
        "data_alvo": "2026-12-01",
        "plano_id": "plano-cert",
        "missoes": ["int-estudo"],
        "origem": "agente",
        "porque_da_origem": "montado na conversa de 01/09, a partir do texto dele",
        "etapas": [
            {
                "id": "curso-1", "titulo": "Curso de fundamentos", "tipo": "curso",
                "prazo": "2026-09-30", "custo": "120.00",
                "porque": "pré-requisito do exame",
            },
            {
                "id": "curso-2", "titulo": "Curso de arquitetura", "tipo": "curso",
                "prazo": "2026-10-10", "custo": "180.00", "depende_de": ["curso-1"],
            },
            {
                "id": "prova", "titulo": "Prova final", "tipo": "prova",
                "prazo": "2026-11-20", "custo": "900.00", "depende_de": ["curso-2"],
            },
        ],
    }
    d.update(extra)
    return d


def assinado(**extra) -> Objetivo:
    o = Objetivo.from_dict(cert(**extra))
    o.assinado_em = date(2026, 9, 1)
    return o


def check(etapa: str, dia: str, origem: str = "usuario") -> Check:
    return Check.from_dict(
        {"objetivo_id": "cert-nuvem", "etapa_id": etapa, "dia": dia, "origem": origem}
    )


PLANO = {
    "id": "plano-cert", "nome": "Certificação", "guardado": 400.0,
    "aporte_planejado_mes": 300.0, "status": "confortavel",
}

VIDA = Vida(
    missoes=[Missao(id="int-estudo", titulo="Estudar", atributo="INT", cadencia="diaria")],
    registros=[RegistroDeMissao(missao_id="int-estudo", dia=HOJE, origem="usuario")],
)


# ---------------------------------------------------------- o que a IA cria

def test_objetivo_nasce_rascunho_mesmo_quando_quem_cria_e_o_usuario(tmp_path):
    """A assinatura é um segundo ato: quem escreveu a decomposição foi o agente."""
    loja = ObjetivoStore(tmp_path / "objetivos.yaml")
    o = loja.criar(cert(origem="usuario"))
    assert not o.assinado
    assert status_do_objetivo(o, [], HOJE) == "rascunho"


def test_rascunho_nao_entra_na_agenda_nem_nos_gauges():
    """Agenda que se enche sozinha de item não combinado é app desinstalado."""
    rascunho = Objetivo.from_dict(cert())
    assert agenda([rascunho], [], HOJE) == []
    assert gauges([rascunho], [], VIDA, HOJE)["objetivos"] == []
    # mas ele aparece onde deve: esperando assinatura
    perfil = contexto_de_perfil([rascunho], [], VIDA, HOJE)
    assert perfil["rascunhos_aguardando_assinatura"][0]["objetivo"] == "cert-nuvem"


def test_objetivo_sem_porque_e_recusado():
    with pytest.raises(ValueError, match="precisa dizer o que ele resolve"):
        Objetivo.from_dict(cert(porque=""))


def test_o_que_o_app_presumiu_nao_cria_objetivo():
    """O app supor que você quer uma certificação não é você querer."""
    with pytest.raises(ValueError, match="não cria objetivo"):
        Objetivo.from_dict(cert(origem="presumido"))


def test_dependencia_pendurada_e_recusada_na_carga():
    """Dependência que aponta para o vazio travaria a agenda em silêncio."""
    d = cert()
    d["etapas"][1]["depende_de"] = ["curso-zero"]
    with pytest.raises(ValueError, match="não é etapa deste"):
        Objetivo.from_dict(d)


def test_assinar_exige_pelo_menos_uma_etapa(tmp_path):
    loja = ObjetivoStore(tmp_path / "objetivos.yaml")
    loja.criar({**cert(), "etapas": []})
    with pytest.raises(ValueError, match="intenção não entra em agenda"):
        loja.assinar("cert-nuvem")


def test_recriar_por_cima_e_recusado(tmp_path):
    """Recriar apagaria os adiamentos já contados — e é assim que o score some."""
    loja = ObjetivoStore(tmp_path / "objetivos.yaml")
    loja.criar(cert())
    with pytest.raises(ValueError, match="já existe"):
        loja.criar(cert())


# ------------------------------------------------------------------ agenda

def test_etapa_bloqueada_aparece_marcada_e_nao_some():
    """Bloqueada é informação: diz por que o prazo vai estourar."""
    o = assinado()
    itens = {i["etapa"]: i for i in agenda([o], [], HOJE, dias=60)}
    assert itens["curso-1"]["situacao"] == "atrasada"
    assert itens["curso-2"]["situacao"] == "bloqueada"
    assert itens["curso-2"]["bloqueada_por"] == ["curso-1"]


def test_atraso_antigo_continua_aparecendo():
    """Sumir com o que venceu há 40 dias é a forma mais educada de mentir."""
    o = assinado()
    itens = agenda([o], [], date(2026, 11, 9), dias=1)
    assert any(i["etapa"] == "curso-1" and i["situacao"] == "atrasada" for i in itens)


def test_etapa_feita_sai_da_agenda():
    o = assinado()
    itens = agenda([o], [check("curso-1", "2026-09-28")], HOJE, dias=60)
    assert "curso-1" not in {i["etapa"] for i in itens}
    assert {i["etapa"] for i in itens} >= {"curso-2"}


def test_check_presumido_nao_conta():
    """O app supor que você fez o curso não é você ter feito o curso."""
    o = assinado()
    assert cumprimento(o, [check("curso-1", "2026-09-28", "presumido")]) == {}


def test_o_primeiro_check_e_o_que_vale():
    """Marcar duas vezes não pode piorar a nota de quem marcou no prazo."""
    o = assinado()
    feito = cumprimento(o, [check("curso-1", "2026-10-05"), check("curso-1", "2026-09-28")])
    assert feito["curso-1"].dia == date(2026, 9, 28)


def test_o_resumo_do_widget_nao_elogia_nem_cobra():
    o = assinado()
    hoje = checks_de_hoje([o], [], VIDA, HOJE)
    # a missão do dia e a etapa vencida. A bloqueada por dependência não entra:
    # oferecer check do que ainda não dá para fazer convida a marcar fora de ordem
    assert [l["id"] for l in hoje["linhas"]] == ["int-estudo", "curso-1"]
    r = hoje["resumo"]
    assert r == "1 de 2 hoje"
    assert not any(p in r.lower() for p in ("parabéns", "quase", "falta", "vamos", "!"))


# ------------------------------------------------------------------- score

def test_dimensao_sem_base_nao_vira_zero():
    """Objetivo que começou ontem não está falhando — está começando."""
    o = assinado(comecou_em="2026-10-14", data_alvo="2026-12-01", etapas=[
        {"id": "e1", "titulo": "Primeira", "tipo": "curso", "prazo": "2026-11-01"},
    ])
    sc = score_do_objetivo(o, [], HOJE, correlacao=correlacionar(o, [], hoje=HOJE))
    por_dim = {c["dimensao"]: c for c in sc["componentes"]}
    assert por_dim["prazo"]["valor"] is None
    assert por_dim["prazo"]["pontos"] is None
    assert por_dim["ritmo"]["valor"] is None          # nenhum dia decorrido ainda
    assert por_dim["dinheiro"]["valor"] is None       # nada a pagar
    # só `adiamento` tem base: nota cheia sobre peso 15, e isso fica dito
    assert sc["peso_aplicado"] == 15
    assert sc["peso_total"] == 100
    assert sc["score"] == 100.0


def test_o_peso_aplicado_sobe_conforme_o_objetivo_ganha_historia():
    o = assinado()
    corr = correlacionar(o, [], planos=[PLANO], vida=VIDA, hoje=HOJE)
    sc = score_do_objetivo(o, [], HOJE, correlacao=corr)
    assert sc["peso_aplicado"] == 100  # as cinco dimensões têm base


def test_empurrar_o_prazo_nao_compra_nota_cheia():
    """O teste que impede o reajuste de virar borracha.

    Duas pessoas chegam em 14/10 com a mesma etapa não feita. A primeira
    deixou a data vencer. A segunda empurrou a data três vezes e está
    "em dia". Se o score não enxergar a diferença, ele não mede nada.
    """
    vencida = assinado(etapas=[
        {"id": "e1", "titulo": "Curso", "tipo": "curso", "prazo": "2026-10-01"},
    ])
    empurrada = assinado(etapas=[
        {"id": "e1", "titulo": "Curso", "tipo": "curso",
         "prazo": "2026-11-01", "prazo_original": "2026-10-01", "adiamentos": 3},
    ])

    sc_v = score_do_objetivo(vencida, [], HOJE, correlacao=correlacionar(vencida, [], hoje=HOJE))
    sc_e = score_do_objetivo(empurrada, [], HOJE, correlacao=correlacionar(empurrada, [], hoje=HOJE))

    dim_v = {c["dimensao"]: c for c in sc_v["componentes"]}
    dim_e = {c["dimensao"]: c for c in sc_e["componentes"]}

    # quem empurrou ganha em `prazo` — nada venceu
    assert dim_v["prazo"]["valor"] == 0.0
    assert dim_e["prazo"]["valor"] is None
    # e paga em `adiamento`, que mede contra o prazo original
    assert dim_v["adiamento"]["valor"] == 1.0
    assert dim_e["adiamento"]["valor"] == 0.0
    assert dim_e["adiamento"]["dias_empurrados"] == 31
    # o resultado: empurrar três vezes não devolve a nota de quem cumpriu
    assert sc_e["score"] < 100.0


def test_cumprir_depois_do_prazo_nao_conta_como_no_prazo():
    o = assinado()
    corr = correlacionar(o, [check("curso-1", "2026-10-05")], hoje=HOJE)
    sc = score_do_objetivo(o, [check("curso-1", "2026-10-05")], HOJE, correlacao=corr)
    dim = {c["dimensao"]: c for c in sc["componentes"]}
    # curso-1 foi feito (tarde) e curso-2 venceu sem check: dois cobráveis
    assert dim["prazo"]["etapas_cobraveis"] == 2
    assert dim["prazo"]["cumpridas_no_prazo"] == 0


def test_ritmo_compara_progresso_com_tempo_gasto():
    """Metade do tempo e um terço das etapas é ritmo de 0,67, não de 0,33."""
    o = assinado(comecou_em="2026-09-01", data_alvo="2026-11-01")
    checks = [check("curso-1", "2026-09-20")]
    sc = score_do_objetivo(o, checks, date(2026, 10, 1), correlacao=correlacionar(o, checks, hoje=date(2026, 10, 1)))
    ritmo = next(c for c in sc["componentes"] if c["dimensao"] == "ritmo")
    assert ritmo["tempo_decorrido"] == 0.4918
    assert ritmo["progresso"] == 0.3333
    assert ritmo["valor"] == 0.6778


def test_toda_dimensao_carrega_a_propria_formula():
    """Número que ninguém refaz à mão decora tela; não muda comportamento."""
    o = assinado()
    sc = score_do_objetivo(o, [], HOJE, correlacao=correlacionar(o, [], planos=[PLANO], vida=VIDA, hoje=HOJE))
    assert len(sc["componentes"]) == 5
    for c in sc["componentes"]:
        assert c["formula"].strip()
        assert c["peso"] > 0


# ---------------------------------------------------------------- reajuste

def test_o_atraso_cascateia_pela_cadeia_de_dependencia():
    """Se o curso 2 atrasa 12 dias, a prova atrasa 12 dias. É só isso."""
    o = assinado()
    p = reajuste_proposto(o, [check("curso-1", "2026-09-28")], HOJE)
    movs = {m["etapa"]: m for m in p["movimentos"]}
    assert movs["curso-2"]["dias"] == 4       # prazo 10/10, hoje 14/10
    assert movs["curso-2"]["para"] == "2026-10-14"
    assert movs["prova"]["dias"] == 4         # herdou o mesmo empurrão
    assert movs["prova"]["motivo"] == "depende de etapa que atrasou"
    assert movs["prova"]["para"] == "2026-11-24"


def test_a_proposta_diz_quanto_da_folga_sobrou():
    o = assinado()
    p = reajuste_proposto(o, [check("curso-1", "2026-09-28")], HOJE)
    assert p["folga_antes_em_dias"] == 11     # prova 20/11, alvo 01/12
    assert p["folga_depois_em_dias"] == 7
    assert p["estoura_o_alvo"] is False


def test_a_proposta_avisa_quando_o_atraso_come_o_alvo():
    o = assinado()
    p = reajuste_proposto(o, [check("curso-1", "2026-09-28")], date(2026, 10, 30))
    assert p["estoura_o_alvo"] is True
    assert p["folga_depois_em_dias"] < 0


def test_a_proposta_nasce_sem_assinatura():
    o = assinado()
    p = reajuste_proposto(o, [], HOJE)
    assert p["origem"] == "agente"
    assert p["assinado"] is False


def test_o_agente_nao_aplica_o_proprio_reajuste():
    """Mexer na data de uma promessa é de quem fez a promessa."""
    o = assinado()
    p = reajuste_proposto(o, [], HOJE)
    with pytest.raises(ValueError, match="só é aplicado pelo `usuario`"):
        aplicar_reajuste(o, p, porque="a semana virou", origem="agente")


def test_reajustar_exige_porque():
    o = assinado()
    p = reajuste_proposto(o, [], HOJE)
    with pytest.raises(ValueError, match="exige `porque`"):
        aplicar_reajuste(o, p, porque="   ")


def test_aplicar_preserva_o_prazo_original_e_conta_o_adiamento():
    """É o que impede o reajuste de apagar a própria história."""
    o = assinado()
    p = reajuste_proposto(o, [check("curso-1", "2026-09-28")], HOJE)
    aplicar_reajuste(o, p, porque="viagem de trabalho comeu a semana")
    e = o.etapa("curso-2")
    assert e.prazo == date(2026, 10, 14)
    assert e.prazo_original == date(2026, 10, 10)
    assert e.adiamentos == 1
    assert e.dias_adiados == 4
    assert "viagem de trabalho" in e.porque


def test_proposta_velha_nao_e_aplicada_por_cima_de_data_nova():
    """Aplicar uma conta velha move a data para o lugar errado, em silêncio."""
    o = assinado()
    p = reajuste_proposto(o, [check("curso-1", "2026-09-28")], HOJE)
    aplicar_reajuste(o, p, porque="primeira vez")
    with pytest.raises(ValueError, match="Recalcule"):
        aplicar_reajuste(o, p, porque="segunda vez, com a conta velha")


def test_reajustar_derruba_o_score_de_adiamento():
    """A ponta solta do produto: reajustar é permitido, e custa."""
    o = assinado()
    antes = score_do_objetivo(o, [], HOJE, correlacao=correlacionar(o, [], hoje=HOJE))
    p = reajuste_proposto(o, [check("curso-1", "2026-09-28")], HOJE)
    aplicar_reajuste(o, p, porque="a semana virou")
    depois = score_do_objetivo(o, [], HOJE, correlacao=correlacionar(o, [], hoje=HOJE))
    dim_a = {c["dimensao"]: c for c in antes["componentes"]}["adiamento"]
    dim_d = {c["dimensao"]: c for c in depois["componentes"]}["adiamento"]
    assert dim_a["valor"] == 1.0
    assert dim_d["adiamentos"] == 2            # curso-2 e prova andaram
    assert dim_d["valor"] < dim_a["valor"]


# --------------------------------------------------------------- correlação

def test_o_motor_nao_descobre_laco_que_a_conversa_nao_declarou():
    o = assinado(plano_id="", missoes=[])
    corr = correlacionar(o, [], planos=[PLANO], vida=VIDA, hoje=HOJE)
    assert corr["plano"] is None
    assert corr["cobertura_financeira"] is None
    assert corr["missoes"] == []
    assert any("nenhum plano financeiro está ligado" in a for a in corr["avisos"])
    # e a ausência não vira nota zero
    sc = score_do_objetivo(o, [], HOJE, correlacao=corr)
    dim = {c["dimensao"]: c for c in sc["componentes"]}
    assert dim["dinheiro"]["valor"] is None
    assert dim["constancia"]["valor"] is None


def test_laco_que_aponta_para_o_vazio_aparece_em_orfaos():
    """Laço quebrado em silêncio é o erro mais caro: o número continua saindo."""
    o = assinado()
    corr = correlacionar(o, [], planos=[], vida=Vida(), hoje=HOJE)
    tipos = {x["tipo"]: x for x in corr["orfaos"]}
    assert tipos["plano"]["id"] == "plano-cert"
    assert tipos["missao"]["id"] == "int-estudo"


def test_a_cobertura_financeira_usa_o_que_o_plano_ja_tem_mais_os_aportes():
    o = assinado()
    corr = correlacionar(o, [check("curso-1", "2026-09-28")], planos=[PLANO], vida=VIDA, hoje=HOJE)
    assert corr["custo_restante"] == 1080.0            # 180 + 900
    assert corr["custo_ja_comprometido"] == 120.0
    cob = corr["cobertura_financeira"]
    assert cob["meses_ate_o_alvo"] == 2                 # out → dez
    assert cob["disponivel_ate_la"] == 1000.0          # 400 + 300×2
    assert cob["cobre"] is False
    assert cob["falta"] == 80.0


# ---------------------------------------------------------- o que a tela lê

def test_o_gauge_entrega_numero_e_faixa_nunca_forma():
    o = assinado()
    g = gauges([o], [], VIDA, HOJE, planos=[PLANO])
    assert [f["chave"] for f in g["frentes"]] == ["FOR", "AGI", "VIT", "INT", "FOC", "OURO"]
    sem_missao = next(f for f in g["frentes"] if f["chave"] == "FOR")
    assert sem_missao["sem_base"] is True              # frente vazia não é 0%
    assert sem_missao["faixa"] == "sem_base"
    alvo = g["objetivos"][0]
    assert alvo["chave"] == "cert-nuvem"
    assert 0 <= alvo["valor"] <= 100
    assert alvo["proxima_etapa"] == "Curso de fundamentos"
    assert alvo["peso_total"] == 100


def test_o_perfil_separa_o_que_ela_assinou_do_que_a_ia_propos():
    rascunho = Objetivo.from_dict({**cert(), "id": "outro", "titulo": "Mestrado"})
    o = assinado()
    perfil = contexto_de_perfil([o, rascunho], [], VIDA, HOJE, planos=[PLANO])
    assert [r["objetivo"] for r in perfil["objetivos"]] == ["cert-nuvem"]
    assert perfil["rascunhos_aguardando_assinatura"][0]["objetivo"] == "outro"
    assert "rascunho não é compromisso dela" in perfil["como_usar"]
    assert perfil["compromisso_total_restante"] == 1200.0


# ----------------------------------------------------------- ida e volta io

def test_so_objetivo_assinado_viaja_para_o_aparelho():
    o = assinado()
    rascunho = Objetivo.from_dict({**cert(), "id": "outro"})
    d = exportar_para_aparelho([o, rascunho])
    assert [x["id"] for x in d["objetivos"]] == ["cert-nuvem"]


def test_dinheiro_atravessa_a_fronteira_como_string_de_duas_casas():
    o = assinado()
    custos = [e["custo"] for e in exportar_para_aparelho([o])["objetivos"][0]["etapas"]]
    assert custos == ["120.00", "180.00", "900.00"]


def test_check_de_objetivo_desconhecido_e_recusado_na_volta():
    linha = json.dumps({
        "objetivo_id": "fantasma", "etapa_id": "e1",
        "dia": "2026-10-14", "origem": "usuario",
    })
    with pytest.raises(ValueError, match="não está no catálogo"):
        importar_do_aparelho(linha, {"cert-nuvem"})


def test_o_check_e_append_e_sobrevive_a_fechar_o_app(tmp_path):
    p = tmp_path / "checks.jsonl"
    marcar(p, check("curso-1", "2026-09-28"))
    marcar(p, check("curso-2", "2026-10-09"))
    assert [c.etapa_id for c in carregar_checks(p)] == ["curso-1", "curso-2"]


def test_a_loja_faz_ida_e_volta_pelo_yaml(tmp_path):
    caminho = tmp_path / "objetivos.yaml"
    loja = ObjetivoStore(caminho)
    loja.criar(cert())
    loja.assinar("cert-nuvem", quando=date(2026, 9, 1))
    loja.save()

    de_volta = ObjetivoStore(caminho).objetivos["cert-nuvem"]
    assert de_volta.assinado
    assert de_volta.etapa("prova").custo == Decimal("900.00")
    assert de_volta.etapa("prova").depende_de == ["curso-2"]
    assert de_volta.etapa("curso-1").prazo_original == date(2026, 9, 30)
