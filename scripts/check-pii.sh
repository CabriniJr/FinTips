#!/usr/bin/env bash
# Trava de PII antes do commit.
#
# Lê os SEUS dados locais (config.yaml, patrimonio.yaml, data/regras-locais.yaml
# — todos fora do Git) e procura qualquer pedaço deles nos arquivos que estão
# indo para o commit. O script é genérico: ele não contém nenhum dado seu, só
# sabe onde procurá-los.
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

# identificadores estruturais que nunca devem aparecer
cat >> "$TERMS" <<'EOF'
BEGIN RSA PRIVATE KEY
PLUGGY_CLIENT_SECRET=
EOF

sort -u "$TERMS" | grep -vE '^.{0,3}$' > "$TERMS.u" && mv "$TERMS.u" "$TERMS"

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
