<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/identidade/assinatura.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/identidade/assinatura-clara.svg">
    <img src="docs/identidade/assinatura.svg" alt="FinTips — uma vida em perspectiva" width="760">
  </picture>
</p>

<p align="center">
  <a href="../../actions/workflows/portao.yml"><img src="../../actions/workflows/portao.yml/badge.svg" alt="portão"></a>
  <a href="../../actions/workflows/android.yml"><img src="../../actions/workflows/android.yml/badge.svg" alt="android"></a>
  <a href="../../releases"><img src="https://img.shields.io/github/v/release/CabriniJr/FinTips?include_prereleases&label=release&color=ffa342" alt="release"></a>
</p>

Centraliza extrato e perfil financeiro na sua máquina, e deixa a inteligência
por conta do seu agente. **O app guarda, aplica e calcula; o agente investiga,
pergunta e registra; você assina.**

```
                       ┌─ painel local (React, 127.0.0.1)
extrato.ofx ─┐         ├─ app Android (offline, sem permissão de rede)
             ├─ motor ─┤
Open Finance ┘         ├─ agente (MCP: 47 primitivas + 2 recursos)
  (Pluggy)             └─ YAML no seu disco (fonte de verdade)
```

Nada sai da máquina: sem conta, sem servidor, sem telemetria. O agente recebe
agregados, nunca o extrato bruto.

