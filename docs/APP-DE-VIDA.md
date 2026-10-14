# O FinTips vira um app de vida

Até aqui o FinTips era um motor financeiro. A partir deste steering ele passa a
ser um app de vida em seis frentes, e **dinheiro é uma delas**.

Nada do que existe se perde. O motor inteiro — parser OFX, classificação com
proveniência, causas, perfil, score, projeção, alavancas — vira o pilar OURO.
As outras cinco frentes são novas.

```
     FOR        AGI        VIT        INT        FOC       OURO
    força     cardio    sono/saúde  estudo     atenção   dinheiro
      │          │          │          │          │          │
      └──────────┴──────────┴──── missões ────────┴──────────┘
                                   │
                        registro: quem disse, e como sabe
                                   │
                    ┌──────────────┴──────────────┐
              app Android                   conector MCP
          (registro e interface)          (o Claude conversa)
```

## Por que seis barras e não um número

A tentação óbvia é XP e nível. Está fora, de propósito.

Nível é um número que só sobe. Por construção, ele não consegue dizer "esta
semana foi pior que a passada" — e essa é a única informação que muda
comportamento. Um nível 47 não distingue alguém em ascensão de alguém que
parou há três meses.

O que o app mostra no lugar:

- **a barra da janela atual** — quanto da frente foi cumprido hoje, nesta
  semana, neste mês. Ela desce quando a pessoa para, que é o ponto.
- **a sequência** — dias consecutivos, a medida de constância.
- **o recorde** — a maior sequência já alcançada, que **não zera na recaída**.

O recorde preservado não é generosidade: é a regra do plano em código. "Nunca
dois dias seguidos. Caiu hoje, amanhã é dia limpo." Zerar tudo junto com a
sequência transformaria um tropeço em perda total, que é exatamente o
pensamento que faz alguém largar o app depois do primeiro escorregão.

## A escada de proveniência ganha um degrau

O lado financeiro responde "quem classificou esta transação", com quatro
origens: heurística, importação, agente, usuário.

O lado da vida responde outra pergunta — "como sabemos que isso foi feito" — e
a resposta inclui algo que o dinheiro não tem: **o aparelho**. O celular sabe
tempo de tela, passos e horário de dormir sem precisar perguntar.

| Origem | O que é | Conta como cumprido? |
|---|---|---|
| `presumido` | o app supôs pela rotina | **não** |
| `agente` | o agente concluiu numa conversa | sim |
| `sensor` | o aparelho mediu | sim |
| `usuario` | a pessoa marcou | sim, e vence tudo |

Duas decisões dentro desta tabela, as duas discutíveis e as duas deliberadas:

**`sensor` fica acima de `agente`.** "Você ficou sem vídeo curto hoje?" é
pergunta factual. Se o celular mediu, a medida vale mais que a interpretação de
quem conversou sobre o assunto.

**`usuario` continua acima de `sensor`.** O aparelho erra de um jeito que a
pessoa sabe explicar: o celular ficou em casa, o vídeo foi visto no computador,
o treino foi na rua. Quem mede não entende contexto.

E `presumido` existe para nunca contar. O app supor que você treinou não é você
ter treinado — é a mesma regra que impede a heurística de classificar gasto
como verdade no lado financeiro.

Esta escada é **separada** da financeira, em vez de uma extensão dela. Fundir
as duas obrigaria o porte para Kotlin a divergir do motor Python, que não tem
nem nunca terá o conceito de sensor. São perguntas diferentes; merecem
vocabulários diferentes.

## Cobertura de evidência

O lado financeiro mostra `cobertura_da_classificacao`: quanto do dinheiro
alguém decidiu, e quanto ainda é palpite. O lado da vida ganha o espelho —
**quanto do que o app afirma veio de medida, e quanto é memória**.

Existe pelo mesmo motivo que o original: deixar visível o que ainda não se
sabe. E tem um motivo extra aqui, que o plano escreve com todas as letras —
força de vontade sozinha já falhou antes, e memória de uso de celular é
justamente o tipo de memória que distorce a favor de quem lembra.

## Para que isso serve: decidir dinheiro

A camada das seis frentes não existe para gamificar. Ela existe para **dar
contexto a decisão de dinheiro e a plano** — é o pilar que faltava ao lado do
perfil e das causas.

O exemplo que define o módulo: duas pessoas olham um tablet de R$ 2.500 com a
mesma sobra, a mesma reserva e o mesmo plano. Na primeira, o tablet é o
aparelho de estudo que falta. Na segunda, é a porta de entrada do vídeo curto
que ela corta há 40 dias. **Nenhum extrato do mundo distingue as duas.** O que
distingue é a missão que ela declarou e a sequência que ela tem hoje.

`contexto_de_compra` devolve quatro coisas, em ordem de força:

