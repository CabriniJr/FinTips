# Arquitetura

## Fluxo

```
  conectores            núcleo determinístico              camada de agente
 ┌───────────┐   ┌────────────────────────────────┐   ┌────────────────────┐
 │ ofx       │   │ parser -> Transaction          │   │ MCP server (stdio) │
 │ pluggy    │──▶│ categorize (regras YAML)       │──▶│ 8 ferramentas      │──▶ Claude
 │ csv (todo)│   │ analysis / plans / score /     │   │ skill "financas"   │
 └───────────┘   │ purchases                      │   └────────────────────┘
                 └────────────────────────────────┘
                         │
                         ▼
                 data/canonico/*.yaml  (fonte de verdade)
```

A fronteira importa: **tudo que é número acontece à esquerda do MCP**. O modelo
recebe agregados prontos e escreve a interpretação. Isso torna o sistema
auditável (você confere a conta) e barato (não se manda 300 transações para o
contexto a cada pergunta).

## Módulos

| Arquivo | Responsabilidade |
|---|---|
| `models.py` | `Transaction`, `Account`, `Statement`; taxonomias de fluxo/canal/categoria |
| `parsers/ofx.py` | OFX SGML e XML; valores pt-BR; datas com timezone; dedup por (FITID, valor, data) |
| `privacy.py` | hash de conta, pseudônimo de pessoa física, remoção de CPF/e-mail/telefone |
| `categorize.py` | regras determinísticas: canal → fluxo → contraparte → categoria |
| `rules/categories.yaml` | a base de conhecimento editável (prefixos de memo, merchants) |
| `analysis.py` | mês a mês, baseline, recorrências, gastos invisíveis, eventos atípicos |
| `plans.py` | cadastro de metas e viabilidade contra a capacidade real |
| `purchases.py` | consultoria de compra: cenários, impacto na reserva, risco de arrependimento |
| `score.py` | score 0–100 em 5 dimensões com pesos explícitos |
| `report.py` | monta o pacote que o agente consome |
| `workspace.py` | onde os dados moram; config; patrimônio |
| `mcp_server.py` | expõe tudo como ferramentas MCP |
| `connectors/` | interface `Connector` + implementação Pluggy |

## Modelo canônico

Três eixos por transação, que não se confundem:

- **fluxo** — o que aconteceu com o patrimônio: `expense`, `income`,
  `savings_out`, `savings_in`, `transfer`, `refund`.
- **canal** — o instrumento: `debit_card`, `pix`, `pix_qr`, `fixed_income`,
  `salary`, `fee`, …
- **categoria** — o assunto do gasto: `mercado`, `transporte`, `lazer`, …

Separar fluxo de categoria é o que permite dizer "guardei 46% da renda" sem
mentir, mesmo com R$ 20 mil transitando entre conta e CDB no mesmo mês.

## Score (100 pontos)

| Dimensão | Peso | Nota cheia quando |
|---|---|---|
| Poupança | 30 | sobra ≥ 40% da renda |
| Reserva | 25 | patrimônio ≥ 6 meses de despesa |
| Estabilidade | 15 | despesa mensal pouco volátil e nenhum mês no vermelho |
| Vazamentos | 10 | taxas + micro-gastos < 15% da despesa |
| Planos | 20 | capacidade mensal cobre o aporte necessário de cada meta |

Cada dimensão devolve os pontos e o máximo, e o motor aponta `proximo_ponto`:
a alavanca com maior ganho marginal.

## Como estender

**Novo banco (OFX):** normalmente nada a fazer — só rodar `fintips ingest`.
Se o memo tiver prefixos diferentes, adicione entradas em `rules/categories.yaml`.

**Novo conector:** herde `Connector`, devolva `list[Statement]`. O resto do
motor não muda.

**Nova regra de categoria:** edite o YAML de regras. Sem deploy, sem código.

**Nova dimensão de score:** adicione peso em `WEIGHTS` e o cálculo em
`compute()`. Mantenha a fórmula visível — score opaco não muda comportamento.

## Backlog

- Cartão de crédito (fatura OFX/CSV) — hoje só conta corrente.
- Projeção de caixa 6–12 meses com recorrências + planos + sazonalidade.
- Orçamento por categoria com alerta de estouro no meio do mês.
- Dashboard servido localmente, lendo `relatorios/analise.yaml`.
- Histórico de score ao longo do tempo (série temporal em `relatorios/`).
