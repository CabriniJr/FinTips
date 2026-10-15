# FinTips MCP · contexto revisado

**Piloto remoto anterior (preview 4).** A partir da preview 5, o produto usa
[servidor Kotlin no celular](../../docs/SERVIDOR-MCP-LOCAL.md). Este serviço
Node fica como referência testada; não é dependência nem destino automático
dos registros do APK atual. A ponte até os chats permanece pendente.

Um endpoint **`/mcp`** para ChatGPT e Claude. O motor roda no Android; este
serviço consulta somente um snapshot mínimo aprovado no aparelho. Não importa
`fintips.mcp_server`, não monta um workspace e não recebe OFX, arquivos do
Librera, títulos, nomes, valores financeiros ou credenciais de fontes.

**Estado:** piloto implementado e testado localmente com o SDK MCP Python.
Nenhum domínio está configurado no APK. Hospedagem HTTPS e conexão real nas
contas ChatGPT/Claude ainda precisam ser feitas; não há sincronização contínua.

## Executar

Node **22+**, sem dependências npm. A porta HTTP é interna; publique atrás de
um proxy TLS que encaminhe apenas o domínio escolhido. Configure os callbacks
**exatos** exibidos pela configuração dos seus clientes de IA:

```bash
export PUBLIC_URL=https://mcp.seu-dominio.example
export OAUTH_REDIRECT_URIS=https://callback-exato-do-chatgpt.example/retorno,https://callback-exato-do-claude.example/retorno
node integracoes/mcp/server.mjs
```

Os domínios `.example` acima são exemplos; não são endpoints para copiar para
a conta. `PUBLIC_URL` precisa ser uma origem HTTPS sem caminho, query,
credenciais ou fragmento. O recurso OAuth é `${PUBLIC_URL}/mcp`.

Há um [Dockerfile](Dockerfile):

```bash
docker build -t fintips-mcp integracoes/mcp
docker run --rm --read-only --cap-drop=ALL --security-opt=no-new-privileges \
  -p 127.0.0.1:8787:8787 \
  -e PUBLIC_URL -e OAUTH_REDIRECT_URIS fintips-mcp
```

O proxy deve manter HTTPS, limitar corpos a 16 KiB e omitir logs de corpos,
headers Authorization e queries OAuth. Não montar `data/`, workspace, backups
ou chaves do Android no container. Não embutir token de hospedagem no APK.
`GET /health` devolve apenas disponibilidade, sem dados de pessoas.

## Vincular pelo Android

1. Na configuração do conector personalizado da IA, use `https://seu-dominio/mcp`.
   Escolha OAuth com **registro automático (DCR)** e cliente público (`none`).
   CIMD e client secrets não são implementados neste piloto. Disponibilidade
   e políticas dependem da conta/workspace.
2. Inicie a autorização. Confira o domínio do servidor; a página mostra um
   código de 12 caracteres e o host de retorno registrado. Expira em 5 minutos.
3. No FinTips → Contexto → Conectar IA, informe a mesma origem e o código.
   Escolha áreas, revise o JSON integral e marque a confirmação.
4. Continue no navegador. Confira novamente o domínio e autorize o snapshot.
   Volte à janela da IA: o OAuth redireciona ao callback registrado.
5. Habilite a ferramenta `ler_contexto_revisado` na conversa. Ela só lê o
   snapshot deste vínculo. Teste separadamente no ChatGPT e no Claude.

O app Android não consegue confirmar a conclusão no navegador. A lista local
é de **tentativas**, não de contas conectadas. App fechado ou sem rede não
atualiza o snapshot. A IA pode consultar a cópia já autorizada até ela vencer.

## O que atravessa

| Escopo escolhido | Campos permitidos | Omissões |
|---|---|---|
| Rotina | seis áreas fixas, evidência `sem_metas`, `sem_registro`, `parcial` ou `completa`; origem usuário | tarefas, contagens, datas, horários, IDs e textos |
| Planos | estado por área: sem planos, em andamento, concluídos ou misto | títulos, motivos, próximos passos, prazos, valores |
| Leitura | conjunto de estados do pacing e fontes usuário/Librera | títulos, perfil, posição, trechos, arquivos e datas |

