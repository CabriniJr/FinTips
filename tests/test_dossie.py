"""Testes do dossiê: o pacote que o agente carrega e o painel desenha.

Duas propriedades. A primeira é de forma: o briefing cabe no orçamento de
tokens e, quando corta, corta o dispensável — nunca o perfil assinado nem as
causas já decididas, que são o que muda a conversa desde a primeira frase.

A segunda é de honestidade: resumir não pode virar esconder. Todo bloco do
briefing carrega a ferramenta que devolve o detalhe, e o cabeçalho avisa o que
ali ainda é palpite.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fintips import dossier, report  # noqa: E402
from fintips.contracts import Proveniencia  # noqa: E402
from fintips.workspace import Workspace  # noqa: E402

FIXTURE = Path(__file__).parent / "fixture.ofx"
TMP = Path("/tmp/fintips-dossie-test")


def _ctx(com_decisoes: bool = False) -> dict:
    if TMP.exists():
        shutil.rmtree(TMP)
    ws = Workspace.open(TMP)
    shutil.copy(FIXTURE, ws.extratos / "fixture.ofx")
    report.ingest(ws, ws.extratos / "fixture.ofx")
    st = report.stores(ws)
    if com_decisoes:
        st["perfil"].assinar(
            "renda", "variavel",
            proveniencia=Proveniencia(origem="usuario", porque="sou PJ, fecho por projeto"),
        )
        st["causas"].gravar(
            efeito_tipo="categoria", efeito_ref="transporte", natureza="necessidade",
            enunciado="uso transporte público todo dia para trabalhar",
            atitude="aceitar",
            proveniencia=Proveniencia(origem="usuario", porque="confirmado na conversa"),
        )
    return report.analyze(ws, st=st)


# ------------------------------------------------------------------- forma

def test_briefing_cabe_no_orcamento():
    ctx = _ctx(com_decisoes=True)
    for orcamento in (3500, 800, 200):
        d = dossier.montar(ctx, orcamento_tokens=orcamento)
        estimado = d["orcamento"]["tokens_estimados"]
        assert estimado == dossier._tokens(d["briefing"])
        # com orçamento apertado o motor corta, e diz o que cortou
        if estimado > orcamento:
            assert d["orcamento"]["cortes"], "estourou o orçamento sem registrar corte"


def test_corte_nunca_derruba_decisao_assinada():
    """Palpite é dispensável; o que alguém assinou, não."""
    ctx = _ctx(com_decisoes=True)
    d = dossier.montar(ctx, orcamento_tokens=1)
    assinado = d["briefing"]["quem_e"]["assinado"]
    assert assinado, "perfil assinado sumiu no corte"
    assert assinado[0]["eixo"] == "renda"
    decididas = [c for c in d["briefing"]["porque_o_dinheiro_sai"]["causas_ativas"]
                 if c["atitude"] != "nenhuma"]
    assert decididas, "causa com atitude sumiu no corte"


def test_todo_bloco_diz_como_expandir():
    """Resumo sem ponteiro vira resumo escondendo — o agente passa a supor."""
    d = dossier.montar(_ctx())
    for nome, bloco in d["briefing"].items():
        assert bloco.get("expandir_com"), f"bloco '{nome}' não diz como buscar o detalhe"


def test_cabecalho_avisa_o_que_e_palpite():
    d = dossier.montar(_ctx())
    cab = d["cabecalho"]
    assert "heuristica" in cab["aviso"] and "importacao" in cab["aviso"]
    assert set(cab["coberturas"]) >= {"classificacao_pct", "perfil_pct", "causal_pct"}


def test_palpite_vem_marcado_para_confirmar():
    d = dossier.montar(_ctx())
    for p in d["briefing"]["quem_e"]["ainda_palpite"]:
        assert p["confirmar_antes_de_usar"] is True


# -------------------------------------------------------------- correlações

def test_correlacao_liga_causa_ao_alvo():
    ctx = _ctx(com_decisoes=True)
    arestas = dossier.correlacoes(ctx)
    causais = [a for a in arestas if a["de_tipo"] == "causa"]
    assert causais, "nenhuma aresta de causa"
    a = causais[0]
    assert a["relacao"] == "explica"
    assert a["para"] == "categoria:transporte"
    assert a["atitude"] == "aceitar"


def test_correlacao_traz_pendencias_com_impacto():
    arestas = dossier.correlacoes(_ctx())
    pend = [a for a in arestas if a["relacao"] == "pendente_sobre"]
    assert pend, "triagem aberta deveria virar aresta"
    assert all("valor_mensal" in a for a in pend)


# -------------------------------------------------------------- observações

def test_observacoes_tem_schema_estavel():
    linhas = dossier.observacoes(_ctx(com_decisoes=True))
    assert linhas
    for l in linhas:
        assert list(l.keys()) == list(dossier.CAMPOS), "schema variou entre linhas"


def test_observacoes_cobrem_as_camadas():
    linhas = dossier.observacoes(_ctx(com_decisoes=True))
    tipos = {l["tipo"] for l in linhas}
    assert {"mes", "causa", "perfil_traco", "score_dimensao", "triagem"} <= tipos


def test_salvar_grava_json_e_jsonl_lidos_de_volta():
    ctx = _ctx(com_decisoes=True)
    out = dossier.salvar(TMP / "relatorios", ctx)
    assert out["linhas"] > 0

    d = json.loads(Path(out["dossie"]).read_text(encoding="utf-8"))
    assert d["schema_version"] == dossier.DOSSIER_SCHEMA

    # o jsonl precisa ser legível linha a linha — é o que permite virar
    # dataframe sem o pacote depender de pandas
    linhas = [json.loads(l) for l in Path(out["observacoes"]).read_text(encoding="utf-8").splitlines() if l]
    assert len(linhas) == out["linhas"]
    assert all(set(l) == set(dossier.CAMPOS) for l in linhas)


def test_dossie_e_derivado_e_pode_ser_apagado():
    """Nada aqui é fonte de verdade: apagar e remontar tem que dar o mesmo."""
    ctx = _ctx(com_decisoes=True)
    primeiro = dossier.salvar(TMP / "relatorios", ctx)
    Path(primeiro["dossie"]).unlink()
    Path(primeiro["observacoes"]).unlink()
    segundo = dossier.salvar(TMP / "relatorios", ctx)
    assert segundo["linhas"] == primeiro["linhas"]
    assert Path(segundo["dossie"]).exists()


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
