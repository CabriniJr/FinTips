# CI Android e build contínua

Pedido do usuário: GitHub Actions observando mudanças para compilar
automaticamente. O watch é por evento de Git: sem polling ou tarefas manuais
para compilar cada alteração.

## Branches e PRs

`android-ci.yml` roda em pushes de `codex/**` e `claude/**`, em PRs e por
disparo manual. Execuções ultrapassadas da mesma origem/branch são canceladas.
O CI usa apenas leitura do repo; não recebe a chave persistente nem publica
release. PRs de forks continuam sem acesso aos secrets de publicação.

Cada execução:

1. Instala dependências, testa JS e reconstrói os assets locais.
2. Compila `assembleDebug` e `assembleRelease` para validar também Compose.
3. Confere assinatura válida, package, launcher único, ausência de INTERNET,
   backup automático desligado e os assets byte a byte contra o build web.
4. Guarda APK, SHA-256 e manifesto em **Artifacts** por 14 dias.

O APK de teste aparece como **FinTips CI**, package `com.fintips.app.ci`.
Ele é separado do **FinTips UI** instalado (`com.fintips.app.ui`) e não
substitui seus registros. Sua chave de depuração é temporária; esse APK é
para avaliação de uma execução, não a sequência de atualizações do app principal.

A UI de avaliação continua WebView offline; o alvo Compose é compilado junto,
mas não foi ativado no launcher por este workflow. CI não comprova fluidez,
TalkBack, teclado, seletor ou lifecycle no celular.

## Main e versões

`android.yml` conserva o caminho do Claude: push em `main` atualiza
`android-main`; tag `android-v*` publica uma versão imutável. O workflow
reconstrói a UI antes do APK, executa Python/JVM/JS, ouro e PII e verifica o
APK offline e a assinatura. Tags recebidas pelo formulário são validadas;
disparo manual de publicação só aceita a main. Tag existente deve apontar ao
commit compilado. Versão publicada não é sobrescrita.

Publicações são serializadas; não cancelar no meio de upload. Um build da
main que ficou atrás do topo é descartado antes de alterar a rolante. Os
downloads novos são conferidos antes de mover a tag, atualizar notas e remover
nomes de anexos antigos. Os arquivos de uma release rolante não têm troca
atômica em grupo; o manifesto/commit e checksums identificam o conjunto atual.

## Assinatura: configuração única

As alphas anteriores usam o certificado público:

`3b2b3a83eec0f218c80f27541a3e27a918d87f7ecda890aecb2e5afbf3afc467`

O job de publicação usa o GitHub environment **Fintips**. O workflow exige
`ANDROID_KEYSTORE_BASE64` desse environment e recusa outro certificado. Sem a
chave, bloqueia publicação em vez de oferecer atualização incompatível que
levaria a desinstalar e perder dados. CI de PRs continua compilando normalmente.

A chave correta foi conferida localmente contra a alpha 3. O conector pode
escrever código/rodar Actions, mas a API de administração de Secrets retornou
403. Configuração pelo proprietário do repo, apenas uma vez:

1. Abrir **Settings → Environments → Fintips → Environment secrets → Add secret**.
2. Nome: `ANDROID_KEYSTORE_BASE64`.
3. Conteúdo: base64 do keystore das alphas, fornecido privadamente ao usuário.
   Não gerar uma chave diferente, não commitar, anexar a release ou colar em
   issue/PR. O arquivo privado de configuração fica fora do repo e dos artifacts.

Não é necessário cadastrar a variável de certificado para esta trava: o digest
das alphas está definido no workflow. Trocar chave/pacote exige uma decisão de
migração explícita; consentimento para CI não implica retirar PII do client.

Após configurar, **Actions → android → Run workflow**, com
`check_signing_only: true`, confere a disponibilidade e o certificado da chave.
Essa opção funciona também na branch de CI para validar a configuração antes
do merge: não compila nem altera releases. O job descarta a chave temporária ao
final e registra apenas o digest do certificado público no resumo.

Sem essa opção, publicação manual continua restrita à main. Push na main ou
tag versionada também usa o environment. Eventuais aprovações/restrições
configuradas pelo proprietário no environment são respeitadas pelo Actions.
O CI de PRs permanece separado e não declara environment nem usa secrets.
Conferir o certificado de `build-info.json` antes de tratar a rolante como
atualização compatível.
