"""O perfil ao longo do tempo: história, envelhecimento e migração.

Estes testes protegem três coisas que, se ficarem para depois, só se consertam
reestruturando — e reestruturando o arquivo que mora na máquina da pessoa.

- **A história não se apaga.** Reassinar um eixo guardava só o nome do
  arquétipo anterior; o `porque`, a data e a evidência sumiam. Num projeto cuja
  premissa é guardar o porquê, o perfil era o único lugar onde ele se perdia.
- **A assinatura envelhece.** Um traço de três anos atrás continua assinado e
  parou de descrever alguém. Cobertura que o conta como decisão atual mente.
- **O formato muda.** Sem um degrau de migração pronto, a primeira mudança de
  esquema faz o app escolher entre recusar o perfil ou interpretá-lo errado em
  silêncio.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from fintips.contracts import Proveniencia
from fintips.profile import (
    PROFILE_SCHEMA,
    PerfilStore,
    TracoDePerfil,
    carregar_catalogo,
    migrar,
    montar,
    retrato,
)

HOJE = date(2026, 10, 14)


def prov(porque: str, quando: str, origem: str = "usuario") -> Proveniencia:
    return Proveniencia(origem=origem, confianca=1.0, porque=porque, quando=quando)


@pytest.fixture
def loja(tmp_path):
    return PerfilStore(tmp_path / "perfil.yaml")


# ------------------------------------------------------------- a história

def test_reassinar_nao_apaga_o_porque_anterior(loja):
    """A pergunta que isso destrava é das boas: por que eu mudei?"""
    loja.assinar("custo", "sufocado", proveniencia=prov("aluguel comeu metade", "2025-03-10T10:00:00"))
    loja.assinar("custo", "enxuto", proveniencia=prov("mudei para um lugar mais barato", "2026-02-01T10:00:00"))

    h = loja.historico("custo")
    assert [x["arquetipo"] for x in h] == ["sufocado", "enxuto"]
    assert h[0]["proveniencia"]["porque"] == "aluguel comeu metade"
    assert h[1]["proveniencia"]["porque"] == "mudei para um lugar mais barato"


def test_a_travessia_traz_os_dois_motivos_lado_a_lado(loja):
    loja.assinar("custo", "sufocado", proveniencia=prov("aluguel comeu metade", "2025-03-10T10:00:00"))
    loja.assinar("custo", "enxuto", proveniencia=prov("mudei de casa", "2026-02-01T10:00:00"))

    t = loja.travessias("custo")
    assert len(t) == 1
    assert t[0]["de"] == "sufocado" and t[0]["para"] == "enxuto"
    assert t[0]["porque_antes"] == "aluguel comeu metade"
    assert t[0]["porque_agora"] == "mudei de casa"


def test_reassinar_o_mesmo_arquetipo_nao_vira_travessia(loja):
    """Reconfirmar não é mudar. A lista de travessias é sobre virar outra coisa."""
    loja.assinar("renda", "variavel", proveniencia=prov("sou PJ", "2025-01-10T10:00:00"))
    loja.assinar("renda", "variavel", proveniencia=prov("continuo PJ", "2026-01-10T10:00:00"))
    assert loja.travessias("renda") == []
    assert len(loja.historico("renda")) == 2


def test_esquecer_tira_do_estado_e_mantem_na_historia(loja):
    """Esquecer é "isto não me descreve mais", não "isto nunca foi verdade"."""
    loja.assinar("fase", "acumulacao", proveniencia=prov("começando a carreira", "2024-01-10T10:00:00"))
    assert loja.esquecer("fase") is True
    assert "fase" not in loja.tracos
    h = loja.historico("fase")
    assert [x["acao"] for x in h] == ["assinar", "esquecer"]


def test_a_historia_sobrevive_a_reabrir_a_loja(tmp_path):
    p = tmp_path / "perfil.yaml"
    PerfilStore(p).assinar("renda", "variavel", proveniencia=prov("sou PJ", "2026-01-10T10:00:00"))
    assert len(PerfilStore(p).historico()) == 1


def test_o_historico_e_append_e_nunca_reescrito(tmp_path):
    p = tmp_path / "perfil.yaml"
    loja = PerfilStore(p)
    for i, arq in enumerate(["sufocado", "carregado", "enxuto"]):
        loja.assinar("custo", arq, proveniencia=prov(f"motivo {i}", f"202{4+i}-01-10T10:00:00"))
    linhas = (tmp_path / "perfil-historico.jsonl").read_text(encoding="utf-8").strip().split("\n")
    assert len(linhas) == 3
    assert all(json.loads(l)["eixo"] == "custo" for l in linhas)


# --------------------------------------------------------- envelhecimento

def test_cada_eixo_declara_o_proprio_ritmo():
    """Consumo envelhece em seis meses; fase de vida, em trinta e seis."""
    v = {e.id: e.validade_em_meses for e in carregar_catalogo()}
    assert v["consumo"] == 6
    assert v["fase"] == 36
    assert v["consumo"] < v["renda"] < v["fase"]


def test_a_idade_sai_da_data_da_assinatura():
    t = TracoDePerfil(eixo="renda", arquetipo="variavel", nome="Variável",
                      proveniencia=prov("sou PJ", "2025-10-14T10:00:00"))
    assert t.idade_em_meses(HOJE) == 12
    assert t.envelhecido(12, HOJE) is True
    assert t.envelhecido(36, HOJE) is False


def test_sem_data_legivel_a_idade_e_desconhecida_e_nao_zero():
    """Devolver 0 afirmaria que a assinatura é de hoje — a mentira conveniente."""
    t = TracoDePerfil(eixo="renda", arquetipo="variavel", nome="Variável",
                      proveniencia=Proveniencia(origem="usuario", porque="x", quando=""))
    assert t.idade_em_meses(HOJE) is None
    assert t.envelhecido(1, HOJE) is False


def test_a_cobertura_separa_assinado_de_ainda_valido(loja):
    """Cobertura que conta decisão de três anos como atual é cobertura que mente."""
    loja.assinar("consumo", "concentrado", proveniencia=prov("compro sempre igual", "2024-01-10T10:00:00"))
    loja.assinar("fase", "acumulacao", proveniencia=prov("carreira começando", "2024-01-10T10:00:00"))

    d = montar(_ctx(), loja, hoje=HOJE)
    cob = d["cobertura"]
    assert cob["assinados"] == 2
    assert cob["validos"] == 1                 # consumo (6 meses) envelheceu; fase (36) não
    assert cob["pct"] > cob["pct_valido"]
    assert cob["envelhecidos"] == ["consumo"]


def test_o_eixo_envelhecido_vira_pedido_de_reconfirmacao(loja):
    loja.assinar("consumo", "concentrado", proveniencia=prov("compro sempre igual", "2024-01-10T10:00:00"))
    d = montar(_ctx(), loja, hoje=HOJE)
    pedido = d["a_reconfirmar"][0]
    assert pedido["eixo"] == "consumo"
    assert pedido["assinado_ha_meses"] >= 6
    assert pedido["porque_na_epoca"] == "compro sempre igual"


def test_traco_envelhecido_nao_some_nem_deixa_de_valer(loja):
    """O app passa a perguntar; ele não apaga o que a pessoa disse."""
    loja.assinar("consumo", "concentrado", proveniencia=prov("x", "2020-01-10T10:00:00"))
    eixo = next(e for e in montar(_ctx(), loja, hoje=HOJE)["eixos"] if e["eixo"] == "consumo")
    assert eixo["assinado"]["arquetipo"] == "concentrado"
    assert eixo["envelhecido"] is True


# ----------------------------------------------------------------- migração

def test_migrar_sobe_a_versao_antiga_sem_perder_traco():
    d = migrar({"schema_version": 1, "tracos": [{"eixo": "renda", "arquetipo": "variavel"}]})
    assert d["schema_version"] == PROFILE_SCHEMA
    assert len(d["tracos"]) == 1


def test_arquivo_sem_versao_e_tratado_como_a_primeira():
    assert migrar({"tracos": []})["schema_version"] == PROFILE_SCHEMA


def test_versao_do_futuro_e_recusada_em_vez_de_adivinhada():
    """Ler um arquivo de versão futura é adivinhar o que os campos novos querem."""
    with pytest.raises(ValueError, match="entende até"):
        migrar({"schema_version": PROFILE_SCHEMA + 1})


def test_perfil_v1_no_disco_abre_sem_erro(tmp_path):
    p = tmp_path / "perfil.yaml"
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "tracos": [{"eixo": "renda", "arquetipo": "variavel", "nome": "Variável",
                    "proveniencia": {"origem": "usuario", "porque": "sou PJ",
                                     "quando": "2026-01-10T10:00:00"}}],
    }, allow_unicode=True), encoding="utf-8")
    loja = PerfilStore(p)
    assert loja.tracos["renda"].arquetipo == "variavel"


# ------------------------------------------------------------------ retrato

def test_o_retrato_junta_dinheiro_vida_e_compromissos(loja):
    loja.assinar("renda", "variavel", proveniencia=prov("sou PJ", "2026-09-10T10:00:00"))
    ctx = _ctx()
    ctx["perfil"] = montar(ctx, loja, hoje=HOJE)
    ctx["objetivos"] = {
        "perfil": {
            "objetivos": [{"objetivo": "cert", "titulo": "Certificação"}],
            "etapas_atrasadas": [{"etapa": "curso-1"}],
            "compromisso_total_restante": 1080.0,
            "rascunhos_aguardando_assinatura": [{"objetivo": "idioma"}],
        },
        "gauges": {"frentes": [
            {"chave": "FOC", "valor": 20.0, "sem_base": False},
            {"chave": "FOR", "valor": 0.0, "sem_base": True},
        ]},
    }
    r = retrato(ctx)
    assert r["compromissos"]["etapas_atrasadas"] == 1
    assert r["compromissos"]["restante_a_pagar"] == 1080.0
    assert r["compromissos"]["rascunhos_esperando"] == 1
    # frente sem base não entra como fraca: ausência de medida não é fraqueza
    assert r["vida"]["frentes_fracas_hoje"] == ["FOC"]
    renda = next(e for e in r["dinheiro"]["eixos"] if e["eixo"] == "renda")
    assert renda["como_se_sabe"] == "assinado"
    assert renda["porque"] == "sou PJ"


def test_o_retrato_nao_tem_numero_agregado(loja):
    """Um índice único de perfil descreveria todo mundo."""
    ctx = _ctx()
    ctx["perfil"] = montar(ctx, loja, hoje=HOJE)
    r = retrato(ctx)
    assert "horóscopo" not in json.dumps(r, ensure_ascii=False)
    assert not any(
        isinstance(v, (int, float)) and k in ("score", "indice", "nota")
        for k, v in r.items()
    )
    assert "índice único" in r["o_que_este_bloco_nao_e"]


def test_o_retrato_diz_para_nao_usar_eixo_envelhecido_sem_perguntar(loja):
    loja.assinar("consumo", "concentrado", proveniencia=prov("x", "2020-01-10T10:00:00"))
    ctx = _ctx()
    ctx["perfil"] = montar(ctx, loja, hoje=HOJE)
    r = retrato(ctx)
    assert r["dinheiro"]["a_reconfirmar"]
    assert "pergunte se ainda é assim" in r["como_usar"]


def _ctx() -> dict:
    """O mínimo que `montar` lê. Indicadores vazios: o casamento não é o assunto."""
    return {
        "baseline": {"taxa_poupanca_media": 0.1, "renda_media_mes": 5000.0,
                     "despesa_media_mes": 4500.0, "volatilidade_despesa": 0.2},
        "score": {"total": 50},
        "patrimonio": {"total": 10000.0},
        "estrutura_de_custo": {"comprometido_pct_renda": 40.0},
        "gastos_invisiveis": {"total": 200.0},
        "planos": [],
    }


# ------------------------------------------------------------------ triagem

def test_o_traco_envelhecido_vira_pergunta_na_triagem(tmp_path):
    """Sem isto o envelhecimento seria só um campo bonito num JSON: o app
    saberia que o traço está velho e nunca perguntaria."""
    from fintips import triage
    from fintips.context import ContextStore

    itens = triage.construir(
        _extrato_vazio(),
        [],
        base={},
        ctx_store=ContextStore(tmp_path / "contexto.yaml"),
        custos_fixos=[], candidatos_fixos=[],
        store=triage.TriageStore(tmp_path / "triagem.yaml"),
        perfil_a_reconfirmar=[{
            "eixo": "consumo", "arquetipo": "concentrado",
            "assinado_ha_meses": 30, "validade_em_meses": 6,
            "porque_na_epoca": "compro sempre nos mesmos lugares",
        }],
    )
    pedido = next(i for i in itens if i.tipo == "perfil_a_reconfirmar")
    assert "ainda é 'concentrado' em consumo?" in pedido.titulo
    assert "30 meses" in pedido.porque_importa
    assert pedido.evidencia["porque_na_epoca"] == "compro sempre nos mesmos lugares"


def test_sem_traco_envelhecido_a_triagem_nao_inventa_pergunta(tmp_path):
    from fintips import triage
    from fintips.context import ContextStore

    itens = triage.construir(
        _extrato_vazio(),
        [], base={}, ctx_store=ContextStore(tmp_path / "contexto.yaml"),
        custos_fixos=[], candidatos_fixos=[],
        store=triage.TriageStore(tmp_path / "triagem.yaml"),
    )
    assert not any(i.tipo == "perfil_a_reconfirmar" for i in itens)


def _extrato_vazio():
    """Um extrato sem transação: a triagem do perfil não depende do dinheiro."""
    from decimal import Decimal

    from fintips.models import Account, Statement

    return Statement(
        account=Account(id_hash="acct:ouro"),
        period_start=date(2026, 1, 1), period_end=HOJE,
        ledger_balance=Decimal("0"), balance_as_of=HOJE, transactions=[],
    )
