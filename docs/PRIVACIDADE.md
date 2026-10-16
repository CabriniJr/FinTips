# Privacidade e PII

## Android preview 11: extratos e separação de fluxos no aparelho

A API recebe também `fluxos_importados`: grupos de canal, origem heurística,
revisão das regras públicas, contagens e centavos por mês. A fronteira fecha
campos extras e confere totais/sinais; memo, identidades e conta continuam
locais. Pix não é classificado por nome no transporte.

A importação salva a fonte no armazenamento privado nativo, fora de backups
Android e do localStorage. A API autorizada recebe resumo por período e valores,
sem identidade bancária; o MCP legado ainda não inclui finanças. Cópia sensível
separada em Downloads, acionada pela pessoa. [Guarda, fronteira e limites](EXTRATOS-ANDROID.md).

## Direção atual: identidade financeira local, planos com contexto

Esclarecimento do usuário em 16/10/2026: valores não precisam de abstração;
o foco é proteger a identidade da origem/destino do extrato. Texto de planos,
estudos, livros/cursos e intenções de compra pode ser processado pelo agente
configurado, com o histórico pertinente. Não exigir modelo local ou substituir
esses significados por um vocabulário fechado.

Origem/destino financeiro real, contas, documentos, credenciais, extrato/memo
bruto e mapas de aliases continuam locais. A projeção por campo/proveniência
vale também em texto misto e resultados de ferramentas. O agente não pode
liberar esses campos reclassificando-os como plano. A regra de não publicar
registros pessoais no repositório continua integralmente válida.

