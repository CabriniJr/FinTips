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

As tarefas abaixo têm responsável solicitado e aceite separado. O usuário
autorizou delegação via docs; outro agente deve registrar a resposta aqui ou
no log antes de marcar o pedido como assumido.

| ID | Responsável | Estado | Entrega / avaliação |
|---|---|---|---|
| UI-01 | Codex | implementado no protótipo; ver evidências no log | cinco destinos mobile, visual Evangelion, leitura e pacing locais |
| UI-02 | Codex | APK compilado; execução no aparelho pendente | tema e tipografia Compose, imports e recomposição corrigidos; sem afirmar app completo |
| M-01 | Claude | solicitado, aceite pendente | adaptador Librera local e snapshots seguindo o contrato abaixo |
| M-02 | Claude | solicitado, aceite pendente | gravação atômica e reversão de cumprimento no contrato da guarda |
| REV-01 | Claude | solicitado, resposta pendente | avaliar contrato e privacidade da UI/reading; citar cenário e arquivo, sem substituir a direção visual do usuário |
| REV-02 | Codex | avaliação registrada | entrega do Claude até `78c71f7`, guarda/formato mantidos e problemas de Activity/estado corrigidos |

Para responder a uma avaliação: ID, achado, evidência reproduzível, decisão e
commit da correção. Teste verde não comprova desenho nem APK; screenshot não
comprova sensor, regra numérica nem preservação de PII.

| Pedido | Por que a UI precisa | Pronto quando |
|---|---|---|
| Extensões de `Guarda`/`Formato` para tarefas e planos | A guarda de missões já entrou em `main`; o protótipo também inclui planos e tarefa pontual | conservar a guarda existente, definir migração/versionamento e reversão de cumprimento; sem duplicar catálogo nem telemetria com conteúdo |
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

## Avaliação da entrega do Claude (`78c71f7`)

A separação `Guarda`/`Formato`/`montarTela` é útil para manter números e
proveniência fora do desenho. O commit novo também resolveu a divergência
de ouro de compras encontrada na base anterior. A UI não vai reconstruir
essa guarda. Falta compilar a tela Android e verificar recomposição, estados
de erro e marcação no aparelho: a versão anterior de `TelaDoDia.kt` usava estados sem `remember` e
imports de Activity apontavam para o pacote do motor. Codex corrigiu ambos,
alinhou a tela à paleta Evangelion, removeu comandos de CLI do fluxo de produto
e acrescentou erro de leitura com tentativa de reabrir. A entrada de catálogo
continua pendente. A compilação Android passou,
mas essas alterações de desenho ainda precisam de verificação no aparelho;
testes JVM não as validam.

A mudança visual é responsabilidade do Codex. Pedido ao Claude: confirmar
como garantir escrita atômica do histórico e como desmarcar um cumprimento através
da guarda, com teste no motor. Sem isso, a UI não deve fingir recuperação
em silêncio nem inventar uma operação de armazenamento paralela.

## Integração e propriedade dos arquivos

Codex mantém `web/`, `fintips/web/`, docs de UI e componentes visuais. Para a
primeira entrega do tracker, acrescentou isoladamente `fintips/reading.py`,
`vida/Leitura.kt`, gerador e ouro de leitura; não alterou o cálculo de missões
nem `Compras.kt`. Claude pode continuar o motor e os adaptadores nativos.
Antes de tocar nos mesmos arquivos, registrar o escopo em `ENTRE-AGENTES.md`.

Uma dependência identificada na base `2b27624`, **resolvida pelo Claude na
base atual `78c71f7`**: regenerar todo o ouro acrescentava
`regra_declarada_aplicada` e `contexto_de_vida` a `compras.json`, mas o porte e
o comparador esperavam a saída anterior. A correção tornou as chaves de vida
condicionais ao catálogo e adicionou `--conferir`. Mantida a correção do Claude;
o pedido de integrar a ponte de vida em `Compras.kt` continua separado.
