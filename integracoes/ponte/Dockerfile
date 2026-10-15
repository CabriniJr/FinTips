# syntax=docker/dockerfile:1
FROM node:22-alpine
WORKDIR /app
COPY --chmod=0644 integracoes/ponte/package.json integracoes/ponte/package-lock.json ./integracoes/ponte/
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --prefix integracoes/ponte --omit=dev --ignore-scripts --strict-ssl=true && npm cache clean --force
COPY --chmod=0644 integracoes/ponte/relay.mjs integracoes/ponte/portal.js ./integracoes/ponte/
COPY --chmod=0644 integracoes/mcp/context.mjs integracoes/mcp/portal.css ./integracoes/mcp/
RUN chmod 0755 /app/integracoes /app/integracoes/ponte /app/integracoes/mcp
USER node
ENV NODE_ENV=production PORT=8787
EXPOSE 8787
CMD ["node", "integracoes/ponte/relay.mjs"]
