"""A aba de configuração: o que o app declara sobre si mesmo.

Uma tela de configuração costuma ser um depósito de chaves e interruptores.
Aqui ela é outra coisa, e a diferença é o ponto deste módulo: **é o lugar onde
o app presta contas**. Onde os seus dados estão, o que nunca sai do aparelho,
que código de terceiros viaja junto, e por onde a sua IA entra.

Três dessas quatro respostas são também declarações legais. A ficha de
Segurança dos Dados da Play Store é uma afirmação sob responsabilidade de quem
publica; as atribuições de código aberto são exigência das próprias licenças.
Uma tela de configuração desatualizada não é um detalhe de acabamento — é o
app afirmando, para o usuário e para a loja, algo que o binário desmente.

## Por que nada aqui é escrito à mão

Toda declaração desta tela é **derivada do código**:

- as licenças saem dos manifestos (`licencas.py`), com conferência cruzada;
- as permissões saem do `AndroidManifest.xml` que de fato foi compilado;
- os caminhos dos dados saem do `Workspace`, que é quem os cria;
- a ligação com a IA sai do mesmo gerador que escreve a config do cliente MCP.

Escrever qualquer uma delas à mão garantiria que, em algumas semanas, a tela
estivesse mentindo. É a mesma regra que atravessa o projeto — nada é verdade
sem proveniência —, aplicada ao próprio app em vez de aos dados da pessoa.

## O que esta tela deliberadamente não tem

Não há conta central. O APK de avaliação mantém um servidor MCP loopback
iniciado pela pessoa, com contexto mínimo e token por sessão. Clientes MCP
podem usar esse contexto; a ponte opcional HTTPS/WSS encaminha consultas dos
chats depois de autorização por áreas. Telemetria continua ausente. Revogações do piloto remoto anterior usam navegador.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import licencas as lic
from .contracts import DEPOSITOS, conferir_depositos

CONFIG_SCHEMA = 2

# Rascunho de transparência, não ficha submetida à Play Store. null recusa
# afirmar "nenhuma coleta" enquanto a hospedagem do conector não está definida.
DADOS_COLETADOS: list[dict] = [{"tipo": "indicadores_reduzidos", "opcional": True,
                               "quando": "consulta MCP local ou da IA após autorizar a ponte e as áreas"}]

DADOS_COLETADOS.append({"tipo": "valores_com_aliases", "opcional": True,
                       "quando": "assistência OpenAI da triagem, após revisar e autorizar a conversa"})

SEGURANCA_DOS_DADOS = {
    "coleta_dados": None,
    "coleta_automatica": False,
    "compartilha_com_terceiros": True,
    "compartilhamento_opcional": True,
    "declaracao_play_store": "pendente da hospedagem concreta da ponte e dos clientes MCP",
    "dados_em_transito_criptografados": False,  # o listener loopback não usa TLS
    "ponte_externa_criptografada": True,  # HTTPS/WSS sem downgrade ou redirect
    "transporte_atual": "HTTP loopback com bearer; ponte opcional HTTPS/WSS; triagem opcional OpenAI HTTPS",
    "permite_excluir_dados": True,
    "como_excluir": (
        "cada registro local é apagável; desinstalar apaga os dados do app. "
        "encerre o servidor local para apagar o contexto e revogar o token. "
        "Snapshots do piloto remoto anterior podem ser revogados no navegador. "
        "Cópias em Downloads e mensagens já recebidas pelos clientes são independentes"
    ),
    "por_que_nao_coleta": (
        "a variante debug usa `android.permission.INTERNET` para escutar "
        "somente em 127.0.0.1 e para uma ponte HTTPS/WSS opcional. "
        "Cada chat exige autorização por áreas; a consulta recebe indicadores "
        "reduzidos, sem cópia no relay, arquivos ou registros completos. "
        "Na triagem, números com aliases e cálculos podem ir à OpenAI; texto, nomes, "
        "datas exatas e origem/destino reais ficam locais. A chave é cifrada no Android Keystore. "
        "O navegador externo ainda atende revogações do piloto anterior. "
        "Isso não torna os indicadores anônimos"
    ),
}


def _manifestos_do_app(raiz: Path):
    """O APK de instrumentação tem permissões próprias e não é o app entregue."""
    for m in sorted((raiz / "kotlin").rglob("AndroidManifest.xml")):
        partes = (parte.lower() for parte in m.relative_to(raiz / "kotlin").parts)
        if any("androidtest" in parte or "unittest" in parte for parte in partes):
            continue
        yield m.read_text(encoding="utf-8")


def _permissoes_do_manifesto(raiz: Path) -> list[str]:
    """As permissões que o APK realmente pede.

    Lido do manifesto compilado, e não de uma lista paralela: a pergunta que
    importa é o que o binário pede, não o que alguém lembrou de escrever.
    """
    achados: list[str] = []
    for texto in _manifestos_do_app(raiz):
        achados += re.findall(r'uses-permission[^>]*android:name="([^"]+)"', texto)
    return sorted(set(achados))


def _flag_do_manifesto(raiz: Path, atributo: str) -> str | None:
    for texto in _manifestos_do_app(raiz):
        achou = re.search(rf'{atributo}="([^"]+)"', texto)
        if achou:
            return achou.group(1)
    return None


def onde_os_dados_moram(ws) -> list[dict]:
    """Cada arquivo do workspace, com o que ele guarda e se entra no Git.

    **Derivado de `contracts.DEPOSITOS`, não escrito aqui.** A primeira versão
    desta função tinha a lista à mão: o `Workspace` tinha dezenove arquivos e a
    lista tinha onze. Faltavam oito, entre eles `regras-locais.yaml`, que é um
    dos sensíveis — a tela afirmava mostrar onde os dados moram e mostrava
    pouco mais da metade. Uma tela de prestação de contas incompleta é pior que
    ausente, porque a pessoa lê o que está lá como se fosse tudo.

    A coluna que importa é `sensivel`. `missoes.yaml` e `objetivos.yaml` são os
    arquivos mais sensíveis que este projeto produz — eles têm salário,
    empregador, nome de gente, hora de dormir e data de prova —, e a pessoa tem
    o direito de ver, numa tela, que eles nunca saem daqui.
    """
    saida = []
    for d in DEPOSITOS:
        saida.append({
            "chave": d.chave,
            "arquivo": str(getattr(ws, d.atributo)),
            "guarda": d.guarda,
            "formato": d.formato,
            "sensivel": d.sensivel,
            "editavel_a_mao": d.editavel_a_mao,
            # Nenhum deles. `data/` inteiro está fora do Git, e esta coluna
            # existe para dizer isso em vez de deixar a pessoa supor.
            "no_git": False,
        })
    # O canônico é diretório, não depósito: ele guarda o extrato convertido, que
    # é derivado e não editado. Entra na lista porque ocupa disco e tem PII.
    saida.append({
        "chave": "canonico",
        "arquivo": str(ws.canonico),
        "guarda": "o extrato convertido, com PII já pseudonimizada",
        "formato": "diretorio",
        "sensivel": True,
        "editavel_a_mao": False,
        "no_git": False,
    })
    return saida


def ligacao_com_a_ia(ws, executavel: str = "") -> dict:
    """Como a sua IA se conecta a este motor, e o que ela recebe.

    A parte que precisa estar visível não é o JSON: é **o que atravessa**. O
    agente recebe agregados e as primitivas MCP; ele não recebe o extrato
    bruto, e isso não é promessa de boa-fé — é o formato das ferramentas.
    """
    import sys

    return {
        "protocolo": "MCP (Model Context Protocol)",
        "roda_onde": "na sua máquina, iniciado pelo seu cliente de IA",
        "config": {
            "mcpServers": {
                "fintips": {
                    "command": executavel or sys.executable,
                    "args": ["-m", "fintips.mcp_server", "--root", str(ws.root)],
                }
            }
        },
        "comando_para_gerar": "fintips mcp-config",
        "o_que_a_ia_recebe": [
            "agregados: baseline, score, planos, projeção, perfil",
            "as primitivas de escrita, que sempre exigem `porque`",
        ],
        "o_que_a_ia_nunca_recebe": [
            "o extrato bruto",
            "o conteúdo de `.fintips-salt`",
            "nomes completos de pessoas físicas em claro",
        ],
        "como_desligar": (
            "remova a entrada do arquivo de config do seu cliente de IA. O "
            "motor não tem serviço em execução esperando conexão: quem sobe o "
            "servidor é o cliente, quando você abre a conversa"
        ),
    }


def montar(ws, raiz: str | Path = ".", executavel: str = "") -> dict:
    """A aba inteira, derivada do código.

    Esta é a função que a tela chama. Ela não recebe nada configurável de
    propósito: uma tela de prestação de contas que aceita parâmetros é uma
    tela que pode ser instruída a dizer outra coisa.
    """
    raiz = Path(raiz)
    conferencia = lic.conferir(raiz)
    permissoes = _permissoes_do_manifesto(raiz)

    return {
        "schema_version": CONFIG_SCHEMA,
        "app": {
            "nome": "FinTips",
            "workspace": str(ws.root),
            "moeda": ws.config.get("moeda", "BRL"),
        },
        "privacidade": {
            "permissoes_do_app": permissoes,
            "sem_permissao_de_rede": "android.permission.INTERNET" not in permissoes,
            "backup_automatico": _flag_do_manifesto(raiz, "android:allowBackup"),
            "resumo": (
                "o servidor MCP da variante debug aceita só loopback e token "
                "da sessão. Uma ponte HTTPS/WSS opcional encaminha consultas "
                "autorizadas dos chats. WebView continua restrito aos assets. "
                "Registros completos permanecem no client"
            ),
            "seguranca_dos_dados": SEGURANCA_DOS_DADOS,
        },
        "dados": {
            "arquivos": onde_os_dados_moram(ws),
            "sensiveis": [d.chave for d in DEPOSITOS if d.sensivel],
            "registro_confere": conferir_depositos(type(ws))["ok"],
            "nada_sincroniza": False,
            "registros_sincronizados": False,
            "contexto_sob_demanda": True,
            "aviso": (
                "o workspace é local e independente da instalação do programa. "
                "Cópias e mensagens já recebidas pela IA são independentes; "
                "revogar um snapshot não apaga essas cópias"
            ),
        },
        "ia": ligacao_com_a_ia(ws, executavel),
        "licencas": {
            "componentes": lic.inventario(raiz, "apk"),
            "no_pacote_python": lic.inventario(raiz, "pacote_python"),
            "conferencia_ok": conferencia["ok"],
            "conferencia": conferencia,
            "aviso_se_falhar": (
                "a lista é derivada dos manifestos. Se a conferência falhar, "
                "diga na tela que ela pode estar incompleta"
            ),
        },
        "o_que_nao_existe_aqui": [
            "conta central do FinTips",
            "sincronização entre aparelhos",
            "sincronização contínua do contexto remoto",
            "telemetria — nenhum coletor ou analytics",
        ],
    }


def exportar_para_aparelho(ws, raiz: str | Path = ".") -> dict:
    """A aba de configuração no formato que o app lê.

    O celular é outra máquina: ele não enxerga o workspace do computador, e os
    caminhos de lá não significam nada nele. Então o que viaja é o que o
    aparelho pode afirmar sobre si — permissões, licenças e o que não existe —,
    e não a lista de arquivos de outra máquina.
    """
    raiz = Path(raiz)
    tudo = montar(ws, raiz)
    return {
        "schema_version": CONFIG_SCHEMA,
        "privacidade": tudo["privacidade"],
        "licencas": lic.exportar_para_aparelho(raiz),
        "o_que_nao_existe_aqui": tudo["o_que_nao_existe_aqui"],
        "nota": (
            "os caminhos de arquivo não viajam: eles são de outra máquina. O "
            "aparelho declara o que ele mesmo guarda"
        ),
    }
