# Scores, fontes automáticas e conexão com o chat

> Atualização preview 5: o motor e o servidor MCP rodam no Android, em loopback.
> C-01 ainda exige ponte autenticada para as contas ChatGPT/Claude;
> [arquitetura e limites atuais](SERVIDOR-MCP-LOCAL.md). Nenhuma fonte de
> UsageStats ou check-in foi ativada por essa mudança.


Pedido em 14/10/2026: vários scores e um agregado com gauges dinâmicos,
leitura/tempo de celular/academia automáticos e conector dentro de Claude ou
ChatGPT. O usuário confirmou: comprometimento é **cumprimento das metas que
ele escolheu**, com pesos ajustáveis e dados ausentes separados de zero.
PII permanece exclusivamente no client.

## Entrega nativa e limites

`GaugeDeVida.kt` implementa o renderer Compose: arco segmentado de 240°,
ponteiro animado, número real imediato, detalhes ao toque, peso parcial
visível e semântica para TalkBack. Animações finitas respeitam o mecanismo de
escala do Compose/Android; não há movimento ocioso em loop.

`TelaDoDia` usa uma lista rolável única e seis gauges abastecidos pelas
frentes de `montarTela`. Frente sem missão mostra arco interrompido, “Sem base”
e `—`; zero registrado com catálogo conserva o ponteiro em zero e a legenda
factual. Esses números são cumprimento registrado, não uma medida de saúde.

O renderer aceita agregado/objetivos com valor, faixa, base e pesos vindos do
motor. Não calcula fórmula, média ou faixa. Peso parcial aparece mesmo quando
o score é 100. No chamador atual só as frentes têm dados: o agregado mostra
“Ainda sem metas combinadas”; a guarda/adaptação de objetivos ainda falta.
V1 não está concluído por esse componente. V2/widget e V3/reajuste continuam
na fila. Não simular fonte ativa para preencher o gauge.

Esta entrega altera a **tela Compose do alvo release**. A alpha 3 publicada
continua com launcher WebView e não ganhou essas integrações. A mudança de
entrada depende da preservação dos registros e da guarda; não pedir
desinstalação como migração. Builds debug/release compilaram; sem validação
visual, TalkBack ou lifecycle em aparelho/emulador nesta revisão.

## Metas e agregado — S-01 solicitado ao Claude

| Indicador | Base local | Critério escolhido | Limite |
|---|---|---|---|
| Leitura | posições/timestamps Librera | progresso e ritmo por período | consulta repetida não é nova sessão; posição final não prova compreensão |
| Atenção | uso dos apps escolhidos | orçamento/janelas de uso | celular pode ser trabalho/estudo; não classificar todo uso como distração |
| Academia | check-in validado | frequência de presença | presença não prova intensidade/duração do treino |
| Comprometimento | metas assinadas e cumprimentos | metas, janela e pesos | não inferir motivação ou personalidade |

O motor deve fornecer um perfil versionado de metas/período/pesos, agregado
normalizado, componentes incluídos/omitidos, origem, frescor, cobertura e
`peso_aplicado`/`peso_total`. Peso zero é desativado, distinto de fonte ausente.
Ausência sai do denominador observado; permissão negada, falha e histórico
incompleto não são zero medido. Valores crus de páginas/minutos/check-ins não
podem ser somados como scores. Usar janela compatível e normalização frente
à meta declarada, com referência Python, porte Kotlin e ouro.

Exemplo **sintético proposto**, ainda sem fórmula implementada nesta UI:
leitura 80/peso 30, atenção 40/peso 20, comprometimento 100/peso 20, academia
ausente/peso 30 → agregado 74,3, base 70/100. O motor precisa confirmar regra
e arredondamento antes de fornecer esse resultado. O score de objetivo atual
tem pesos fixos: não ganhou pesos ajustáveis nesta revisão. Alterar perfil
não deve reescrever histórico para aparentar melhora.

## Fontes automáticas — discovery oficial

**Android/tempo de uso (A-02):** usar `UsageStatsManager` com autorização
especial de uso, não presumir acesso à base privada do Bem-estar Digital.
Agregados podem ampliar bordas; eventos têm retenção limitada e consultas
podem estar indisponíveis antes do desbloqueio. Soma por app em multiwindow
não é automaticamente tempo total de tela. Comparar períodos/definições no
aparelho; janela, fonte e cobertura aparecem na UI. Configurar uma vez,
coletar ao retomar/em fundo conforme limites do Android, preservar revogação
e deduplicação. Nomes/pacotes e histórico detalhado ficam locais. [1]

**TotalPass (A-06):** a API pública encontrada atende academias/ERPs para
validar entrada, não demonstra autorização de um app pessoal para baixar o
histórico do beneficiário. Validar caminho oficial de histórico/exportação;
não usar chave de academia ou endpoints privados como OAuth pessoal. Tokens,
dados brutos, ID de deduplicação e timestamp ficam no Android. Check-in
solicitado/abrir o app não prova visita validada. [2]

Notificação de confirmação é hipótese de piloto local opcional, se o serviço
realmente a emitir; exige validar formato e autorização própria. Não fazer
captura indiscriminada de notificações nem scraping de telas como coletor
definitivo. Sem fonte comprovada, indicar indisponibilidade, oferecer correção
manual e não penalizar pela falta de integração. Nenhuma conta real foi acessada.

## Conector dentro de Claude ou ChatGPT — C-01 / UI-06

MCP é o caminho comum para expor ferramentas dentro desses chats. Chamar uma
API de LLM pelo APK é outro produto. O piloto será somente leitura, com
vínculo/revogação, versão da representação e frescor.

Claude documenta conectores remotos nas superfícies suportadas, inclusive
mobile; configurar na conta e testar consulta no Android. A chamada vem da
infraestrutura Anthropic: `localhost` do telefone não fica acessível por isso.
ChatGPT orienta adicionar MCP em Plugins; configuração personalizada é pela
web e depende de políticas da conta/workspace. Não prometer configuração no
app Android; validar uso no cliente pretendido. [3][4][5]

Qualquer ponte remota recebe apenas representação que passou por filtro e
allowlist **no client, antes da rede**. PII, títulos, listas de apps, academias,
localização, textos livres e credenciais permanecem locais. Remover nomes não
torna scores/datas automaticamente anônimos; padrões podem identificar.
Sem saída comprovadamente sem PII, o campo fica local e o conector informa
omissão. Não publicar o MCP atual com payloads completos como atalho.
Validar app fechado/offline/retorno; Android não garante servidor permanente.

| ID | Responsável solicitado | Evidência para concluir |
|---|---|---|
| UI-05 | Codex | gauges ligados à guarda, estados vazios/parciais e acessibilidade Android |
| S-01 | Claude | agregado por metas/pesos escolhidos, porte e ouro |
| A-02 | Claude | estatísticas reais após autorização única, cobertura/revogação |
| A-06 | Claude | via autorizada de histórico pessoal e check-in confirmado/deduplicado |
| C-01 / UI-06 | Claude + Codex | consulta real no chat, client-filter, revogação e ausência de PII em saídas |

Os pedidos aguardam aceite nos docs; não declarar que o outro agente os assumiu.

Fontes oficiais consultadas em 14/10/2026:

1. [Android UsageStatsManager](https://developer.android.com/reference/android/app/usage/UsageStatsManager)
2. [TotalPass: API de entrada](https://dev.totalpass.com/reference/overview)
3. [Claude: usar conectores](https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities)
4. [Claude: MCP remoto](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
5. [ChatGPT: conectar MCP](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)
