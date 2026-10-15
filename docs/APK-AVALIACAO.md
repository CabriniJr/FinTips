# APK para avaliar a UI

**Estado atual — preview 7:** ponte HTTPS/OAuth para ChatGPT e Claude e cliente
WSS Android implementados. O motor e os registros ficam no celular; cada
consulta usa o mesmo MCP local, com áreas aprovadas por conector e sem snapshot
remoto. **Hospedagem e autorização nas contas reais ainda precisam de ativação.**
Veja [implantação e vínculo](../integracoes/ponte/README.md). O APK não embute
um domínio externo. O fluxo abaixo das versões anteriores é histórico.


**Estado atual — preview 6:** teste MCP real no início, botão de teste local,
códigos MCP-00 a MCP-06 e versão/API Android na tela. O servidor MCP Kotlin no próprio celular, loopback
com token e controle por notificação. Sem túnel ou contas conectadas.
[Funcionamento e avaliação atuais](SERVIDOR-MCP-LOCAL.md). As notas da
preview 4 abaixo são históricas.


**Atualização alpha 4 (`versionCode=4`):** a UI WebView agora chama o motor
Kotlin para áreas do dia, pacing e conferência de saldo OFX. Inclui preparação
de contexto e vínculo/revogação pelo navegador para um único MCP. Hospedagem
HTTPS e conexão real nas contas das IAs ainda pendentes.
[Fluxos e limites atuais](MOTOR-EMBARCADO-MCP.md).

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

A distribuição seguinte é **Alpha 3**, `versionCode=3`,
`0.6.0-ui-preview.3`, com os mesmos fluxos locais da v2 e a mesma assinatura.
[Release pública e anexos](https://github.com/CabriniJr/FinTips/releases/tag/android-v0.6.0-alpha.3).
Build, tag de origem e downloads foram conferidos; detalhes em
[RELEASES-ANDROID.md](RELEASES-ANDROID.md). A alpha 3 organiza a distribuição,
sem declarar sensores ou migração Compose concluídos.

## O que testar

- Criar e concluir tarefas diárias, mudar o dia e reabrir o app.
- Criar planos de vida com motivo e próximo passo.
- Em Vida → Estudos, adicionar livro manual ou selecionar `app-Progress.json`
  do Librera; atualizar posição, observar histórico e ajustar prazo/frequência.
- Registrar tempo de uso manual em Contexto.
- Navegação, tipografia, contraste, teclado, diálogos e alvos de toque.

Na alpha 4, Finanças oferece somente leitura e conferência de saldo OFX; não
há classificação ou histórico financeiro no APK. Sensores e sincronização
automática do Librera continuam pendentes. O fluxo de conexão das IAs exige
hospedagem HTTPS; a consulta real nas contas ainda não foi validada.
Nenhum dado de demonstração vem preenchido como se fosse da pessoa.

## Como funciona esta versão

O APK de avaliação embute os assets web em WebView com origem HTTPS virtual
`appassets.androidplatform.net`. São arquivos do próprio APK, não um site
remoto. O destino de produção continua Kotlin/Compose; a tela Compose do dia
permanece no alvo release. Avaliar esta variante não comprova a versão Compose.

Não há permissão INTERNET. Requisições e navegação externa são bloqueadas,
arquivos pessoais são escolhidos no seletor Android e importados no client.
`localStorage` fica no armazenamento privado do WebView. A saída opcional de
contexto para MCP ocorre pelo navegador externo após revisão e confirmação;
não carregar o servidor remoto no WebView. Não há analytics.
`allowBackup=false` impede backup automático do
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