| O que | É o quê |
|---|---|
| `regra_declarada` | a regra de espera que ela assinou, aplicada |
| `missoes_em_jogo` | qual sequência esta compra põe em risco, e o `porque` que ela escreveu |
| `custo_em_aportes` | o preço em meses da missão de aporte |
| `frentes_no_momento` | as seis barras de hoje, para ver se a compra cai numa frente já fraca |

### A colisão só existe porque ela declarou

O motor **não decide que tablet é vício**. A colisão aparece porque a pessoa
escreveu `colide_com: [tablet, celular, streaming]` na missão dela, com
`porque`. Se a palavra não está na lista, a compra não toca aquela frente.

Isso é a mesma regra das causas, no mesmo lugar: `causes.py` não tem
`detectar_causas()` e nunca vai ter. Inferir que um aparelho alimenta um vício
seria o app diagnosticando — e diagnóstico errado sobre vício é pior que
silêncio.

### Uma coisa, e só uma, mexe no veredito

`regra_declarada`. Quando o preço passa do limite que a pessoa escreveu, o
veredito vira espera e a saída traz `regra_declarada_aplicada`, com o `porque`
dela ao lado.

A distinção que sustenta isso: **não é o motor opinando, é o motor aplicando
uma decisão que ela já tomou**. "O app guarda, aplica e calcula" — aplicar
regra assinada é literalmente o trabalho dele. Por isso a regra exige `porque`
no carregamento e falha sem ele: regra que mexe em veredito sem dizer de onde
veio é opinião do app disfarçada.

Todo o resto informa e não decide. Há teste comparando os dois lados abaixo do
limite da regra: colisão, sequência e meses de aporte presentes ou ausentes,
o veredito, o score de prudência, a reserva e a melhor estratégia **idênticos**.

### Plano contra aporte

`contexto_de_planos` põe o aporte declarado contra o que os planos exigem por
mês. Quando não fecham, o motor mostra a diferença e para: subir o aporte,
esticar o prazo ou cortar plano é escolha dela.

## Onde as missões moram

No workspace, fora do Git. `fintips/rules/exemplo-missoes.yaml` é só um molde.

A razão é a mesma de `regras-locais.yaml`, e mais forte: plano de vida tem
salário, empregador, nome de gente, valor de patrimônio e hora de dormir. A
lista do que alguém treina e quanto aporta diz mais sobre a pessoa do que o
extrato bancário.

Missão nasce com origem `usuario`, sempre. O app não sabe quantas vezes alguém
deve treinar; quem sabe é a pessoa, com o corpo e a semana que tem. O catálogo
embutido no pacote é molde, nunca sugestão de rotina.

E a trava de PII aprendeu a olhar para cá. O `scripts/check-pii.sh` agora colhe
os termos de `data/missoes.yaml` e `data/registros.jsonl` e procura cada um nos
arquivos que vão para o commit. Três decisões dentro disso:

- **colhe com o YAML de verdade, não com `grep`.** As frases mais sensíveis do
  plano estão em bloco dobrado (`porque: >`), e `grep` de linha pega só o `>` —
  era um buraco exatamente onde o risco é maior.
- **texto só entra como frase; número entra sozinho.** Título de missão de uma
  palavra — "Leitura", "Dentista" — é genérico, e colhê-lo faria o script
  acusar qualquer doc do projeto que mencionasse a palavra. Esta própria
  explicação foi acusada quando a regra ainda não existia, o que é a melhor
  demonstração possível de por que ela existe. Já R$ 4.300 de aporte não é
  palavra genérica nenhuma, e entra.
- **`colide_com` fica fora.** São palavras de categoria de produto — "tablet",
  "console". O que é pessoal ali é a *ligação* entre a palavra e a missão, não
  a palavra.

Isso já pagou na primeira execução: a varredura acusou que o fixture Kotlin e o
molde do pacote carregavam frases copiadas do plano de verdade — dois títulos
de missão e meia dúzia de `como_medir`. Estavam commitados. O repositório foi
corrigido, não o arquivo pessoal: **o Git é que cede.**

## A divisão de trabalho

| | Faz o quê | Por quê |
|---|---|---|
| **App Android** | registro e interface: marcar missão, ver as barras, ler os números | é o que se usa de pé, no meio do dia, em dez segundos |
| **Conector MCP** | a conversa longa: entrevista de causa, assinatura de perfil, a revisão da semana | conversa boa precisa de teclado e de tempo |
| **Workspace** | a verdade, em arquivo | os dois leem e escrevem o mesmo lugar, como já funciona hoje |

O Claude continua sendo um conector sobre o mesmo workspace. O app não embute
agente: isso exigiria chave de API no aparelho e mandaria dado financeiro para
fora da máquina, que é o contrário do que sustenta o projeto.

## O celular é outra máquina