**Índice** · [Baixar](#baixar) · [A ideia](#a-ideia) · [O que ele faz](#o-que-ele-faz)
· [Como ele é](#como-ele-é) · [Identidade](#identidade) · [Instalação](#instalação)
· [Uso](#uso) · [Para onde vai](#para-onde-vai) · [Documentos](#documentos)

## Baixar

| | |
|---|---|
| **Android, última versão** | [android-v0.6.0-alpha.3](../../releases/tag/android-v0.6.0-alpha.3) |
| **Android, último build da `main`** | [android-main](../../releases/tag/android-main) — pré-release rolante, substituída a cada push |
| **Todas as versões** | [releases](../../releases) |

O APK é de **avaliação**: variante debug, com a UI web embarcada em WebView.
Sem permissão `INTERNET`, sem analytics, sem upload — os dados ficam no
aparelho, e desinstalar apaga os registros. Confira o download com
`sha256sum -c SHA256SUMS.txt`, que vai junto na release.

O motor Python é o produto que funciona hoje; o app é a porta em andamento.
Enquanto o harness diferencial não fechar módulo a módulo, não se troca um
motor testado por um que ninguém conferiu.

## A ideia

Um app de finanças que decide por você erra de um jeito específico: ele acha que
"transporte" é uma coisa só, que mercado é sempre essencial, que gasto
pulverizado é desperdício. Nenhuma dessas afirmações é verdade sobre uma pessoa
concreta — são médias disfarçadas de conselho.

Aqui a inversão é explícita: **nada é verdade sem proveniência**.

| Origem | Vale como verdade? |
|---|---|
| `heuristica` — lista embutida no pacote | não, só ranqueia o que olhar primeiro |
| `importacao` — derivado dos seus dados | não |
| `agente` — conclusão do agente, após conversar | sim |
| `usuario` — você afirmou | sim, e vence tudo |

O painel mostra, o tempo todo, **quanto do seu dinheiro está classificado por
decisão e quanto ainda é palpite**. Começa em 0%.

## O que ele faz

- **Gera objetos a partir da importação**: agrupa variações do mesmo
  estabelecimento (`Gelato Roma-LJ0046` e `-LJ0084` viram um só; `EMV CMT*144318981`
  vira `EMV CMT`), classifica cadência e mede presença mensal.
- **Triagem periódica**: a cada extrato novo, recalcula o que está em aberto —
  contraparte sem categoria, dinheiro classificado só por palpite, candidato a
  compromisso, custo fixo que derivou, contexto faltando — **ordenado pelo custo
  mensal em reais de deixar assim**.
- **Motor de regras genérico**: o agente escreve condições que descrevem
  comportamento (`uber` + `sábado e domingo` → lazer), simula antes de gravar, e
  a aplicação é determinística e reproduzível.
- **Custo fixo é afirmação, não detecção**: o motor levanta candidatos; só vira
  compromisso o que alguém confirma, com a natureza que fizer sentido (contratual,
  rotina, sazonal, reembolsado…).
- **Contexto híbrido**: núcleo demarcado para o que é universal (moradia, cartão,
  renda, reserva) + chave livre para o que é só seu
  (`transporte.reembolsado_pela_empresa`).
- **Registra a decisão, não só o gasto.** O celular quebrou: consertar por
  R$ 700 ou trocar por R$ 2.500? O motor compara pelo que decide a troca —
  R$ 87,50 contra R$ 69,44 por mês de uso — e guarda a pergunta, as
  alternativas **com o motivo de cada descarte**, os números da época e, depois,
  no que deu. Na próxima vez que a mesma pergunta aparecer (o notebook, a
  geladeira), ela chega com o precedente junto, em vez de ser refeita do zero.
  Ver `docs/DECISOES.md`.
- **Guarda o porquê, não só o quanto.** Uma causa liga um padrão de gasto ao
  motivo dele, nas palavras da pessoa, mais a atitude tomada — inclusive
  `aceitar`, que é decisão legítima e tira o gasto da lista de culpa. Causa
  nunca é derivada: duas pessoas com o mesmo extrato de delivery podem estar
  com jornada dupla ou com tédio de domingo, e só perguntar distingue.
- **Monta o perfil em cinco eixos independentes** (fase, renda, custo, consumo,
  constância). O catálogo casa arquétipos contra os seus números e devolve
  isso como **palpite, com a evidência anexada** — perfil mesmo só existe
  quando o agente conclui depois de conversar, ou quando você afirma. A tela
  mostra quanto do perfil já é decisão: começa em 0%, igual à classificação.
- **Projeta caixa** em 12 meses com cenários, e diz o mês em que cada meta fecha.
- **Calcula alavancas**: quanto falta de sobra para a próxima faixa de score, o
  que o gasto invisível custa em doze meses, quantos meses a reserva antecipa
  se ele sair do variável, que mês cada plano fecha se for priorizado. Cada uma
  é o motor rodado de novo, não uma estimativa paralela — e nenhuma é conselho.
  A frase que interpreta o número é do agente, que conversou com você.
- **Avalia intenção de compra** contra reserva, planos e o seu histórico de
  arrependimento.
- **Lê a compra à luz das seis frentes.** Dinheiro (OURO) é uma de seis
  — força, agilidade, vitalidade, intelecto, foco e ouro —, e as outras cinco
  existem para dar contexto a decisão financeira. Duas pessoas olham o mesmo
  tablet de R$ 2.500 com a mesma sobra: numa é o aparelho de estudo que falta,
  na outra é a porta de entrada do vídeo curto que ela corta há 40 dias. Nenhum
  extrato distingue; a missão declarada, sim. O motor devolve qual sequência a
  compra põe em risco, o preço em meses de aporte e as seis barras de hoje —
  **e não decide que tablet é vício**: a colisão só existe porque a pessoa
  escreveu `colide_com` na missão dela. A única coisa dessa camada que mexe no
  veredito é a regra de espera que ela mesma assinou, e ela vai nomeada na
  resposta, com o `porque` dela ao lado.
- **Decompõe o objetivo, em conversa.** Um plano financeiro responde "quanto e
  até quando", e para a maior parte do que alguém persegue isso é pouco. Uma
  certificação não é uma linha de R$ 2.000 em dezembro: são cursos com prazo
  cada um, uma prova marcada, e o estudo diário que sustenta tudo — e o
  dinheiro, normalmente, não é a frente que falha. Você conta em texto corrido;
  o agente devolve as etapas com prazo, custo e dependência, ligadas ao plano
  financeiro e às missões. **O objetivo nasce rascunho**: até você assinar, ele
  não entra na agenda, nos gauges nem no score — agenda que se enche sozinha de
  item que ninguém combinou é app desinstalado. Reajustar prazo é permitido e
  **custa**: o prazo original não se apaga, e adiamento é uma das cinco
  dimensões do score, senão bastaria empurrar a data para estar sempre em dia.
  Ver `docs/APP-DE-VIDA.md`.

## Como ele é

<p align="center">
  <img src="https://github.com/CabriniJr/FinTips/releases/download/android-v0.6.0-alpha.3/hoje.png" width="46%" alt="Tela Hoje: cabeçalho FINTIPS, seletor de semana, 2 de 4 tarefas feitas e a lista do dia">
  &nbsp;&nbsp;
  <img src="https://github.com/CabriniJr/FinTips/releases/download/android-v0.6.0-alpha.3/leitura.png" width="46%" alt="Tela Vida: as seis áreas, o livro em andamento com porcentagem e o gráfico de posições observadas">
</p>

<p align="center"><sub>
Dados sintéticos de QA, capturados no navegador com a origem local do APK —
não é captura de aparelho.
</sub></p>

A direção visual é **Neon Genesis Evangelion** — painéis chanfrados, réguas,
marcações de posição, tipografia condensada pesada. O sistema inteiro está em
[Identidade](#identidade).

Mas a escolha estética não afrouxa nenhuma regra do projeto — e é aí que o
desenho fica interessante, porque a referência empurra para o lado contrário.
Painel de Evangelion é cheio de alarme bonito que não quer dizer nada, e este
app é construído sobre a premissa de que **nada é verdade sem proveniência**.
Então:

- **Cor sozinha não comunica nada.** Nem conclusão, nem erro, nem de onde veio
  um registro. A hierarquia vem de tamanho, espaçamento e borda antes de cor,
  as seis áreas sempre exibem o nome junto do ícone, e erro tem texto e estado
  explícitos. Quem não distingue vermelho de âmbar continua lendo o app.
- **Nenhum número é enfeite.** Sem radar aleatório, sem contador inventado, sem
  alerta falso, sem estática sobre texto, sem luz piscando. As barras do dia
  mostram tarefas registradas; as linhas do gráfico de leitura ligam posições
  que você marcou, e não representam sessões. Na captura acima, o rótulo
  `Informado por você` e o `Primeira estimativa` estão ali por isso.
- **Nenhum texto elogia nem cobra.** "2 de 4 tarefas feitas" é informação;
  "quase lá!" é opinião do app sobre o seu dia, e é o que faz um app ser
  fechado.
- **O motor entrega número, a tela escolhe a forma.** `gauges()` devolve
  `valor` de 0 a 100, a `faixa` que nomeia a zona e a `legenda`. Ele não sabe o
  que é ponteiro, arco ou barra — trocar a forma não muda o motor, e mudar a
  fórmula não muda a tela. E o que ainda não tem como ser medido vem marcado
  `sem_base`: a tela desenha vazio, porque zero ali afirmaria um fracasso que
  não aconteceu.

O movimento foi pedido depois do primeiro APK e segue a mesma disciplina:
transição de 130 ms na saída e 280 ms na entrada, onda no ponto do toque,
encaixe do check — e `prefers-reduced-motion` respeitado. As fontes (Barlow
Condensed, sob SIL OFL) são distribuídas localmente: **a interface não faz
requisição a serviço de fonte nem carrega imagem remota**, o que é consequência
direta de não haver permissão de rede no APK.

Detalhe em [`docs/LINGUAGEM-VISUAL.md`](docs/LINGUAGEM-VISUAL.md), movimento em
[`docs/MOVIMENTO-UI.md`](docs/MOVIMENTO-UI.md), e os limites do protótipo em
[`docs/UI-MOBILE.md`](docs/UI-MOBILE.md). O tema escuro é a direção atual,
inclusive com o sistema no claro; um tema claro exigiria paleta e validação
próprias.

## Identidade

<p align="center">
  <img src="docs/identidade/marca.svg" alt="A marca do FinTips: painel âmbar com o canto superior direito chanfrado, carregando FT" width="104">
</p>

A marca não é um logo desenhado por fora e colado no produto: ela é **um
painel da própria interface**. Um retângulo âmbar com o canto superior direito
cortado, carregando as iniciais vazadas na cor do fundo. É literalmente o
mesmo desenho que o Android usa como ícone do app.

### O gesto

O **chanfro** é a única coisa que precisa ser lembrada. Ele aparece na marca,
no quadro da assinatura, nos cartões da interface e nas amostras da paleta
abaixo. Um retângulo com um canto cortado comunica *instrumento* — mostrador de
painel, não cartão de banco — e essa é a diferença que o app quer marcar.

Ele é sempre o **superior direito**, sempre em 45°, e nunca aparece duas vezes
na mesma forma. Chanfro em todos os cantos vira losango e perde o sentido.

### A palavra

`FINTIPS` em caixa alta, condensada e pesada, com as contraformas retangulares
— sem curva em lugar nenhum. A assinatura alinha a altura do painel da marca
com a altura da caixa alta da palavra, e é isso que faz as duas lerem como uma
peça só em vez de um ícone encostado num texto.

A linha `UMA VIDA EM PERSPECTIVA` vem em monoespaçada, espaçada, em texto
secundário. Ela é posicionamento, não slogan: o app não é sobre dinheiro, é
sobre uma vida da qual o dinheiro é uma das seis frentes.

Nos arquivos da identidade a palavra está **desenhada em `path`, não em
`text`**. SVG com texto depende da fonte existir na máquina de quem olha, e
Barlow Condensed não está em lugar nenhum por padrão — a assinatura sairia com
uma fonte qualquer, diferente a cada leitor. Dentro do produto, a fonte é
distribuída localmente sob SIL OFL, e **a interface não faz requisição a
serviço de fonte**: consequência direta de não haver permissão de rede no APK.

### A paleta

<p align="center">
  <img src="docs/identidade/paleta.svg" alt="Paleta: paper, card, ink, ink-3, accent, signal, registrado, atenção, erro" width="840">
</p>

| Papel | Token | |
|---|---|---|
| Fundo | `--paper` | `#080808` |
| Painel | `--card` | `#0d0c0b` |
| Texto | `--ink` | `#f1efe6` |
| Texto secundário | `--ink-3` | `#bdad99` |
| Ação, seção ativa | `--accent` | `#ffa342` |
| Identidade, títulos | `--signal` | `#ff4b35` |
| Progresso registrado | `--s3` | `#a4ec8c` |
| Atenção | `--warn` | `#e9c56e` |
| Erro real | `--crit` | `#ff9c8c` |

Vermelho é **estrutura** — identifica a tela, não acusa problema. Âmbar é
**ação**. Verde é **registro que existe**, nunca elogio. Quem usar vermelho
para erro e âmbar para alerta quebra o sistema, porque o vermelho já está
ocupado identificando a própria tela.

### A voz

Esta é a parte da identidade que não se vê e é a que mais define o produto.

| | |
|---|---|
| **Nunca elogia, nunca cobra** | "2 de 4 feitas" é informação. "Quase lá!" é opinião do app sobre o seu dia. |
| **Nunca conclui sem proveniência** | Todo número diz de onde veio: `Informado por você`, `Primeira estimativa`. |
| **Ausência não vira zero** | O que não tem como ser medido aparece vazio, não em 0% — zero afirmaria um fracasso que não aconteceu. |
| **Nome antes de cor** | As seis áreas sempre exibem o nome junto do ícone. Quem não distingue âmbar de vermelho continua lendo o app. |
| **Número antes de adjetivo** | "R$ 87,50 contra R$ 69,44 por mês de uso", não "a troca compensa". |

### Usando

Os arquivos estão em [`docs/identidade/`](docs/identidade/) e são gerados, não
desenhados à mão — `marca.svg`, `assinatura.svg`, `assinatura-clara.svg` e
`paleta.svg`.

Não estique a marca fora de proporção, não gire o chanfro, não troque o âmbar
por outra cor para "combinar" com um fundo, e não ponha a assinatura sobre
fotografia. Sobre fundo claro, use `assinatura-clara.svg` em vez de inverter a
escura.

O sistema completo da interface, com movimento e requisitos de porte, está em
[`docs/LINGUAGEM-VISUAL.md`](docs/LINGUAGEM-VISUAL.md).

## A jornada, em três passos

```
1. IMPORTAR            2. CONVERSAR                 3. VIVER COM ISSO
extrato .ofx      →    o agente investiga,     →    "posso comprar isso?"
(futuro: Open          pergunta e registra          "quando fecho a viagem?"
 Finance)              com evidência                "onde estou perdendo?"
```

O extrato entra e vira modelo canônico. **Nada é concluído aí** — as três
coberturas (classificação, perfil, causas) começam em 0%. O perfil nasce na
conversa com o agente, que investiga antes de perguntar e grava cada decisão
com `porque`. Daí em diante o painel centraliza o que foi acumulando, e as
perguntas do dia a dia passam a ter contra o que ser respondidas.

Detalhe de cada etapa, com os buracos que ainda existem, em `docs/JORNADA.md`.

## Instalação

```bash
pip install -e ".[tudo]"    # motor + CLI + painel + servidor MCP
```

O painel já vem compilado dentro do pacote: **não é preciso ter Node para usar**.
Node só entra para desenvolver o frontend (`cd web && npm install && npm run dev`).

## Uso

```bash
fintips init
fintips ingest "Extrato da Conta - PagBank.ofx"
fintips holdings set --conta 1500 --investido 20000
fintips analyze                                # panorama + score
fintips triagem                                # o que está em aberto
fintips categorias --criar transporte-trabalho --nome "Transporte — trabalho"
fintips contexto --gravar moradia.situacao --valor com_familia
fintips perfil                                 # sugestões, assinaturas, cobertura
fintips perfil --retrato                       # dinheiro, vida e compromissos juntos
fintips perfil --historico                     # como o perfil mudou, e por quê
fintips perfil --assinar renda --arquetipo variavel --porque "sou PJ"
fintips alavancas                              # o que muda o número, e quanto
fintips decisoes --historico "celular"         # precedentes de um assunto
fintips config                                 # privacidade, dados, IA e licenças
fintips config --licencas                      # só as atribuições do APK
fintips objetivos                              # agenda, score e atrasos
fintips objetivos --reajustar cert-nuvem       # calcula o atraso; não aplica
fintips aparelho --saida missoes.json          # catálogo para o celular
fintips mcp-config                             # config pronta do cliente MCP
fintips serve                                  # painel em http://127.0.0.1:8420
```

O workspace padrão é `~/Documents/FinTips`:

```
FinTips/
  config.yaml          seus nomes em Pix, apelidos de pessoas
  .fintips-salt        segredo local do pseudonimizador (não versionar)
  data/
    extratos/          .ofx originais
    canonico/          .yaml gerado (fonte de verdade)
    taxonomia.yaml     suas categorias, com quem as criou
    regras.yaml        regras de classificação com proveniência
    contexto.yaml      fatos sobre você, com evidência
    perfil.yaml        traços assinados, um por eixo
    causas.yaml        por que o dinheiro sai, e o que se decidiu
    decisoes.yaml      bifurcações: alternativas, escolha e desfecho
    custos-fixos.yaml  compromissos definidos
    triagem.yaml       o que já foi resolvido ou adiado
    regras-locais.yaml estabelecimentos do seu dia a dia (fora do Git)
    planos.yaml        metas financeiras
    missoes.yaml       as seis frentes (fora do Git)
    registros.jsonl    cumprimento das missões, em append (fora do Git)
    objetivos.yaml     objetivos decompostos em etapas (fora do Git)
    checks.jsonl       etapas marcadas como feitas, em append (fora do Git)
    patrimonio.yaml    saldo + investimentos
  relatorios/          análises geradas
    dossie.json        briefing do agente + correlações (derivado)
    observacoes.jsonl  uma linha por observação, vira dataframe (derivado)
```

## Rodar com Docker (Linux)

Três comandos, do zero ao painel:

```bash
./scripts/fintips-docker.sh setup          # .env com o seu UID, workspace e imagem
./scripts/fintips-docker.sh importar extrato.ofx
./scripts/fintips-docker.sh up             # http://127.0.0.1:8420
```

O `setup` resolve as três coisas que dão errado ao rodar isto em Linux: o
volume sair com dono root (ele passa o seu UID/GID para o build), o `~` do
caminho não ser expandido pelo compose (ele grava o caminho absoluto) e o
painel acabar publicado na rede (o mapeamento é `127.0.0.1:8420:8420`, e
trocar aquilo por `8420:8420` serve o seu extrato para a rede inteira).

Qualquer comando do CLI passa pelo mesmo script:

```bash
./scripts/fintips-docker.sh triagem
./scripts/fintips-docker.sh perfil
./scripts/fintips-docker.sh alavancas
./scripts/fintips-docker.sh down
```

Para conectar o agente ao mesmo workspace:

```bash
./scripts/fintips-docker.sh mcp-config     # imprime o JSON do cliente MCP
```

Seus dados ficam no workspace montado (`~/Documents/FinTips` por padrão), nunca
dentro da imagem: o container é descartável, o workspace não.

## Como plugin do Claude

`.claude-plugin/plugin.json` sobe o servidor MCP e carrega a skill `financas`,
que ensina o agente a conduzir a triagem: investigar antes de perguntar, simular
antes de gravar, e dizer o que mudou depois.

O agente chega pré-carregado: os recursos `fintips://briefing` (quem é a
pessoa, causas ativas, o que está aberto) e `fintips://spec` (a regra de
proveniência e os vocabulários) o cliente lê sozinho, sem gastar um turno. Os
prompts `conversa_de_compra` e `entender_um_gasto` trazem roteiro pronto.

As 42 ferramentas se dividem em ler (`analise_completa`, `triagem`, `investigar`,
`listar_taxonomia`, `listar_regras`, `contexto_do_usuario`, `custos_fixos`,
`buscar_transacoes`, `projecao`, `perfil`, `alavancas`, `briefing`,
`listar_causas`, `listar_decisoes`, `historico_de_decisoes`), simular
(`simular_regra`) e escrever (`criar_categoria`, `definir_regra`,
`remover_regra`, `definir_custo_fixo`, `remover_custo_fixo`, `gravar_fato`,
`esquecer_fato`, `assinar_perfil`, `esquecer_traco`, `gravar_causa`,
`decidir_causa`, `esquecer_causa`, `abrir_decisao`, `escolher_alternativa`,
`registrar_desfecho`, `esquecer_decisao`, `resolver_item`,
`salvar_plano`, `avaliar_compra`, `patrimonio`, `ingerir_extrato`).

Toda escrita exige `porque` — é o que torna a decisão auditável depois.

Para usar fora do plugin, peça a config ao próprio CLI:

```bash
fintips mcp-config                 # JSON para o Claude Desktop
fintips mcp-config --claude-code   # o comando `claude mcp add-json` pronto
```

Ele imprime o caminho absoluto do interpretador onde o fintips está instalado,
e não `"command": "python"`. A diferença importa: o cliente MCP sobe o servidor
a partir de um diretório qualquer, e o `python` do PATH quase nunca é o
interpretador certo — num venv, num pyenv, ou num Debian onde `python` sequer
existe. O sintoma é o servidor aparecer como falho no cliente sem nenhuma
mensagem útil.

## Decisões que sustentam o resto

- **Aporte não é despesa.** Mandar dinheiro para o CDB é poupança; resgate é
  liquidez voltando; Pix entre contas suas é neutro. Sem isso, a taxa de poupança
  é ficção.
- **Conciliação obrigatória.** Se a soma das transações não bate com o saldo
  declarado, o motor avisa antes de qualquer análise.
- **O LLM não calcula.** `report.analyze()` é a única fonte do contexto,
  consumida igualmente pelo painel, pelo agente e pela triagem.
- **O app não diz quem você é.** Arquétipo casado por número é `importacao` —
  palpite com evidência, que serve para começar a conversa. Um extrato com
  sobra alta pode ser disciplina ou um mês passado na casa da mãe; o extrato
  não distingue as duas coisas, e fingir que distingue é o erro que este
  projeto existe para não cometer.
- **Alavanca não é dica.** O motor entrega a régua — número e efeito
  recalculado. O conselho depende de saber se aquele gasto é a única coisa boa
  da semana da pessoa, e isso o extrato não conta.
- **Resumo com ponteiro.** O briefing que o agente carrega é enxuto, e
  `analise_completa` corta os blocos que têm ferramenta própria — perfil,
  taxonomia, contrapartes, projeção — de 12 mil para 3,4 mil tokens no fixture.
  Mas cada bloco cortado diz quantos itens existem e qual ferramenta devolve o
  detalhe. Resumir escondendo é pior que não resumir: o agente passa a supor.
  O relatório em disco e o painel continuam lendo a análise inteira.
- **PII fica em casa.** Conta vira hash; pessoa física vira apelido local ou
  pseudônimo estável. As regras públicas só citam marcas nacionais — a padaria da
  sua esquina vai em `data/regras-locais.yaml`, fora do Git, porque a lista de
  onde você compra identifica onde você mora. Ver `docs/PRIVACIDADE.md`.

## Para onde vai

O que está escrito aqui é o que já tem forma decidida — não é lista de desejo.

**O cartão de crédito é o maior ponto cego do motor.** Hoje ele enxerga a
fatura saindo da conta, como um custo fixo que varia. Ele não enxerga a compra
parcelada que comprometeu os próximos doze meses antes de aparecer em qualquer
extrato. Enquanto isso não entrar, a projeção subestima compromisso — e o
lugar certo para resolver é a mesma disciplina do resto: a parcela é afirmação
de quem comprou, não dedução do extrato.

**Sensores como evidência de máquina.** A escada de proveniência da vida já
tem o degrau `sensor`, acima de `agente` e abaixo de `usuario`, e ele está
vazio. Tempo de tela e passos são as duas primeiras entradas: o aparelho sabe
sem precisar perguntar, e isso é mais forte que memória — memória de tempo de
tela distorce a favor de quem lembra. O degrau existe desde o começo
justamente para isso não virar palpite promovido a fato.

**A tela nativa em Compose.** O APK de hoje embarca a interface web numa
WebView. A lógica do aparelho já está portada e testada contra o ouro; falta a
tela. As três primeiras são os gauges da tela inicial, o widget de check e a
tela do reajuste — contratos escritos em
[`docs/ENTRE-AGENTES.md`](docs/ENTRE-AGENTES.md).

**Open Finance via agregador**, para o extrato parar de ser um arquivo que
alguém baixa à mão. O desenho está em
[`docs/OPEN-FINANCE.md`](docs/OPEN-FINANCE.md), e a regra não muda: o que entra
vira `importacao`, que **não** conclui nada sozinho.

**O harness fechando módulo a módulo.** Enquanto o Kotlin não reproduzir o
Python inteiro, o Python é o produto. A conta de quanto falta é visível: cada
módulo portado tem um arquivo em
`kotlin/motor/src/jvmTest/resources/ouro/`, e são 18 hoje.

O que **não** está no caminho, e é decisão e não esquecimento: conta na nuvem,
sincronização entre aparelhos, telemetria, e qualquer função que deduza do
extrato o *motivo* de um gasto. O extrato mostra o dinheiro saindo; ele nunca
diz por quê.

## Antes de dar push

```bash
bash scripts/check-pii.sh --all
python3 scripts/gerar-ouro.py --conferir     # o ouro ainda é o do Python?
fintips config --conferir                    # as licenças ainda batem?
cp scripts/check-pii.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

As duas primeiras linhas rodam também no CI, em `.github/workflows/portao.yml`,
junto de `pytest`, `:motor:jvmTest` e os testes do painel. Rodar à mão continua
valendo: o CI te avisa depois do push, e o `pre-commit` te avisa antes — e a
diferença entre os dois é um commit com dado pessoal já existindo no histórico.

A segunda linha existe por causa de um furo real: depois de um merge, o ouro no
disco descrevia uma versão **anterior** do motor Python e a suíte Kotlin passava
verde contra ouro velho. Teste vermelho interrompe; ouro velho deixa os dois
motores se afastarem em silêncio.

No Windows, um comando só faz tudo (trava, commit, rebase e push):

```powershell
.\scripts\publicar.ps1 "mensagem do commit"
```

O script lê o seu `config.yaml`, `data/patrimonio.yaml`, `data/regras-locais.yaml`,
`data/missoes.yaml` e `data/registros.jsonl` — todos fora do Git — e procura
qualquer pedaço deles nos arquivos do commit. Ele próprio não guarda nada: só
sabe onde os seus dados ficam.

O catálogo de missões é o arquivo mais sensível do workspace, mais que o
extrato: ele diz a que horas você deita, quanto do salário você aporta e que
vício você está cortando. Na primeira execução com dados reais, a trava acusou
dois vazamentos já commitados — fixture de teste e molde do pacote com frases
copiadas do plano. Em colisão, o Git cede.

## Testes

```bash
python -m pytest tests/ -q              # 194 no motor Python
cd kotlin && ./gradlew :motor:jvmTest   # 134 no motor Kotlin, contra o ouro
cd web && npm test                      # o painel
```

Os testes Kotlin não conferem comportamento: conferem **paridade**. Cada um lê
um arquivo de `kotlin/motor/src/jvmTest/resources/ouro/`, gravado por
`scripts/gerar-ouro.py` a partir do Python, e cobra o mesmo número. Uma fórmula
pode estar certa nos dois lados e divergir na terceira casa — isso aparece ali
ou não aparece em lugar nenhum.

## Integração contínua

Dois workflows, e os dois existem por um motivo que já custou caro:

- **`portao.yml`** roda a cada push e PR: testes Python, `:motor:jvmTest` sem a
  flag Android (é essa linha que prova que o motor continua puro), paridade do
  ouro, varredura de PII e o build do painel.
- **`android.yml`** compila o APK e publica. Push na `main` atualiza a
  pré-release rolante `android-main`; uma tag `android-v*` cria a release
  versionada, que não se reescreve.

O segundo existe porque **a publicação não podia ser feita de outro jeito**. Os
agentes que trabalham neste repositório recebem 403 ao criar tag ou release —
não por falta de permissão (um deles tem admin), mas porque o tipo de sessão
não permite esse ato. Um workflow do Actions, sim.

### A assinatura, que não é detalhe

O Android recusa instalar uma atualização assinada com chave diferente da
instalada. A chave de depuração que o Gradle gera nasce na máquina de quem
compila — então, sem intervenção, **cada build do CI sairia com uma chave nova**
e atualizar exigiria desinstalar o app, o que apaga os registros. Num app cujos
dados só existem no aparelho, isso é perda de dado, não inconveniência.

Para resolver, em *Settings → Secrets and variables → Actions*:

| nome | tipo | o quê |
|---|---|---|
| `ANDROID_KEYSTORE_BASE64` | secret | o `debug.keystore` em base64 (`base64 -w0 ~/.android/debug.keystore`) |
| `ANDROID_CERT_SHA256` | variable | a impressão digital esperada; o build falha se mudar |

Sem o secret o build continua, mas a release sai dizendo, em letra visível, que
aquele APK não instala por cima do anterior. O workflow não finge que está tudo
bem.

## Documentos

- `docs/ENTRE-AGENTES.md` — **leia primeiro se você é um agente**: faixas, estado e log
- `docs/VISUAL.md` — índice do sistema visual, e o que a tela não decide
- `docs/LINGUAGEM-VISUAL.md` — a direção Evangelion: tokens, paleta e o que cor **não** comunica
- `docs/MOVIMENTO-UI.md` — transições, resposta ao toque e movimento reduzido
- `docs/APP-DE-VIDA.md` — as seis frentes e **objetivos**: etapas, score e reajuste
- `docs/RELEASES-ANDROID.md` — build, evidências e como a release é publicada
- `docs/PLAY-STORE.md` — o que está pronto para publicar e o que bloqueia
- `docs/JORNADA.md` — o que a pessoa vive: importar, conversar, viver com isso
- `docs/PORTE-KOTLIN.md` — a porta para Kotlin e o harness que a sustenta
- `docs/ARQUITETURA.md` — a fronteira app/agente, contratos, regras, triagem
- `docs/UI-MOBILE.md` — UI para celular: áreas de vida, tarefas diárias, planos e contexto com persistência no client
- `docs/PRIVACIDADE.md` — modelo de ameaça e o que nunca sai da máquina
- `docs/DECISOES.md` — o ADR financeiro: alternativas, números da época, desfecho
- `docs/OPEN-FINANCE.md` — por que via agregador e como plugar
