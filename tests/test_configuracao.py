"""A aba de configuração como contrato, e as licenças como declaração.

O que estes testes protegem não é uma tela. É a honestidade de duas
declarações que têm peso fora do app: a ficha de Segurança dos Dados da Play
Store, que é afirmação sob responsabilidade de quem publica, e as atribuições
de código aberto, que são exigência das próprias licenças.

Toda vez que um deles quebrar, o app terá começado a afirmar sobre si mesmo
algo que o binário desmente.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from fintips import configuracao as cfg
from fintips import licencas as lic
from fintips.workspace import Workspace

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def ws():
    return Workspace.open(tempfile.mkdtemp())


# -------------------------------------------------------------- licenças

def test_a_conferencia_passa_no_repositorio_de_hoje():
    r = lic.conferir(RAIZ)
    assert r["ok"], r


def test_dependencia_nova_sem_declaracao_quebra(tmp_path):
    """O caso comum, e o mais perigoso: o app continua funcionando e a tela
    continua bonita enquanto deixa de citar código que viaja no binário."""
    _copia_minima(tmp_path)
    g = tmp_path / "kotlin" / "app" / "build.gradle.kts"
    g.write_text(g.read_text() + '\nimplementation("com.squareup.okhttp3:okhttp:4.12.0")\n')
    r = lic.conferir(tmp_path)
    assert not r["ok"]
    assert "gradle:com.squareup.okhttp3:okhttp" in r["nao_declarados"]


def test_declaracao_que_sobrou_tambem_quebra(tmp_path):
    """Atribuir crédito a código que não viaja mais é errar para o outro lado."""
    _copia_minima(tmp_path)
    p = tmp_path / "fintips" / "rules" / "licencas.yaml"
    d = yaml.safe_load(p.read_text())
    d["componentes"].append(
        {"id": "pypi:requests", "nome": "Requests", "licenca": "Apache-2.0",
         "embarca_em": ["pacote_python"]}
    )
    p.write_text(yaml.safe_dump(d, allow_unicode=True))
    r = lic.conferir(tmp_path)
    assert not r["ok"]
    assert "pypi:requests" in r["declarados_sem_uso"]


def test_copyleft_forte_para_tudo(tmp_path):
    """Não é o inventário que decide o que podemos publicar."""
    _copia_minima(tmp_path)
    p = tmp_path / "fintips" / "rules" / "licencas.yaml"
    d = yaml.safe_load(p.read_text())
    d["componentes"][0]["licenca"] = "GPL-3.0"
    p.write_text(yaml.safe_dump(d, allow_unicode=True))
    r = lic.conferir(tmp_path)
    assert not r["ok"]
    assert r["licenca_que_bloqueia"]


def test_licenca_desconhecida_nao_e_assumida_como_permissiva(tmp_path):
    """Assumir aqui é assumir risco jurídico por omissão."""
    _copia_minima(tmp_path)
    p = tmp_path / "fintips" / "rules" / "licencas.yaml"
    d = yaml.safe_load(p.read_text())
    d["componentes"][0]["licenca"] = "LicencaQueNinguemViu-1.0"
    p.write_text(yaml.safe_dump(d, allow_unicode=True))
    r = lic.conferir(tmp_path)
    assert not r["ok"]
    assert r["sem_licenca_conhecida"]


def test_o_pyproject_e_lido_por_parser_e_nao_por_regex():
    """A primeira versão varria strings com operador e achou uma dependência
    chamada `motor`, que era a seta `->` da descrição do projeto."""
    nomes = [n for n, _ in lic._python(RAIZ)]
    assert "pypi:motor" not in nomes
    assert "pypi:pyyaml" in nomes


def test_a_varredura_do_gradle_enxerga_debugimplementation():
    """Foi por `debugImplementation` que o webkit entrou no APK."""
    ids = [i for i, _ in lic._gradle(RAIZ)]
    assert "gradle:androidx.webkit:webkit" in ids


def test_o_que_so_serve_para_compilar_nao_entra_na_tela():
    """A loja cobra atribuição do que vai no binário. Vite e Babel não vão —
    e uma tela com 117 pacotes de build é uma tela que ninguém lê."""
    nomes = {c["nome"] for c in lic.inventario(RAIZ, "apk")}
    assert "react" in nomes
    assert not any("vite" in n or "babel" in n for n in nomes)


def test_a_superficie_decide_a_lista():
    apk = {c["id"] for c in lic.inventario(RAIZ, "apk")}
    py = {c["id"] for c in lic.inventario(RAIZ, "pacote_python")}
    assert "pypi:fastapi" in py and "pypi:fastapi" not in apk
    assert "gradle:androidx.webkit:webkit" in apk


def test_superficie_inexistente_e_recusada():
    with pytest.raises(ValueError, match="não existe"):
        lic.inventario(RAIZ, "geladeira")


def test_toda_atribuicao_leva_o_nome_da_licenca_e_se_exige_aviso():
    for c in lic.inventario(RAIZ, "apk"):
        assert c["licenca_nome"]
        assert isinstance(c["exige_aviso"], bool)


# ---------------------------------------------------------- configuração

def test_as_permissoes_vem_do_manifesto_compilado(ws):
    """A pergunta que importa é o que o binário pede, não o que alguém
    lembrou de escrever numa lista paralela."""
    d = cfg.montar(ws, RAIZ)
    assert d["privacidade"]["permissoes_do_app"] == []
    assert d["privacidade"]["sem_permissao_de_rede"] is True
    assert d["privacidade"]["backup_automatico"] == "false"


def test_a_ficha_da_loja_diz_que_nao_coleta_e_diz_por_que(ws):
    s = cfg.montar(ws, RAIZ)["privacidade"]["seguranca_dos_dados"]
    assert s["coleta_dados"] is False
    assert s["compartilha_com_terceiros"] is False
    assert "INTERNET" in s["por_que_nao_coleta"]


def test_a_tela_lista_o_salt_entre_os_arquivos(ws):
    """Sem ele os apelidos não voltam — e quem copia o workspace sem o salt
    descobre isso tarde."""
    arquivos = cfg.montar(ws, RAIZ)["dados"]["arquivos"]
    assert any(".fintips-salt" in a["arquivo"] for a in arquivos)
    assert all(a["no_git"] is False for a in arquivos)


def test_a_ligacao_com_a_ia_diz_o_que_nao_atravessa(ws):
    ia = cfg.montar(ws, RAIZ)["ia"]
    assert "fintips" in ia["config"]["mcpServers"]
    assert any("extrato bruto" in x for x in ia["o_que_a_ia_nunca_recebe"])
    assert any("salt" in x for x in ia["o_que_a_ia_nunca_recebe"])


def test_nao_existe_interruptor_de_telemetria(ws):
    """Um interruptor, mesmo desligado, ensinaria que existe caminho de saída."""
    d = cfg.montar(ws, RAIZ)
    assert any("telemetria" in x for x in d["o_que_nao_existe_aqui"])
    assert "telemetria" not in json.dumps(d["app"], ensure_ascii=False).lower()


def test_o_aparelho_nao_recebe_caminho_de_outra_maquina(ws):
    """O celular é outra máquina: os caminhos de lá não significam nada nele."""
    d = cfg.exportar_para_aparelho(ws, RAIZ)
    assert "dados" not in d
    assert str(ws.root) not in json.dumps(d, ensure_ascii=False)
    assert d["licencas"]["quantos"] > 0


def test_o_export_carrega_o_resultado_da_conferencia(ws):
    """A tela precisa poder dizer que a lista pode estar incompleta em vez de
    apresentá-la como completa."""
    d = cfg.exportar_para_aparelho(ws, RAIZ)
    assert d["licencas"]["conferencia_ok"] is True
    assert "incompleta" in d["licencas"]["nota"]


def _copia_minima(destino: Path) -> None:
    """Copia só o que a conferência lê — manifestos e a declaração."""
    for rel in (
        "pyproject.toml",
        "fintips/rules/licencas.yaml",
        "kotlin/app/build.gradle.kts",
        "kotlin/motor/build.gradle.kts",
        "web/package-lock.json",
    ):
        alvo = destino / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes((RAIZ / rel).read_bytes())
