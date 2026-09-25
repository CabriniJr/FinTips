# FinTips — o que governa este repositório

## Máxima

> **O destino é Kotlin, e o produto final é um app.**

O motor Python é a implementação de referência, não o destino. Cada coisa
construída aqui é construída para ser portada: Kotlin Multiplatform com
Android na frente, Compose Multiplatform quando o motor estiver de pé. Um app
de finança pessoal vive no celular da pessoa — é lá que ela está quando o
celular quebra e a decisão precisa ser tomada.

Isso tem consequências práticas, e elas valem para toda mudança nova:

1. **Feature nova nasce portável.** Sem dependência de biblioteca que só existe
   em Python, sem lógica escondida em comprehension que não tem equivalente
   direto, sem `float` onde o valor é dinheiro.
2. **O que entra no motor entra no ouro.** `scripts/gerar-ouro.py` grava a
   resposta do Python em `kotlin/motor/src/jvmTest/resources/ouro/*.json`, e o
   teste Kotlin cobra exatamente aquilo. Motor sem ouro é motor que vai divergir
   em silêncio.
3. **Porta replica. Não corrige, não melhora, não simplifica.** Se a regra é
   ruim, ela muda nos dois motores ao mesmo tempo, num commit que só faz isso.
4. **Enquanto o Kotlin não reproduz, o Python é o produto que funciona.** Não se
   troca um motor testado por um que ninguém conferiu.

Detalhe do porte, com as decisões já tomadas (dinheiro em `Long` de centavos, o
harness diferencial, o que já foi portado): `docs/PORTE-KOTLIN.md`.

## A regra que sustenta o produto

**Nada é verdade sem proveniência.** Heurística embutida e derivação dos dados
ranqueiam o que olhar primeiro; só `agente` e `usuario` concluem. Toda escrita
carrega `porque` — é o que a torna auditável depois.

Não existe detecção de motivo, nem de escolha. O extrato mostra que o dinheiro
saiu; ele nunca diz por quê, nem o que a pessoa considerou antes. `causes.py` e
`decisions.py` não têm, e não devem ter, função que deduza isso do extrato.

## Onde as coisas ficam

| Camada | Arquivo | O que guarda |
|---|---|---|
| contratos | `fintips/contracts.py` | tipos da fronteira app/agente |
| causas | `fintips/causes.py` | por que o dinheiro sai, e o que se decidiu |
| decisões | `fintips/decisions.py` | bifurcações pontuais, alternativas e desfecho |
| análise | `fintips/report.py` | `analyze()` — única fonte do contexto |
| agente | `fintips/mcp_server.py` | as primitivas MCP |
| porte | `kotlin/motor/` | o motor que vai virar o app |

## Rodando

```bash
pip install -e ".[tudo]"
fintips init && fintips ingest extrato.ofx
fintips serve                 # painel em 127.0.0.1:8420
fintips mcp-config            # config pronta para o cliente MCP
for t in tests/test_*.py; do python "$t" || break; done
```
