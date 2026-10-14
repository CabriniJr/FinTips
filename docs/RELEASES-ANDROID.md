# Distribuição Android

Release de avaliação atual: `android-v0.6.0-alpha.3`, com notas em
[releases/android-v0.6.0-alpha.3.md](releases/android-v0.6.0-alpha.3.md).
O APK é a variante debug offline com UI aprovada. `assembleRelease` abre
apenas a tela Compose do dia e não oferece a mesma experiência; não trocar as
variantes sem verificar conteúdo, persistência e migração.

## Release publicada

[FinTips Android · Alpha 3](https://github.com/CabriniJr/FinTips/releases/tag/android-v0.6.0-alpha.3)
foi publicada em 14/10/2026, como pre-release. A tag aponta para a fonte
`2aca938cb4316c0e7caa76de4e6c3254973a45ea`. Os seis assets foram baixados e
comparados byte a byte ao pacote preparado; os digests do GitHub também batem.
APK, fonte, manifesto, screenshots sintéticas e checksums estão disponíveis.

A instalação correta em `CabriniJr` resolveu o bloqueio de escrita. O upload
local em `uploads.github.com` ainda respondeu 401; a publicação foi concluída
por [GitHub Actions](https://github.com/CabriniJr/FinTips/actions/runs/38641942043),
usando o token do próprio runner. A branch operacional
`codex/publish-android-alpha3` contém o workflow e o verificador dessa entrega,
com hashes de arquivos públicos preparados como Git blobs. Não foi necessário
versionar APK ou enviar chave privada. O job verifica fonte, tag, manifesto,
bytes dos arquivos e downloads antes de tornar o rascunho público.

O fonte da UI e os contratos para as próximas etapas estão no
[PR #8](https://github.com/CabriniJr/FinTips/pull/8), sem merge automático de main.

## Preparar

1. Build com JDK 17, SDK 34 e wrapper Gradle 8.10.2:

   ```bash
   cd web
   npm ci
   npm test
   npm run build
   cd ../kotlin
   ./gradlew -Pfintips.android=true :app:assembleDebug
   ```

2. Conferir `apksigner verify --print-certs`, package, versão, launcher único,
   ausência de INTERNET e assets idênticos a `fintips/web/`. Comparar o digest
   do certificado público com a build anterior. Nunca versionar ou publicar
   chave de assinatura, arquivo pessoal, cache ou dump de localStorage.
3. Commitar a fonte após o portão de testes/PII do repo. Gerar o ZIP de fonte
   com `git archive HEAD`, sem arquivos ignorados. Registrar SHA de origem,
   versão e digest do certificado em `build-info.json`.
4. Colocar APK, fonte, imagens sintéticas e manifesto numa pasta separada.
   Gerar `SHA256SUMS.txt` desses arquivos. Conferir que o APK corresponde ao
   commit registrado e que o APK anterior continua intacto.

## Publicar

O usuário autorizou explicitamente a publicação da build e release no GitHub.
A fonte deve estar disponível no repo antes de publicar uma tag que a aponta.
Subir a branch de trabalho sem force push; abrir PR do escopo final quando
aplicável. A release alpha pode apontar ao commit dessa branch, sem exigir
merge de main nem incluir trabalho de outro agente.

Criar primeiro uma release em rascunho, anexar/verificar todos os arquivos e
então publicar como **pre-release**. Usar `--notes-file` para preservar o texto
das notas e `--target` com o SHA completo da fonte. O comando deve falhar se
esse commit ainda não estiver acessível no GitHub.

```bash
gh release create android-v0.6.0-alpha.3 \
  --repo CabriniJr/FinTips --target "$FINTIPS_SOURCE_SHA" \
  --title "FinTips Android · Alpha 3" --draft --prerelease \
  --notes-file docs/releases/android-v0.6.0-alpha.3.md \
  "$FINTIPS_RELEASE_DIR/FinTips-Android-v0.6.0-alpha.3.apk" \
  "$FINTIPS_RELEASE_DIR/FinTips-Android-v0.6.0-alpha.3-source.zip" \
  "$FINTIPS_RELEASE_DIR/SHA256SUMS.txt" \
  "$FINTIPS_RELEASE_DIR/build-info.json" \
  "$FINTIPS_RELEASE_DIR/hoje.png" "$FINTIPS_RELEASE_DIR/leitura.png"
```

Após conferir os assets via API e download, publicar:

```bash
gh release edit android-v0.6.0-alpha.3 \
  --repo CabriniJr/FinTips --draft=false --prerelease
```

Se a integração devolver `403 Resource not accessible by integration`, não
publicar no repo/conta de outra pessoa, substituir credenciais ou marcar a
release como concluída. Entregar o pacote pronto e registrar o bloqueio.
Escrita de código/tags/releases e upload dos assets exigem `Contents: write`
para a integração no repositório `CabriniJr/FinTips`.
