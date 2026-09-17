# A porta para Kotlin

O alvo é Kotlin Multiplatform com Android: o motor vira `commonMain`,
compartilhado entre o servidor, o desktop e o app de celular — que é onde app
de finança pessoal de fato vive. A UI vai para Compose Multiplatform depois que
o motor estiver de pé.

Enquanto isso, **o Python continua sendo o produto que funciona**. Trocar antes
de o Kotlin reproduzir o comportamento seria trocar um motor com 75 testes por
um que ninguém conferiu.

## A regra que governa a porta

> Porta replica. Não corrige, não melhora, não simplifica.

Isso já valeu a pena antes mesmo do primeiro módulo ficar pronto. Ao portar a
leitura de valor, eu tinha "melhorado" a regra de separador: `"1.234"` viraria
mil duzentos e trinta e quatro, que é o que qualquer brasileiro lê. O motor
Python lê **um real e vinte e três**, porque faz `Decimal("1.234")`. A melhoria
teria entrado escondida numa porta de 7 mil linhas e aparecido meses depois
como um número estranho num extrato.

Se a regra é ruim — e pode ser —, ela muda nos dois motores ao mesmo tempo, com
teste, num commit que só faz isso.

## O harness diferencial

`scripts/gerar-ouro.py` roda o motor Python e grava a resposta em
`kotlin/motor/src/jvmTest/resources/ouro/*.json`. Os testes Kotlin cobram
exatamente aquilo e, quando divergem, nomeiam o caso:

```
leitura de valor divergiu do motor Python:
  "1.234" → python 123 (1.234), kotlin 123400
```

Duas regras sobre o ouro:

- **É gerado, nunca escrito à mão.** Ouro escrito à mão é a opinião de quem
  escreveu sobre o que o motor deveria fazer; ouro gerado é o que ele faz. A
  diferença aparece nos casos esquisitos, que são os que importam.
- **Precisa cobrir fronteira.** Um teste `o_ouro_cobre_os_casos_de_fronteira`
  falha se o ouro perder o empate de arredondamento, a entrada vazia ou o
  negativo em parênteses. Harness que só testa o fácil passa sempre e não
  protege nada.

## Dinheiro: centavos em Long

A primeira decisão, e a que mais podia dar errado em silêncio.

| Opção | Por que não / por que sim |
|---|---|
| `Double` | `0.1 + 0.2` não é `0.3`. Motor que soma extrato não erra centavo por representação. |
| `BigDecimal` | Semântica idêntica ao Python, mas só existe na JVM — fecharia o iOS antes de a conversa acontecer. |
| **`Long` de centavos** | Exato, em todos os alvos. E onde o Python divide (média, custo por mês) ele faz **uma** divisão e arredonda logo em seguida: divisão inteira meio-para-o-par dá o mesmo resultado. |

Onde o Python usa `float` de propósito — volatilidade, desvio padrão,
percentual — o Kotlin usa `Double` também, para o harness comparar maçã com
maçã.

## Ordem dos módulos

Do que não depende de nada para o que depende de tudo. Cada linha só começa
quando a anterior tem ouro fechando.

| # | Módulo | Estado |
|---|---|---|
| 1 | `Dinheiro` — leitura de valor e arredondamento | **pronto**, 14 testes |
| 2 | `Modelo` — Transacao, Conta, Extrato, taxonomias | a fazer |
| 3 | `LeitorOfx` — SGML e XML, dedup por FITID | a fazer |
| 4 | `Privacidade` — hash de conta, pseudônimo | a fazer |
| 5 | `Contratos` — Proveniencia, autoridade, Causa, Regra | a fazer |
| 6 | `Classificacao` — regras determinísticas e cobertura | a fazer |
| 7 | `Analise` — baseline, meses, recorrências, invisível | a fazer |
| 8 | `Score`, `Projecao`, `Planos`, `Compras` | a fazer |
| 9 | `Perfil`, `Causas`, `Alavancas`, `Triagem`, `Dossie` | a fazer |
| 10 | Persistência YAML (`expect`/`actual` por alvo) | a fazer |
| 11 | Servidor MCP (SDK Kotlin) e HTTP (Ktor) | a fazer |
| 12 | Compose Multiplatform no lugar do painel React | a fazer |

O painel React continua funcionando durante tudo isso, porque fala JSON e não
sabe quem serve.

## Rodar

```bash
cd kotlin && gradle :motor:jvmTest        # motor + harness diferencial
python3 scripts/gerar-ouro.py             # regrava o ouro a partir do Python
```

O alvo Android está desligado por propriedade (`fintips.android=false`) porque
exige o SDK instalado — sem ele o Gradle nem configura o projeto. Ligue ao
abrir no Android Studio; o `commonMain` não muda, é só mais um alvo lendo o
mesmo código.
