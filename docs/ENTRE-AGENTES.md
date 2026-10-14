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
