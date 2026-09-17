# Privacidade e PII

Extrato bancário é um dos conjuntos de dados pessoais mais reveladores que
existem: identifica onde você esteve, com quem se relaciona, o que consome e
quanto ganha. O projeto trata isso como requisito, não como recurso.

## Princípios

1. **Local por padrão.** Extratos e YAML canônico ficam em
   `~/Documents/FinTips`. O servidor MCP roda na sua máquina e lê do disco.
2. **Minimização na saída.** O que vai para o modelo é o agregado e o
   necessário; o texto bruto do banco só é gravado se você ligar
   `incluir_memo_bruto: true`.
3. **Identificador direto nunca é persistido em claro.**

| Dado | Como fica no YAML |
|---|---|
| Número da conta | `acct:0a1b2c3d4e` (SHA-256 com sal local) |
| Nome de pessoa física | apelido que você definiu (`pai`) ou `PF:5ceb61` |
| CPF, CNPJ, e-mail, telefone, cartão | removidos do texto (`[cpf]`, `[email]`…) |
| Estabelecimento | em claro no YAML local; nas **regras públicas**, só marcas nacionais |
| FITID | mantido, porque é a chave de deduplicação entre extratos |

O pseudônimo é **estável**: a mesma pessoa gera o mesmo `PF:` em todos os
extratos, então dá para analisar padrão de repasse sem saber de quem se trata.
O sal fica em `.fintips-salt`, só na sua máquina. Apagou o sal, quebrou a
ligação com os extratos anteriores.

## Regras locais vs. regras públicas

`fintips/rules/categories.yaml` é versionado e por isso contém apenas redes
nacionais e códigos de adquirente. Os estabelecimentos do seu bairro vão em
`data/regras-locais.yaml`, que o `.gitignore` barra e o motor funde em memória na
hora de classificar. O motivo é direto: uma lista com a sua padaria, o seu bar e a
loja de trilha onde você compra é um perfil de localização e hábito — o mesmo tipo
de dado que o resto do projeto se dá ao trabalho de pseudonimizar.

## O que nunca deve entrar no repositório

```gitignore
data/
relatorios/
.fintips-salt
config.yaml        # contém apelidos = nomes reais
*.ofx
```

Já está no `.gitignore` do projeto. Se for versionar, versione só o código e as
regras.

## Segredos de conector

Credenciais de Open Finance (clientId/clientSecret) não vão para arquivo do
projeto. Use variável de ambiente ou, melhor, o Gerenciador de Credenciais do
Windows via `keyring`:

```python
import keyring
keyring.set_password("fintips", "PLUGGY_CLIENT_SECRET", "...")
```

O `apiKey` de sessão vive só em memória e expira em 2 horas.

## Modelo de ameaça (o que este projeto resolve e o que não resolve)

| Ameaça | Tratamento |
|---|---|
| Vazamento do YAML (backup, sync, repo público) | sem conta, sem CPF, sem nome de terceiro |
| Conteúdo indo para o modelo | só agregados; memo bruto desligado por padrão |
| Segredo em texto plano | fora do projeto, em env/keyring |
| **Máquina comprometida** | **não resolve** — quem tem seu disco tem o extrato |
| **Reidentificação por contexto** | **parcial** — um `PF:` que recebe R$ 2.000 todo mês é identificável por quem te conhece |

## Dados de terceiros

Pessoas que aparecem no seu extrato não consentiram com nada. Por isso o padrão
é pseudonimizar, o apelido é escolha manual sua, e nenhuma análise do agente
deve produzir perfil de terceiro — o objeto da análise é você.
