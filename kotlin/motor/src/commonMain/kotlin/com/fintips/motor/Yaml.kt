package com.fintips.motor

import kotlin.math.abs

/**
 * Escreve o YAML que o motor Python lê — caractere por caractere.
 *
 * Este é o ponto do porte em que um erro não aparece como número errado, e sim
 * como **arquivo estranho semanas depois**. Os dois motores compartilham os
 * mesmos arquivos em `data/`; se o Kotlin gravar algo que o Python leia diferente,
 * quem migrar perde o histórico — e nada no caminho avisa.
 *
 * O alvo é o que o Python produz com
 * `yaml.safe_dump(allow_unicode=True, sort_keys=False)`, que é um subconjunto
 * pequeno e bem definido: mapas e listas em bloco, escalares simples, ordem de
 * inserção preservada, acento sem escape.
 *
 * ## As regras que ninguém adivinha
 *
 * **Citar não é questão de gosto.** Um texto puro que o YAML 1.1 resolveria
 * como outro tipo precisa de aspas, ou volta da leitura como outra coisa. Daí
 * o arquivo canônico ter `hora: '10:00'` e `hora: 08:00` lado a lado: `10:00`
 * casa o padrão sexagesimal e viraria o inteiro 600; `08:00` começa com zero,
 * não casa, e fica puro.
 *
 * **Indicador só vale na posição certa.** `-a` é texto puro e `- a` precisa de
 * aspas; `a:b` é puro e `a: b` não é; `,a` precisa e `a,b` não.
 *
 * **Sequência dentro de mapa não indenta.** `transacoes:` e o `- id:` seguinte
 * começam na mesma coluna.
 *
 * O que este emissor não sabe fazer, ele **recusa em voz alta** em vez de
 * inventar: é preferível uma exceção a um arquivo que o outro motor lê torto.
 */
object Yaml {

    // ------------------------------------------------------------ documento

    /** Emite o documento inteiro, com a quebra de linha final que o Python põe. */
    fun emitir(valor: Any?): String {
        val sb = StringBuilder()
        when (valor) {
            is Map<*, *> -> {
                if (valor.isEmpty()) return "{}\n"
                escreverMapa(sb, valor, 0)
            }
            is List<*> -> {
                if (valor.isEmpty()) return "[]\n"
                escreverLista(sb, valor, 0)
            }
            else -> {
                sb.append(escalar(valor)).append('\n')
            }
        }
        return sb.toString()
    }

    private fun escreverMapa(sb: StringBuilder, mapa: Map<*, *>, indento: Int) {
        for ((chave, valor) in mapa) {
            sb.append(" ".repeat(indento)).append(escalar(chave)).append(':')
            escreverValorDeChave(sb, valor, indento)
        }
    }

    /** O que vem depois de `chave:` — na mesma linha, ou nas de baixo. */
    private fun escreverValorDeChave(sb: StringBuilder, valor: Any?, indento: Int) {
        when {
            valor is Map<*, *> && valor.isEmpty() -> sb.append(" {}\n")
            valor is List<*> && valor.isEmpty() -> sb.append(" []\n")
            valor is Map<*, *> -> {
                sb.append('\n')
                escreverMapa(sb, valor, indento + 2)
            }
            valor is List<*> -> {
                sb.append('\n')
                // a sequência fica na mesma coluna da chave: é assim que o
                // PyYAML emite, e é o que faz `transacoes:` e `- id:` alinharem
                escreverLista(sb, valor, indento)
            }
            else -> sb.append(' ').append(escalar(valor, indento + 2)).append('\n')
        }
    }

    private fun escreverLista(sb: StringBuilder, lista: List<*>, indento: Int) {
        for (item in lista) {
            sb.append(" ".repeat(indento)).append('-')
            when {
                item is Map<*, *> && item.isEmpty() -> sb.append(" {}\n")
                item is List<*> && item.isEmpty() -> sb.append(" []\n")
                item is Map<*, *> -> {
                    // a primeira chave vai na linha do traço; as outras descem
                    var primeira = true
                    for ((chave, valor) in item) {
                        if (primeira) {
                            sb.append(' ')
                            primeira = false
                        } else {
                            sb.append(" ".repeat(indento + 2))
                        }
                        sb.append(escalar(chave)).append(':')
                        escreverValorDeChave(sb, valor, indento + 2)
                    }
                }
                item is List<*> -> throw IllegalArgumentException(
                    "lista dentro de lista não aparece nos arquivos do FinTips e " +
                        "este emissor não a escreve — melhor recusar que inventar layout",
                )
                else -> sb.append(' ').append(escalar(item, indento + 2)).append('\n')
            }
        }
    }

    // -------------------------------------------------------------- escalar

