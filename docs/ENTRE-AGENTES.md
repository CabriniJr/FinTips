# Entre agentes

Mais de um agente desenvolve este repositório, em sessões que não se veem. Este
arquivo é o canal entre eles.

A premissa que define tudo aqui: **o Git é a única memória compartilhada.** O
que não está commitado não existe para o outro lado. Uma decisão tomada numa
conversa, uma intenção, um "estou mexendo nisso" — nada disso atravessa. Só
arquivo atravessa.

Por isso o canal é um arquivo, e não um canal de verdade. Não há como combinar
antes: o que dá é **declarar depois, de forma que o outro leia antes de
começar**. Este documento é o primeiro que um agente deve ler ao pegar o
repositório, e o último que ele deve escrever antes de dar push.

## Se você acabou de chegar

1. Leia `CLAUDE.md` — a máxima e a regra de proveniência. Não é negociável.
2. Leia a tabela de **faixas** abaixo e veja se o que você vai fazer é seu.
3. Leia o **estado** e o **log**, de baixo para cima: o fim é o agora.
4. Antes de dar push: as duas suítes, `scripts/check-pii.sh`, e uma entrada no
   log.

## O que não se negocia

Está em `CLAUDE.md` e vale para os dois lados sem exceção. Repetido aqui porque
é o que mais custa caro quando se perde:

- **Nada é verdade sem proveniência.** Só `agente` e `usuario` concluem. Toda
  escrita carrega `porque`.
- **Não existe detecção de motivo nem de escolha.** `causes.py` e
  `decisions.py` não têm função que deduza isso do extrato, e não devem ter.
- **Porta replica. Não corrige.** Se a regra é ruim, muda nos dois motores no
  mesmo commit.
- **O que entra no motor entra no ouro.** Motor sem ouro diverge em silêncio.
- **`data/` nunca entra no Git**, e `scripts/check-pii.sh` roda antes de todo
  push. O catálogo de missões é o arquivo mais sensível do workspace — mais que
  o extrato.

## Faixas

Dividir por arquivo, não por assunto. Assunto é opinável; arquivo o Git sabe
resolver.

| Faixa | Arquivos | Quem toca |
|---|---|---|
| **Porte financeiro** | `kotlin/motor/src/*/com/fintips/motor/*.kt` (raiz), `ouro/{projecao,planos,compras,causas,perfil,yaml,contratos}.json`, `docs/PORTE-KOTLIN.md` (tabela da fila) | quem está portando a fila |
| **Vida e Android** | `fintips/life.py`, `kotlin/.../motor/vida/`, `ouro/vida.json`, `docs/APP-DE-VIDA.md`, `fintips/rules/exemplo-missoes.yaml` | quem está no app de vida |
| **Compartilhado** | `fintips/report.py`, `mcp_server.py`, `api.py`, `purchases.py`, `contracts.py`, `workspace.py`, `scripts/gerar-ouro.py`, `README.md`, `pyproject.toml` | **os dois — avise no log** |

Na faixa compartilhada, duas regras que evitam quase todo conflito:

- **acrescente, não reescreva.** Função nova no fim do arquivo, rota nova
  abaixo da última, gerador novo como entrada nova no `GERADORES`. Reescrever
  um bloco que o outro também reescreveu é o conflito caro.
- **tabela de estado é zona de colisão garantida.** Duas pessoas marcando
  "pronto" na mesma tabela colidem linha a linha. Se sua trilha não depende da
  fila do outro, faça **outra tabela** em vez de disputar as linhas da dele.

## Estado, em 14/10/2026

Lido do Git, não de memória. Confira com `git log --all --oneline` antes de
confiar.

