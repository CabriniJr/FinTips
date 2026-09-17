# FinTips em container.
#
# Duas coisas guiaram este arquivo, e as duas são consequência do que o FinTips
# é: um app que lê o seu extrato bancário e roda na sua máquina.
#
# 1. **A porta não sai do localhost.** Dentro do container o uvicorn escuta em
#    0.0.0.0 porque não há alternativa — é assim que o Docker consegue publicar
#    a porta. Quem limita o alcance é o mapeamento no compose
#    (`127.0.0.1:8420:8420`), que impede a máquina da rede ao lado de abrir o
#    seu painel. Se você trocar aquilo por `8420:8420`, estará servindo o seu
#    extrato para a rede inteira. Não troque.
#
# 2. **Os arquivos são seus, não do root.** O workspace é um volume montado da
#    sua casa. Se o processo rodar como root, os YAML gerados ficam com dono
#    root e você não consegue editá-los sem sudo. Por isso o UID/GID entram
#    como argumento de build.

# ---------------------------------------------------------------- estágio 1
# O painel é compilado aqui para a imagem final não precisar de Node.
FROM node:22-alpine AS web

WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/ ./
# vite.config.js manda o build para ../fintips/web — ou seja, /app/fintips/web
RUN npm run build


# ---------------------------------------------------------------- estágio 2
FROM python:3.12-slim AS runtime

ARG UID=1000
ARG GID=1000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FINTIPS_ROOT=/dados

# Usuário com o mesmo UID de quem está do lado de fora: o que o container
# escrever no volume sai com o seu dono.
#
# O `if` existe porque UID/GID vindos de fora podem já estar ocupados na
# imagem base. Engolir o erro com `|| true` faria o build quebrar lá na frente,
# no USER, com uma mensagem que não diz nada sobre a causa.
RUN set -eux; \
    if ! getent group "${GID}" >/dev/null; then groupadd --gid "${GID}" fintips; fi; \
    if ! getent passwd "${UID}" >/dev/null; then \
        useradd --uid "${UID}" --gid "${GID}" --create-home --shell /bin/bash fintips; \
    fi; \
    mkdir -p /dados; \
    chown -R "${UID}:${GID}" /dados

WORKDIR /app

# As dependências primeiro, em camada própria: mexer no código não reinstala
# o FastAPI inteiro a cada build.
COPY pyproject.toml README.md LICENSE ./
COPY fintips/__init__.py ./fintips/
RUN pip install --no-cache-dir ".[tudo]"

COPY fintips/ ./fintips/
COPY skills/ ./skills/
COPY scripts/ ./scripts/
COPY .claude-plugin/ ./.claude-plugin/

# O painel compilado no estágio anterior entra por cima do que veio do repo,
# garantindo que a imagem sirva o build feito agora e não um artefato velho.
COPY --from=web /app/fintips/web ./fintips/web

# Editável no fim: substitui a instalação parcial do passo das dependências
# (que existia só para cachear fastapi/uvicorn/mcp) pelo código completo.
RUN pip install --no-cache-dir --no-deps -e . && chown -R "${UID}:${GID}" /app

# Numérico, não pelo nome: se o UID já pertencia a outro usuário da imagem
# base, o nome `fintips` não existe — o número sempre funciona.
USER ${UID}:${GID}
VOLUME ["/dados"]
EXPOSE 8420

# Sem `--no-browser` o app tenta abrir um navegador que não existe aqui dentro.
CMD ["fintips", "--root", "/dados", "serve", "--host", "0.0.0.0", "--port", "8420", "--no-browser"]
