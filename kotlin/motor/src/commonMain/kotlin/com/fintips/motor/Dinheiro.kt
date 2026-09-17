package com.fintips.motor

/**
 * Dinheiro em centavos inteiros.
 *
 * Esta é a primeira decisão da porta para Kotlin e a que mais podia dar errado
 * em silêncio, então vale escrever por quê.
 *
 * O motor Python usa `Decimal`: exato na soma, e arredondado só na saída com
 * `quantize(Decimal("0.01"))`, que por padrão usa **meio-para-o-par**
 * (HALF_EVEN). Reproduzir isso em Kotlin tinha três caminhos:
 *
 * - `Double` — descartado. `0.1 + 0.2` não é `0.3`, e um motor que soma
 *   extrato não pode errar centavo por representação.
 * - `java.math.BigDecimal` — exato e com a mesma semântica, mas só existe na
 *   JVM. Usar aqui prenderia o `commonMain` a JVM e Android, fechando a porta
 *   para iOS antes mesmo de ela ser discutida.
 * - **centavos em `Long`** — exato, disponível em todos os alvos, e com uma
 *   propriedade que fecha a questão: nos pontos onde o Python divide (média
 *   mensal, custo por mês), ele faz **uma** divisão e arredonda logo em
 *   seguida. Uma divisão inteira com HALF_EVEN dá exatamente o mesmo
 *   resultado que dividir em `Decimal` e depois quantizar.
 *
 * O limite: `Long` em centavos vai até ~92 quatrilhões de reais. Não é o
 * gargalo de ninguém.
 *
 * Onde o Python usa `float` de propósito — volatilidade, desvio padrão,
 * percentuais — o Kotlin usa `Double` também, para o harness diferencial
 * comparar maçã com maçã.
 */
