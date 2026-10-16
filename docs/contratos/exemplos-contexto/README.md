# Contexto global proposto

**Design, ainda sem endpoint implementado.** O [schema de contexto](../agente-contexto-v1.schema.json)
especifica a visão que API e MCP deverão obter do mesmo executor. O
[plano de execução](../../PLANO-AGENTE-DE-VIDA.md#21-visão-geral-e-contexto-de-todos-os-artefatos)
define cobertura, consultas e critérios de aceite.

`01-panorama-paginado.json` representa uma base **sintética**, com três áreas,
14 tipos descobríveis e dez artefatos. A primeira página traz três deles.
O catálogo desse exemplo descreve sua base fictícia, não afirma que os
adaptadores ou esses totais existem no APK. Os demais registros são alcançáveis
por consulta/cursor; referências a eles em relações continuam válidas.

O exemplo reúne objetivo de estudo, livro e plano de compra. Títulos e valores
são legíveis; a origem financeira é uma referência sem o mapa da contraparte.
Não há projeção financeira calculada nem recomendação de compra nesse fixture.

O contrato distingue:

- Catálogo completo **no escopo concedido**, com contagem e consultas por tipo.
  Escopo reduzido precisa aparecer em `restricoes_de_escopo`; não é visão global.
- Panorama de todas as áreas desse escopo, com relações, lacunas e referências.
- Página de detalhes completa ou parcial, com total/cursor explícitos.
- Revisão e referências vinculadas a um contexto/grant emitidos pelo aparelho.
- Valores tipados compartilhados com o [contrato de turno](../agente-turno-v1.schema.json),
  inclusive texto de planejamento, quantidades e referências locais.

Estados de adaptador, ausência de dados e cobertura parcial são distintos.
`nao_implementado` não equivale a zero registros. O contexto deve revelar essa
limitação, e o agente não pode concluir sobre dados que não conseguiu consultar.

O executor definitivo precisa conferir: catálogo versus todos os tipos/campos
canônicos, todas as áreas do escopo, totais versus consulta, IDs únicos,
proveniência, integridade das relações, autorização, projeção financeira e
paginação estável. A travessia de todas as páginas deve recuperar os registros
autorizados sem omitir/duplicar itens, preservando concluídos/histórico. Mudança
de snapshot/grant invalida o cursor; um mesmo alias não pode passar a apontar
para outro registro. Tipos novos entram na cobertura no mesmo PR que os cria.

Visão geral não exige enviar cada registro em cada chamada. O agente recebe
panorama e sabe consultar tudo, com limites explícitos. Séries, scores e
projeções ficam consultáveis com suas unidades/regras/fontes; o agente não
precisa interpretar uma captura de tela do gauge. Resumos de conversa também
mantêm acesso às decisões e mensagens de planejamento autorizadas de origem.

`python scripts/verificar-contrato-agente-proposto.py` confere os dois schemas
sem resolver recursos na rede. Além dos casos de turno, valida o exemplo de
contexto e rejeita quatro alterações estruturais, incluindo paginação
contraditória e valor fora do contrato comum. O CI já executa esse comando.
**Isso ainda não comprova cobertura do banco nem proteção de dados no app.**
