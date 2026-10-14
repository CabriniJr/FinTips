"""O registro de depósitos: um lugar só para o que o app escreve no seu disco.

Estes testes existem por causa de um erro concreto, e o erro vale mais que a
correção. A aba de configuração mostra "onde os seus dados moram", e a lista
foi escrita à mão: o `Workspace` tinha dezenove arquivos e a lista tinha onze.
Faltavam oito, entre eles `regras-locais.yaml`. A tela afirmava mostrar onde os
dados moram e mostrava pouco mais da metade.

O mesmo tipo de lista paralela existia na varredura de PII — cinco arquivos
colhidos contra dez marcados como sensíveis. `objetivos.yaml` ficava de fora,
com nome de curso pago, data de prova e custo.

A lição que estes testes travam: **toda lista paralela ao código envelhece**, e
a correção não é lembrar de atualizá-la — é derivá-la e cruzar.
"""

from __future__ import annotations

import inspect

import pytest

from fintips import configuracao as cfg
from fintips.contracts import (
    DEPOSITOS,
    POR_CHAVE,
    Deposito,
    conferir_depositos,
    migrar,
)
from fintips.workspace import Workspace

RAIZ = "."


def test_o_registro_descreve_o_workspace_de_hoje():
    r = conferir_depositos(Workspace)
    assert r["ok"], r


def test_todo_caminho_do_workspace_esta_declarado():
    """Depósito que existe no código e não está no registro some da tela."""
    no_codigo = {
        n for n, v in inspect.getmembers(Workspace, lambda o: isinstance(o, property))
        if n.endswith("_path")
    }
    assert no_codigo == {d.atributo for d in DEPOSITOS}


def test_deposito_novo_sem_declaracao_quebra_a_conferencia():
    class WorkspaceComExtra(Workspace):
        @property
        def extrato_secreto_path(self):
            return self.data / "segredo.yaml"

    r = conferir_depositos(WorkspaceComExtra)
    assert not r["ok"]
    assert "extrato_secreto_path" in r["no_codigo_e_nao_declarados"]


def test_declaracao_que_aponta_para_o_vazio_tambem_quebra(monkeypatch):
    fantasma = Deposito("fantasma", "fantasma_path", "nada", "yaml")
    monkeypatch.setattr("fintips.contracts.DEPOSITOS", DEPOSITOS + (fantasma,))
    r = conferir_depositos(Workspace)
    assert not r["ok"]
    assert "fantasma_path" in r["declarados_e_fora_do_codigo"]


def test_esquema_acima_de_um_exige_migrador(monkeypatch):
    """Quem bumpa a versão escreve o degrau no mesmo commit — o arquivo antigo
    já está na máquina de alguém, e não há como implantar correção nele."""
    sem = Deposito("planos", "planos_path", "metas", "yaml", esquema=2)
    outros = tuple(d for d in DEPOSITOS if d.chave != "planos")
    monkeypatch.setattr("fintips.contracts.DEPOSITOS", outros + (sem,))
    r = conferir_depositos(Workspace)
    assert not r["ok"]
    assert "planos" in r["esquema_novo_sem_migrador"]


def test_cada_deposito_diz_o_que_guarda_em_portugues():
    """A coluna `guarda` é texto de tela: ela aparece para a pessoa."""
    for d in DEPOSITOS:
        assert d.guarda and not d.guarda.endswith(".yaml")
        assert d.formato in ("yaml", "jsonl", "texto", "diretorio")


def test_os_arquivos_mais_sensiveis_estao_marcados():
    """Plano de vida tem salário, empregador, nome de gente e hora de dormir;
    objetivo tem nome de curso pago e data de prova."""
    sensiveis = {d.chave for d in DEPOSITOS if d.sensivel}
    assert {"missoes", "objetivos", "causas", "decisoes", "contexto",
            "patrimonio", "regras_locais", "config", "salt"} <= sensiveis


# ------------------------------------------------------- a tela deriva daqui

def test_a_tela_de_configuracao_lista_todos_os_depositos(tmp_path):
    ws = Workspace.open(tmp_path)
    arquivos = cfg.onde_os_dados_moram(ws)
    chaves = {a["chave"] for a in arquivos}
    assert {d.chave for d in DEPOSITOS} <= chaves
    assert "canonico" in chaves          # diretório, não depósito, mas tem PII
    assert all(a["no_git"] is False for a in arquivos)


def test_a_tela_mostra_o_caminho_real_daquele_workspace(tmp_path):
    ws = Workspace.open(tmp_path)
    arquivos = {a["chave"]: a["arquivo"] for a in cfg.onde_os_dados_moram(ws)}
    assert arquivos["objetivos"] == str(ws.objetivos_path)
    assert str(tmp_path) in arquivos["missoes"]


def test_a_tela_admite_quando_o_registro_nao_confere(tmp_path, monkeypatch):
    fantasma = Deposito("fantasma", "fantasma_path", "nada", "yaml")
    monkeypatch.setattr("fintips.contracts.DEPOSITOS", DEPOSITOS + (fantasma,))
    d = cfg.montar(Workspace.open(tmp_path), RAIZ)
    assert d["dados"]["registro_confere"] is False


# ------------------------------------------------------------------ migração

def test_migrar_despacha_para_o_migrador_do_deposito():
    d = migrar("perfil", {"schema_version": 1, "tracos": []})
    assert d["schema_version"] == POR_CHAVE["perfil"].esquema


def test_deposito_sem_migrador_devolve_o_dado_como_veio():
    """Correto enquanto o esquema for 1 — e a conferência é quem garante isso."""
    original = {"schema_version": 1, "planos": [{"id": "x"}]}
    assert migrar("planos", original) is original


def test_migrar_deposito_que_nao_existe_e_recusado():
    with pytest.raises(ValueError, match="não existe"):
        migrar("geladeira", {})


# -------------------------------------------------- a varredura deriva daqui

def test_a_varredura_de_pii_cobre_todo_deposito_sensivel():
    """A lista paralela que existia aqui deixava `objetivos.yaml` de fora.

    O script lê `DEPOSITOS` e colhe de todo sensível em yaml ou jsonl. Este
    teste trava a ponte: se alguém voltar a escrever caminhos à mão no script,
    os nomes de arquivo reaparecem e isto quebra.
    """
    script = open("scripts/check-pii.sh", encoding="utf-8").read()
    assert "from fintips.contracts import DEPOSITOS" in script
    assert "dep.sensivel" in script
    # Nenhum caminho de depósito sensível pode estar escrito à mão no corpo.
    for alvo in ("data/missoes.yaml", "data/registros.jsonl", "data/objetivos.yaml"):
        corpo = script.split("PYEOF")[1] if "PYEOF" in script else script
        assert alvo not in corpo, f"{alvo} voltou a ser caminho fixo na varredura"
