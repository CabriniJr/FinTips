#!/usr/bin/env bash
# Trava de PII antes do commit.
#
# Lê os SEUS dados locais (config.yaml, patrimonio.yaml, data/regras-locais.yaml,
# data/missoes.yaml, data/registros.jsonl — todos fora do Git) e procura
# qualquer pedaço deles nos arquivos que estão indo para o commit. O script é
# genérico: ele não contém nenhum dado seu, só sabe onde procurá-los.
#
# O catálogo de missões é o arquivo mais sensível do workspace, e não é
# exagero: plano de vida tem salário, empregador, nome de gente, valor de
# patrimônio e hora de dormir. A lista do que você treina e quanto aporta diz
# mais sobre você do que o extrato bancário.
#
#   bash scripts/check-pii.sh            # confere o que está staged
#   bash scripts/check-pii.sh --all      # confere todos os arquivos versionados
#
# Instalar como hook (recomendado):
#   cp scripts/check-pii.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

if [ "${1:-}" = "--all" ]; then
  mapfile -t FILES < <(git ls-files)
else
  mapfile -t FILES < <(git diff --cached --name-only --diff-filter=ACM)
  [ ${#FILES[@]} -eq 0 ] && mapfile -t FILES < <(git ls-files)
fi
[ ${#FILES[@]} -eq 0 ] && { echo "nada para conferir"; exit 0; }

TERMS=$(mktemp); trap 'rm -f "$TERMS"' EXIT

# nomes próprios e apelidos do config.yaml
[ -f config.yaml ] && grep -oE '^[[:space:]]*-?[[:space:]]*[A-ZÀ-Ý][A-Za-zÀ-ÿ]+([[:space:]][A-ZÀ-Ý][A-Za-zÀ-ÿ]+)+' config.yaml \
  | sed 's/^[[:space:]-]*//' >> "$TERMS"
[ -f config.yaml ] && grep -oE '^[[:space:]]+[^:#]+:' config.yaml | sed 's/[[:space:]:]//g' \
  | grep -E '^[A-Za-zÀ-ÿ]+$' >> "$TERMS"

# valores do patrimônio (formatos com ponto e com vírgula)
if [ -f data/patrimonio.yaml ]; then
  grep -oE 'valor:[[:space:]]*[0-9.]+' data/patrimonio.yaml | grep -oE '[0-9.]+' | while read -r v; do
    echo "$v"; echo "${v/./,}"
  done >> "$TERMS"
fi

# estabelecimentos locais
[ -f data/regras-locais.yaml ] && grep -oE '^[[:space:]]+-[[:space:]]+.+' data/regras-locais.yaml \
  | sed 's/^[[:space:]]*-[[:space:]]*//' >> "$TERMS"

# missões, regras declaradas e registros — data/missoes.yaml e data/registros.jsonl
#
# Colhido com o YAML de verdade, e não com grep, por um motivo concreto: as
# frases mais sensíveis do plano estão em bloco dobrado (`porque: >`), e grep
# de linha pega só o `>`. Era um buraco exatamente onde o risco é maior.
#
# Só frases (termo com espaço, 8 caracteres ou mais) e números entram. Palavra
# única genérica — "Leitura", "Dentista", "tablet" — daria falso positivo em
# qualquer doc do projeto, e varredura que grita por tudo é varredura que se
# aprende a ignorar. Frase copiada do plano, essa sim só aparece se vazou.
if [ -f data/missoes.yaml ] || [ -f data/registros.jsonl ]; then
  python3 -I - <<'PYEOF' >> "$TERMS"
import json, pathlib
try:
    import yaml
except ImportError:
    raise SystemExit(0)

# `colide_com` fica de fora de propósito: são palavras de categoria de produto
# ("tablet", "console", "streaming"), genéricas por natureza. O que é pessoal
# ali é a LIGAÇÃO entre a palavra e a missão, não a palavra. Colhê-las faria o
# script gritar em cima do próprio molde do pacote — e varredura que grita por
# tudo é varredura que se aprende a ignorar.
TEXTO = {"titulo", "porque", "como_medir", "nota", "enunciado", "medida", "notas"}
NUMERO = {"valor_mensal", "acima_de", "preco", "custo_alvo"}
saida = []

def anda(no):
    if isinstance(no, dict):
        for k, v in no.items():
            if k in TEXTO and isinstance(v, str):
                saida.append(" ".join(v.split()))
            elif k in NUMERO and v is not None:
                saida.append(str(v))
            else:
                anda(v)
    elif isinstance(no, list):
        for x in no:
            anda(x)

m = pathlib.Path("data/missoes.yaml")
if m.exists():
    anda(yaml.safe_load(m.read_text(encoding="utf-8")) or {})

r = pathlib.Path("data/registros.jsonl")
if r.exists():
    for linha in r.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            anda(json.loads(linha))

for t in saida:
    t = t.strip()
    if not t:
        continue
    numero = t.replace(".", "").replace(",", "").isdigit()
    # Texto só entra como FRASE. "Dentista" ou "Leitura" é título de missão de
    # uma palavra: genérico, e colhê-lo faria o script acusar qualquer doc do
    # projeto que mencionasse a palavra — inclusive esta explicação. Número
    # entra sozinho, porque R$ 4.300 de aporte não é palavra genérica nenhuma.
    if not numero and " " not in t:
        continue
    print(t)
    if numero and "." in t:
        print(t.replace(".", ","))
PYEOF
fi

# identificadores estruturais que nunca devem aparecer
cat >> "$TERMS" <<'EOF'
BEGIN RSA PRIVATE KEY
PLUGGY_CLIENT_SECRET=
EOF

# Termo de uma palavra passa com 4+ caracteres (nome próprio do config);
# frase precisa de 8+, pelo motivo explicado acima.
sort -u "$TERMS" \
  | grep -vE '^.{0,3}$' \
  | awk 'index($0, " ") == 0 || length($0) >= 8' > "$TERMS.u" && mv "$TERMS.u" "$TERMS"

FOUND=0
while IFS= read -r term; do
  hits=$(grep -rniwF -- "$term" "${FILES[@]}" 2>/dev/null | grep -v '^scripts/check-pii.sh:')
  if [ -n "$hits" ]; then
    echo "PII: \"$term\""
    echo "$hits" | head -3 | sed 's/^/      /'
    FOUND=1
  fi
done < "$TERMS"

# extratos e dados fora da fixture de teste
for f in "${FILES[@]}"; do
  case "$f" in
    tests/fixture.ofx) ;;
    *.ofx|data/*|relatorios/*|.fintips-salt|config.yaml)
      echo "ARQUIVO: $f não deveria estar versionado"; FOUND=1 ;;
  esac
done

if [ $FOUND -ne 0 ]; then
  echo
  echo "commit bloqueado — tire esses dados antes de subir."
  exit 1
fi
echo "ok: nenhum dado pessoal nos arquivos do commit (${#FILES[@]} arquivos conferidos)"
