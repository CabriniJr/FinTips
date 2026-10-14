# A linguagem visual

Um documento só, para as duas telas: o painel web e o app Android. Antes disto,
o sistema existia apenas nos comentários de `web/src/styles.css` — o que
funciona para quem mexe no CSS e não serve para quem desenha a tela do celular.

A linguagem é emprestada do **delineax**: preto e branco, canto vivo, borda de
1px sólida, sombra dura deslocada sem desfoque, tipografia monoespaçada em caixa
alta para interface e sem serifa para leitura corrida.

## Os tokens

Valores de `web/src/styles.css`, que é a fonte. Qualquer tela nova copia daqui,
e não de uma paleta parecida.

| Token | Claro | Escuro | O que é |
|---|---|---|---|
| `--paper` | `#f4f3f0` | `#12110f` | fundo da página |
| `--card` | `#ffffff` | `#1b1a17` | fundo de caixa |
| `--card-2` | `#faf9f7` | `#201f1b` | caixa secundária, linha de tabela no hover |
| `--ink` | `#000000` | `#f5f3ec` | texto e borda estrutural |
| `--ink-2` | `#454442` | `#b4b1a6` | texto secundário |
| `--ink-3` | `#7c7a75` | `#85827a` | rótulo, legenda |
| `--line` | `#000000` | `#f5f3ec` | borda de caixa: **sempre tinta cheia** |
| `--line-2` | `#d9d7d1` | `#3a3833` | régua interna: divide sem fechar caixa |
| `--marca` | `#e9e7e1` | `#2a2823` | bloco de destaque atrás de palavra |

Sombra dura, em três intensidades. **Nunca há blur**: o deslocamento é o
próprio efeito.

```
--lift:       4px 4px 0 ink     caixa em repouso
--lift-sm:    3px 3px 0 ink     botão em repouso
--lift-press: 1px 1px 0 ink     botão pressionado
```

Tipografia: `IBM Plex Mono` para interface, `IBM Plex Sans` para leitura.
Interface vai em caixa alta com `letter-spacing` entre `0.08em` e `0.18em` —
quanto menor a fonte, maior o espaçamento.

Tempo: `120ms cubic-bezier(0.2, 0, 0.1, 1)`. Um só, em toda a aplicação.

## O gesto

É o que dá vida ao resto, e é uma regra só:

> O elemento repousa sobre a própria sombra e, no toque ou hover, **anda na
> direção dela**.

```css
.btn            { box-shadow: 3px 3px 0 ink; }
.btn:hover      { transform: translate(2px, 2px); box-shadow: 1px 1px 0 ink; }
.btn:active     { transform: translate(3px, 3px); box-shadow: 0 0 0 ink; }
```

É o gesto de apertar um adesivo contra o papel. Rápido, curto e **igual em toda
a aplicação** — animação que varia de lugar para lugar vira ruído em vez de
linguagem.

Só `transform` e `box-shadow` são animados, porque as duas rodam no compositor
e não causam reflow.

## A cor sobrevive num lugar só: dado

Interface é monocromática. O que tem matiz é número, e por um motivo prático:
gráfico precisa distinguir séries, e hachura é pior que cor para isso.

```
--s1 #1f5fb5   --s2 #c0491c   --s3 #10795a   --s4 #a37000
--good #10795a   --warn #a37000   --crit #b8322f
```

Consequência que vale para o app de hábito: **não existe verde de comemoração
nem vermelho de falha na interface.** A barra sobe porque a pessoa fez; não há
confete, e não há alerta vermelho por missão não cumprida. `--crit` é para
número crítico, não para julgamento de comportamento.

## O que a tela não decide

Esta parte não é estética, é contrato. Vale para o painel e para o app.

**A tela não calcula.** Todo número vem de função pura e testada: no app, de
`montarTela(vida, hoje)`; no painel, do JSON de `/api/*`. Se um número estiver
errado na tela, o erro está no motor, e o motor tem teste. Cálculo que nasce na
camada de desenho não tem harness nenhum atrás.

**A tela não elogia e não cobra.** O resumo do dia é `"1 de 2 hoje"`. "Você está
indo bem" é o app opinando sobre o dia de alguém com base em quantas caixas
foram marcadas — e é a frase que faz desinstalar no primeiro dia ruim. Há teste
proibindo as palavras de elogio no resumo (`AparelhoTest`).

**A tela não esconde o vazio.** As seis frentes aparecem sempre, inclusive as
que não têm missão: elas mostram `—`, porque frente sem missão é informação
sobre o que a pessoa não está treinando. Esconder a barra esconderia a lacuna.
Mesma regra da cobertura de classificação, que começa em 0% e diz isso.

**A tela não marca nada sozinha.** Toque é origem `usuario`. O app nunca grava
`presumido` — ele existe exatamente para não contar.

## Onde está cada tela

| Tela | Arquivo | Estado |
|---|---|---|
| Painel web | `web/src/styles.css`, `views.jsx`, `profile.jsx`, `triage.jsx`, `charts.jsx` | funcionando |
| App Android | `kotlin/app/src/main/kotlin/com/fintips/app/TelaDoDia.kt` | **escrita, nunca compilada** |
| Aba das seis frentes no painel | não existe | a fazer |

## Dívida conhecida: a tela Android está fora do sistema

Escrevi `TelaDoDia.kt` com uma paleta que **não é esta**:

```kotlin
private val TINTA = Color(0xFF1B1E24)   // deveria ser --ink: #000000
private val PAPEL = Color(0xFFEDEEF1)   // deveria ser --paper: #f4f3f0
private val LINHA = Color(0xFFB9BEC8)   // deveria ser --line: tinta cheia
```

Cinza-azulado frio em vez do preto sobre papel quente do sistema. Não foi
decisão: foi paleta pega de outro lugar enquanto eu resolvia o problema de
armazenamento, e ninguém conferiu porque a tela não compila nesta máquina.

Outras três dívidas no mesmo arquivo:

- **não há tema escuro.** O painel tem, por `prefers-color-scheme`; a tela do
  celular ignora.
- **o gesto não existe.** Os cartões não andam na direção da sombra ao toque —
  e esse gesto é a linguagem, não um enfeite.
- **a sombra é falsa.** Está desenhada como uma `Box` cinza deslocada atrás de
  outra, o que funciona mas não é o `--lift` de tinta cheia.

É o primeiro trabalho de quem pegar a faixa visual, e é trabalho de verdade:
a tela só vai ser vista de fato por quem tiver o SDK.

## Dado para desenhar, sem workspace

```bash
fintips aparelho --exemplo --saida missoes.json
```

As 14 missões do molde do pacote, com as duas pontas que a tela precisa
exercitar: uma missão com `valor_mensal`, uma com `colide_com`, as cinco
cadências, e as frentes `AGI`, `VIT` e `OURO` **sem missão diária** — o caso em
que a barra tem de mostrar `—` em vez de um zero que parece desempenho ruim.

Zero dado pessoal: é o mesmo arquivo que o `check-pii.sh` confere a cada commit.
