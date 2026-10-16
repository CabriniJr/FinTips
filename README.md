<p align="center">
  <img src="docs/identidade/campanha.png" alt="FinTips — uma vida em perspectiva. Marca FT, painéis chanfrados e instrumentos em âmbar e vermelho sobre preto." width="1100">
</p>

<h1 align="center">FinTips</h1>
<p align="center"><strong>Seus planos. Seu contexto. No seu aparelho.</strong></p>

<p align="center">
  <a href="https://github.com/CabriniJr/FinTips/actions/workflows/portao.yml"><img src="https://github.com/CabriniJr/FinTips/actions/workflows/portao.yml/badge.svg" alt="CI: testes, paridade e privacidade"></a>
  <a href="https://github.com/CabriniJr/FinTips/releases/tag/android-main"><img src="https://img.shields.io/badge/Android-main-ffa342?style=flat-square&logo=android&logoColor=080808" alt="Android — build contínuo da main"></a>
  <a href="docs/PORTE-KOTLIN.md"><img src="https://img.shields.io/badge/Kotlin-Multiplatform-ff4b35?style=flat-square&logo=kotlin&logoColor=white" alt="Kotlin Multiplatform"></a>
  <a href="docs/PRIVACIDADE.md"><img src="https://img.shields.io/badge/dados-no_client-a4ec8c?style=flat-square" alt="Dados pessoais no client"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-bdad99?style=flat-square" alt="Licença MIT"></a>
</p>

<p align="center">
  <a href="#android">Baixar Android</a> ·
  <a href="#veja-em-ação">Demonstrações</a> ·
  <a href="#comece-no-computador">Início rápido</a> ·
  <a href="#documentação">Documentação</a> ·
  <a href="CONTRIBUTING.md">Contribuir</a>
</p>

FinTips reúne **rotina, leitura, planos de vida e finanças pessoais** para dar
contexto às suas decisões. Você escolhe as metas; o app guarda os registros e
calcula o progresso; seu agente de IA investiga, pergunta e ajuda a entender as
alternativas. As decisões continuam sendo suas.

O foco é **Android**. A interface tem a linguagem de instrumentos de *Neon
Genesis Evangelion*: preto, alto contraste, tipografia condensada, painéis
chanfrados e movimento que responde ao toque. Os dados pessoais ficam no client.

## Veja em ação

<table>
  <tr>
    <th align="center">Seu dia, em movimento</th>
    <th align="center">Um ritmo realista de leitura</th>
  </tr>
  <tr>
    <td align="center">
      <picture>
        <source media="(prefers-reduced-motion: reduce)" srcset="docs/media/hoje.png">
        <img src="docs/media/hoje.gif" width="340" alt="Demonstração: marcar tarefas, atualizar o progresso diário e alternar entre Hoje e Planos.">
      </picture>
    </td>
    <td align="center">
      <picture>
        <source media="(prefers-reduced-motion: reduce)" srcset="docs/media/leitura.png">
        <img src="docs/media/leitura.gif" width="340" alt="Demonstração: registrar uma posição no livro e ajustar frequência e prazo de leitura.">
      </picture>
    </td>
  </tr>
  <tr>
    <td align="center">Checks, progresso e transições entre abas.</td>
    <td align="center">Histórico, previsão e ajustes no seu ritmo.</td>
  </tr>
</table>

<p align="center"><sub>
Interface embarcada no APK, gravada no Chromium com dados fictícios.
Não são capturas de um aparelho Android.
<a href="docs/media/README.md">Origem e reprodução</a> ·
<a href="docs/media/hoje.png">Hoje sem animação</a> ·
<a href="docs/media/leitura.png">Leitura sem animação</a>
</sub></p>

## O que cabe aqui

| | No FinTips |
|---|---|
| **Seis áreas da vida** | Força, Movimento, Saúde, Estudos, Foco e Finanças, com tarefas e planos próprios. |
| **Rotina diária** | Tarefas recorrentes, histórico por dia e progresso baseado no que foi registrado. |
| **Livros e aprendizado** | Posições de leitura, importação local do Librera e previsão a partir do histórico. |
| **Planos com motivo** | Intenção, próximo passo e prazo. O porquê acompanha a decisão. |
| **Finanças pessoais** | Motor local com OFX, categorias, reserva, compromissos, metas, cenários e projeções. |
| **Contexto para o agente** | Servidor MCP local para investigar e registrar decisões com proveniência. |

**Nada é verdade sem proveniência.** Uma importação ou heurística ajuda a
investigar; uma conclusão exige decisão do usuário ou do agente, com motivo.
Dado ausente aparece como ausência, sem inventar progresso ou fracasso.

## Android

<p>
  <a href="https://github.com/CabriniJr/FinTips/releases/download/android-main/FinTips-Android-main.apk"><strong>↓ Baixar APK — último build da main</strong></a>
  &nbsp;·&nbsp;
  <a href="https://github.com/CabriniJr/FinTips/releases/tag/android-main">Notas, código-fonte e checksums</a>