    fun escalar(valor: Any?, indentoDaContinuacao: Int = 2): String = when (valor) {
        null -> "null"
        is Boolean -> if (valor) "true" else "false"
        is Int -> valor.toString()
        is Long -> valor.toString()
        is Double -> comoPython(valor)
        is Float -> comoPython(valor.toDouble())
        is String -> texto(valor, indentoDaContinuacao)
        else -> throw IllegalArgumentException(
            "tipo sem regra de emissão: ${valor::class.simpleName}",
        )
    }

    private fun texto(v: String, indentoDaContinuacao: Int): String = when {
        podeSerPuro(v) && !precisaCitar(v) -> v
        v.contains('\n') -> aspasSimplesMultilinha(v, indentoDaContinuacao)
        v.any { it == '\t' || it < ' ' || it == '\u007f' } -> aspasDuplas(v)
        else -> "'" + v.replace("'", "''") + "'"
    }

    /**
     * Um texto puro que o YAML 1.1 resolveria como outro tipo precisa de aspas.
     *
     * São os resolvedores implícitos do PyYAML, na forma em que ele os aplica —
     * inclusive as pegadinhas: o expoente do float exige sinal explícito (por
     * isso `1e3` fica puro e `1.5` não), o sexagesimal exige primeiro dígito de
     * 1 a 9 (por isso `08:00` fica puro), e o carimbo de data curto exige dois
     * dígitos em mês e dia (por isso `2026-6-5` fica puro).
     */
    fun precisaCitar(v: String): Boolean =
        RESOLVEDORES.any { it.matches(v) }

    private val RESOLVEDORES: List<Regex> = listOf(
        // nulo (inclui o texto vazio)
        Regex("^(~|null|Null|NULL|)$"),
        // booleano — repare que `y`, `n`, `Y` e `N` sozinhos **não** entram
        Regex("^(yes|Yes|YES|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF)$"),
        // inteiros: binário, octal, decimal, hexadecimal e sexagesimal
        Regex("^[-+]?0b[01_]+$"),
        Regex("^[-+]?0[0-7_]+$"),
        Regex("^[-+]?(0|[1-9][0-9_]*)$"),
        Regex("^[-+]?0x[0-9a-fA-F_]+$"),
        Regex("^[-+]?[1-9][0-9_]*(:[0-5]?[0-9])+$"),
        // floats: o expoente exige sinal, como no PyYAML
        Regex("^[-+]?([0-9][0-9_]*)\\.[0-9_]*([eE][-+][0-9]+)?$"),
        Regex("^[-+]?\\.[0-9_]+([eE][-+][0-9]+)?$"),
        Regex("^[-+]?[0-9][0-9_]*(:[0-5]?[0-9])+\\.[0-9_]*$"),
        Regex("^[-+]?\\.(inf|Inf|INF)$"),
        Regex("^\\.(nan|NaN|NAN)$"),
        // data e carimbo de tempo
        Regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
        Regex(
            "^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}([Tt]|[ \\t]+)[0-9]{1,2}:[0-9]{2}:[0-9]{2}" +
                "(\\.[0-9]*)?([ \\t]*(Z|[-+][0-9]{1,2}(:[0-9]{2})?))?$",
        ),
        // os dois de mesclagem e valor
        Regex("^=$"),
        Regex("^<<$"),
    )

    /**
     * Se o texto pode ir sem aspas, pela forma — antes de olhar o tipo.
     *
     * Indicador é posicional: `-`, `?` e `:` só indicam quando vêm seguidos de
     * espaço ou no fim; `,`, `[`, `{` e companhia só indicam no começo. No meio
     * do texto, o que atrapalha é `": "` e `" #"`, que abririam um mapa ou um
     * comentário.
     */
    fun podeSerPuro(v: String): Boolean {
        if (v.isEmpty()) return false
        if (v.first() == ' ' || v.last() == ' ') return false
        if (v.any { it == '\n' || it == '\t' || it < ' ' || it == '\u007f' }) return false
        if (v == "---" || v == "..." || v.startsWith("--- ") || v.startsWith("... ")) return false

        val primeiro = v[0]
        if (primeiro in "#,[]{}&*!|>'\"%@`") return false
        if (primeiro in "-?:" && (v.length == 1 || v[1] == ' ')) return false

        if (v.contains(": ")) return false
        if (v.contains(" #")) return false
        if (v.last() == ':') return false
        return true
    }

    private fun aspasDuplas(v: String): String {
        val sb = StringBuilder("\"")
        for (c in v) {
            when {
                c == '\\' -> sb.append("\\\\")
                c == '"' -> sb.append("\\\"")
                c == '\t' -> sb.append("\\t")
                c == '\r' -> sb.append("\\r")
                c < ' ' || c == '\u007f' -> throw IllegalArgumentException(
                    "caractere de controle sem regra de escape neste emissor: " +
                        "código ${c.code}. Recusar é melhor que gravar torto",
                )
                else -> sb.append(c)
            }
        }
        return sb.append('"').toString()
    }