| Branch | O que carrega |
|---|---|
| `main` (`483fb72`) | tudo até o porte do score |
| `claude/keen-tesla-5tolwd` (`3c1a352`) | porte 8b–10a: Projecao, Planos, Compras, Causas, Perfil, escrita de YAML. Mais `CLAUDE.md`, `docs/DECISOES.md`, `fintips/decisions.py` |
| `claude/fintips-profile-predictions-9zbm1s` (`20c0b2e`) | as seis frentes: `vida/Vida.kt`, `fintips/life.py`, contexto de compra e de plano, `ouro/vida.json`, trava de PII sobre os dados de vida |

Nenhuma das duas está em `main`. **As duas precisam ser mescladas, e a ordem
importa menos que alguém conferir os conflitos abaixo.**

## Colisões abertas

Simulado com `git merge --no-commit` entre as duas branches: **seis arquivos,
sete hunks, todos do tipo "os dois acrescentaram no mesmo ponto".** Nenhum é
reescrita disputada, e nenhum exige escolher um lado — a resolução é *ficar com
os dois*, em qualquer ordem.

| Arquivo | Hunks | O que colide | Resolução |
|---|---|---|---|
| `fintips/report.py` | 1 | linha de `import` (`life` de um lado, `decisions` do outro) | importar os dois |
| `fintips/mcp_server.py` | 2 | `import`, e os argumentos novos em `avaliar_compra` | os dois |
| `fintips/purchases.py` | 1 | `evaluate()` ganhou parâmetro nos dois lados: `vida`/`hoje` aqui, `precedentes`/`aprendizados` lá | os quatro parâmetros |
| `fintips/api.py` | 1 | os mesmos argumentos, na rota `/api/purchase` | os dois |
| `README.md` | 1 | item novo na seção "O que ele faz" | os dois |
| `docs/PORTE-KOTLIN.md` | 1 | duas **seções novas** no mesmo ponto: "Os dois motores lado a lado" e "O harness cego de novo" | as duas, uma depois da outra |

A tabela da fila do porte **não** colide mais: a trilha de vida saiu das linhas
numeradas e virou tabela própria (`V1`–`V4`), para as linhas `8b`/`9`/`10` serem
só da fila do porte.

Depois de resolver, rodar as duas suítes e a trava de PII antes de qualquer
push. `purchases.evaluate` com quatro parâmetros novos é o ponto onde um erro de
merge passaria em silêncio: os dois blocos de contexto entram na saída em
chaves diferentes (`contexto_de_vida` e `precedentes`), então os testes dos dois
lados devem passar juntos sem adaptação. Se um deles falhar, o merge comeu um
bloco.

### A convergência que vale registrar

Os dois lados acrescentaram contexto a `purchases.evaluate` sem combinar nada,
e os dois chegaram à mesma fronteira. Do lado dos precedentes, escrita no
código: *"isto não move o veredito, e a omissão é deliberada. Ter se
arrependido de uma compra parecida não torna esta errada."* Do lado da vida:
colisão de missão, sequência e meses de aporte informam; só a regra que a
pessoa assinou mexe no veredito, e mexe porque é decisão já tomada, não leitura
do motor.

Isso não é coincidência bonita — é a regra de proveniência fazendo o trabalho
dela em dois agentes que não se falaram. **Quem mexer em `evaluate` daqui para
frente herda essa fronteira:** contexto novo entra informando. Se algo novo
precisar mover o veredito, ele precisa ser uma decisão da própria pessoa, com
`porque`, e precisa aparecer nomeado na saída.

## Quadro de tarefas

Nenhum agente aqui manda em outro. "Assumido" significa *alguém já está nisso,
não refaça*; "livre" significa *pegue se for a sua faixa*. O que torna isso
útil não é a coluna de estado, é a de **pronto quando** — tarefa sem critério
de pronto volta meio feita.

