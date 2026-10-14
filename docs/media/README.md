# Demonstrações do README

`hoje.gif` mostra tarefas sendo marcadas, progresso diário e transições entre
Hoje e Planos. `leitura.gif` mostra o histórico de um livro, registro de uma nova
posição e ajuste da frequência e do prazo. PNGs de Hoje, Leitura e Planos
acompanham as animações para consulta sem movimento.

São gravações da **interface real embarcada**, no Chromium com viewport de
390 × 844 e origem virtual `appassets.androidplatform.net`, usada pela WebView.
Não são capturas de um aparelho Android nem imagens de telas geradas por IA.
Todas as tarefas, livros, datas e planos foram inventados para a demonstração.
O cenário usa 14/01/2026 para não depender do dia em que foi gravado.

## Reproduzir

Instale FFmpeg no sistema e as ferramentas de captura em um ambiente separado:

```bash
python3 -m venv /tmp/fintips-demo-env
/tmp/fintips-demo-env/bin/pip install -r docs/media/requirements.txt
/tmp/fintips-demo-env/bin/python -m playwright install --with-deps chromium ffmpeg
/tmp/fintips-demo-env/bin/python scripts/gravar-demos-readme.py
```

Se Chromium já estiver instalado, o último comando aceita
`--browser /caminho/do/chromium`. A gravação desta entrega usou `/usr/bin/chromium`.
O script funciona de qualquer diretório e lê somente os assets públicos em
`fintips/web/`. Para gravar uma versão nova da interface, compile-a antes com
`npm ci` e `npm run build` em `web/`.

O navegador recebe um perfil temporário novo para cada fluxo. Somente arquivos
do bundle são atendidos; pedidos externos e caminhos fora dele são bloqueados.
O script não abre `config.yaml`, `data/`, backups ou um perfil de navegador do
usuário. As posições iniciais do livro são parte do cenário fictício; o GIF
mostra o registro manual, não uma conexão com a nuvem do Librera.

Vídeos WebM intermediários vivem em uma pasta temporária e são removidos ao
final. FFmpeg converte a captura em GIF a 12 fps, com paleta reduzida. Não há
retoque da UI. `capture-info.json` registra viewport, cenário e SHA-256 dos
assets usados, sem caminhos privados. Regravações podem ter diferenças de
timing; a receita reproduz o fluxo, não exige GIFs idênticos byte a byte.

No README, `<picture>` oferece PNG para `prefers-reduced-motion: reduce`.
Os links de capturas estáticas continuam disponíveis em leitores sem suporte
à preferência de movimento.
