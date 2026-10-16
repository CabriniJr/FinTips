# Exemplos do contrato proposto do agente

**Design, não API disponível.** Estes arquivos especificam a forma de um
resultado de turno, emitido pelo executor local após validar a proposta do
agente. Não são prompts, respostas de modelo real, dados de usuário nem
propostas importáveis na preview 9. O nome `fintips_turno_proposto_v1` distingue
esta proposta dos protocolos de triagem existentes.

O [plano de execução](../../PLANO-AGENTE-DE-VIDA.md) define responsabilidades,
privacidade, dependências e critérios de produto. O [schema](../agente-turno-v1.schema.json)
não anuncia ferramentas nem cria tabelas, modelos Kotlin ou rotas.

| Exemplo | Situação sintética | Efeito esperado |
|---|---|---|
| `01-conversa-sem-cadastro.json` | Saudação ou comentário sem nova intenção | zero comandos; preservar a mensagem na sessão |
| `02-pergunta-capacidade.json` | Intenção compreendida, mas orçamento de tempo ausente | pergunta estruturada vinculada à decisão; zero registros |
| `03-estudo-livro-agenda.json` | Objetivo confirmado na conversa, recurso existente, prazo e tempo escolhidos | proposta de grafo, reutilizando livro; ainda sem escrita |
| `04-cenario-financeiro.json` | Duas simulações da mesma carteira e horizonte já foram calculadas | proposta de cenário/decisão; não efetiva compra, crédito ou aporte |
| `05-agente-indisponivel.json` | Agente indisponível | preservar mensagem e zero registros; não fabricar plano como fallback |

O exemplo 03 é um **recorte de contrato**, com uma atividade e uma sessão.
Não demonstra um currículo completo, distribuição de várias semanas nem uma
certificação alcançada. Os exemplos não provam compreensão: a avaliação do
agente compara entradas sintéticas com o grafo/efeitos esperados, inclusive
correções, negação e várias intenções; ver P3/P5/P6 no plano.

## Referências e unidades

- `contexto_42` vincula aliases ao snapshot de revisão 42 e ao grant da sessão.
  É um identificador sintético. A implementação emite referências opacas,
  imprevisíveis, não derivadas de títulos/IDs pessoais.
- `prazo_01`, `dia_planejado_01`, `janela_01`, `intencao_01` e
  `resposta_orcamento` representam valores/evidências emitidos pelo executor,
  relacionados ao contexto. Mapas de identidades financeiras ficam locais.
- `texto_planejamento` permite ao agente gerar títulos/etapas em linguagem
  natural, como nos exemplos 03 e 04. Não depende de extrair um título por regra
  local nem de uma referência para cada palavra. O contexto de estudo/compra
  também pode chegar ao agente com seu significado.
- Esse tipo textual só é aceito nos campos permitidos pelo catálogo. Não libera
  memo bancário, identidade financeira, documentos ou credenciais e não elimina
  a projeção por proveniência antes de enviar contexto/API/MCP.
- `livro_existente_01` é um recurso já consultado, não um livro novo. Os
  `novo_*` têm escopo da proposta; não são IDs de registros persistidos.
- `simulacao_*` representa resultados do motor associados à mesma base. O
  exemplo não contém números financeiros fictícios apresentados como cálculo.
- Quantidades são inteiras e têm unidade: centavos de BRL, minutos ou
  pontos-base, por exemplo. `1000 pontos_base` são 10 pontos percentuais;
  não significam 1.000 páginas, minutos ou avanço observado.
- `origem=proposta_agente` identifica uma hipótese; as evidências referenciam
  a intenção e os limites declarados. Não é evidência de trabalho realizado.

## O executor ainda precisa validar

Validação JSON é apenas o primeiro portão. O executor comum de P1/P2 deve:

1. Resolver **somente** referências emitidas naquele contexto/grant; recusar
   contexto vencido, referência desconhecida/reordenada ou revisão concorrente.
2. Consultar o catálogo implementado: tipo/campo, unidade, operações permitidas,
   limites, proveniência e política de privacidade. `campos` flexível no schema
   não é autorização para inventar campos/capacidades. `texto_planejamento`
   não pode preencher campo classificado como identidade financeira local.
3. Recusar IDs locais duplicados, relações penduradas, ciclos de dependência,
   trocas de unidade e referências de texto usadas como dinheiro ou vice-versa.
4. Exigir simulações válidas, frescas e da mesma base para sessões e cenários.
   `simulacoes_refs` vazio não dispensa o cálculo quando a operação o exige.
5. Distinguir declaração, proposta, cálculo e observação. A origem deve ser
   compatível com evidência/campo; o modelo não pode declarar sua hipótese como
   observação de fonte nem transformar posição de leitura em domínio do livro.
6. Validar intervalos/opções/perguntas contra a decisão pendente. “Escolher
   outro tempo” abre a resposta estruturada; não vira um objetivo novo.
7. Verificar validade e autoridade no aparelho, aplicar atomicamente e emitir
   recibo idempotente. Não há `confirmado=true` no contrato do agente.

`substitui_proposta_ref` pode substituir apenas proposta pendente da mesma
sessão. Não exclui registro aceito. Hash, validade absoluta, autorização e
recibo pertencem ao executor; `expira_em_segundos` representa a duração de
validade emitida por ele, nunca um TTL escolhido livremente pelo modelo.

O agente pode receber e escrever texto de planejamento autorizado. Isso não
libera identidades financeiras em perguntas, títulos ou justificativas. O
schema de turno não é o schema de contexto de saída nem um detector de PII.
A projeção financeira por campo/proveniência e seus testes são entregas
explícitas de P1/P3, sem dependência de modelo local.

## Conferência estrutural

Requer Python e `jsonschema` 4.18 ou mais recente (Draft 2020-12).
A partir da raiz do repo:

```bash
python scripts/verificar-contrato-agente-proposto.py
```

O job `motor Python` do portão executa esta conferência no CI.
A conferência valida os cinco exemplos e rejeita adulterações: campos extras,
comandos em noop, aprovação pelo agente, quantidade fracionária, unidade
inválida, texto livre em referência e proveniência ausente. Não chama modelos,
não resolve aliases e não modifica os motores atuais. P1 deve integrar os
contratos definitivos e sua conformidade ao CI Python/Kotlin/API/MCP.