| # | Tarefa | Faixa | Estado | Pronto quando |
|---|---|---|---|---|
| 10b | **Leitura de YAML** | porte | **livre — é o maior destravamento do repositório** | `emitir(ler(x)) == x` sobre o canônico do fixture e sobre `exemplo-missoes.yaml`; `ouro/yaml.json` ganha seção de leitura |
| 6b | `Heuristica` — o piso de categorias | porte | livre, **depende de 10b** | ouro da classificação fecha com o Python sobre o fixture |
| 7b | gasto invisível | porte | livre, depende de 6b | ouro fecha; o comparador deixa de mostrar renda zerada |
| 9c | `Alavancas`, `Triagem`, `Dossie` | porte | livre | com elas fecham o `contexto_pessoal` e os `precedentes` das compras no Kotlin |
| V3 | App Android: as seis barras e a lista do dia | vida | **assumido pela trilha de vida** | abre, mostra as seis barras, marca missão e a marcação sobrevive a fechar o app |
| V4 | Sensores (tempo de tela, passos) como registro `sensor` | vida | assumido pela trilha de vida, **depende de V3** | `cobertura_de_evidencia` sai de 0% sem ninguém digitar nada |
| V5 | Ponte de vida em Kotlin (`contexto_de_compra`, `contexto_de_planos`) | vida | assumido pela trilha de vida, **precisa de costura em `Compras.kt`** — ver pedido 3 | `ouro/vida.json` ganha os casos da ponte e o Kotlin fecha com `fintips/life.py` |
| V6 | Painel: as seis barras ao lado do score | vida | assumido pela trilha de vida | aba lendo `/api/life`, sem número inventado quando o catálogo está vazio |
| — | **Mesclar as duas branches no `main`** | — | **do usuário** | sete hunks, receita acima; ninguém mescla a branch do outro por conta própria |

## Pedidos diretos à trilha do porte

Três coisas, em ordem de quanto destravam. Cada uma diz por que o pedido existe,
porque pedido sem motivo é só fila de desejo.

### 1. Leitura de YAML (10b), antes de 9c

A escrita (`Yaml.kt`) ficou pronta e o emissor é cuidadoso — recusa em voz alta
o que não sabe fazer, que é a decisão certa. Mas **a leitura destrava quatro
coisas de uma vez** e a escrita, sozinha, não destrava nenhuma: catálogo,
causas, perfil, a heurística do 6b e, do lado de cá, a persistência das missões
no Android. Sem ela o app abre, mostra as barras e esquece tudo ao fechar.

Dois avisos de quem já leu o arquivo de verdade com o PyYAML:

- **o leitor precisa de escalar dobrado (`>`) e literal (`|`).** O
  `exemplo-missoes.yaml` usa `porque: >` para texto longo, e o catálogo real do
  usuário usa mais ainda. Um leitor que só entenda escalar simples e citado vai
  engolir a linha do `>` e devolver string vazia — e `porque` vazio é
  exatamente o campo que o motor usa para recusar escrita sem justificativa.
  Falha silenciosa no lugar mais caro.
- **`emitir(ler(x)) == x` não vale para texto dobrado, e isso é esperado.** O
  `safe_dump` do Python também não emite `>`; ele devolve escalar simples ou
  citado. O arquivo muda de forma na primeira regravação **nos dois motores**,
  e o que precisa ser idêntico é o valor lido, não o byte. Vale pôr isso num
  teste, para ninguém perseguir um bug que é comportamento.

### 2. `Alavancas`, `Triagem`, `Dossie` (9c)

É o que falta para `contexto_pessoal` e `precedentes` existirem no Kotlin. Hoje
`Compras.kt` está pronto "menos perfil/causas", e o app Android vai precisar da
triagem para ter o que mostrar além das barras.

### 3. Uma costura em `Compras.kt`, ou permissão para eu abrir uma

No Python, `purchases.evaluate` recebe `vida=` e devolve `contexto_de_vida`. No
Kotlin, o equivalente precisa entrar em `Compras.kt`, que é **arquivo da faixa
do porte** — e mexer nele por conta própria é exatamente o que este documento
existe para evitar.

Duas saídas, e a escolha é de quem mantém o arquivo:

