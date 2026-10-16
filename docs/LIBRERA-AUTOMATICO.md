# Librera automático e guarda nativa — preview 12

Esta entrega implementa a coleta de leitura e sua guarda comum. Ainda não é o
agente completo de gestão, decomposição de planos e replanejamento por tools.
O perfil/score financeiro completo e P1/P3/P5 continuam com os aceites do plano.

## Usar no Android

Em **Vida → Estudos**, toque em **Conectar arquivo do Librera** e escolha o
`app-Progress.json` que recebe as atualizações do Librera. A seleção concede
acesso persistente somente ao documento escolhido. O perfil padrão é
`principal`; outro perfil fica em detalhes. Use o perfil das importações
anteriores para conservar a identidade dos livros e seus vínculos.

A primeira leitura já atualiza os livros. Um job Android persistente relê a
fonte a partir de intervalos de 15 minutos, inclusive sem WebView. O sistema
pode adiar por bateria/Doze; forçar a parada suspende jobs até abrir o app.
Retomar o app também tenta atualizar. **Verificar agora** serve à conferência,
não é necessário a cada posição. Reconectar resolve uma permissão revogada;
**Desconectar** revoga o acesso e cancela o job, preservando livros/histórico.

O documento precisa realmente mudar. Uma cópia/exportação estática não ganha
posições novas. Para nuvem, o provedor Android precisa oferecer seleção e
grant persistente do documento atualizado; isso não conecta uma conta Drive
por OAuth. Diretórios privados de outro app que o Android bloqueia não são
contornados. Librera/Syncthing/provedor precisa tornar o JSON acessível.

A tela distingue a hora da leitura do arquivo do timestamp de cada posição.
Um arquivo lido agora pode conter uma posição antiga; isso não torna o pacing
atualizado. A fonte guarda apenas a última posição por livro: mudanças entre
duas coletas não podem ser reconstruídas. O FinTips forma histórico com as
posições que observou.

## Mesma autoridade para UI, job e contexto

`EstadoCliente` grava `noBackupFilesDir/estado-cliente-v1.json` por `AtomicFile`.
É autoridade de vida, leitura, caderno/relações e conversa, junto da configuração
da fonte Librera. A UI usa uma interface local síncrona de guarda; operações
de domínio/IA continuam no canal com origem restrita. Navegação e subrecursos
externos do WebView continuam bloqueados. Não há chamadas de rede nessa guarda.

Na primeira abertura, o bootstrap lê/valida os stores WebView anteriores,
valida o bundle no Kotlin e grava o nativo atomicamente. Só depois passa a usar
a autoridade nativa. O legado permanece intacto como recuperação e não recebe
novas escritas; não há dual-write. Fonte ilegível ou migração inválida não vira
estado vazio. A abertura bloqueada oferece cópia nativa e cópia do legado.

Revisões de bundle e chat são independentes: um autosave da conversa não
sobrescreve o progresso que o job acabou de importar. Alteração concorrente do
mesmo bundle recusa a gravação obsoleta; UI e propostas precisam reler/revisar.
A fonte tem token/geração próprios: uma seleção ou leitura pendente não pode
reativar uma conexão que foi cancelada/trocada.

O job importa diretamente na mesma leitura canônica, em vez de manter fila ou
outro tracker. Corrigir manualmente prevalece naquele dia, arquivo atrasado
não substitui posição mais nova e remoção de livro fica suprimida na fonte até
restauração explícita. Mesmo livro/perfil preserva id, prazo, frequência e
relações. Perfis diferentes ficam separados. Recuo continua seguindo o pacing
existente; chegar a 100% não conclui tarefa, objetivo ou certificação.

A API da triagem lê o bundle nativo atual. O MCP já autorizado pode renovar seu
**resumo reduzido v1** pelo nativo após a coleta, mesmo sem UI, preservando as
áreas da sessão e a pausa. O job não inicia MCP, não amplia grants, não chama a
API paga e não envia títulos, URI ou `pt`. O contexto completo por artefatos e
os comandos de gestão/replanejamento ainda exigem P1/P3/P5/P7; não anunciar
esta atualização como aquele conector completo.

## Guarda, limites e cópia

O registro único é `fintips/rules/guardas-android.json`, derivado para o Kotlin
pelo gerador conferido no CI. As classes consomem os nomes/descritores; a
configuração exportada e `guarda.descritores` leem esse mesmo registro. Ele
complementa o registro do Workspace desktop, cuja autoridade YAML não muda.
Extratos continuam no seu depósito nativo existente, sem mudança de schema.

O bundle mantém schema 1, até 3.000 artefatos conforme o contrato existente.
A guarda nativa limita a 8 MB e a fonte JSON a 2 MB. Exceder limites, JSON
incompleto, erro do provedor ou revogação preservam o último estado válido.
Não há poda silenciosa de histórico. `pt`, caminhos e metadados extras do
Librera são descartados; URI e perfil da conexão ficam locais.

Cópias da UI passam a ler os registros nativos. Extratos continuam com cópia
própria em Finanças. A cópia nativa de recuperação conserva inclusive bytes
ilegíveis; pode incluir URI/metadados pessoais e deve ficar no aparelho.
Restauração automática da cópia nativa ainda não está implementada. Atualizar
por cima preserva os registros; desinstalar/limpar dados apaga a guarda.

## Validação

- Referência Python/Kotlin com ouro: parser mínimo, normalização, repetição,
  atualização, atraso, correção manual, perfil, futuro, recuo e supressão.
- Projeção MCP reduzida derivada do bundle também compara com o Python.
- Instrumentação Android: guarda/CAS/corrupção; migração WebView e livro
  atualizado na UI; URI com grant persistente, job real sem WebView, arquivo
  inválido, revogação e cancelamento preservando histórico. Provedor sintético
  existe apenas no APK de testes, nunca no APK público.
- UI 320/390/768: conectar/atualizar/desconectar e legado intacto, com guarda e
  bridge simulados. Não é prova de provedor/nuvem reais do usuário.

Room/consultas estruturadas podem substituir a guarda no futuro com migrador
validado. Nesta etapa, um documento atômico preserva o bundle já existente e
permite a transação comum; não são quatro lojas concorrentes.