Nenhum escopo começa selecionado. Ausência de registro **não prova falha**.
Não há inferência de motivação, conclusão automática de tarefas ou score novo.
Indicadores reduzidos continuam sendo contexto pessoal; não são anunciados
como anônimos. O navegador e a IA escolhidos têm suas próprias políticas.

A mesma representação é conferida na saída Kotlin e na entrada do serviço.
Chaves extras, texto fora dos vocabulários, duplicatas e ordem ambígua são
recusados. O ouro Python é aceito também pelo validador JavaScript.

## Autorização e retenção

- OAuth authorization code + PKCE **S256**, scope único `context:read`,
  metadados RFC 8414/9728 e issuer `iss` nas respostas bem-sucedidas.
- Redirects por igualdade exata com allowlist do operador. Nenhum callback
  fornecido na requisição é aceito sem registro. Não há fetch de URLs externas.
- Códigos de autorização: uso único, 2 minutos após aprovação. Tokens de acesso:
  até 15 minutos. Refresh rotaciona; reutilizá-lo revoga a família.
- Snapshots: até **1 hora** desde a aprovação, inclusive após refresh. Um timer
  elimina o contexto ao vencer; toda consulta verifica a validade novamente.
- Revogar pelo app abre o navegador com a chave local; a confirmação elimina
  snapshot, tokens e códigos associados. A chave de revogação não é exposta à
  IA. Somente hashes dos tokens de acesso/refresh/revogação são guardados.
- Nenhuma gravação em disco ou log de pedidos. Códigos de pareamento são
  aleatórios (60 bits); polls usam segredo independente de 256 bits.
- Descoberta/initialize são públicos e não contêm contexto. `tools/call` com
  dados exige bearer autorizado; argumentos extras e escrita são recusados.
- Browser POST exige Origin da própria origem; não há CORS. CSP limita scripts,
  estilos e conexão à própria origem e bloqueia frames. Payload chega em
  fragmento; o portal o remove do histórico antes de ler, sem request HTTP com
  o fragmento. A confirmação é que faz o POST do snapshot ao serviço.

A chave de revogação fica no armazenamento privado do WebView. Ela é enviada
somente ao servidor escolhido na confirmação, que guarda seu hash. Tokens
OAuth ficam no serviço e no cliente de IA, como exigido pelo protocolo;
credenciais de fontes como bancos, Librera ou TotalPass nunca entram aqui.

**Uma instância, estado efêmero:** reinício/deploy revoga tudo, inclusive os
registros DCR. Pode ser necessário remover e adicionar o conector na IA após
reiniciar. Não suporta múltiplas réplicas, recuperação de sessão ou uso de
produção com disponibilidade contínua. Há limites globais de requisições,
clientes, autorizações e tokens; este piloto não oferece isolamento de quota
por cliente. Compartilhe o endereço apenas com participantes do piloto.

A revogação não apaga mensagens que a IA já recebeu. Backups, extensões e
sincronização do próprio navegador são independentes do armazenamento do app.

## Verificar

```bash
node --test integracoes/mcp/*.test.mjs
pip install -e '.[mcp]'
python scripts/verificar-mcp-sdk.py
```

Cobertura: contrato Python/Kotlin/JS; rejeição de PII; PKCE, audience, cliente,
redirect, uso único, refresh/replay, isolamento, expiração, revogação, Origin,
limite de corpo e handshake/chamada via SDK real. São testes locais; não
comprovam hospedagem HTTPS nem autenticação nas contas dos provedores.

Referências oficiais consultadas em 15/10/2026:
[ChatGPT: OAuth MCP](https://developers.openai.com/plugins/build/auth) ·
[Claude: conectores MCP remotos](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).
Copie o callback da tela da sua conexão, em vez de adivinhar um caminho.
