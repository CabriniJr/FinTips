"""Testes do perfil e das alavancas (v0.4).

A propriedade protegida aqui é a mesma do resto do projeto, aplicada ao lugar
onde é mais tentador afrouxá-la: **o app não decide quem o usuário é**. O
casamento de arquétipo por número é palpite e não grava nada; perfil só existe
quando alguém com autoridade assina, com `porque`.

E a segunda propriedade, das alavancas: nenhuma delas produz conselho em
prosa. Cada uma carrega um número e um efeito recalculado pelo motor — a
interpretação é trabalho do agente.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fintips import levers, profile as profile_mod, report  # noqa: E402
from fintips.contracts import Proveniencia  # noqa: E402
from fintips.workspace import Workspace  # noqa: E402

FIXTURE = Path(__file__).parent / "fixture.ofx"
TMP = Path("/tmp/fintips-v04")


def _ws() -> Workspace:
    if TMP.exists():
        shutil.rmtree(TMP)
    ws = Workspace.open(TMP)
    shutil.copy(FIXTURE, ws.extratos / "fixture.ofx")
    return ws


def _ctx() -> dict:
    ws = _ws()
    report.ingest(ws, ws.extratos / "fixture.ofx")
    return report.analyze(ws)


# ------------------------------------------------------------------ catálogo

def test_catalogo_carrega_com_eixos_independentes():
    catalogo = profile_mod.carregar_catalogo()
    ids = [e.id for e in catalogo]
    assert len(ids) == len(set(ids)), "eixo duplicado no catálogo"
    assert {"fase", "renda", "custo"} <= set(ids)
    for eixo in catalogo:
        assert eixo.arquetipos, f"eixo {eixo.id} sem arquétipos"
        for a in eixo.arquetipos:
            assert a.sinais, f"arquétipo {a.id} não tem sinal — casaria com qualquer um"
            assert a.o_que_muda, f"arquétipo {a.id} não diz qual cálculo muda"


def test_sinal_sem_dado_nao_casa():
    """Indicador ausente falha o sinal. Nada casa por omissão."""
    s = profile_mod.Sinal(indicador="taxa_poupanca", minimo=0.2)
    assert s.casa(None) is False
    assert s.casa(0.1) is False
    assert s.casa(0.3) is True


# ----------------------------------------------------------------- casamento

def test_casamento_sai_com_evidencia_e_nao_grava_nada():
    ctx = _ctx()
    leituras = profile_mod.casar(ctx)
    assert leituras, "nenhum eixo avaliado"
    for l in leituras:
        if l["sugerido"]:
            assert l["sugerido"]["evidencia"], "sugestão sem evidência anexada"
            assert l["sugerido"]["aderencia"] >= l["minimo"]
        else:
            assert l["sem_leitura_porque"], "sem sugestão e sem dizer por quê"
    # o casamento é leitura pura: o arquivo de perfil não nasce dele
    assert not (TMP / "data" / "perfil.yaml").exists()


def test_perfil_comeca_em_zero_por_cento():
    ctx = _ctx()
    assert ctx["perfil"]["cobertura"]["assinados"] == 0
    assert ctx["perfil"]["cobertura"]["pct"] == 0.0
    assert all(e["assinado"] is None for e in ctx["perfil"]["eixos"])


# ----------------------------------------------------------------- assinatura

def test_importacao_nao_assina_perfil():
    """O número sozinho não conclui quem a pessoa é — nem com confiança alta."""
    loja = profile_mod.PerfilStore(TMP / "perfil-teste.yaml")
    for origem in ("heuristica", "importacao"):
        try:
            loja.assinar(
                "fase", "acumulacao",
                proveniencia=Proveniencia(origem=origem, confianca=0.99, porque="casou"),
            )
            raise AssertionError(f"origem '{origem}' não deveria poder assinar perfil")
        except ValueError:
            pass


def test_assinar_exige_porque():
    loja = profile_mod.PerfilStore(TMP / "perfil-porque.yaml")
    try:
        loja.assinar("fase", "acumulacao", proveniencia=Proveniencia(origem="usuario"))
        raise AssertionError("deveria exigir porque")
    except ValueError:
        pass


def test_agente_nao_derruba_o_que_o_usuario_afirmou():
    loja = profile_mod.PerfilStore(TMP / "perfil-autoridade.yaml")
    loja.assinar(
        "renda", "variavel",
        proveniencia=Proveniencia(origem="usuario", porque="sou PJ, fecho por projeto"),
    )
    loja.assinar(
        "renda", "fixa",
        proveniencia=Proveniencia(origem="agente", confianca=0.95, porque="entrada igual em 6 meses"),
    )
    assert loja.tracos["renda"].arquetipo == "variavel"
    assert loja.tracos["renda"].proveniencia.origem == "usuario"


def test_arquetipo_inexistente_no_eixo_e_recusado():
    loja = profile_mod.PerfilStore(TMP / "perfil-invalido.yaml")
    try:
        loja.assinar(
            "renda", "sufocado",  # existe, mas no eixo 'custo'
            proveniencia=Proveniencia(origem="usuario", porque="t"),
        )
        raise AssertionError("deveria recusar arquétipo de outro eixo")
    except ValueError:
        pass


def test_personalizado_exige_nome_e_descricao():
    loja = profile_mod.PerfilStore(TMP / "perfil-custom.yaml")
    try:
        loja.assinar(
            "consumo", "personalizado",
            proveniencia=Proveniencia(origem="usuario", porque="nenhum dos dois me descreve"),
        )
        raise AssertionError("personalizado sem nome deveria falhar")
    except ValueError:
        pass
    t = loja.assinar(
        "consumo", "personalizado",
        nome="Concentrado em duas contrapartes",
        descricao="mercado e transporte respondem por quase tudo; o resto é ruído",
        proveniencia=Proveniencia(origem="usuario", porque="conferi no extrato dos últimos 6 meses"),
    )
    assert t.arquetipo == "personalizado"
    assert profile_mod.PerfilStore(TMP / "perfil-custom.yaml").tracos["consumo"].nome == t.nome


def test_divergencia_entre_assinado_e_sugerido_aparece():
    ws = _ws()
    report.ingest(ws, ws.extratos / "fixture.ofx")
    st = report.stores(ws)
    ctx = report.analyze(ws, st=st)

    eixo = next(e for e in ctx["perfil"]["eixos"] if e["sugerido"])
    outro = next(
        c["id"] for c in eixo["candidatos"]
        if c["id"] != eixo["sugerido"]["id"]
    )
    st["perfil"].assinar(
        eixo["eixo"], outro,
        proveniencia=Proveniencia(origem="usuario", porque="o extrato não conta a história toda"),
    )
    ctx2 = report.analyze(ws, st=st)
    assinado = next(e for e in ctx2["perfil"]["eixos"] if e["eixo"] == eixo["eixo"])
    assert assinado["assinado"]["arquetipo"] == outro
    assert assinado["diverge_da_sugestao"] is True
    assert eixo["eixo"] in ctx2["perfil"]["divergencias"]
    assert ctx2["perfil"]["cobertura"]["pct"] > 0


# ------------------------------------------------------------------ alavancas

def test_alavancas_tem_numero_e_efeito_e_nunca_conselho():
    ctx = _ctx()
    out = levers.calcular(ctx)
    assert out["alavancas"], "nenhuma alavanca calculada"
    for a in out["alavancas"]:
        assert a["numero"] is not None, f"alavanca {a['id']} sem número"
        assert a["efeito"], f"alavanca {a['id']} sem efeito recalculado"
        assert a["evidencia"], f"alavanca {a['id']} sem evidência"
        assert a["origem"] == "importacao"
        texto = " ".join(str(v) for v in a["efeito"].values())
        for proibido in ("você deveria", "recomendamos", "é melhor", "evite"):
            assert proibido not in texto.lower(), "alavanca virou conselho"


def test_alavancas_ordenadas_por_ganho():
    ctx = _ctx()
    out = levers.calcular(ctx)
    ganhos = [a["ordenacao"] for a in out["alavancas"]]
    assert ganhos == sorted(ganhos, reverse=True), "alavancas fora de ordem"


def test_alavanca_de_score_bate_com_o_recalculo():
    """O ganho prometido é o score recalculado, não uma estimativa solta."""
    ctx = _ctx()
    out = levers.calcular(ctx)
    for a in out["alavancas"]:
        if a["tipo"] != "score":
            continue
        esperado = round(a["efeito"]["score_depois"] - ctx["score"]["score"], 1)
        assert a["efeito"]["ganho_de_score"] == esperado


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
