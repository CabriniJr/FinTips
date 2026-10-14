# FinTips Android · Alpha 3

Uma vida em perspectiva: tarefas do dia, áreas de vida, planos e leitura no
celular, com a linguagem visual de Neon Genesis Evangelion e alto contraste.

## Instalar

Baixe **FinTips-Android-v0.6.0-alpha.3.apk** nos arquivos desta release e abra
no Android. Requer **Android 8 ou posterior** e Android System WebView atualizado.
Se solicitado pelo sistema, permita a instalação pelo navegador ou gerenciador
de arquivos usado para abrir o APK.

O aplicativo instalado se chama **FinTips UI**. Esta build conserva o pacote
`com.fintips.app.ui` e a assinatura das duas entregas anteriores: instale por
cima para manter os registros. Não desinstale nem limpe os dados para atualizar.

## O que você pode usar

- **Hoje:** criar tarefas, repetir diariamente, consultar outros dias, concluir
  e desfazer a conclusão.
- **Vida:** navegar pelas seis áreas; em Estudos, acompanhar livros com
  porcentagem, histórico e estimativa de ritmo baseada nos registros.
- **Leitura:** adicionar livros ou importar uma cópia local de
  `app-Progress.json` do Librera; ajustar prazo e frequência, corrigir posição
  e reimportar sem duplicar o mesmo snapshot.
- **Planos:** registrar objetivo, motivo e próximo passo.
- **Contexto:** registrar tempo de uso manual e fazer cópias locais.
- **Interação:** transições entre abas, resposta ao toque, formulários com
  entrada/saída e indicadores animados; suporte a movimento reduzido.

Esta alpha 3 organiza a distribuição Android da UI e dos fluxos já aprovados;
não acrescenta coleta automática ou novas integrações em relação ao APK v2.

## Seus dados ficam no aparelho

O APK funciona offline, sem permissão INTERNET, analytics ou upload. Fontes e
arquivos são escolhidos no próprio Android. PII permanece exclusivamente no
client. Cópias exportadas contêm conteúdo pessoal: guarde-as com cuidado.

A exportação local salva em **Downloads/FinTips** no Android 10 ou posterior,
com limite de 2 MB. No Android 8/9 a interface informa essa limitação.
Desinstalar ou limpar o armazenamento apaga os registros locais.

## Estado da alpha

Esta build usa a UI web empacotada em **WebView local**. A evolução nativa em
Kotlin/Compose é a prioridade Android, mas a migração ainda não está concluída.
Finanças, UsageStats, Health Connect, sincronização automática do Librera e
conexão com ChatGPT **ainda não estão disponíveis**. Tempo de uso continua manual.

Build, assinatura e assets embarcados são verificados antes da entrega.
Os fluxos web foram avaliados em diferentes larguras e com movimento reduzido;
a compilação não comprova fluidez, seletor de arquivos ou lifecycle no aparelho.
Esta release continua destinada à avaliação, não à distribuição de produção.

## Feedback no celular

Ao relatar um problema, informe modelo, versão do Android, tela/ação e o que
aconteceu. Prioridades: fluidez das transições, teclado, botão Voltar,
importação local e preservação dos registros ao atualizar. Remova dados pessoais
de screenshots antes de abrir uma issue pública.

## Arquivos da release

- `FinTips-Android-v0.6.0-alpha.3.apk`: APK assinado com a chave de depuração
  das entregas anteriores.
- `SHA256SUMS.txt`: checksums para conferir os arquivos.
- `build-info.json`: versão, commit de origem, certificado público de assinatura
  e detalhes do build; não contém chave privada nem dados pessoais.
- `FinTips-Android-v0.6.0-alpha.3-source.zip`: fonte exata da build, incluindo
  o wrapper Gradle e os assets locais; não inclui chave de assinatura.
- `hoje.png` e `leitura.png`: imagens ilustrativas com dados sintéticos de QA,
  capturadas no navegador com a origem local do APK, não em dispositivo.

![Hoje — dados de exemplo](https://github.com/CabriniJr/FinTips/releases/download/android-v0.6.0-alpha.3/hoje.png)

![Leitura — dados de exemplo](https://github.com/CabriniJr/FinTips/releases/download/android-v0.6.0-alpha.3/leitura.png)

---

## Procedência desta publicação

Esta release foi publicada por um segundo agente, porque a integração que
construiu o APK recebeu `HTTP 403` ao escrever no repositório.

Dito com precisão, para não haver confusão depois:

- **O APK não foi construído a partir da tag desta release.** Ele saiu do
  commit `2aca938cb4316c0e7caa76de4e6c3254973a45ea`, que nunca chegou ao
  GitHub. O fonte daquele commit está nesta tag, aplicado sobre `78c71f7`,
  junto de trabalho posterior que **não** está no binário.
- O `FinTips-Android-v0.6.0-alpha.3-source.zip` é o fonte exato do build.
  Quem quiser reproduzir deve partir dele, não da tag.
- Os checksums em `SHA256SUMS.txt` conferem com os arquivos anexados. Isso
  prova integridade do transporte, **não** que o APK corresponde ao fonte:
  essa correspondência não foi reproduzida por quem publicou.
- O `gradle-wrapper.jar` do fonte foi conferido contra a origem oficial e é
  byte a byte idêntico ao de `gradle/gradle` na tag `v8.10.2`
  (`2db75c40782f5e8ba1fc278a5574bab070adccb2d21ca5a6e5ed840888448046`).
- `device_or_emulator_tested: false`. A compilação não prova fluidez, seletor
  de arquivos nem lifecycle no aparelho.
- A variante empacotada é a **debug**, com `applicationIdSuffix .ui` e a UI web
  embarcada em WebView. O que se instala não é a tela Compose nativa.

Build assinado com chave de depuração. Avaliação, não distribuição de produção.
