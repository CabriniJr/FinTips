# Contratos necessários à UI

Em 14/10/2026 o usuário atribuiu principalmente a **UI ao Codex**, permitindo
registrar pedidos em docs. Esta é a lista para quem trabalha no motor e no app
nativo, incluindo Claude Code. São pedidos registrados no Git; não significam
que o outro agente já leu, aceitou ou implementou cada item.

Direção visual: [LINGUAGEM-VISUAL.md](LINGUAGEM-VISUAL.md). O protótipo em
`web/` já oferece Hoje, Vida, Finanças, Planos e Contexto, com tarefas, planos,
registro manual de uso e leitura. A persistência é local ao navegador; **não
está conectada à persistência de missões do motor**. Não criar uma rota remota
para ligar as duas coisas: PII vive exclusivamente no client.

## Pedidos, por prioridade

| Pedido | Por que a UI precisa | Pronto quando |
|---|---|---|
| Repositório local de vida no Android | A pessoa precisa conservar tarefas e planos após fechar o app | armazenamento transacional no aparelho, IDs estáveis, recorrência, edição e recuperação de erro; nenhuma telemetria com conteúdo |
| Contrato de leitura das seis áreas | Separar tarefa cumprida de inferência e score | valor, origem, período, amostra/cobertura e estado ausente; vazio não vira zero medido |
| Adaptador Librera via seletor de documentos | Alimentar porcentagem sem compartilhar títulos ou arquivos | arquivo escolhido no aparelho, projeção mínima, perfil explícito, deduplicação e snapshots locais; [formato verificado](LEITURA-LIBRERA.md) |
| Capacidades de sensores | Evitar botão que promete acesso indisponível | estado `disponivel`, `nao_suportado`, `precisa_permissao`, `negado`, `sem_fonte`, `erro`, mais origem e atualização; Android UsageStats/Health Connect, iOS conforme entitlement |
| Exportação segura para ChatGPT | Dar contexto sem tirar PII do client | projeção local com allowlist, revisão do payload exato, exclusão de texto livre/IDs/nome de livro/app e bloqueio de saída fora do contrato |
| Backup e restauração locais | Recuperar registros sem servidor | versão de schema, validação, prévia de conflito, escrita atômica, preservação do arquivo inválido; protótipo atual apenas baixa a cópia |

O gráfico e o pacing de leitura já têm cálculo de referência em Python,
Kotlin e réplica JS, com ouro. O adaptador Android não precisa recriar a regra.
Precisa entregar os pontos locais `{dia, progresso_bp}` ao `ritmoDeLeitura`,
preservando em armazenamento a proveniência e o timestamp da fonte.

Não marcar missão como concluída ao chegar a 100% de posição. Só a pessoa
confirma conclusão; abrir uma página não prova tempo de estudo ou compreensão.
Não transformar títulos de livros, rotinas, metas ou nomes de apps em labels
de analytics. Percentuais/contexto derivados também precisam de revisão de
privacidade antes de sair do aparelho: remover nome não garante anonimato.

## Integração e propriedade dos arquivos

Codex mantém `web/`, `fintips/web/`, docs de UI e componentes visuais. Para a
primeira entrega do tracker, acrescentou isoladamente `fintips/reading.py`,
`vida/Leitura.kt`, gerador e ouro de leitura; não alterou o cálculo de missões
nem `Compras.kt`. Claude pode continuar o motor e os adaptadores nativos.
Antes de tocar nos mesmos arquivos, registrar o escopo em `ENTRE-AGENTES.md`.

Uma dependência identificada na base `2b27624`: regenerar todo o ouro acrescenta
`regra_declarada_aplicada` e `contexto_de_vida` a `compras.json`, mas o porte e
o comparador de compras ainda esperam a saída anterior. O ouro existente passa;
o regenerado acusa divergência. Esse trabalho não alterou o fixture de compras
para mascarar a diferença. Resolver a costura de `Compras.kt` e o comparador
na trilha financeira, junto com o ouro atualizado.
