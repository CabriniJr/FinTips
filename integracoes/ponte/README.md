# FinTips · ponte MCP para o celular

Esta é a implementação do caminho **ChatGPT/Claude → HTTPS/OAuth → WSS → MCP
Kotlin no Android**. Cada chamada consulta o aparelho. O relay não mantém um
snapshot nem recebe registros completos. O serviço antigo em `../mcp` continua
referência histórica; o entrypoint novo é `relay.mjs`.

**Código e testes não equivalem a contas vinculadas.** A instalação precisa de
uma origem HTTPS real e o usuário precisa concluir a autorização em cada IA.
O APK não tem um domínio externo embutido. A autorização mostra um código,
confirmado no FinTips com revisão de áreas; não exige chave de API do ChatGPT
ou Claude no telefone.

## Implantação

Há duas configurações prontas, sem instância criada por este commit:

- [Blueprint Render](../../render.yaml): usa o URL HTTPS da plataforma e gera
  `PHONE_JOIN_SECRET`. O plano declarado é `free`; confira a disponibilidade na
  sua conta. O botão abaixo abre a configuração para revisar e implantar.
- [Compose + Caddy](compose.yaml): para um servidor seu, com domínio apontando
  para ele e portas 80/443. O Caddy cuida do TLS e do upgrade WebSocket.

