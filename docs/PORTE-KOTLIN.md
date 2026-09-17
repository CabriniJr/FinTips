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

## O harness precisa ser testado também

Depois de portar o leitor OFX, quebrei o fuso padrão de propósito — de -3 para
-2 — esperando ver o harness acusar. **Ele não acusou**, e a explicação vale
mais que o susto: todo `DTPOSTED` do fixture traz `[-3:BRT]` explícito, então o
fuso padrão nunca era exercitado. O harness não estava cego; o fixture é que
não fazia a pergunta.

Duas consequências:

- Nasceu `ouro/datas.json`, isolado do fixture, com data sem fuso, data sem
  hora, fuso fracionário e `dd/mm/aaaa`.
- Virou prática: **a cada módulo portado, quebrar o Kotlin de propósito e
  confirmar que o teste falha nomeando o problema**. Inverter a ordenação das
  transações, por exemplo, derruba três testes de uma vez — esse morde.

Harness é tão bom quanto o dado que ele compara.

## Dependências que o Python não precisava

Duas coisas que são biblioteca padrão no Python e não são no Kotlin:

| O que | Python | Kotlin |
|---|---|---|
| data e hora | `datetime` | `kotlinx-datetime` (única dependência do `commonMain`) |
| SHA-256 | `hashlib` | `expect`/`actual` — `MessageDigest` na JVM e no Android |
| normalização Unicode | `unicodedata` | ainda não resolvido; trava o `norm()` e o `pseudonimo` |

Criptografia entra por `expect`/`actual` em vez de implementação à mão: cada
alvo já traz a sua, e escrever SHA-256 no braço é ruim mesmo quando o algoritmo
é conhecido.

O `pseudonimo` ficou **de fora** desta fatia de propósito. No Python ele é
`"PF:" + digest(_norm(nome), sal, 6)`, e sem o `_norm` o hash de "José" sairia
diferente — a mesma pessoa viraria duas. Portar meio é pior que não portar.

## Ordem dos módulos

Do que não depende de nada para o que depende de tudo. Cada linha só começa
quando a anterior tem ouro fechando.

| # | Módulo | Estado |
|---|---|---|
| 1 | `Dinheiro` — leitura de valor e arredondamento | **pronto** |
| 2 | `Modelo` — Transacao, Conta, Extrato, taxonomias | **pronto** |
| 3 | `LeitorOfx` — SGML e XML, dedup por FITID | **pronto** |
| 4 | `Privacidade` — hash de conta (pseudônimo espera o `norm`) | **parcial** |
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
