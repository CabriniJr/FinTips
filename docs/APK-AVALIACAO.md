# APK para avaliar a UI

O usuário pediu um APK para instalar no próprio celular e devolver feedback.
Após a entrega v2, definiu Android como foco. A próxima evolução segue
[ANDROID-PRIMEIRO.md](ANDROID-PRIMEIRO.md); este APK continua sendo a avaliação
em WebView descrita abaixo.
A variante **debug** agora abre a UI Evangelion com os cinco destinos: Hoje,
Vida, Finanças, Planos e Contexto. O nome de instalação é **FinTips UI** e o
application ID é `com.fintips.app.ui`, separado do futuro app de produção.

A segunda versão (`versionCode=2`) acrescenta [movimento e respostas de interação](MOVIMENTO-UI.md).
O armazenamento mantém o mesmo schema e application ID. Atualizar sobre a
primeira versão exige a mesma assinatura. Na entrega v2, a assinatura foi
comparada com o primeiro APK e coincide; instale sobre ele para preservar os
registros, sem desinstalar ou limpar dados.

## O que testar

- Criar e concluir tarefas diárias, mudar o dia e reabrir o app.
- Criar planos de vida com motivo e próximo passo.
- Em Vida → Estudos, adicionar livro manual ou selecionar `app-Progress.json`
  do Librera; atualizar posição, observar histórico e ajustar prazo/frequência.
- Registrar tempo de uso manual em Contexto.
- Navegação, tipografia, contraste, teclado, diálogos e alvos de toque.

Finanças ainda não está ligada ao motor neste APK e aparece como pendente.
Sensores, sincronização automática do Librera e ChatGPT continuam pendentes.
Nenhum dado de demonstração vem preenchido como se fosse da pessoa.

## Como funciona esta versão

O APK de avaliação embute os assets web em WebView com origem HTTPS virtual
`appassets.androidplatform.net`. São arquivos do próprio APK, não um site
remoto. O destino de produção continua Kotlin/Compose; a tela Compose do dia
permanece no alvo release. Avaliar esta variante não comprova a versão Compose.

Não há permissão INTERNET. Requisições e navegação externa são bloqueadas,
arquivos pessoais são escolhidos no seletor Android e importados no client.
`localStorage` fica no armazenamento privado do WebView; não há upload,
analytics nem fonte externa. `allowBackup=false` impede backup automático do
app. Desinstalar ou limpar dados apaga os registros.

O botão de cópia salva JSON em **Downloads/FinTips** no Android 10 ou posterior,
sem escolher provedor de nuvem. O arquivo contém conteúdo pessoal e tem limite
de 2 MB. No Android 8/9 a UI e os registros locais funcionam, mas essa exportação
informa a limitação. O APK requer Android 8+ e WebView atualizado.

## Build reproduzível

```bash
cd web
npm ci
npm run build
cd ../kotlin
./gradlew -Pfintips.android=true :app:assembleDebug
```

JDK 17, SDK Android 34 e Gradle 8.10.2. O wrapper está versionado. Arquivo:
`kotlin/app/build/outputs/apk/debug/app-debug.apk`. A variante debug usa chave
de depuração, não assinatura de produção; o arquivo da chave não entra no Git.

A compilação e a origem virtual/fluxos web foram verificados nesta entrega.
Não houve execução em emulador ou aparelho. O teste do seletor Android,
salvamento em Downloads, teclado e lifecycle real precisa do feedback no celular.
