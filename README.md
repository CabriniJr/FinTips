# FinTips

Centraliza extrato e perfil financeiro na sua máquina, e deixa a inteligência
por conta do seu agente. O app guarda, aplica e calcula; o agente investiga,
pergunta e registra; você assina. Um painel local mostra tudo.

```
                       ┌─ painel local (React, 127.0.0.1)
extrato.ofx ─┐         │
             ├─ motor ─┼─ agente Claude (MCP: 33 primitivas + 2 recursos)
Open Finance ┘         │
  (Pluggy)             └─ YAML no seu disco (fonte de verdade)
```

Nada sai da máquina: sem conta, sem servidor, sem telemetria. O agente recebe
agregados, nunca o extrato bruto.

## A ideia

Um app de finanças que decide por você erra de um jeito específico: ele acha que
"transporte" é uma coisa só, que mercado é sempre essencial, que gasto
pulverizado é desperdício. Nenhuma dessas afirmações é verdade sobre uma pessoa
concreta — são médias disfarçadas de conselho.

Aqui a inversão é explícita: **nada é verdade sem proveniência**.

| Origem | Vale como verdade? |
|---|---|
| `heuristica` — lista embutida no pacote | não, só ranqueia o que olhar primeiro |
| `importacao` — derivado dos seus dados | não |
| `agente` — conclusão do agente, após conversar | sim |
| `usuario` — você afirmou | sim, e vence tudo |

O painel mostra, o tempo todo, **quanto do seu dinheiro está classificado por
decisão e quanto ainda é palpite**. Começa em 0%.

## O que ele faz

- **Gera objetos a partir da importação**: agrupa variações do mesmo
  estabelecimento (`Gelato Roma-LJ0046` e `-LJ0084` viram um só; `EMV CMT*144318981`
  vira `EMV CMT`), classifica cadência e mede presença mensal.
- **Triagem periódica**: a cada extrato novo, recalcula o que está em aberto —
  contraparte sem categoria, dinheiro classificado só por palpite, candidato a
  compromisso, custo fixo que derivou, contexto faltando — **ordenado pelo custo
  mensal em reais de deixar assim**.
- **Motor de regras genérico**: o agente escreve condições que descrevem
  comportamento (`uber` + `sábado e domingo` → lazer), simula antes de gravar, e
  a aplicação é determinística e reproduzível.
- **Custo fixo é afirmação, não detecção**: o motor levanta candidatos; só vira
  compromisso o que alguém confirma, com a natureza que fizer sentido (contratual,
  rotina, sazonal, reembolsado…).
- **Contexto híbrido**: núcleo demarcado para o que é universal (moradia, cartão,
  renda, reserva) + chave livre para o que é só seu
  (`transporte.reembolsado_pela_empresa`).
- **Guarda o porquê, não só o quanto.** Uma causa liga um padrão de gasto ao
  motivo dele, nas palavras da pessoa, mais a atitude tomada — inclusive
  `aceitar`, que é decisão legítima e tira o gasto da lista de culpa. Causa
  nunca é derivada: duas pessoas com o mesmo extrato de delivery podem estar
  com jornada dupla ou com tédio de domingo, e só perguntar distingue.
- **Monta o perfil em cinco eixos independentes** (fase, renda, custo, consumo,
  constância). O catálogo casa arquétipos contra os seus números e devolve
  isso como **palpite, com a evidência anexada** — perfil mesmo só existe
  quando o agente conclui depois de conversar, ou quando você afirma. A tela
  mostra quanto do perfil já é decisão: começa em 0%, igual à classificação.
- **Projeta caixa** em 12 meses com cenários, e diz o mês em que cada meta fecha.
- **Calcula alavancas**: quanto falta de sobra para a próxima faixa de score, o
  que o gasto invisível custa em doze meses, quantos meses a reserva antecipa
  se ele sair do variável, que mês cada plano fecha se for priorizado. Cada uma
  é o motor rodado de novo, não uma estimativa paralela — e nenhuma é conselho.
  A frase que interpreta o número é do agente, que conversou com você.
- **Avalia intenção de compra** contra reserva, planos e o seu histórico de
  arrependimento.

## A jornada, em três passos

