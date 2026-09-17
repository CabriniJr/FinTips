#!/usr/bin/env bash
# FinTips em Docker, num comando.
#
# O que este script resolve, e por que ele existe em vez de um parágrafo no
# README: as três coisas que dão errado ao rodar isto em Linux são sempre as
# mesmas — o volume sai com dono root, o `~` do caminho não é expandido pelo
# compose, e o painel acaba publicado em 0.0.0.0 sem ninguém perceber. Todas
# são decididas aqui, uma vez.
#
#   ./scripts/fintips-docker.sh setup          prepara .env, workspace e imagem
#   ./scripts/fintips-docker.sh up             sobe o painel
#   ./scripts/fintips-docker.sh down           para tudo
#   ./scripts/fintips-docker.sh logs           acompanha o painel
#   ./scripts/fintips-docker.sh importar a.ofx copia o extrato e ingere
#   ./scripts/fintips-docker.sh mcp-config     a config para o cliente do agente
#   ./scripts/fintips-docker.sh <qualquer>     repassa para o CLI do fintips

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

ENV_FILE="$RAIZ/.env"
WORKSPACE_PADRAO="$HOME/Documents/FinTips"

cor() { printf '\033[1m%s\033[0m\n' "$*"; }
erro() { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    erro "docker compose não encontrado. Instale o plugin: https://docs.docker.com/compose/install/"
  fi
}

exige_docker() {
  command -v docker >/dev/null 2>&1 || erro "docker não está instalado."
  docker info >/dev/null 2>&1 || erro \
    "o daemon do Docker não responde. Suba com 'sudo systemctl start docker', ou
adicione seu usuário ao grupo docker: sudo usermod -aG docker \$USER (e relogue)."
}

carrega_env() {
  [[ -f "$ENV_FILE" ]] || erro "rode primeiro: ./scripts/fintips-docker.sh setup"
  set -a; # shellcheck disable=SC1090
  source "$ENV_FILE"; set +a
}

cmd_setup() {
  exige_docker
  local workspace="${1:-$WORKSPACE_PADRAO}"
  mkdir -p "$workspace"

  # O caminho vai absoluto para o .env porque o compose não expande `~`.
  cat > "$ENV_FILE" <<EOF
# gerado por scripts/fintips-docker.sh — não versionar
FINTIPS_UID=$(id -u)
FINTIPS_GID=$(id -g)
FINTIPS_WORKSPACE=$workspace
FINTIPS_PORTA=${FINTIPS_PORTA:-8420}
EOF
  cor "workspace: $workspace"
  cor "uid/gid:   $(id -u):$(id -g)  (os arquivos gerados serão seus)"

  cor "construindo a imagem…"
  compose build painel

  cor "inicializando o workspace…"
  compose run --rm cli init

  cat <<EOF

Pronto. Próximos passos:

  1. Coloque um extrato .ofx em $workspace/data/extratos/
  2. ./scripts/fintips-docker.sh importar caminho/do/extrato.ofx
  3. ./scripts/fintips-docker.sh up      → http://127.0.0.1:${FINTIPS_PORTA:-8420}
  4. ./scripts/fintips-docker.sh mcp-config   para conectar o agente

EOF
}

cmd_up() {
  exige_docker; carrega_env
  compose up -d painel
  cor "painel em http://127.0.0.1:${FINTIPS_PORTA:-8420}  (só nesta máquina)"
  cor "logs: ./scripts/fintips-docker.sh logs"
}

cmd_down() { exige_docker; compose down; }
cmd_logs() { exige_docker; compose logs -f painel; }

cmd_importar() {
  exige_docker; carrega_env
  local arquivo="${1:-}"
  [[ -n "$arquivo" ]] || erro "uso: ./scripts/fintips-docker.sh importar extrato.ofx"
  [[ -f "$arquivo" ]] || erro "arquivo não encontrado: $arquivo"

  local destino="$FINTIPS_WORKSPACE/data/extratos"
  mkdir -p "$destino"
  cp "$arquivo" "$destino/"
  local nome; nome="$(basename "$arquivo")"
  cor "copiado para $destino/$nome"
  compose run --rm cli ingest "/dados/data/extratos/$nome"
  cor "agora rode: ./scripts/fintips-docker.sh triagem"
}

cmd_mcp_config() {
  carrega_env
  cat <<EOF
Cole isto na configuração de MCP do seu cliente (Claude Desktop, Claude Code):

{
  "mcpServers": {
    "fintips": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "$FINTIPS_WORKSPACE:/dados",
        "-e", "FINTIPS_ROOT=/dados",
        "--user", "$(id -u):$(id -g)",
        "fintips:local",
        "python", "-m", "fintips.mcp_server"
      ]
    }
  }
}

O container do MCP sobe e morre a cada sessão do agente, e enxerga o mesmo
workspace do painel — o que o agente gravar conversando aparece na tela, e o
que você decidir na tela o agente lê na próxima pergunta.
EOF
}

case "${1:-ajuda}" in
  setup)       shift; cmd_setup "$@" ;;
  up)          shift; cmd_up "$@" ;;
  down)        shift; cmd_down "$@" ;;
  logs)        shift; cmd_logs "$@" ;;
  importar)    shift; cmd_importar "$@" ;;
  mcp-config)  shift; cmd_mcp_config "$@" ;;
  ajuda|-h|--help)
    awk 'NR==1{next} /^#/{sub(/^# ?/, ""); print; next} {exit}' "${BASH_SOURCE[0]}" ;;
  *)
    exige_docker; carrega_env
    compose run --rm cli "$@" ;;
esac