Esta seção define o **destino da implementação**; as previews descritas abaixo
ainda têm seus limites anteriores. [Arquitetura, fronteira e sequência P3/P5](PLANO-AGENTE-DE-VIDA.md#5-fronteira-de-privacidade-identidade-financeira-contexto-preservado).

## Android preview 8: triagem com valores e labels abstratas

O usuário autorizou números, relações e componentes de cálculo com aliases;
manteve nomes e origem/destino reais no client. A triagem reconstrói o contexto
por schema, em Kotlin, sem encaminhar conversa, títulos, descrições, IDs ou
datas exatas. A correspondência dos aliases fica no aparelho. A API só sugere
opções e números válidos; gravar exige confirmação local do lote.

A conexão OpenAI é direta pelo Android, opcional e separada do MCP. Chave cifrada
com Android Keystore, digitada em janela nativa, fora do WebView, backups e
relay. `store: false` não equivale a retenção zero; valores abstratos ainda
revelam rotina. [Fronteira, persistência e API](TRIAGEM-CONVERSACIONAL.md).

## Android preview 7: motor local, consulta remota autorizada

O motor e o servidor MCP vivem no Android, em `127.0.0.1`, com bearer em
memória e foreground service controlado pela pessoa. Uma ponte externa
opcional aceita OAuth PKCE dos chats e encaminha cada consulta por WSS aberto
pelo telefone. O app conserva suas próprias aprovações por áreas. Não há cópia
remota reutilizada: offline, pausa, fonte inválida ou contexto vencido resultam
em indisponibilidade. Encerrar o serviço encerra também o canal externo.

Registros completos, nomes, títulos, datas, valores, contagens, identificadores
pessoais, OFX e texto livre ficam no client. Só a projeção fechada de estados
e fontes sai em consulta autorizada; app e relay validam a allowlist.
**Indicadores reduzidos ainda revelam rotina e não são anônimos.** Mensagens
já entregues à IA continuam sob as políticas do cliente escolhido.

O relay guarda em memória metadados de autorização e hashes das credenciais,
não arquivos pessoais nem snapshots de contexto. HTTPS/WSS protege o trânsito
externo; o bearer do MCP local não sai do telefone. Credenciais do canal e
aprovações do app também não são persistidas nesta alpha. Reiniciar app/relay
exige nova autorização; os registros do app permanecem no armazenamento local.
A hospedagem deve desativar logs de pedidos/corpos/tokens. Terminação TLS e
políticas do provedor devem ser conferidas antes da publicação na Play Store.

A variante debug declara INTERNET, permissões do foreground service e
notificação; essas permissões não limitam destinos. O código mantém o socket
local no loopback e só abre conexão externa nativa após informar uma origem
HTTPS e consentir. Não segue redirects HTTP. O WebView continua restrito aos
assets locais, sem fetch remoto. O Compose release não ganha esse serviço.
Não há domínio externo embutido, coleta automática de sensores ou analytics.

A hospedagem e as contas reais ainda não foram ativadas; os testes usam OAuth
real de protocolo, SDK MCP e fontes sintéticas. [Arquitetura e implantação](../integracoes/ponte/README.md).
As próximas seções registram o piloto anterior e o workspace Python histórico.

## Android alpha 4 e MCP remoto

Registros completos continuam no client. O fluxo Conectar IA permite escolher
indicadores reduzidos de rotina, estado dos planos por área e estados do ritmo
de leitura. O motor Kotlin aplica allowlist antes de abrir o navegador externo;
a pessoa revisa o JSON integral. Não exporta títulos, nomes, IDs, datas, valores,
lista de apps ou texto livre. Indicadores reduzidos ainda revelam aspectos da
rotina e **não são anunciados como anônimos**.

O navegador exige confirmação antes de enviar ao servidor escolhido. O piloto
MCP remoto é somente leitura; snapshots expiram em uma hora e podem ser
revogados. A revogação não apaga mensagens já recebidas pela IA. Credenciais
de bancos e fontes ficam locais; tokens OAuth do conector ficam com o serviço
e o cliente de IA, como parte da autorização. O APK não tem INTERNET, mas
o navegador tem sua própria rede: isso é saída opcional de contexto.

Hospedagem e contas ainda não estão configuradas/testadas. Contrato, retenção
e limites: [motor embarcado](MOTOR-EMBARCADO-MCP.md) e
[serviço MCP](../integracoes/mcp/README.md). As seções seguintes descrevem o
workspace Python local, que não é publicado por este novo serviço.

Extrato bancário é um dos conjuntos de dados pessoais mais reveladores que
existem: identifica onde você esteve, com quem se relaciona, o que consome e
quanto ganha. O projeto trata isso como requisito, não como recurso.

## Princípios

1. **Local por padrão.** Extratos e YAML canônico ficam em
   `~/Documents/FinTips`. O servidor MCP roda na sua máquina e lê do disco.
2. **Minimização na saída.** O que vai para o modelo é o agregado e o
   necessário; o texto bruto do banco só é gravado se você ligar
   `incluir_memo_bruto: true`.
3. **Identificador direto nunca é persistido em claro.**

| Dado | Como fica no YAML |
|---|---|
| Número da conta | `acct:0a1b2c3d4e` (SHA-256 com sal local) |
| Nome de pessoa física | apelido que você definiu (`pai`) ou `PF:5ceb61` |
| CPF, CNPJ, e-mail, telefone, cartão | removidos do texto (`[cpf]`, `[email]`…) |
| Estabelecimento | em claro no YAML local; nas **regras públicas**, só marcas nacionais |
| FITID | mantido, porque é a chave de deduplicação entre extratos |

O pseudônimo é **estável**: a mesma pessoa gera o mesmo `PF:` em todos os
extratos, então dá para analisar padrão de repasse sem saber de quem se trata.
O sal fica em `.fintips-salt`, só na sua máquina. Apagou o sal, quebrou a
ligação com os extratos anteriores.

## Regras locais vs. regras públicas

`fintips/rules/categories.yaml` é versionado e por isso contém apenas redes
nacionais e códigos de adquirente. Os estabelecimentos do seu bairro vão em
`data/regras-locais.yaml`, que o `.gitignore` barra e o motor funde em memória na
hora de classificar. O motivo é direto: uma lista com a sua padaria, o seu bar e a
loja de trilha onde você compra é um perfil de localização e hábito — o mesmo tipo
de dado que o resto do projeto se dá ao trabalho de pseudonimizar.

## O arquivo mais sensível do workspace não é o extrato

É `data/missoes.yaml`.

O extrato diz onde o dinheiro foi. O catálogo de missões diz a que horas você
deita, quantas vezes por semana você treina, quanto do salário você aporta, que
vício você está cortando e há quantos dias. Plano de vida tem salário,
empregador, nome de gente e valor de patrimônio no mesmo arquivo.

Por isso ele mora em `data/`, com `data/registros.jsonl` ao lado, e o pacote
carrega só o molde em `fintips/rules/exemplo-missoes.yaml` — a mesma divisão de
`regras-locais.yaml`, por uma razão mais forte.

A trava de PII colhe os termos desses dois arquivos e procura cada um nos
arquivos que vão para o commit. Como ela colhe, e por quê:

| Decisão | Motivo |
|---|---|
| lê o YAML de verdade, não com `grep` | as frases mais sensíveis estão em bloco dobrado (`porque: >`), e `grep` de linha pega só o `>` |
| texto só entra como frase (espaço + 8 caracteres) | "Leitura" sozinha acusaria metade da documentação, e varredura que grita por tudo se aprende a ignorar |
| número entra sozinho | o valor do seu aporte não é palavra genérica |
| `colide_com` fica fora | são categorias de produto ("tablet", "console"); o que é pessoal é a ligação, não a palavra |

Na primeira execução com dados reais ela acusou dois vazamentos já commitados:
o fixture de teste Kotlin e o molde do pacote carregavam frases copiadas
literalmente do plano. **O repositório foi corrigido, não o arquivo pessoal** —
em caso de colisão, o Git cede.

## O que nunca deve entrar no repositório

```gitignore
data/              # inclui missoes.yaml e registros.jsonl
relatorios/
.fintips-salt
config.yaml        # contém apelidos = nomes reais
*.ofx
```

Já está no `.gitignore` do projeto. Se for versionar, versione só o código e as
regras.

## Segredos de conector

Credenciais de Open Finance (clientId/clientSecret) não vão para arquivo do
projeto. Use variável de ambiente ou, melhor, o Gerenciador de Credenciais do
Windows via `keyring`:

```python
import keyring
keyring.set_password("fintips", "PLUGGY_CLIENT_SECRET", "...")
```

O `apiKey` de sessão vive só em memória e expira em 2 horas.

## Modelo de ameaça (o que este projeto resolve e o que não resolve)

| Ameaça | Tratamento |
|---|---|
| Vazamento do YAML (backup, sync, repo público) | sem conta, sem CPF, sem nome de terceiro |
| Conteúdo indo para o modelo | só agregados; memo bruto desligado por padrão |
| Segredo em texto plano | fora do projeto, em env/keyring |
| **Máquina comprometida** | **não resolve** — quem tem seu disco tem o extrato |
| **Reidentificação por contexto** | **parcial** — um `PF:` que recebe R$ 2.000 todo mês é identificável por quem te conhece |

## Dados de terceiros

Pessoas que aparecem no seu extrato não consentiram com nada. Por isso o padrão
é pseudonimizar, o apelido é escolha manual sua, e nenhuma análise do agente
deve produzir perfil de terceiro — o objeto da análise é você.
