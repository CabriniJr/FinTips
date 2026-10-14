# Contribuindo com o FinTips

O destino é um app Android em Kotlin e Compose. Python é o motor de referência,
e a interface embarcada atual é React em WebView. Antes de escolher uma tarefa,
leia [CLAUDE.md](CLAUDE.md) e o estado em
[docs/ENTRE-AGENTES.md](docs/ENTRE-AGENTES.md). O canal registra faixas de trabalho
e contratos para que agentes e pessoas possam colaborar pelo Git.

## Ambiente

Python 3.10+, Node 20+ para a UI e JDK 17 para o motor Kotlin. O Gradle Wrapper
está versionado; o motor JVM não precisa de SDK Android. Para compilar o APK,
prepare o SDK conforme [RELEASES-ANDROID.md](docs/RELEASES-ANDROID.md).

```bash
git clone https://github.com/CabriniJr/FinTips.git
cd FinTips
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[tudo]" pytest
```

No Windows, ative com `.venv\Scripts\Activate.ps1` no PowerShell. Use
`python` em vez de `python3` e `gradlew.bat` em vez de `./gradlew`.
O portão com Bash pode rodar no Git Bash ou WSL. O script
[publicar.ps1](scripts/publicar.ps1) documenta o fluxo de publicação usado no
Windows; não é necessário para preparar um PR.

Para trabalhar na interface, instale as dependências e rode o Vite:

```bash
cd web
npm ci
npm run dev
```

Em outro terminal, com o ambiente Python ativo, execute `fintips serve`.
O Vite abre em `http://localhost:5173` e encaminha a API para o motor em
`127.0.0.1:8420`. Para gerar os assets embarcados, use `npm run build`.

## Antes de enviar um PR

Execute da raiz; no Windows, ajuste o comando do wrapper:

```bash
python3 -m pytest -q
python3 scripts/gerar-ouro.py --conferir
bash scripts/check-pii.sh --all
python3 -m fintips.cli config --conferir
```

```bash
cd kotlin
./gradlew :motor:jvmTest --no-daemon
```

```bash
cd web
npm test
npm run build
```

O workflow [portao.yml](.github/workflows/portao.yml) executa essas verificações
em pushes e PRs. Em mudanças de UI, mostre o comportamento em largura de
celular, confira teclado/foco e movimento reduzido. Use um cenário fictício.

## O que um PR precisa preservar

- **Dados pessoais no client.** Não versione `data/`, extratos, backups,
  credenciais ou frases copiadas de um plano pessoal. O teste também é público.
- **Proveniência.** Heurística e importação ajudam a investigar; conclusões
  carregam a origem e o motivo. Ausência de dados não equivale a zero.
- **Paridade.** Regra nova do motor precisa de ouro Python e do equivalente
  Kotlin. O porte replica a referência; corrigir uma fórmula exige mudar ambos.
- **Identidade e acessibilidade.** Reutilize os
  [assets de marca](docs/identidade/README.md) e a
  [linguagem visual](docs/LINGUAGEM-VISUAL.md). Cor precisa de nome e estado;
  transições respeitam [movimento reduzido](docs/MOVIMENTO-UI.md).

Abra o PR com o problema, o comportamento resultante e a validação relevante.
Em arquivos compartilhados, registre sua faixa e o handoff em
`docs/ENTRE-AGENTES.md`. Evite misturar um porte de motor com uma reformulação
visual no mesmo PR.

## Issues e demonstrações

Para um bug, informe versão/build, dispositivo ou navegador, passos para
reproduzir e o resultado esperado. Uma captura deve usar dados fictícios.
Nunca anexe um workspace ou extrato para demonstrar o problema.

Os GIFs do README são gravados da interface real. A receita e a origem estão
em [docs/media/README.md](docs/media/README.md). Os banners e logos têm outro
gerador, documentado no [kit de identidade](docs/identidade/README.md).
