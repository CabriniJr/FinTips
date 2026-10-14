# Decisões: o ADR financeiro

## O problema

O celular quebra numa terça. Você considera consertar por R$ 700, trocar por
R$ 2.500 ou aguentar o aparelho antigo mais um semestre. Pesa a reserva, pesa
que a assistência não cobre a placa, pesa que naquele mês a sobra estava
apertada. Escolhe uma.

Três meses depois, nada disso existe. Não sobrou que a assistência não cobria a
placa, nem que a reserva estava em quatro meses e não em seis. Sobrou uma linha
no extrato: R$ 2.500 numa loja de eletrônicos.

Quando a mesma pergunta voltar — e ela volta, com o notebook, com a geladeira,
com o carro — a conta é refeita do zero, com o mesmo esforço, sem nada do que
se aprendeu na anterior.

O extrato não resolve isso, e não é por falta de dado. Ele mostra que o
dinheiro saiu; ele nunca mostra o que foi considerado antes, nem o que se
concluiu depois.

## O que o registro guarda

Um ADR de arquitetura guarda contexto, decisão, alternativas e consequências.
Aqui é o mesmo, com uma adição que só faz sentido em dinheiro: **os números da
época**.

| Campo | Por que existe |
|---|---|
| `situacao` | o que aconteceu, nas palavras da pessoa |
| `pergunta` | o que precisava ser escolhido |
| `alternativas` | os caminhos, **inclusive os descartados**, com o motivo do descarte |
| `escolhida` + `porque` | o caminho tomado e a razão dele |
| `instantaneo` | sobra, reserva, score e planos em risco no dia — congelados |
| `desfecho` | no que deu, na palavra da pessoa: funcionou, arrependi, indiferente |
| `revisar_em` | quando reabrir, para a escolha que tem prazo |
| `substitui` | quando se muda de ideia, sem apagar a decisão anterior |

Três desses campos carregam quase todo o valor, e são os três que uma
implementação apressada joga fora.

**As alternativas descartadas.** "Comprei um celular novo" não informa nada
daqui a um ano. "Descartei o conserto porque a assistência não cobria a placa"
evita reabrir a mesma investigação inteira.

**O instantâneo.** Uma escolha não é boa ou ruim em abstrato. Comprar à vista
com quatro meses de reserva é outra decisão que a mesma compra com duas semanas
de caixa. Sem os números de então, todo registro antigo vira julgamento injusto
do passado — e a pessoa passa a se cobrar por uma coerência que as condições não
permitiam. É a única parte que o app preenche sozinho, porque é a única que ele
sabe.

**O desfecho.** Decisão sem desfecho é história, não aprendizado. A triagem
cobra o veredito três meses depois da escolha — tempo de o arrependimento
aparecer e de ainda se lembrar do porquê. E `cedo_para_saber` é resposta
legítima: a decisão volta para a fila em vez de virar uma conclusão que ninguém
verificou.

## A conta que o motor faz

Uma só, e é a que decide a maioria das trocas:

```
consertar      R$   700,00   8 meses  →  R$ 87,50 por mês de uso
comprar novo   R$ 2.500,00  36 meses  →  R$ 69,44 por mês de uso
```

O aparelho de R$ 2.500 é mais barato que o conserto de R$ 700. Ninguém faz essa
conta de cabeça no dia em que o celular quebra, e é exatamente o dia em que ela
importa. Com `custo_mensal` preenchido, o plano de operadora entra junto: R$ 90
por mês durante 36 meses são R$ 3.240, mais que o aparelho.

O motor calcula. Ele não diz o que fazer: R$ 18 por mês de diferença podem ser
irrelevantes para uma pessoa e decisivos para outra, e o extrato não distingue
as duas.

## O que o histórico devolve na próxima

`historico_de_decisoes` procura precedentes por texto, tipo e ligação. Cada um
volta assim:

```
2026-06-15  Celular quebrou
   escolheu: consertar (R$ 700,00) → arrependi
   porque: não tinha R$ 2.500 naquele mês
   descartou comprar novo: a reserva estava em dois meses
   condições da época: sobra R$ 1.240, score 42, reserva 2 meses
```

Isso não vira veredito, e a omissão é deliberada. Ter se arrependido de uma
escolha parecida não torna esta errada — pode ter sido outro momento, outro
preço, outra necessidade. O que o histórico faz é devolver à conversa a
informação que sempre some: que a pergunta já foi feita, o que se considerou, e
o que a própria pessoa disse depois.

`avaliar_compra` passa a trazer esses precedentes anexados, **sem mexer no
veredito calculado** — há teste garantindo isso. O número é do motor; a leitura
é de quem conhece a pessoa.

## O que o módulo não faz

Não existe detecção de decisão, e não deve existir. Nenhuma função olha o
extrato e conclui que houve uma escolha: R$ 2.500 numa loja de eletrônicos pode
ser troca planejada, emergência ou presente para outra pessoa.

Pelo mesmo motivo, o arrependimento não é inferido. Comprar de novo na mesma
categoria não prova nada sobre a compra anterior, e não comprar não prova
acerto. A taxa de arrependimento em `aprendizados` sai só de desfecho que a
própria pessoa registrou.

Como nas causas, a origem `heuristica` e `importacao` é recusada na escrita: uma
decisão nasce de `agente` ou `usuario`, sempre.

## Na fila

Três itens novos na triagem, com pesos que dizem o que é urgente:

| Item | Peso | Por quê |
|---|---|---|
| `decisao_aberta` | 1.5 | é a única fila em que a **pessoa** está esperando para agir; o resto é o motor esperando dados |
| `decisao_a_revisar` | 1.0 | o prazo que a própria decisão pediu venceu |
| `decisao_sem_desfecho` | 0.7 | a escolha foi feita e ninguém registrou no que deu |

## Uso

```bash
fintips decisoes                        # tudo, com as alternativas e o desfecho
fintips decisoes --abertas              # só o que ainda não foi decidido
fintips decisoes --historico "celular"  # precedentes de um assunto
```

Pelo agente: `historico_de_decisoes` → `abrir_decisao` → `escolher_alternativa`
→ `registrar_desfecho`. O roteiro completo está em `skills/financas/SKILL.md`.

## No porte

`Decisao` e `Alternativa` já existem em `kotlin/motor/.../Contratos.kt`, com o
ouro cobrando a serialização campo a campo e os dois casos de fronteira do custo
por mês de uso (sem horizonte e horizonte zero).

O harness pagou o próprio custo na primeira rodada: o peso `1.5` da decisão
aberta caiu num valor onde o arredondamento Kotlin divergia do Python
(`33.33 × 1.5 = 49,994999…`, que o Python arredonda para 49,99 e a porta
arredondava para 50,0). O bug era anterior e estava dormindo; a decisão só
passou por cima dele. `arredondar` virou `expect`/`actual`, e na JVM usa
`BigDecimal(double)`, que é a expansão decimal exata que o `round()` do Python
arredonda.
