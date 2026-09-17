# Arquitetura

## A fronteira

O FinTips tem uma divisão de responsabilidade que explica quase todas as
decisões de código:

> **O app guarda, aplica e calcula. O agente descobre, pergunta e decide.
> O usuário assina.**

Nada que dependa da vida de uma pessoa está embutido no pacote. "Transporte é
custo fixo" é conclusão sobre alguém — e depende de essa pessoa usar transporte
para trabalhar, de a empresa reembolsar ou não, de metade das corridas serem
passeio de sábado. O app não sabe disso e não deve fingir que sabe.

O que o app garante é a forma: contratos versionados, aplicação determinística,
recálculo consistente e **proveniência em tudo**.

```
  conectores          núcleo determinístico            interfaces
 ┌───────────┐   ┌──────────────────────────┐   ┌────────────────────────┐
 │ ofx       │   │ parser   → Transaction   │   │ MCP stdio (21 tools)   │──▶ agente
 │ pluggy    │──▶│ heurística (palpite)     │──▶│ FastAPI 127.0.0.1:8420 │──▶ painel
 │ csv (todo)│   │ mapping  (decisões)      │   │ CLI                    │
 └───────────┘   │ entities → Counterparty  │   └────────────────────────┘
                 │ commitments → CustoFixo  │            ▲
                 │ context  → Fato          │            │
                 │ triage   → o que falta   │     report.analyze() é a
                 │ analysis/score/projection│     ÚNICA fonte do contexto
                 └──────────────────────────┘
                         │
                         ▼
                 data/*.yaml  (no disco do usuário)
```

As três interfaces consomem o mesmo dicionário. Se um número muda, muda nos três.

## Proveniência

Quatro origens, em ordem de autoridade:

| Origem | O que é | Vale como verdade? |
|---|---|---|
| `heuristica` | lista embutida no pacote, palpite genérico | **não** |
| `importacao` | derivado dos próprios dados (cadência, agrupamento) | não |
| `agente` | o agente concluiu, normalmente após conversar | sim |
| `usuario` | a pessoa afirmou | sim, e vence tudo |

Consequências concretas, todas testadas:

- Uma heurística nunca sobrescreve uma decisão do usuário, mesmo sendo mais
  específica ou mais "confiante".
- Um fato de menor autoridade não apaga um de maior.
- `cobertura_da_classificacao` mostra quanto do dinheiro está classificado por
  decisão e quanto ainda é palpite. Começa em 0%.

## Contratos (`contracts.py`)

| Tipo | O que representa |
|---|---|
| `Proveniencia` | origem, confiança, porquê, evidência, quando, por quem |
| `Categoria` | uma categoria da taxonomia do usuário |
| `Condicao` / `Efeito` / `Regra` | o `quando` e o `então` de uma classificação |
| `CustoFixo` | compromisso mensal **definido** (não detectado) |
| `Fato` | um pedaço de contexto, com o que o sustenta e prazo opcional |
| `ItemDeTriagem` | algo em aberto, com o custo mensal de não decidir |

## Módulos

| Arquivo | Responsabilidade |
|---|---|
| `models.py` | `Transaction`, `Account`, `Statement`; taxonomias de fluxo e canal |
| `parsers/ofx.py` | OFX SGML/XML; valores pt-BR; dedup por (FITID, valor, data) |
| `privacy.py` | hash de conta, pseudônimo de pessoa física, limpeza de CPF/e-mail |
| `categorize.py` | piso heurístico — marca tudo como palpite de baixa confiança |
| `taxonomy.py` | categorias como dado do usuário; sugestões do pacote são heurística |
| `mapping.py` | motor de regras genérico + cobertura da classificação |
| `context.py` | núcleo demarcado + fatos livres; cálculo de lacuna e impacto |
| `commitments.py` | custo fixo definido, com base, método e proveniência |
| `discovery.py` | detecção de padrão → **candidatos**, nunca conclusões |
| `entities.py` | contrapartes agrupadas, cadência, id estável |
| `triage.py` | a fila do que está em aberto, ordenada por impacto em reais |
| `analysis.py` | mês a mês, baseline, gasto invisível, eventos atípicos |
| `plans.py`, `purchases.py`, `score.py`, `projection.py` | metas, compra, score, caixa |
| `report.py` | monta o contexto único |
| `api.py`, `mcp_server.py`, `cli.py` | as três interfaces |

## Motor de regras

Uma regra é `quando` → `então`, com proveniência.

```yaml
- id: r-7afe61d4
  quando:
    memo_casa: "(bilhete|TOP SP|TARFA|AUTOPASS|PRODATA|EMV CMT|ATM TMOB)"
    fluxo: expense
  entao:
    categoria: transporte-trabalho
  proveniencia:
    origem: usuario
    confianca: 1.0
    porque: terminais de transporte público, uso diário confirmado
```