    /**
     * A dobra de linha do escalar entre aspas simples.
     *
     * Dentro de aspas simples, uma quebra de linha **dobra** para espaço; para
     * dizer "aqui há uma quebra de verdade", o PyYAML deixa uma linha em branco
     * e indenta a continuação. Emitir `'a\nb'` com a quebra crua faria o leitor
     * devolver `"a b"` — o texto da pessoa mudaria em silêncio.
     */
    private fun aspasSimplesMultilinha(v: String, indento: Int): String {
        require(!v.contains("\n\n")) {
            "quebras de linha seguidas não aparecem nos arquivos do FinTips e " +
                "este emissor não as dobra — melhor recusar que gravar torto"
        }
        require(!v.contains('\r')) { "retorno de carro não tem regra de dobra aqui" }
        val partes = v.split("\n").map { it.replace("'", "''") }
        val recuo = " ".repeat(indento)
        return "'" + partes.joinToString("\n\n$recuo") + "'"
    }

    // ---------------------------------------------------------------- float

    /**
     * O `repr` de float do Python, que é o que o PyYAML grava.
     *
     * Os dois usam a representação mais curta que faz round-trip, mas trocam
     * para notação científica em pontos diferentes: o Python só a partir de
     * 1e16, o Kotlin já em 1e7. Um patrimônio de dez milhões sairia como
     * `1.0E7`, que o PyYAML leria como texto — e o valor sumiria da conta.
     *
     * Sobre o `.0`: o `repr` do Python devolve `1e+16`, e o PyYAML normaliza
     * para `1.0e+16` antes de gravar.
     *
     * **A única divergência conhecida** é `5e-324`, o menor subnormal: a JVM
     * devolve "4.9E-324" e o Python "5e-324", os dois fazendo round-trip e
     * discordando sobre qual é a forma mais curta. Numa amostra de 8 mil
     * doubles — metade em faixa de dinheiro, metade em padrões de bits
     * aleatórios — foi a única. Não existe extrato com esse valor, então fica
     * registrada em vez de contornada com um caso especial que ninguém
     * conseguiria testar de novo.
     */
    fun comoPython(d: Double): String {
        if (d.isNaN()) return ".nan"
        if (d == Double.POSITIVE_INFINITY) return ".inf"
        if (d == Double.NEGATIVE_INFINITY) return "-.inf"
        if (d == 0.0) return if (1.0 / d < 0) "-0.0" else "0.0"

        val negativo = d < 0
        val (digitos, expoente) = digitosDe(abs(d))

        // `expoente` é o de `0.D1D2... × 10^expoente`; na forma `D.DDD e N`,
        // o expoente publicado é um a menos
        val expPublicado = expoente - 1
        val corpo = if (expPublicado < -4 || expPublicado >= 16) {
            val mantissa = if (digitos.length == 1) "${digitos[0]}.0"
            else "${digitos[0]}.${digitos.substring(1)}"
            val sinal = if (expPublicado < 0) "-" else "+"
            "${mantissa}e$sinal${abs(expPublicado).toString().padStart(2, '0')}"
        } else {
            fixo(digitos, expoente)
        }
        return if (negativo) "-$corpo" else corpo
    }

    /**
     * Os dígitos significativos e o expoente decimal, tirados do `toString`.
     *
     * O `toString` do Kotlin já dá a representação mais curta que faz
     * round-trip — a mesma que o Python usa. O que muda é a **apresentação**,
     * então basta reler os dígitos e reapresentá-los pela regra do Python.
     */
    private fun digitosDe(a: Double): Pair<String, Int> {
        val s = a.toString()
        val partes = s.split("E", "e")
        val mantissa = partes[0]
        val expExtra = if (partes.size > 1) partes[1].toInt() else 0

        val ponto = mantissa.indexOf('.')
        val cru = mantissa.replace(".", "")
        val inteiros = if (ponto < 0) mantissa.length else ponto

        val semZerosAEsquerda = cru.trimStart('0')
        val zerosCortados = cru.length - semZerosAEsquerda.length
        val digitos = semZerosAEsquerda.trimEnd('0').ifEmpty { "0" }
        return digitos to (inteiros - zerosCortados + expExtra)
    }

    /** Monta a forma sem expoente a partir dos dígitos e da posição do ponto. */
    private fun fixo(digitos: String, expoente: Int): String = when {
        expoente <= 0 -> "0." + "0".repeat(-expoente) + digitos
        expoente >= digitos.length -> digitos + "0".repeat(expoente - digitos.length) + ".0"
        else -> digitos.substring(0, expoente) + "." + digitos.substring(expoente)
    }
}
