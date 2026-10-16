FROM node:22-alpine
ENV NODE_ENV=production PORT=8787
WORKDIR /app
COPY --chown=node:node package.json context.mjs server.mjs portal.js portal.css ./
USER node
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=3s CMD node -e "fetch('http://127.0.0.1:8787/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.mjs"]
