# Publicar na Play Store

Este documento não é um tutorial da Play Console — a documentação do Google faz
isso melhor e muda mais rápido. Ele responde outra pergunta: **o que, neste
repositório, está pronto e o que bloqueia**, e por quê.

O estado abaixo é conferível. `fintips config` imprime as permissões lidas do
manifesto compilado e as licenças derivadas dos manifestos de dependência, e
`fintips config --conferir` falha se a declaração divergir do código.

## O que já está resolvido

| Exigência | Estado | Onde se confere |
|---|---|---|
| `applicationId` estável | `com.fintips.app` | `kotlin/app/build.gradle.kts` |
| `targetSdk` dentro da janela | 34 | idem |
| `minSdk` declarado | 26 (Android 8) | idem |
| `versionCode` monotônico | 3 | idem, e o CI o carimba |
| Permissões justificáveis | **nenhuma** | `AndroidManifest.xml` |
| Backup automático | desligado | `android:allowBackup="false"` |
| Atribuições de código aberto | 14 componentes, derivados | `fintips config --licencas` |
| Ficha de Segurança dos Dados | respondida e derivada | `fintips config` |

A ausência de permissões é a coisa mais valiosa desta lista e vale dizer por
quê: **sem `android.permission.INTERNET` não existe requisição a fazer**. A
ficha de Segurança dos Dados deixa de ser uma promessa de boa-fé e passa a ser
uma consequência do manifesto — não há caminho de saída para um dado, nem por
engano, nem por uma atualização futura que ninguém leu.

## O que bloqueia hoje

### 1. A assinatura de release — este é o bloqueio de verdade

O APK publicado é **debug**, assinado com chave de depuração. A Play Store não
aceita isso, e a consequência é maior do que parece: a chave de assinatura de
um app Android **não pode ser trocada depois**. Publicar com a chave errada
significa não conseguir atualizar o app nunca mais, com o único remédio sendo
publicar outro app, com outro `applicationId`, e pedir para todo mundo
reinstalar — perdendo os registros, que só existem no aparelho.

O que falta:

- gerar um **upload key** novo, guardado fora do repositório;
- habilitar o **Play App Signing**, em que o Google guarda a chave de
  distribuição e você guarda só a de upload. É o que torna a perda da sua chave
  recuperável em vez de fatal;
- apontar `signingConfigs` no `:app` e trocar a variante publicada para
  `release`.

Hoje o CI assina com a chave de depuração do runner, **que muda a cada build**.
Por isso o workflow avisa em letra visível na release que aquele APK não
instala por cima do anterior, e por isso existe a variável
`ANDROID_CERT_SHA256`: com ela definida, o build falha quando o certificado
muda, em vez de descobrir pelo usuário que não conseguiu atualizar.

### 2. A política de privacidade precisa de uma URL pública

A Play Console exige um endereço acessível, não um arquivo no repositório. O
conteúdo já existe e é curto — `docs/PRIVACIDADE.md` —, e o fato de o app não
ter permissão de rede faz dele uma política honesta e pequena. Falta publicá-lo
(GitHub Pages serve) e colar a URL na ficha.

### 3. A variante publicada ainda é a WebView

O APK de avaliação embarca a interface web numa WebView. Isso **é** publicável
— muitos apps o fazem —, mas o alvo `release` hoje abre a tela Compose, que
cobre menos do que a web. Publicar sem decidir qual das duas é a variante de
produção entregaria ao usuário uma versão diferente da que foi avaliada.

A decisão é de produto e está na faixa visual, não nesta.

### 4. Conta de desenvolvedor e a lista da loja

Taxa única de registro, ícone 512×512, gráfico de destaque 1024×500, capturas
por formato de tela, descrição curta e completa, classificação de conteúdo e
público-alvo. A identidade já existe em `docs/identidade/` e as capturas da
alpha 3 estão nos anexos da release — **mas as capturas de hoje são de QA
sintético no navegador, não de aparelho**, e a loja exige capturas reais do app
em execução.

## A ficha de Segurança dos Dados, item a item

Esta é a parte que mais gente erra, porque a ficha é uma declaração sob
responsabilidade de quem publica, e as respostas mudam quando o código muda.
Por isso ela sai de `fintips/configuracao.py` e não de um texto à mão:

| Pergunta | Resposta | De onde ela vem |
|---|---|---|
| O app coleta dados? | Não | não há permissão de rede |
| Compartilha com terceiros? | Não | idem |
| Dados em trânsito criptografados? | Não se aplica | não há trânsito |
| O usuário pode pedir exclusão? | Sim | desinstalar apaga tudo |
| Há coleta obrigatória? | Não | — |

Quando os sensores entrarem — tempo de tela e passos são os primeiros —, **esta
ficha muda**, porque passa a existir leitura de dados do aparelho. A resposta
continuará sendo "não sai do dispositivo", mas a pergunta sobre coleta deixa de
ser trivial. A hora de atualizar a ficha é no mesmo commit que pede a
permissão, não depois.

## Antes de cada publicação

```bash
fintips config --conferir      # as licenças batem com os manifestos?
fintips config                 # as permissões são as que você espera?
```

O primeiro comando está no portão de push e no CI. O segundo é para ler com os
olhos: a tela de configuração é o que o app afirma sobre si mesmo, e é a única
parte do produto cujo erro tem consequência fora do produto.