Campos de `quando`: `contraparte_id`, `contraparte_contem`, `memo_casa` (regex),
`canal`, `fluxo`, `categoria_atual`, `valor_min`, `valor_max`, `dias_semana`,
`hora_min`, `hora_max`. Campos de `entao`: `categoria`, `fluxo`, `marcar`,
`rotulo`.

**Precedência**: autoridade da proveniência, depois especificidade da condição,
depois confiança. A primeira regra que casa vence, e a aplicação é determinística
— o mesmo extrato com o mesmo conjunto de regras dá sempre o mesmo resultado.

`simular_regra` existe porque a hipótese costuma estar errada: a regra óbvia
("contraparte contém 'bilhete'") pegou 1 transação de R$ 15 nos dados reais,
enquanto a que descreve os terminais de fato pegou 31, somando R$ 105/mês.

## Custo fixo

Detecção e definição são coisas diferentes, de propósito:

- `discovery.detect_fixed_costs` acha padrões previsíveis e devolve
  **candidatos**, sempre rotulados como heurística.
- `commitments.CommitmentStore.definir` grava um **compromisso**, com base
  (`categoria`, `contraparte`, `regra` ou `valor`), método de cálculo
  (`declarado`, `mediana_meses_completos`, `media`) e natureza nomeada por quem
  define — contratual, rotina, sazonal, reembolsado, o que fizer sentido.

Só o compromisso entra na projeção e sai do relatório de gasto invisível. A
detecção roda apenas sobre **meses completos**: um mês pela metade derruba a
média e faz despesa estável parecer volátil.

## Contexto híbrido

Duas coisas são verdade ao mesmo tempo, e o desenho reflete isso:

- **Núcleo** (`context.NUCLEO`): sete chaves que valem para qualquer pessoa, com
  `porque_importa` escrito pelo app — o texto descreve qual cálculo muda, não uma
  pergunta pronta. A pergunta é do agente, que sabe com quem está falando.
- **Fatos livres**: qualquer chave que a vida da pessoa exigir, como
  `transporte.reembolsado_pela_empresa`. O app valida a forma, não o conteúdo.

## Triagem

A cada importação (e sob demanda) o motor recalcula o que está em aberto:

| Tipo | Quando aparece |
|---|---|
| `contraparte_nova` | apareceu no extrato e ninguém classificou |
| `classificacao_fraca` | está classificada só por heurística e pesa dinheiro |
| `candidato_custo_fixo` | o padrão parece fixo, mas ninguém confirmou |
| `custo_fixo_derivou` | o valor declarado não bate mais com o observado |
| `fato_ausente` / `fato_vencido` | falta contexto, ou o prazo expirou |
| `evento_sem_explicacao` | movimento grande e atípico sem nota |

Cada item traz o **impacto mensal em reais** de deixá-lo em aberto, e é isso que
ordena a fila. O que foi resolvido não volta; o que foi adiado volta no fim.

## Como estender

**Novo banco (OFX)**: normalmente nada a fazer. Memo com prefixo diferente →
acrescente em `rules/categories.yaml` (lembrando que aquilo é só palpite).

**Novo conector**: herde `Connector`, devolva `list[Statement]`.

**Novo tipo de item de triagem**: acrescente um bloco em `triage.construir` que
calcule o impacto. A interface não muda.

**Nova chave de núcleo**: um `ChaveDoNucleo` em `context.NUCLEO`, com
`porque_importa` e `peso`. A lacuna, o impacto e a entrada na triagem saem de
graça.

## Pensado como produto

- Schemas versionados (`CONTRACTS_SCHEMA`, `CONTEXT_SCHEMA`, `TAXONOMY_SCHEMA`,
  `RULES_SCHEMA`, `COMMITMENTS_SCHEMA`, `TRIAGE_SCHEMA`).
- Workspace por perfil: multiusuário é um diretório a mais, não uma refatoração.
- Frontend fala só com a API — hospedar em outro lugar é trocar a base URL e
  acrescentar autenticação.
- Regras públicas × locais: o pacote traz redes nacionais; o que é do bairro do
  usuário fica em `data/`, fora do Git.
- Conector é interface: OFX hoje, Open Finance amanhã, sem tocar no núcleo.
- Build do frontend versionado dentro do pacote: `pip install` sem Node.

## Backlog

- Cartão de crédito (fatura OFX/CSV) — maior ponto cego.
- Orçamento por categoria com alerta de estouro no meio do mês.
- Histórico de score e de decisões ao longo do tempo.
- Sazonalidade na projeção (13º, férias, IPVA).
- Regras com janela de validade (o padrão mudou a partir de tal mês).
- Multiusuário: autenticação e workspaces nomeados.