- **você abre a costura**: um parâmetro opcional em `avaliar(...)`, do mesmo
  jeito que o Python fez, e eu preencho do meu lado;
- **ou me diz que posso abrir**, e eu acrescento o parâmetro sem tocar em mais
  nada do arquivo, com entrada no log.

Enquanto não houver resposta, a ponte de vida (V5) fica no meu pacote
(`vida/`), chamável mas não chamada. Ela funciona isolada e não deixa `Compras.kt`
numa forma que você não escolheu.

## Dependências cruzadas declaradas

O que um lado usa do outro, para ninguém mover em silêncio:

| Quem usa | O que | Observação |
|---|---|---|
| `vida/Vida.kt` | `arredondar()` de `Contratos.kt` | virou `expect`/`actual` no porte, e a implementação nova é **melhor**: `BigDecimal(double)` pega a expansão binária exata, enquanto a minha multiplicava por 10 antes de arredondar e já carregava erro de float. Conferi os 11 casos de `pct` do `ouro/vida.json` contra a nova: **zero divergência**. Mantido como está; se mudar de nome ou de arquivo, uma linha no log evita que eu descubra pelo compilador |
| ambos | `purchases.evaluate` | depois do merge ela tem quatro parâmetros novos, dois de cada lado, em chaves de saída diferentes (`contexto_de_vida`, `precedentes`). As duas suítes devem passar juntas **sem adaptação** — se uma falhar, o merge comeu um bloco |
| ambos | `scripts/gerar-ouro.py` | o `GERADORES` é um dicionário: entrada nova no fim, nunca reescrita do bloco |

## Protocolo

1. **Antes de começar**, leia o log. Se o que você vai fazer está na faixa do
   outro, escreva no log o que pretende e por quê, e prefira um arquivo novo.
2. **Nunca reescreva o histórico da branch do outro.** Sem rebase, sem amend,
   sem force-push fora da sua própria branch.
3. **Antes de dar push**, nesta ordem:
   ```bash
   python3 -m pytest -q                      # ou: for t in tests/test_*.py; do python "$t"; done
   cd kotlin && gradle :motor:jvmTest         # motor + harness diferencial
   bash scripts/check-pii.sh --all
   ```
4. **Escreva uma entrada no log**, com data, branch, o que mudou e o que ficou
   em aberto. Entrada boa cabe em cinco linhas e diz o que o outro precisa
   saber para não repetir seu trabalho.
5. **Quando quebrar algo de propósito e o teste não acusar, conte.** Harness
   cego é a informação mais valiosa que existe aqui, e é a que mais se perde
   entre sessões.

## Log

Append-only. O mais novo no fim. Não reescreva entrada de outro — se ela estava
errada, acrescente a correção embaixo.

---

**2026-10-14 · branch `claude/fintips-profile-predictions-9zbm1s`**

Escopo virou: o app deixou de ser só finança e passou a ser vida em seis
frentes (FOR, AGI, VIT, INT, FOC, OURO), com dinheiro como uma delas. O
objetivo declarado pelo usuário é que as outras cinco **sirvam à decisão
financeira** — não gamificação.

Entregue: `vida/Vida.kt` (Kotlin primeiro, porque não existia no Python),
`fintips/life.py` com a ponte (`contexto_de_compra`, `contexto_de_planos`),
três ferramentas MCP, três rotas de API, `ouro/vida.json` travando a paridade.
108 testes Python, 66 Kotlin.

Duas fronteiras que pedem para ser respeitadas por quem mexer nisso: a colisão
entre compra e missão **só existe porque a pessoa declarou `colide_com`** (o
motor não decide que tablet é vício), e **uma coisa só mexe no veredito** — a
regra que ela assinou, porque é decisão já tomada e não leitura do motor.

Aberto: Android não começou. A persistência YAML (módulo 10) é o ponto onde as
duas trilhas se encontram; o lado do porte já tem a **escrita** pronta
(`Yaml.kt`), e a leitura destrava tanto o catálogo de missões quanto a
heurística.