```
1. IMPORTAR            2. CONVERSAR                 3. VIVER COM ISSO
extrato .ofx      →    o agente investiga,     →    "posso comprar isso?"
(futuro: Open          pergunta e registra          "quando fecho a viagem?"
 Finance)              com evidência                "onde estou perdendo?"
```

O extrato entra e vira modelo canônico. **Nada é concluído aí** — as três
coberturas (classificação, perfil, causas) começam em 0%. O perfil nasce na
conversa com o agente, que investiga antes de perguntar e grava cada decisão
com `porque`. Daí em diante o painel centraliza o que foi acumulando, e as
perguntas do dia a dia passam a ter contra o que ser respondidas.

Detalhe de cada etapa, com os buracos que ainda existem, em `docs/JORNADA.md`.

## Rodar com Docker (Linux)

Três comandos, do zero ao painel:

```bash
./scripts/fintips-docker.sh setup          # .env com o seu UID, workspace e imagem
./scripts/fintips-docker.sh importar extrato.ofx
./scripts/fintips-docker.sh up             # http://127.0.0.1:8420
```

O `setup` resolve as três coisas que dão errado ao rodar isto em Linux: o
volume sair com dono root (ele passa o seu UID/GID para o build), o `~` do
caminho não ser expandido pelo compose (ele grava o caminho absoluto) e o
painel acabar publicado na rede (o mapeamento é `127.0.0.1:8420:8420`, e
trocar aquilo por `8420:8420` serve o seu extrato para a rede inteira).

Qualquer comando do CLI passa pelo mesmo script:

```bash
./scripts/fintips-docker.sh triagem
./scripts/fintips-docker.sh perfil
./scripts/fintips-docker.sh alavancas
./scripts/fintips-docker.sh down
```

Para conectar o agente ao mesmo workspace:

```bash
./scripts/fintips-docker.sh mcp-config     # imprime o JSON do cliente MCP
```

Seus dados ficam no workspace montado (`~/Documents/FinTips` por padrão), nunca
dentro da imagem: o container é descartável, o workspace não.

## Instalação

```bash
pip install -e ".[tudo]"    # motor + CLI + painel + servidor MCP
```

O painel já vem compilado dentro do pacote: **não é preciso ter Node para usar**.
Node só entra para desenvolver o frontend (`cd web && npm install && npm run dev`).

## Uso

```bash
fintips init
fintips ingest "Extrato da Conta - PagBank.ofx"
fintips holdings set --conta 1500 --investido 20000
fintips analyze                                # panorama + score
fintips triagem                                # o que está em aberto
fintips categorias --criar transporte-trabalho --nome "Transporte — trabalho"
fintips contexto --gravar moradia.situacao --valor com_familia
fintips perfil                                 # sugestões, assinaturas, cobertura
fintips perfil --assinar renda --arquetipo variavel --porque "sou PJ"
fintips alavancas                              # o que muda o número, e quanto
fintips serve                                  # painel em http://127.0.0.1:8420
```

O workspace padrão é `~/Documents/FinTips`:

```
FinTips/
  config.yaml          seus nomes em Pix, apelidos de pessoas
  .fintips-salt        segredo local do pseudonimizador (não versionar)
  data/
    extratos/          .ofx originais
    canonico/          .yaml gerado (fonte de verdade)
    taxonomia.yaml     suas categorias, com quem as criou
    regras.yaml        regras de classificação com proveniência
    contexto.yaml      fatos sobre você, com evidência
    perfil.yaml        traços assinados, um por eixo
    causas.yaml        por que o dinheiro sai, e o que se decidiu
    custos-fixos.yaml  compromissos definidos
    triagem.yaml       o que já foi resolvido ou adiado
    regras-locais.yaml estabelecimentos do seu dia a dia (fora do Git)
    planos.yaml        metas financeiras
    patrimonio.yaml    saldo + investimentos
  relatorios/          análises geradas
    dossie.json        briefing do agente + correlações (derivado)
    observacoes.jsonl  uma linha por observação, vira dataframe (derivado)
```

## Como plugin do Claude

