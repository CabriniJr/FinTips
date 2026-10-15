# Motor embarcado e um MCP para ChatGPT e Claude

**Estado atual — preview 5:** servidor MCP Kotlin no próprio celular, loopback
com token e controle por notificação. Sem túnel ou contas conectadas.
[Funcionamento e avaliação atuais](SERVIDOR-MCP-LOCAL.md). As notas da
preview 4 abaixo são históricas.


O usuário confirmou ambos com o mesmo conector. A entrega alpha 4 liga o
motor Kotlin à UI WebView aprovada, preservando package `.ui`, assinatura,
origem local e os schemas de tarefas, planos e livros. Não muda o launcher para
Compose nem migra ou regrava os registros da alpha 3.

## Disponibilidade

| Fluxo | Estado nesta entrega |
|---|---|
| Áreas do dia | calculadas por `montarTela` no Kotlin, sobre tarefas do dia escolhido |
| Ritmo dos livros | `ritmoDeLeitura` Kotlin, inclusive prazos, recuo e dados antigos |
| OFX | leitura e conferência de saldo em memória; sem classificação, score ou histórico financeiro |
| Contexto mínimo | projeção Python/Kotlin com ouro, escopos desmarcados, JSON revisável |
| Vínculo e revogação | UI abre portal externo com projeção validada; não afirma conclusão externa |
| Serviço remoto | MCP comum somente leitura, OAuth PKCE e snapshots de 1 h; testado localmente |
| Conta ChatGPT/Claude | depende de hospedagem HTTPS e configuração/consulta real em cada conta |
| Sensores e atualização de contexto em fundo | não implementados |

## Fronteiras

`FinTipsMotor` é um WebMessageListener disponível apenas para
`https://appassets.androidplatform.net`, somente no frame principal e em
mensagem de texto. Operações possuem limites de tamanho e rodam no executor
local; erros públicos não contêm pedido, caminho ou exceção do parser.

O contrato JSON é testado no próprio módulo puro `:motor`. O adaptador Android
só converte JSON, verifica origem e trata o ciclo de vida. Não há servidor local
para acessar o motor, acesso a caminhos livres ou operação de escrita na ponte.
WebView antigo sem WEB_MESSAGE_LISTENER informa indisponibilidade e preserva
os dados. Nenhum fallback silencioso ao JavaScript é anunciado como Kotlin.

A UI continua no client. Os IDs necessários para associar checks entram no
motor no mesmo processo; não entram na projeção para IA. O OFX escolhido é
lido em memória, até 1 MiB; o usuário informa explicitamente o saldo anterior.
O extrato não é gravado pelo novo fluxo e nunca participa do MCP. Não passar
os defaults `expense` do parser como se fossem classificação financeira.

O APK segue sem INTERNET. `ia.abrir` valida origem HTTPS, formato do código,
chave de revogação e **toda a projeção allowlisted** antes de abrir ACTION_VIEW
no navegador externo. O fragmento contém só a projeção reduzida já revisada,
o código de pareamento e a chave de revogação. O portal exige confirmação
antes de transmiti-los ao seu serviço; nunca carregar conteúdo remoto dentro
do WebView que possui os registros pessoais.

O navegador tem sua própria rede: ausência de INTERNET no APK **não é mais
prova de ausência de saída opcional**. A declaração de configuração agora
expõe isso e deixa a ficha da Play Store pendente da hospedagem concreta.
Indicadores não são anunciados como anônimos. Credenciais OAuth pertencem ao
vínculo remoto; credenciais de bancos ou sensores não atravessam.

## Aceites e continuidade

A consulta no SDK MCP é evidência de interoperabilidade do protocolo, não de
conexão com ChatGPT ou Claude. Para fechar C-01, publicar HTTPS, configurar os
dois callbacks exatos, conectar ambas as contas e conferir consulta e
revogação no Android. Receber um código não conclui vínculo; abrir navegador
não conclui autorização. O app apresenta tentativas, sem selo de conectado.

S-01 continua solicitado ao Claude: agregado e pesos escolhidos pela pessoa,
com base ausente separada de zero. Esta entrega não inventa esse score.
A-02/A-06 permanecem solicitados: coleta automática com fonte e cobertura.
Antes de automatizar o envio, revisar autenticação do aparelho, armazenamento
de credenciais e consentimento para as áreas selecionadas; não adicionar token
de serviço no APK. Detalhes do serviço e retenção estão no
[README MCP](../integracoes/mcp/README.md).

## Avaliação Android

Atualize por cima da alpha anterior. Teste tarefas e livros existentes, checks
em outros dias, mudança de posição/prazo, seletor OFX e saldo correto/incorreto.
Em Contexto → Conectar IA, revise cada escopo, deixe todos desmarcados e
confira que não é possível seguir sem consentimento. Sem servidor, avalie a
preparação do contexto; não há conta conectada para testar consulta remota.

A validação automatizada inclui ouro Python/Kotlin/JS, contrato do APK,
serviço MCP e SDK real, builds debug/release e verificador de assinatura,
package, permissões e assets. QA no navegador não substitui WebView Android,
TalkBack, abertura/retorno do navegador, processo encerrado ou dispositivo.