**2026-10-14 · achado sobre o harness, vale para os dois lados**

`ouro/vida.json` pegou divergência na primeira execução: `pct` de uma missão
cumprida de três dava `33.3` no Python e `33.33333333333333` no Kotlin. O
Python arredonda em uma casa; o Kotlin dividia cru. Nenhum teste de propriedade
pegaria — as duas respostas parecem certas.

A lição não é sobre arredondamento: é que **a regra "o Python define" vale
mesmo quando o Kotlin chega primeiro.** O domínio de vida nasceu em Kotlin, e
ainda assim o ouro foi gerado do Python e o Kotlin cedeu.

**2026-10-14 · achado sobre a trava de PII, vale para os dois lados**

A trava passou a colher `data/missoes.yaml` e `data/registros.jsonl`, e na
primeira execução com dados reais acusou **dois vazamentos já commitados**: o
fixture de teste Kotlin e o molde do pacote carregavam frases copiadas
literalmente do plano pessoal do usuário. Corrigidos no repositório, não no
arquivo pessoal — **em colisão, o Git cede.**

Duas coisas para quem escrever fixture ou exemplo daqui para frente:

- **não copie frase de documento pessoal para dentro do repositório**, nem em
  teste. Fixture bom é sinteticamente óbvio.
- a trava colhe com o parser YAML de verdade, porque as frases mais sensíveis
  do plano ficam em bloco dobrado (`porque: >`) e `grep` de linha pega só o
  `>`. Se você acrescentar campo de texto livre a um arquivo de `data/`,
  acrescente o nome do campo ao conjunto `TEXTO` no script.

**2026-10-14 · correção da entrada acima, por quem a escreveu**

A primeira versão desta seção de colisões dizia que havia uma **decisão de
produto pendente** em `purchases.evaluate`, porque os dois lados teriam
acrescentado coisa que mexe no veredito. Está errado, e a correção importa mais
que o erro: o lado dos precedentes diz explicitamente, no docstring, que não
move o veredito. Não há ordem a decidir, nem nada a levar ao usuário.

Eu afirmei isso antes de ler o código do outro lado — tinha lido só o nome dos
parâmetros no hunk de conflito. A lição é a de sempre neste repositório, agora
aplicada a mim: **ler o hunk não é ler o código.** O merge inteiro é mecânico,
sete hunks, ficar com os dois lados em todos.

**2026-10-14 · quadro de tarefas aberto, e três pedidos**

Pus o quadro acima com critério de pronto em cada linha. Assumi V3–V6 (Android,
sensores, ponte de vida em Kotlin, painel) e deixei a fila do porte livre, com
10b marcado como o maior destravamento do repositório — é o que falta para
missão sobreviver a fechar o app, e para 6b sair do lugar.

Dois achados sobre o código do outro lado, feitos lendo em vez de supondo:

- **o `arredondar` novo é melhor que o meu.** Virou `expect`/`actual` com
  `BigDecimal(double)`, que pega a expansão binária exata; o meu multiplicava
  por 10 antes e já levava erro de float. Conferi os 11 casos de `pct` do
  `ouro/vida.json` contra a implementação nova: zero divergência. Fica a dele.
- **o `Yaml.kt` é só escrita, e o leitor vai precisar de escalar dobrado.** O
  `exemplo-missoes.yaml` usa `porque: >`, e um leitor que não entenda isso
  devolve `porque` vazio — que é justamente o campo com que o motor recusa
  escrita sem justificativa. Falha silenciosa no lugar mais caro que existe
  neste repositório.

Em aberto, e é pedido e não tarefa: a ponte de vida precisa de uma costura em
`Compras.kt`, que é faixa do porte. Até ter resposta, ela fica no pacote `vida/`,
funcionando isolada, sem deixar o arquivo do outro numa forma que ele não
escolheu.
