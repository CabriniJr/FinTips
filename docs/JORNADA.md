# A jornada

Este documento existe porque é fácil olhar para os módulos e perder de vista o
que a pessoa vive. A ordem abaixo é a ordem real, e cada etapa diz qual peça do
código a sustenta — se alguma etapa não tiver peça, é buraco de produto, não
detalhe de implementação.

```
  1. IMPORTAR          2. CONVERSAR                3. VIVER COM ISSO
  ────────────         ───────────────             ─────────────────
  extrato .ofx    →    agente lê o briefing   →    "posso comprar isso?"
  (futuro:             investiga, pergunta,        "quando fecho a viagem?"
   Open Finance)       registra com evidência      "onde estou perdendo?"
        │                     │                            │
        └──────────── mesmo workspace em disco ────────────┘
                              │
                     painel: perfil, score, previsões,
                     alavancas, planos, triagem
```

## 1. Importar — a janela de gastos

A pessoa traz de 3 a 6 meses de extrato. Não menos: um mês não tem recorrência,
e sem recorrência não há custo fixo, baseline nem projeção honesta.

```bash
./scripts/fintips-docker.sh importar "Extrato da Conta - PagBank.ofx"
```

O que o motor faz sozinho, e só isso: normaliza para o modelo canônico,
deduplica por FITID, hasheia a conta, pseudonimiza pessoas físicas, confere a
conciliação contra o saldo declarado e aplica um **piso heurístico** de
classificação — marcado como palpite de baixa confiança, porque é o que ele é.

O que ele **não** faz: concluir. `cobertura_da_classificacao` começa em 0%,
`perfil.cobertura` começa em 0%, `causas.cobertura` começa em 0%. As três
medindo a mesma coisa em camadas diferentes: quanto disso alguém decidiu.

> Open Finance entra aqui, por agregador, sem tocar no resto — `connectors/`
> já tem a interface e a implementação Pluggy. Ver `docs/OPEN-FINANCE.md`.

## 2. Conversar — onde o perfil nasce

A pessoa chama o agente. Ele chega pré-carregado: o recurso `fintips://briefing`
traz quem ela é, o que ainda é palpite e o que está aberto; `fintips://spec`
traz a regra de proveniência e os vocabulários.

O loop, que é sempre o mesmo:

1. `triagem` — a fila ordenada pelo custo mensal em reais de deixar em aberto.
   Não é lista de tarefas: é lista de dinheiro sem decisão.
2. `investigar` — antes de perguntar. Dia da semana, hora, distribuição,
   presença mensal. É aqui que "11 corridas de app" vira "6 de sábado à noite e
   5 às 6h de dia útil" — dois comportamentos, não um.
3. **Perguntar**, com o dado concreto na mão e uma pergunta por vez.
4. `simular_regra` antes de gravar, porque a hipótese costuma estar errada.
5. **Gravar** com `porque`: `criar_categoria`, `definir_regra`,
   `definir_custo_fixo`, `gravar_fato`, `gravar_causa`, `assinar_perfil`.
6. `resolver_item`, dizendo o que foi feito.

Duas ou três decisões por conversa. A fila não precisa acabar hoje, e resolver
rápido sem entender é pior do que deixar em aberto.

**O perfil nasce daqui, não da importação.** O catálogo de arquétipos casa os
números e devolve sugestão com evidência — `importacao`, palpite. Vira perfil
quando o agente conclui depois de conversar, ou quando a pessoa afirma. É por
isso que `PerfilStore.assinar` recusa origem derivada: rodar a análise mil vezes
nunca cria perfil.

**As causas também nascem daqui**, e são o que separa conselho de chute. O
motor sabe que saem R$ 400 em delivery; só a conversa sabe se é jornada dupla
ou tédio de domingo. E `aceitar` é resposta legítima — nomeia o gasto como
escolha e encerra o assunto.

## 3. Viver com isso — as perguntas que voltam

Com perfil e causas registrados, as perguntas seguintes têm contra o que ser
respondidas:

| A pessoa pergunta | O caminho | O que muda por ter perfil e causa |
|---|---|---|
| "posso comprar um tablet?" | prompt `conversa_de_compra` → `briefing` + `avaliar_compra` + `listar_causas` | o veredito sai da conta; o perfil diz o que reler (renda variável esconde o pior mês) e a causa traz a frase dela sobre aquela categoria |
| "quando eu fecho a viagem?" | `projecao` / aba Previsões | cenários com a sobra real, e o mês em que cada meta fecha |
| "onde estou perdendo dinheiro?" | `alavancas` / aba Alavancas | número e efeito recalculado; a leitura do que vale a pena é do agente |
| "como eu melhoro?" | `alavancas` + `triagem` | o que rende mais, e o que está travando a conta por falta de decisão |
| "quero juntar para X" | `salvar_plano` → Previsões | o plano entra na fila de prioridade e passa a disputar a mesma sobra |

E o painel centraliza o que foi acumulando: perfil por eixo com quem assinou,
score em cinco dimensões com a fórmula visível, previsões com as premissas
expostas, alavancas com a evidência, planos, compromissos e a triagem do que
ainda falta decidir.

## O ciclo se fecha

Extrato novo → a triagem recalcula o que mudou → causa vencida volta para a
fila (comportamento envelhece) → a conversa retoma de onde parou, porque tudo
ficou gravado com evidência e `porque`.

O que faz isso funcionar é chato e estrutural: **um workspace só**. O que o
agente grava conversando aparece no painel; o que a pessoa decide no painel o
agente lê na próxima pergunta. Não existem dois caminhos de decisão, e é por
isso que a API de escrita expõe exatamente as mesmas primitivas do MCP.

## Onde a jornada ainda tem buraco

Honestidade sobre o estado atual, para não vender o que não existe:

- **Cartão de crédito** é o maior ponto cego. Sem a fatura, parte do consumo
  real fica invisível e a taxa de poupança calculada sai otimista. A chave
  `cartao_credito.usa` existe justamente para o motor saber que está cego.
- **Causas e correlações não aparecem no painel** ainda — hoje só o agente as
  consome, via dossiê.
- **Open Finance** está desenhado e não ligado.
- **Onboarding sem agente** é possível (tudo tem CLI e API), mas é trabalhoso:
  a jornada foi desenhada supondo que a parte de perguntar é do agente.