@JvmInline
value class Dinheiro(val centavos: Long) : Comparable<Dinheiro> {

    operator fun plus(outro: Dinheiro) = Dinheiro(centavos + outro.centavos)
    operator fun minus(outro: Dinheiro) = Dinheiro(centavos - outro.centavos)
    operator fun times(n: Int) = Dinheiro(centavos * n)
    operator fun unaryMinus() = Dinheiro(-centavos)

    override fun compareTo(other: Dinheiro) = centavos.compareTo(other.centavos)

    val absoluto: Dinheiro get() = Dinheiro(if (centavos < 0) -centavos else centavos)
    val negativo: Boolean get() = centavos < 0
    val zero: Boolean get() = centavos == 0L

    /**
     * Divide arredondando meio-para-o-par, igual ao `quantize` do Python.
     *
     * Meio-para-o-par existe para que arredondamentos repetidos não puxem a
     * soma sempre para cima: com meio-para-cima, mil valores terminados em
     * meio centavo viram mil erros na mesma direção.
     */
    fun dividir(divisor: Int): Dinheiro = dividir(divisor.toLong())

    /**
     * Mesma divisão, com divisor em `Long`.
     *
     * Existe porque a taxa de poupança divide centavos por centavos: um
     * patrimônio de R$ 21 milhões já estoura `Int`, e o erro apareceria como
     * número negativo absurdo em vez de exceção.
     */
    fun dividir(divisor: Long): Dinheiro {
        require(divisor != 0L) { "divisão por zero em Dinheiro" }
        val d = divisor
        val q = centavos / d
        val resto = centavos % d
        if (resto == 0L) return Dinheiro(q)

        val dobroResto = 2 * (if (resto < 0) -resto else resto)
        val absD = if (d < 0) -d else d
        val mesmoSinal = (centavos < 0) == (d < 0)
        val passo = if (mesmoSinal) 1L else -1L

        return when {
            dobroResto > absD -> Dinheiro(q + passo)
            dobroResto < absD -> Dinheiro(q)
            // empate exato: vai para o par
            q % 2 == 0L -> Dinheiro(q)
            else -> Dinheiro(q + passo)
        }
    }

    /** Fração do valor, usada onde o Python multiplica por um fator decimal. */
    fun proporcao(numerador: Int, denominador: Int): Dinheiro =
        Dinheiro(centavos * numerador).dividir(denominador)

    /** Para comparar com a saída do Python, que serializa como float de 2 casas. */
    fun paraDouble(): Double = centavos / 100.0

    /** Texto canônico: sempre duas casas, ponto decimal, sem separador de milhar. */
    override fun toString(): String {
        val sinal = if (centavos < 0) "-" else ""
        val abs = if (centavos < 0) -centavos else centavos
        val inteiros = abs / 100
        val cents = abs % 100
        return "$sinal$inteiros.${cents.toString().padStart(2, '0')}"
    }

    companion object {
        val ZERO = Dinheiro(0)

        /**
         * Lê valor de texto, replicando `parsers/ofx.py::parse_amount`.
         *
         * Replicando mesmo, inclusive no que parece errado. Na primeira versão
         * eu tinha "melhorado" a regra: três dígitos depois de um ponto único
         * viraria separador de milhar, e `"1.234"` seria mil duzentos e trinta
         * e quatro. O motor Python lê aquilo como **um real e vinte e três**,
         * porque `Decimal("1.234")` é um e duzentos e trinta e quatro
         * milésimos, e o arredondamento para centavos derruba o resto.
         *
         * Se essa regra é um bug, e pode ser, ele se corrige nos dois motores
         * de uma vez, com teste, e de propósito. Corrigir durante a porta é
         * como trocar o motor do carro e aproveitar para mexer no freio: se
         * algo sair diferente depois, ninguém sabe qual das duas mudanças foi.
         */
        fun de(texto: String): Dinheiro {
            var s = texto.replace("R$", "").replace('\u00A0', ' ').trim()
            val negativo = s.startsWith("-") || (s.startsWith("(") && s.endsWith(")"))
            s = s.trim('(', ')', '-', '+', ' ')
            if (s.isEmpty()) return ZERO

            val temVirgula = s.contains(',')
            val temPonto = s.contains('.')
            s = when {
                // o separador decimal é o que aparece por último
                temVirgula && temPonto ->
                    if (s.lastIndexOf(',') > s.lastIndexOf('.')) s.replace(".", "").replace(',', '.')
                    else s.replace(",", "")
                temVirgula -> s.replace(".", "").replace(',', '.')
                else -> s
            }

            val valor = paraCentavos(s)
            return Dinheiro(if (negativo) -valor else valor)
        }

        /**
         * Converte "12.3456" em centavos arredondando meio-para-o-par, que é o
         * que o `quantize(Decimal("0.01"))` do Python faz na saída.
         */
        private fun paraCentavos(s: String): Long {
            val ponto = s.indexOf('.')
            val inteiros = if (ponto < 0) s else s.substring(0, ponto)
            val fracao = if (ponto < 0) "" else s.substring(ponto + 1)

            val reais = if (inteiros.isEmpty()) 0L else inteiros.toLong()
            val centavos = when {
                fracao.isEmpty() -> 0L
                fracao.length == 1 -> fracao.toLong() * 10
                else -> fracao.substring(0, 2).toLong()
            }
            var total = reais * 100 + centavos

            // dígitos além do centavo decidem o arredondamento
            val sobra = if (fracao.length > 2) fracao.substring(2) else ""
            if (sobra.isNotEmpty()) {
                val primeiro = sobra[0] - '0'
                val restoNaoZero = sobra.drop(1).any { it != '0' }
                val sobeUm = when {
                    primeiro > 5 -> true
                    primeiro < 5 -> false
                    restoNaoZero -> true
                    else -> total % 2 != 0L   // empate exato vai para o par
                }
                if (sobeUm) total += 1
            }
            return total
        }

        fun deReais(reais: Long) = Dinheiro(reais * 100)
    }
}

/** Soma exata: nenhuma divisão no meio, então nenhum arredondamento no meio. */
fun Iterable<Dinheiro>.somar(): Dinheiro = Dinheiro(sumOf { it.centavos })

/** Média com uma única divisão no fim — o mesmo que o Python faz. */
fun Collection<Dinheiro>.media(): Dinheiro =
    if (isEmpty()) Dinheiro.ZERO else somar().dividir(size)