`.claude-plugin/plugin.json` sobe o servidor MCP e carrega a skill `financas`,
que ensina o agente a conduzir a triagem: investigar antes de perguntar, simular
antes de gravar, e dizer o que mudou depois.

O agente chega pré-carregado: os recursos `fintips://briefing` (quem é a
pessoa, causas ativas, o que está aberto) e `fintips://spec` (a regra de
proveniência e os vocabulários) o cliente lê sozinho, sem gastar um turno. Os
prompts `conversa_de_compra` e `entender_um_gasto` trazem roteiro pronto.

As 33 ferramentas se dividem em ler (`analise_completa`, `triagem`, `investigar`,
`listar_taxonomia`, `listar_regras`, `contexto_do_usuario`, `custos_fixos`,
`buscar_transacoes`, `projecao`, `perfil`, `alavancas`, `briefing`,
`listar_causas`), simular
(`simular_regra`) e escrever (`criar_categoria`, `definir_regra`,
`remover_regra`, `definir_custo_fixo`, `remover_custo_fixo`, `gravar_fato`,
`esquecer_fato`, `assinar_perfil`, `esquecer_traco`, `gravar_causa`,
`decidir_causa`, `esquecer_causa`, `resolver_item`,
`salvar_plano`, `avaliar_compra`, `patrimonio`, `ingerir_extrato`).

Toda escrita exige `porque` — é o que torna a decisão auditável depois.

Para usar fora do plugin:

```json
{
  "mcpServers": {
    "fintips": {
      "command": "python",
      "args": ["-m", "fintips.mcp_server", "--root", "C:/Users/<voce>/Documents/FinTips"]
    }
  }
}
```

## Decisões que sustentam o resto

- **Aporte não é despesa.** Mandar dinheiro para o CDB é poupança; resgate é
  liquidez voltando; Pix entre contas suas é neutro. Sem isso, a taxa de poupança
  é ficção.
- **Conciliação obrigatória.** Se a soma das transações não bate com o saldo
  declarado, o motor avisa antes de qualquer análise.
- **O LLM não calcula.** `report.analyze()` é a única fonte do contexto,
  consumida igualmente pelo painel, pelo agente e pela triagem.
- **O app não diz quem você é.** Arquétipo casado por número é `importacao` —
  palpite com evidência, que serve para começar a conversa. Um extrato com
  sobra alta pode ser disciplina ou um mês passado na casa da mãe; o extrato
  não distingue as duas coisas, e fingir que distingue é o erro que este
  projeto existe para não cometer.
- **Alavanca não é dica.** O motor entrega a régua — número e efeito
  recalculado. O conselho depende de saber se aquele gasto é a única coisa boa
  da semana da pessoa, e isso o extrato não conta.
- **Resumo com ponteiro.** O briefing que o agente carrega é enxuto, mas cada
  bloco diz qual ferramenta devolve o detalhe. Resumir escondendo é pior que
  não resumir: o agente passa a supor.
- **PII fica em casa.** Conta vira hash; pessoa física vira apelido local ou
  pseudônimo estável. As regras públicas só citam marcas nacionais — a padaria da
  sua esquina vai em `data/regras-locais.yaml`, fora do Git, porque a lista de
  onde você compra identifica onde você mora. Ver `docs/PRIVACIDADE.md`.

## Antes de dar push

```bash
bash scripts/check-pii.sh --all
cp scripts/check-pii.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

No Windows, um comando só faz tudo (trava, commit, rebase e push):

```powershell
.\scripts\publicar.ps1 "mensagem do commit"
```

O script lê o seu `config.yaml`, `data/patrimonio.yaml` e `data/regras-locais.yaml`
— todos fora do Git — e procura qualquer pedaço deles nos arquivos do commit. Ele
próprio não guarda nada: só sabe onde os seus dados ficam.

## Testes

```bash
for t in tests/test_*.py; do python "$t" || break; done
```

## Documentos

- `docs/JORNADA.md` — o que a pessoa vive: importar, conversar, viver com isso
- `docs/ARQUITETURA.md` — a fronteira app/agente, contratos, regras, triagem
- `docs/PRIVACIDADE.md` — modelo de ameaça e o que nunca sai da máquina
- `docs/OPEN-FINANCE.md` — por que via agregador e como plugar
