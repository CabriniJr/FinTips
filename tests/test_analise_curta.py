"""Testes do corte da análise na fronteira do agente.

`analyze()` é a fonte única: painel, CLI, relatório em disco e agente leem a
mesma coisa. O que muda para o agente é só o **tamanho** — e a linha entre
cortar tamanho e cortar informação é justamente o que estes testes vigiam.

A regra herdada do dossiê: resumo com ponteiro, nunca resumo que esconde. Um
bloco que sai sem dizer quantos itens existem e por qual ferramenta voltar não
economiza contexto — ele faz o agente supor, que é o defeito que este projeto
existe para não ter.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fintips import report  # noqa: E402
from fintips.workspace import Workspace  # noqa: E402

FIXTURE = Path(__file__).parent / "fixture.ofx"
TMP = Path("/tmp/fintips-analise-curta")
MCP_FONTE = Path(__file__).resolve().parents[1] / "fintips" / "mcp_server.py"


def _ctx() -> dict:
    if TMP.exists():
        shutil.rmtree(TMP)
    ws = Workspace.open(TMP)
    shutil.copy(FIXTURE, ws.extratos / "fixture.ofx")
    report.ingest(ws, ws.extratos / "fixture.ofx")
    return report.analyze(ws)


def _tamanho(obj) -> int:
    return len(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def test_corte_vale_a_pena():
    ctx = _ctx()
    inteiro, curto = _tamanho(ctx), _tamanho(report.para_agente(ctx))
    # com nove transações de fixture o contexto já passa de 12 mil tokens;
    # se o corte não derrubar pelo menos metade, não está pagando a
    # complexidade que ele adiciona
    assert curto < inteiro / 2, f"cortou pouco: {inteiro} → {curto}"


def test_nenhum_bloco_some_em_silencio():
    ctx = _ctx()
    curto = report.para_agente(ctx)
    faltando = set(ctx) - set(curto)
    assert not faltando, f"blocos sumiram sem deixar ponteiro: {faltando}"


def test_todo_bloco_cortado_diz_por_onde_voltar():
    ctx = _ctx()
    curto = report.para_agente(ctx)
    for bloco in report.DETALHE_EM:
        valor = curto[bloco]
        assert isinstance(valor, dict), f"{bloco} virou {type(valor).__name__}, sem lugar para o ponteiro"
        assert valor.get("detalhe_em"), f"{bloco} foi resumido sem dizer qual ferramenta expande"


def test_o_ponteiro_aponta_para_ferramenta_que_existe():
    # ponteiro para ferramenta inexistente é pior que nenhum ponteiro: o agente
    # tenta, falha, e conclui que o detalhe não existe.
    fonte = MCP_FONTE.read_text(encoding="utf-8")
    ferramentas = set(re.findall(r"@mcp\.tool\(\)\ndef (\w+)", fonte))
    assert ferramentas, "não consegui ler as ferramentas do mcp_server.py"
    for bloco, ferramenta in report.DETALHE_EM.items():
        assert ferramenta in ferramentas, (
            f"o bloco '{bloco}' aponta para '{ferramenta}', que não é ferramenta MCP"
        )


def test_o_que_enquadra_a_conversa_passa_inteiro():
    # estes são baratos e a resposta muda sem eles — cortá-los seria economizar
    # no lugar errado.
    ctx = _ctx()
    curto = report.para_agente(ctx)
    for bloco in ("baseline", "score", "meses", "conciliacao", "contexto",
                  "patrimonio", "gastos_invisiveis", "estrutura_de_custo",
                  "cobertura_da_classificacao", "saldo_conta"):
        assert curto[bloco] == ctx[bloco], f"'{bloco}' devia passar inteiro"


def test_quantidade_real_sobrevive_ao_corte():
    ctx = _ctx()
    curto = report.para_agente(ctx, topo=2)

    assert curto["contrapartes"]["quantas"] == len(ctx["contrapartes"])
    assert len(curto["contrapartes"]["maiores"]) <= 2
    assert curto["triagem"]["quantos"] == len(ctx["triagem"]["itens"])
    assert curto["taxonomia"]["quantas"] == len(ctx["taxonomia"])
    assert curto["projecao"]["meses_projetados"] == len(ctx["projecao"]["linhas"])


def test_contraparte_cortada_e_a_menor_nunca_a_maior():
    ctx = _ctx()
    curto = report.para_agente(ctx, topo=1)
    maior = max(ctx["contrapartes"], key=lambda c: abs(c.get("custo_mensal") or 0))
    assert curto["contrapartes"]["maiores"][0]["id"] == maior["id"], (
        "o corte tirou a contraparte que mais custa"
    )


def test_o_perfil_assinado_nunca_e_cortado():
    # sugestão do catálogo é palpite e pode esperar; traço assinado é verdade
    # que já foi decidida, e some do cálculo se o agente não souber dele.
    ctx = _ctx()
    ctx["perfil"] = {
        "cobertura": {"eixos": 5, "assinados": 1, "pct": 20.0},
        "eixos": [{
            "eixo": "renda", "nome": "Renda",
            "assinado": {"arquetipo": "variavel", "nome": "Renda variável",
                         "proveniencia": {"porque": "sou PJ e recebo por projeto"}},
            "sugerido": {"id": "fixa", "nome": "Renda fixa", "aderencia": 0.8,
                         "evidencia": ["x" * 400]},
        }],
        "divergencias": [],
    }
    eixo = report.para_agente(ctx)["perfil"]["eixos"][0]
    assert eixo["assinado"]["arquetipo"] == "Renda variável"
    assert eixo["assinado"]["porque"] == "sou PJ e recebo por projeto"
    assert "evidencia" not in json.dumps(eixo), "a evidência do palpite passou junto"


def test_analyze_continua_inteiro_e_o_relatorio_em_disco_tambem():
    # o corte é da fronteira do agente. Se vazar para `analyze`, o painel e o
    # relatório perdem dado sem ninguém pedir.
    ctx = _ctx()
    ws = Workspace.open(TMP)
    caminho = report.save_report(ws, ctx)

    import yaml
    salvo = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    assert len(salvo["contrapartes"]) == len(ctx["contrapartes"])
    assert "linhas" in salvo["projecao"], "a projeção mês a mês sumiu do relatório"
    assert "detalhe_em" not in salvo["triagem"], "o corte do agente vazou para o disco"


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
