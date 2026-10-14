# Sistema visual

A direção vigente é **Neon Genesis Evangelion**, escolhida pelo usuário em
14/10/2026 e reforçada após rejeitar a primeira aplicação discreta.

- [Linguagem, referências e tokens](LINGUAGEM-VISUAL.md)
- [UI mobile e limites do protótipo](UI-MOBILE.md)
- [Contratos e pedidos para motor/Claude](NECESSIDADES-UI.md)

A direção anterior monocromática está no histórico de Git (até `78c71f7`).
Os gestos de sombra deslocada daquele desenho não governam a nova linguagem.
A fronteira de responsabilidade permanece: o motor fornece números e
proveniência; a UI apresenta sem elogiar, cobrar ou concluir sozinha.

## Android

`kotlin/app/` pertence à trilha visual. A tela do dia recebeu os tokens,
fonte local e correção de estado/imports, preservando `Guarda`/`Formato`.
`assembleDebug` passou com JDK 17, SDK 34 e Gradle 8.10.2 em 14/10/2026.
O desenho e o ciclo de vida precisam de revisão no aparelho: não foram executados. Os cinco destinos e o tracker completo são revisáveis no web e no APK
debug local de avaliação; a navegação correspondente ainda precisa de
implementação Compose. [Recorte do APK](APK-AVALIACAO.md).
A compilação JVM do motor não comprova compilação nem funcionamento do APK.

## Compilação Android verificada

```bash
cd kotlin
./gradlew -Pfintips.android=true :app:assembleDebug
```

Requer JDK 17, SDK Android 34 e `ANDROID_HOME` apontando para o SDK.
APK de depuração: `app/build/outputs/apk/debug/app-debug.apk`.
As versões Kotlin agora estão centralizadas no build raiz; AGP entra no
classpath compartilhado **somente** com a flag Android. Sem a flag, o motor
continua puro e `:motor:jvmTest` funciona sem o SDK.

Não há permissão INTERNET e `allowBackup=false` no manifesto. A tela nativa
mostra o dia e o catálogo já instalado; seleção de catálogo, navegação nos
cinco destinos e tracker ainda precisam de implementação Compose.