Parece obvio escrito assim, e não era: o app Android **não lê o workspace**.
Ele não tem `~/Documents/FinTips/data/` e nunca vai ter. Isso tem duas
consequências que mudaram o desenho.

**O aparelho precisa do catálogo em formato próprio.** O workspace guarda
`missoes.yaml` porque é arquivo que a pessoa edita à mão, e YAML existe para
isso. O que viaja para o celular é JSON, por `fintips aparelho --saida
missoes.json`, e o histórico volta por `fintips aparelho --registros`.

**A leitura de YAML em Kotlin deixou de bloquear o app.** Era o item 10b, e
estava marcado no canal como o maior destravamento do repositório. Continua
valendo para a heurística e para o catálogo no desktop — mas o Android não
espera por ele.

A fronteira de plataforma ficou do tamanho de três linhas. `Guarda` recebe
duas funções, "ler texto" e "acrescentar texto", e **toda** decisão fica em
`commonMain`: o que recusar, o que conta como cumprido, como a sequência anda,
o que a tela mostra. O Android entrega as duas funções sobre `filesDir` e não
tem onde esconder erro.

Isso não é elegância: é que o código em `androidMain` **não roda em teste nenhum
desta máquina**, porque o alvo exige SDK e emulador. Onde não há teste, não pode
morar regra.

### A tela, e o que ela não faz

`montarTela(vida, hoje)` é função pura: devolve as seis barras, a lista do dia
com sequência e recorde, e a cobertura de evidência. A camada Compose só
desenha — e desenho errado se vê na tela, enquanto número errado, não.

Três coisas a tela não faz, as três por decisão:

- **não elogia e não cobra.** O resumo é "1 de 2 hoje". "Você está indo bem" é
  o app opinando sobre o dia de alguém com base em caixas marcadas, e é a frase
  que faz desinstalar no primeiro dia ruim. Existe teste proibindo as palavras.
- **não esconde frente vazia.** As seis aparecem sempre; a vazia mostra "—",
  porque frente sem missão é informação.
- **não marca nada sozinha.** Toque é origem `usuario`. O app nunca grava
  `presumido`, que existe exatamente para não contar.

## O que isso muda na ordem de construção

A porta para Kotlin continua, mas a prioridade virou. Antes o Android era o
módulo 12; agora é o produto.

| Ordem nova | O que | Estado |
|---|---|---|
| 1 | Domínio de vida: atributos, missões, registro, sequência | **pronto**, 14 testes |
| 2 | Persistência: ler e gravar missões e registros | **pronto** (`fintips/life.py`) |
| 3 | Contexto de compra e de plano, com a regra declarada | **pronto**, 33 testes |
| 4 | Conector MCP (`frentes`, `registrar_missao`, `aporte_vs_planos`) e API | **pronto** |
| 5 | App Android: as seis barras e a lista do dia | **lógica pronta e testada** (16 casos); a tela Compose **não compilou aqui** |
| 6 | Sensores: tempo de tela e passos como evidência | a fazer |
| 7 | Painel: as seis barras ao lado do score | a fazer |
| 8 | Resto da porta: projeção, planos, compras | **pronto** — entrou por PR #3 |

O motor financeiro portado — dinheiro, OFX, contratos, regras, análise, score —
continua valendo e continua testado contra o Python. Ele só deixou de ser a
frente de ataque.

### O único módulo em que o Kotlin veio primeiro

As seis frentes nasceram no Kotlin, porque não existiam no Python. Agora
existem nos dois, e isso cria um risco que o resto da porta não tem: dois
motores sem nada obrigando a concordar.

Por isso `ouro/vida.json` foi gerado e `OuroVidaTest` cobra — **na direção de
sempre, com o Python como referência**, mesmo tendo chegado depois. O harness
achou divergência real na primeira execução:

```
barras divergiram do motor Python:
  [um_de_tres_e_um_terco/FOC] pct: python 33.3, kotlin 33.33333333333333
  [dois_de_tres/FOC]          pct: python 66.7, kotlin 66.66666666666666
```

Uma missão cumprida de três. O Python arredonda em uma casa, o Kotlin dividia
cru. Nenhum teste de propriedade pegaria: as duas respostas parecem certas, e a
diferença só apareceria quando alguém comparasse a barra do app com o número do
painel. Corrigido no Kotlin, com `arredondar(x, 1)`.

Confirmado quebrando de propósito: subir o corte de `contaComoCumprido` de
`agente` para `sensor` derruba dois testes, um nomeando a escada inteira e
outro nomeando o caso de buraco de um dia.

## O que ainda falta saber

O plano aponta para uma seção **App (idealização)** que não veio no PDF — era
uma página filha do documento. É provável que ela já responda coisas que aqui
estão decididas por conta própria: se existe nível, como a missão vira pontos,
como as barras se comportam. Quando ela aparecer, este documento muda.
