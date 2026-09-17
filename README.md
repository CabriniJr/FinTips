# FinTips

Motor financeiro pessoal. Extrato bancário entra, modelo canônico em YAML sai,
e em cima disso: score, planos, detecção de gasto invisível e consultoria de
compra. Tudo roda local; o Claude conversa com o motor por MCP.

```
extrato.ofx ──parser──> YAML canônico ──análise──> score / planos / compras
   (banco)               (fonte de verdade)          (MCP -> agente Claude)
```

## Instalação

```bash
cd FinTips
pip install -e .            # motor + CLI
pip install -e ".[mcp]"     # + servidor MCP
```

## Uso

```bash
fintips init                                   # cria o workspace
fintips ingest "Extrato da Conta - PagBank.ofx"
fintips holdings set --conta 1500 --investido 20000
fintips analyze                                # panorama + score
fintips plan add --id trekking --nome "Trekking" --custo 8000 --data 2027-03-01 --aporte 600
fintips buy --item "Monitor 27 QHD" --preco 1800 --parcelas 10
```

O workspace padrão é `~/Documents/FinTips`. Layout:

```
FinTips/
  config.yaml          perfil, seus nomes em Pix, apelidos de pessoas
  .fintips-salt        segredo local do pseudonimizador (não versionar)
  data/
    extratos/          .ofx originais
    canonico/          .yaml gerado (fonte de verdade)
    planos.yaml        metas financeiras
    patrimonio.yaml    saldo + investimentos
    regras-locais.yaml estabelecimentos do seu dia a dia (fora do Git)
  relatorios/          análises geradas
```

## Como plugin do Claude

`.claude-plugin/plugin.json` sobe o servidor MCP e carrega a skill `financas`.
O agente ganha sete ferramentas: `analise_completa`, `score_financeiro`,
`avaliar_compra`, `listar_planos`, `salvar_plano`, `buscar_transacoes`,
`patrimonio`, `ingerir_extrato`.

Para usar fora do plugin, aponte o MCP direto:

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
  liquidez voltando; Pix entre contas suas é neutro. Sem essa separação, a taxa
  de poupança é ficção.
- **Classificação determinística.** Regras em `fintips/rules/categories.yaml`.
  O mesmo extrato sempre gera o mesmo YAML — o LLM interpreta, não calcula.
- **Conciliação obrigatória.** Se a soma das transações não bate com o saldo
  declarado, o motor avisa antes de qualquer análise.
- **PII fica em casa.** Conta vira hash; pessoa física vira apelido local ou
  pseudônimo estável. As regras públicas só citam marcas nacionais — a padaria da
  sua esquina vai em `data/regras-locais.yaml`, que o `.gitignore` barra, porque a
  lista de onde você compra identifica onde você mora. Ver `docs/PRIVACIDADE.md`
  e o modelo em `fintips/rules/exemplo-regras-locais.yaml`.

## Antes de dar push

```bash
bash scripts/check-pii.sh            # confere o que está staged
cp scripts/check-pii.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

O script lê o seu `config.yaml`, `data/patrimonio.yaml` e `data/regras-locais.yaml`
— todos fora do Git — e procura qualquer pedaço deles nos arquivos do commit. Ele
próprio não guarda nada: só sabe onde os seus dados ficam.

## Testes

```bash
python tests/test_engine.py     # ou: python -m pytest tests -q
```

## Documentos

- `docs/ARQUITETURA.md` — módulos, fluxo de dados, como estender
- `docs/PRIVACIDADE.md` — modelo de ameaça e o que nunca sai da máquina
- `docs/OPEN-FINANCE.md` — por que via agregador e como plugar
