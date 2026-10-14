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

Simulado com `git merge --no-commit` entre as duas branches: **seis arquivos
em conflito de conteúdo.** Não são erro de ninguém — são dois trabalhos
honestos no mesmo arquivo. O que cada um precisa:

| Arquivo | O que colide | Proposta |
|---|---|---|
| `fintips/report.py` | `analyze()` reescrito de um lado; `load_vida()` acrescentado do outro | ficar com o `analyze()` dele e reaplicar `load_vida()` por cima — são blocos independentes |
| `fintips/mcp_server.py` | ferramentas novas nos dois lados, e a `_SPEC` editada nos dois | as ferramentas somam; a `_SPEC` precisa ser lida pelos dois pedaços e refeita à mão uma vez |
| `fintips/purchases.py` | `evaluate()` ganhou parâmetro nos dois lados (`precedentes` lá, `vida` aqui) | somar os dois parâmetros; a ordem no veredito precisa de decisão humana — ver abaixo |
| `fintips/api.py` | rotas novas nos dois lados | somam; conflito é só de vizinhança |
| `README.md` | seção "O que ele faz" com item novo nos dois | somam |
| `docs/PORTE-KOTLIN.md` | a tabela da fila, reescrita nos dois | **já reduzido**: a trilha de vida saiu da fila e virou tabela própria (`V1`–`V4`), para as linhas numeradas serem só da fila do porte |

### A colisão que não é de texto

Em `purchases.evaluate`, os dois lados acrescentaram coisa que **mexe no
veredito**. Isso não é merge, é decisão de produto, e ela não é de agente
nenhum:

- a regra de espera declarada (`espera_antes_de_comprar`) — do lado da vida;
- o que a trilha do porte acrescentou ao redor de precedentes e perfil.

Quando duas regras podem mudar o mesmo veredito, a ordem entre elas é uma
escolha com consequência visível na tela. **Isso vai para o usuário, não para
o merge.**

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
