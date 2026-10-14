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

## Onde as missões moram

No workspace, fora do Git. `fintips/rules/exemplo-missoes.yaml` é só um molde.

A razão é a mesma de `regras-locais.yaml`, e mais forte: plano de vida tem
salário, empregador, nome de gente, valor de patrimônio e hora de dormir. A
lista do que alguém treina e quanto aporta diz mais sobre a pessoa do que o
extrato bancário.

Missão nasce com origem `usuario`, sempre. O app não sabe quantas vezes alguém
deve treinar; quem sabe é a pessoa, com o corpo e a semana que tem. O catálogo
embutido no pacote é molde, nunca sugestão de rotina.

## A divisão de trabalho

| | Faz o quê | Por quê |
|---|---|---|
| **App Android** | registro e interface: marcar missão, ver as barras, ler os números | é o que se usa de pé, no meio do dia, em dez segundos |
| **Conector MCP** | a conversa longa: entrevista de causa, assinatura de perfil, revisão de domingo | conversa boa precisa de teclado e de tempo |
| **Workspace** | a verdade, em arquivo | os dois leem e escrevem o mesmo lugar, como já funciona hoje |

O Claude continua sendo um conector sobre o mesmo workspace. O app não embute
agente: isso exigiria chave de API no aparelho e mandaria dado financeiro para
fora da máquina, que é o contrário do que sustenta o projeto.

## O que isso muda na ordem de construção

A porta para Kotlin continua, mas a prioridade virou. Antes o Android era o
módulo 12; agora é o produto.

| Ordem nova | O que | Estado |
|---|---|---|
| 1 | Domínio de vida: atributos, missões, registro, sequência | **pronto**, 14 testes |
| 2 | Persistência: ler e gravar missões e registros | a fazer |
| 3 | App Android: as seis barras e a lista do dia | a fazer |
| 4 | Sensores: tempo de tela e passos como evidência | a fazer |
| 5 | Conector MCP das missões, ao lado do financeiro | a fazer |
| 6 | OURO ligado ao motor financeiro já portado | a fazer |
| 7 | Resto da porta: projeção, planos, compras | adiado |

O motor financeiro portado — dinheiro, OFX, contratos, regras, análise, score —
continua valendo e continua testado contra o Python. Ele só deixou de ser a
frente de ataque.

## O que ainda falta saber

O plano aponta para uma seção **App (idealização)** que não veio no PDF — era
uma página filha do documento. É provável que ela já responda coisas que aqui
estão decididas por conta própria: se existe nível, como a missão vira pontos,
como as barras se comportam. Quando ela aparecer, este documento muda.
