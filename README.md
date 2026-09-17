# FinTips

Centraliza extrato e perfil financeiro na sua máquina, e deixa a inteligência
por conta do seu agente. O app guarda, aplica e calcula; o agente investiga,
pergunta e registra; você assina. Um painel local mostra tudo.

```
                       ┌─ painel local (React, 127.0.0.1)
extrato.ofx ─┐         │
             ├─ motor ─┼─ agente Claude (MCP: 28 primitivas)
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
    custos-fixos.yaml  compromissos definidos
    triagem.yaml       o que já foi resolvido ou adiado
    regras-locais.yaml estabelecimentos do seu dia a dia (fora do Git)
    planos.yaml        metas financeiras
    patrimonio.yaml    saldo + investimentos
  relatorios/          análises geradas
```

## Como plugin do Claude

`.claude-plugin/plugin.json` sobe o servidor MCP e carrega a skill `financas`,
que ensina o agente a conduzir a triagem: investigar antes de perguntar, simular
antes de gravar, e dizer o que mudou depois.

As 28 ferramentas se dividem em ler (`analise_completa`, `triagem`, `investigar`,
`listar_taxonomia`, `listar_regras`, `contexto_do_usuario`, `custos_fixos`,
`buscar_transacoes`, `projecao`, `perfil`, `alavancas`), simular
(`simular_regra`) e escrever (`criar_categoria`, `definir_regra`,
`remover_regra`, `definir_custo_fixo`, `remover_custo_fixo`, `gravar_fato`,
`esquecer_fato`, `assinar_perfil`, `esquecer_traco`, `resolver_item`,
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
python tests/test_engine.py && python tests/test_v02.py && \
  python tests/test_v03.py && python tests/test_v04.py
```

## Documentos

- `docs/ARQUITETURA.md` — a fronteira app/agente, contratos, regras, triagem
- `docs/PRIVACIDADE.md` — modelo de ameaça e o que nunca sai da máquina
- `docs/OPEN-FINANCE.md` — por que via agregador e como plugar