[Implantar o blueprint na Render](https://render.com/deploy?repo=https://github.com/CabriniJr/FinTips)

O relay é **uma instância com estado em memória**. Sleep, restart ou deploy
revogam cadastros OAuth e sessões; será necessário reautorizar os chats. Por
isso o blueprint não ativa deploy automático a cada push. Não criar réplicas
sem substituir o coordenador por armazenamento/roteamento apropriados.

### Compose

Copie `.env.example` para `.env` **local e fora do Git**. Preencha `MCP_DOMAIN`
e gere `PHONE_JOIN_SECRET` com `openssl rand -hex 32`. O convite aceita 64
caracteres hex ou 43 base64url, ambos com 256 bits gerados aleatoriamente.

```bash
cd integracoes/ponte
docker compose --env-file .env up --build -d
```

Não montar `data/`, workspace, backups, chaves Android ou diretórios pessoais
no relay. O container copia somente código/estilos e dependências npm. A chave
TLS pertence ao proxy; os volumes do Caddy não guardam registros do FinTips.

### Callbacks

`OAUTH_CALLBACKS` é um array de `{uri, provider}`. Os callbacks padrão foram
conferidos na documentação oficial; confirme os valores exibidos pela sua
configuração, especialmente se a plataforma informar outro caminho:

```json
[
  {"uri":"https://chatgpt.com/connector_platform_oauth_redirect","provider":"chatgpt"},
  {"uri":"https://claude.ai/api/mcp/auth_callback","provider":"claude"}
]
```

A allowlist usa igualdade exata, sem wildcard ou fetch de URLs indicados pelo
cliente. O app aceita somente hosts de retorno ChatGPT/Claude e confere o
provedor antes de aprovar. O issuer é fixado pela origem configurada e volta
na resposta OAuth. Registro dinâmico (DCR), cliente público `none`, PKCE S256,
resource binding, refresh rotativo e revogação estão implementados. CIMD e
client secrets não são anunciados como suportados.

Na Render, `RENDER_EXTERNAL_URL` fornece a origem. Fora dela, configure
`PUBLIC_URL=https://seu-dominio`. Nunca publicar Node HTTP diretamente.
`GET /health` informa disponibilidade sem nomes, tokens ou contexto.

## Vincular de verdade

1. Instale o APK atual; inicie o servidor em **Contexto → Servidor IA local**.
2. Em **Conectar aos chats**, informe a origem HTTPS da ponte e o convite
   privado da configuração da hospedagem. Autorize a conexão de saída.
3. Na configuração de conectores da IA, adicione `${origem}/mcp` e selecione
   OAuth com registro dinâmico. Disponibilidade depende da conta/workspace.
4. Inicie a autorização na IA. A página FinTips mostra um código de 12 letras.
5. No app, confira esse código, o provedor e o host de retorno. Escolha áreas,
   revise o JSON e autorize especificamente esse conector.
6. Volte à janela da IA. Ela conclui o OAuth; o app recebe esse estado. Peça
   para consultar `ler_contexto_revisado`: o app então mostra consulta recebida.
7. Repita para a outra IA, usando **o mesmo endpoint**. As áreas podem ser
   diferentes para cada autorização.

Use o código da autorização que você iniciou na IA. O host de retorno não é
uma identidade de conta verificada: o app não coleta e-mail ou nome da conta.
"Ponte online", "autorização aguardando IA", "OAuth concluído" e "consulta
recebida" são estados distintos. Abrir o site da IA não cria o conector.

## Onde ficam os dados

| Informação | Caminho |
|---|---|
| Registros, livros, tarefas, planos, OFX, títulos e valores | só cliente |
| Projeção reduzida | calculada e validada no celular; transita após consulta autorizada |
| Token do MCP loopback | nunca sai do telefone |
| Convite de implantação | configuração privada do operador; enviado só ao enroll HTTPS |
| Credencial do canal | app em memória; hash no relay |
| Aprovação por áreas | app em memória e metadados OAuth do relay |
| Resposta da consulta | em trânsito; não gravada nem reutilizada pelo relay |

O telefone abre WSS de saída; não precisa de IP público, porta no roteador ou
listener Wi-Fi. O relay aceita respostas só da conexão/dispositivo do pedido,
com nonce e ID de uso único. Valida a allowlist novamente e recusa ampliação
de áreas, argumentos ocultos e texto livre. O cliente guarda suas próprias
aprovações: o relay não consegue inventar um grant e pedir mais áreas.

Fonte inválida, pausa, contexto vencido, aparelho offline, timeout ou revogação
produzem indisponibilidade, **sem structuredContent antigo**. Não inferir meta
não cumprida. Encerrar/revogar no app impede novas respostas imediatamente;
a revogação HTTP é tentada sem bloquear a UI. Falta de rede pode atrasar a
limpeza no relay, mas não permite consultar dados com a aprovação removida.
Mensagens que a IA já recebeu não são apagadas pela revogação.

Nesta alpha, credenciais e aprovações do telefone não são persistidas. Reinício
do processo/atualização preserva os registros, mas exige nova sessão da ponte.
Reconexão de rede dentro do mesmo processo é automática com backoff limitado.
O Android/OEM pode interromper rede/processo; não é disponibilidade permanente.
A TTL do contexto local continua 1 h sem atualização e não é renovada por
consulta remota. O relay não acessa sensores nem preenche tarefas.

## Testes

```bash
npm ci --prefix integracoes/ponte
node --test integracoes/ponte/*.test.mjs
cd kotlin
./gradlew :conector:test :conector:classpathDeTeste
cd ..
python scripts/verificar-ponte-mcp-sdk.py
```

O último comando usa dois clientes OAuth e o SDK MCP real, relay HTTPS/WSS,
cliente Kotlin, sessão Kotlin e socket MCP local. Inclui atualização de fonte
e pausa sem cópia antiga. CA e credenciais são efêmeras, em pipes de teste.
Não simula login nas contas reais; esses aceites são feitos após hospedar e
autorizar pela UI dos provedores. O CI também continua exercitando o serviço
Android em emulador, com permissão de notificação negada e background.

Fontes oficiais consultadas em 15/10/2026:

- [OpenAI: autorização MCP e redirect estável](https://developers.openai.com/plugins/build/auth).
- [Anthropic: OAuth e callback de todas as superfícies](https://github.com/anthropics/claude-plugins-official/blob/8f814f49002ff824e8a9ba43cf96112dc7f5948d/plugins/mcp-server-dev/skills/build-mcp-server/references/auth.md).