</p>

A alpha é uma build de avaliação com a interface web embarcada em WebView.
Você já pode testar tarefas, áreas da vida, planos e leitura. O **motor Kotlin
está ligado à UI** para as frentes do dia, o ritmo dos livros e a conferência
de saldo OFX. A **preview 10 registra os extratos no aparelho**, mostra histórico
e totais observados por mês e inclui esse resumo no contexto da API do assistente.
Saldo inicial é opcional e importações repetidas não duplicam movimentações.
[Guarda, privacidade e limites](docs/EXTRATOS-ANDROID.md). Classificação, score
e cenários financeiros completos continuam no computador. A migração da tela para Compose está em andamento.

A **preview 9 coloca o agente no trabalho de registro**: em Hoje → Conversar,
você conta os planos e responde perguntas inline. A IA preenche vários campos,
prepara vínculos e mostra um resumo para salvar de uma vez. Formulários e
contratos ficam nos detalhes. Correções de ritmo podem ser feitas conversando.
A OpenAI recebe valores e referências abstratas; mensagens, nomes e
origem/destino reais ficam no Android, com a chave no Keystore. A interpretação
privada ainda usa extração local limitada; não há LLM embarcado.
[Fluxo, 14 contratos e API local](docs/TRIAGEM-CONVERSACIONAL.md).

O APK embarca um **servidor MCP no próprio celular**, iniciado em Contexto →
Servidor IA local. Ele escuta somente em `127.0.0.1`, com token por sessão e
notificação de controle. A preview 7 adiciona a ponte HTTPS/WSS com OAuth
para os dois chats: cada consulta chega ao motor no telefone, sem snapshot
remoto. A conexão exige hospedagem e aprovação por áreas em cada IA; não vem
ativada. A UI usa assets locais. Registros completos ficam no aparelho; não
há analytics ou backup automático. **Desinstalar
apaga os dados**. Faça uma cópia local antes de
remover o app. Baixe APKs pelas releases e confira `SHA256SUMS.txt`.
O início continua confirmado por consulta MCP ao socket real e oferece
**Testar servidor neste celular**, com códigos de erro e versão da build.

[Todas as releases](https://github.com/CabriniJr/FinTips/releases) ·
[Guia de avaliação](docs/APK-AVALIACAO.md) ·
[Como a build é publicada](docs/RELEASES-ANDROID.md)

## Comece no computador

Pré-requisito: **Python 3.10+**. O repositório inclui o painel compilado;
Node só é necessário para desenvolver a interface.

```bash
git clone https://github.com/CabriniJr/FinTips.git
cd FinTips
python3 -m venv .venv
source .venv/bin/activate           # Linux, macOS ou WSL
pip install -e ".[tudo]"
fintips init
fintips serve
```

Abra **http://127.0.0.1:8420**. Para trazer as finanças, importe seu extrato pela
aba Dados ou use `fintips ingest caminho/do/extrato.ofx`.
O workspace padrão é `~/Documents/FinTips`, fora do repositório.

[Comandos e Docker](docs/GUIA-TECNICO.md) ·
[Jornada de uso](docs/JORNADA.md) ·
[Desenvolvimento no Windows](CONTRIBUTING.md#ambiente)

## Seu agente, com contexto

O servidor **MCP local** fornece ferramentas para investigar gastos, simular
regras, comparar escolhas e registrar decisões com o motivo. Há um plugin do
Claude no repositório e configuração para Claude Desktop e Claude Code:

```bash
fintips mcp-config                 # configuração para Claude Desktop
fintips mcp-config --claude-code   # comando de registro no Claude Code
```

O mesmo contrato MCP roda agora **dentro do APK Android**, sem servidor externo
para executar o motor ou guardar registros. Em Contexto → Servidor IA local,
escolha áreas, revise o contexto e inicie a sessão. Os indicadores aprovados
são recalculados ao usar o app; encerrar revoga o token e apaga o contexto.

A **ponte comum para ChatGPT e Claude está implementada**: OAuth PKCE →
HTTPS → canal WSS de saída → mesmo MCP Kotlin no telefone. Cada chat tem áreas
aprovadas separadamente; pausa, offline e revogação não retornam dados antigos.
[Implantação e vínculo](integracoes/ponte/README.md) incluem Render e Compose.
**Hospedagem e consulta nas contas reais ainda precisam ser ativadas.** Código
testado não significa conta vinculada. O piloto anterior fica como histórico.
[Servidor no celular](docs/SERVIDOR-MCP-LOCAL.md) · [Privacidade](docs/PRIVACIDADE.md).

## Privacidade como arquitetura

- **PII fica no client.** Extratos, nomes, títulos de livros e planos pessoais
  não entram no Git. O agente recebe agregados, não o extrato bruto.
- **Você controla os registros.** A interface salva localmente e oferece
  cópias locais; não depende de uma conta no FinTips.
- **Origem acompanha o número.** Informado por você, importado ou estimado são
  estados diferentes. O app guarda essa diferença.

Usar um agente externo compartilha o contexto agregado com o cliente de IA
escolhido. O [modelo de privacidade](docs/PRIVACIDADE.md) detalha essa fronteira.

## Para onde vai

| Frente | Estado |
|---|---|
| Tarefas, planos e leitura no Android | Disponíveis na alpha de avaliação. |
| Motor financeiro e MCP local | Disponíveis no computador; porte Kotlin em andamento. |
| Motor Kotlin na UI Android | Frentes, pacing e conferência OFX; sem migração dos registros. |
| Servidor MCP no celular | Loopback Kotlin, token por sessão e atualização local das áreas aprovadas. |
| Mesmo MCP para ChatGPT e Claude | Ponte HTTPS/OAuth + WSS implementada; hospedagem e contas a ativar. |
| UI nativa em Compose | Em desenvolvimento. |
| Scores por área e agregado | Contratos e motor; integração visual nativa em andamento. |
| Tempo de uso e atividade física | Discovery documentado; coleta automática ainda pendente. |
| Librera cloud e TotalPass | Integrações planejadas; ainda não conectadas no APK. |

A direção é reduzir o registro manual e fazer o contexto entrar naturalmente
na rotina, com permissões explícitas e processamento no client.
[Automação](docs/AUTOMACAO-SEM-TOIL.md) · [Android primeiro](docs/ANDROID-PRIMEIRO.md)

## Como funciona

```mermaid
flowchart LR
  registros[Registros no aparelho] --> android[Android · rotina, planos e leitura]
  extrato[Extrato no computador] --> motor[Motor financeiro local]
  motor --> painel[Painel · finanças e cenários]
  motor --> mcp[MCP · contexto agregado]
  mcp --> agente[Seu agente de IA]
  classDef local fill:#080808,color:#f1efe6,stroke:#ffa342;
  classDef contexto fill:#080808,color:#f1efe6,stroke:#ff4b35;
  class registros,android,extrato,motor,painel local;
  class mcp,agente contexto;
```

O **Python é a referência funcional**. O motor Kotlin Multiplatform é conferido
contra arquivos de ouro gerados pelo Python. O destino é Kotlin e Compose no
Android; cada porte precisa manter a paridade.

[Arquitetura](docs/ARQUITETURA.md) · [Porte Kotlin](docs/PORTE-KOTLIN.md) ·
[Guia técnico](docs/GUIA-TECNICO.md)

## Documentação

| Quero… | Começar por… |
|---|---|
| Testar no celular | [Avaliação Android](docs/APK-AVALIACAO.md) |
| Entender o produto e os objetivos | [App de vida](docs/APP-DE-VIDA.md) · [Jornada](docs/JORNADA.md) |
| Acompanhar o agente de planejamento | [Plano de execução: contexto global, artefatos, agenda e MCP](docs/PLANO-AGENTE-DE-VIDA.md) — proposto, ainda não disponível no APK |
| Conhecer o modelo de dados e o agente | [Arquitetura](docs/ARQUITETURA.md) · [Guia técnico](docs/GUIA-TECNICO.md) |
| Entender como meus dados são protegidos | [Privacidade](docs/PRIVACIDADE.md) |
| Explorar automação e conectores | [Automação](docs/AUTOMACAO-SEM-TOIL.md) · [Librera](docs/LEITURA-LIBRERA.md) · [Open Finance](docs/OPEN-FINANCE.md) |
| Usar a identidade visual | [Kit de marca](docs/identidade/README.md) · [Linguagem visual](docs/LINGUAGEM-VISUAL.md) · [Movimento](docs/MOVIMENTO-UI.md) |
| Compilar, testar ou contribuir | [Contribuição](CONTRIBUTING.md) · [Porte Kotlin](docs/PORTE-KOTLIN.md) · [Releases](docs/RELEASES-ANDROID.md) |

## Contribua

Bugs, ideias e PRs são bem-vindos. Leia [CONTRIBUTING.md](CONTRIBUTING.md) para
preparar o ambiente, executar o portão de qualidade e trabalhar nas frentes
ativas. Demonstrações e issues devem usar **dados fictícios**, sem anexar
extratos, backups ou planos pessoais.

[Reportar um bug](https://github.com/CabriniJr/FinTips/issues/new) ·
[Ver trabalho aberto](https://github.com/CabriniJr/FinTips/pulls) ·
[Coordenação entre agentes](docs/ENTRE-AGENTES.md)

---

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: light)" srcset="docs/identidade/logo-claro.png">
    <img src="docs/identidade/logo-escuro.png" alt="FinTips" width="180">
  </picture>
  <br><sub>Código sob <a href="LICENSE">MIT</a> · Barlow Condensed sob <a href="web/src/fonts/OFL.txt">SIL OFL</a></sub>
</p>
