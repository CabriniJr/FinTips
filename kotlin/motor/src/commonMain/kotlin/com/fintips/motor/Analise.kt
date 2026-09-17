package com.fintips.motor

import kotlin.math.sqrt

/**
 * A análise: mês a mês, baseline, recorrências e eventos atípicos.
 *
 * Aqui a porta encontra o único lugar onde o motor Python usa `float` de
 * propósito — volatilidade e mediana — e onde o Kotlin precisa usar `Double`
 * para comparar maçã com maçã. O resto continua em centavos inteiros.
 *
 * A regra que separa os dois mundos: **dinheiro é exato, estatística é
 * aproximada**. Somar gasto em `Double` erraria centavo; calcular desvio
 * padrão em inteiro exigiria uma biblioteca de racionais para ganhar
 * precisão que ninguém vai olhar, já que o número sai arredondado em três
 * casas.
 */

data class ResumoMensal(
    val mes: String,
    val renda: Dinheiro = Dinheiro.ZERO,
    val despesa: Dinheiro = Dinheiro.ZERO,   // positivo: quanto saiu
    val aportes: Dinheiro = Dinheiro.ZERO,
    val resgates: Dinheiro = Dinheiro.ZERO,
    val transferenciasLiq: Dinheiro = Dinheiro.ZERO,
    val estornos: Dinheiro = Dinheiro.ZERO,
    val porCategoria: Map<String, Dinheiro> = emptyMap(),
) {
    /** Quanto sobrou: o que entrou menos o que saiu, mais estorno. */
    val sobra: Dinheiro get() = renda - despesa + estornos

    /**
     * Quanto da renda sobrou.
     *
     * Calculado em aritmética inteira escalada, e não sobre a média já
     * arredondada: o Python divide em `Decimal` de precisão cheia e só
     * arredonda no fim. Arredondar antes daria um resultado diferente na
     * quarta casa, que é justamente onde este número mora.
     */
    val taxaPoupanca: Double
        get() = if (renda.centavos <= 0) 0.0
                else razaoArredondada(sobra.centavos, renda.centavos, 4)
}

/** Agrupa as transações por mês, separando por fluxo. */
fun mensal(transacoes: List<Transacao>): List<ResumoMensal> {
    val baldes = LinkedHashMap<String, MutableResumo>()
    for (t in transacoes) {
        val m = baldes.getOrPut(t.mes) { MutableResumo(t.mes) }
        val valor = t.valor.absoluto
        when (t.fluxo) {
            Fluxos.RECEITA -> m.renda += valor
            Fluxos.DESPESA -> {
                m.despesa += valor
                m.porCategoria[t.categoria] = (m.porCategoria[t.categoria] ?: Dinheiro.ZERO) + valor
            }
            Fluxos.APORTE -> m.aportes += valor
            Fluxos.RESGATE -> m.resgates += valor
            Fluxos.ESTORNO -> m.estornos += valor
            Fluxos.TRANSFERENCIA -> m.transferenciasLiq += t.valor   // com sinal
        }
    }
    return baldes.keys.sorted().map { baldes[it]!!.congelar() }
}

private class MutableResumo(val mes: String) {
    var renda = Dinheiro.ZERO
    var despesa = Dinheiro.ZERO
    var aportes = Dinheiro.ZERO
    var resgates = Dinheiro.ZERO
    var transferenciasLiq = Dinheiro.ZERO
    var estornos = Dinheiro.ZERO
    val porCategoria = LinkedHashMap<String, Dinheiro>()

    fun congelar() = ResumoMensal(
        mes, renda, despesa, aportes, resgates, transferenciasLiq, estornos,
        porCategoria.toList().sortedByDescending { it.second.centavos }.toMap(),
    )
}

/**
 * Descarta meses parciais das pontas.
 *
 * Um mês pela metade derruba a média e faz despesa estável parecer volátil —
 * o efeito é um score pior por artefato de recorte, não por comportamento.
 * Com dois meses ou menos não há o que descartar: sobraria nada.
 */
fun mesesCompletos(extrato: Extrato): List<ResumoMensal> {
    val meses = mensal(extrato.transacoes)
    if (meses.size <= 2) return meses
    var fora = meses
    if (extrato.periodoInicio.dayOfMonth > 1) fora = fora.drop(1)
    if (extrato.periodoFim.dayOfMonth < 26) fora = fora.dropLast(1)
    return fora.ifEmpty { meses }
}

data class Baseline(
    val mesesConsiderados: List<String>,
    val rendaMediaMes: Dinheiro,
    val despesaMediaMes: Dinheiro,
    val sobraMediaMes: Dinheiro,
    val taxaPoupancaMedia: Double,
    val volatilidadeDespesa: Double,
    val mesesNoVermelho: Int,
)

/**
 * Os números que todo o resto do motor usa como referência.
 *
 * Dois cuidados de paridade, os dois invisíveis até alguém conferir na mão:
 *
 * - a **taxa de poupança** sai das somas, não das médias já arredondadas. O
 *   Python divide em precisão cheia; arredondar antes mudaria a quarta casa.
 * - a **volatilidade** é desvio padrão populacional sobre a média, calculada
 *   em `Double` como no Python, e arredondada em três casas.
 */
fun baseline(extrato: Extrato): Baseline {
    var meses = mesesCompletos(extrato)
    if (meses.isEmpty()) meses = mensal(extrato.transacoes)
    if (meses.isEmpty()) {
        return Baseline(emptyList(), Dinheiro.ZERO, Dinheiro.ZERO, Dinheiro.ZERO, 0.0, 0.0, 0)
    }

    val somaRenda = meses.map { it.renda }.somar()
    val somaDespesa = meses.map { it.despesa }.somar()
    val n = meses.size

    val despesasEmDouble = meses.map { it.despesa.paraDouble() }
    val media = despesasEmDouble.average()
    val volatilidade =
        if (despesasEmDouble.size > 1 && media != 0.0) desvioPadraoPopulacional(despesasEmDouble) / media
        else 0.0

    return Baseline(
        mesesConsiderados = meses.map { it.mes },
        rendaMediaMes = somaRenda.dividir(n),
        despesaMediaMes = somaDespesa.dividir(n),
        sobraMediaMes = (somaRenda - somaDespesa).dividir(n),
        taxaPoupancaMedia = if (somaRenda.centavos == 0L) 0.0
            else razaoArredondada(somaRenda.centavos - somaDespesa.centavos, somaRenda.centavos, 4),
        volatilidadeDespesa = arredondar(volatilidade, 3),
        mesesNoVermelho = meses.count { it.sobra.negativo },
    )
}

data class Recorrencia(
    val contraparte: String,
    val categoria: String,
    val meses: List<String>,
    val ocorrencias: Int,
    /** Mediana em reais. `Double` porque a mediana de contagem par cai no meio centavo. */
    val valorTipico: Double,
    val custoMensal: Dinheiro,
    val tipo: String,   // assinatura | recorrente | sangria
)

/**
 * Contrapartes que reaparecem mês após mês — o custo fixo real.
 *
 * A classificação em três tipos é o que dá utilidade ao resultado:
 * **assinatura** é mesmo valor uma vez por mês (dá para cancelar),
 * **sangria** é muita compra pequena no mesmo lugar (não dá para cancelar, dá
 * para notar), e **recorrente** é o resto. Tratar os três como a mesma coisa
 * produziria a sugestão inútil de "corte o mercado".
 */
fun recorrencias(transacoes: List<Transacao>, minimoDeMeses: Int = 3): List<Recorrencia> {
    val grupos = LinkedHashMap<Pair<String, String>, MutableList<Transacao>>()
    for (t in transacoes) {
        if (t.fluxo != Fluxos.DESPESA || t.contraparte.isEmpty()) continue
        grupos.getOrPut(t.contraparte to t.categoria) { mutableListOf() }.add(t)
    }

    val totalDeMeses = maxOf(transacoes.map { it.mes }.toSet().size, 1)
    val saida = mutableListOf<Recorrencia>()

    for ((chave, txs) in grupos) {
        val (contraparte, categoria) = chave
        val meses = txs.map { it.mes }.toSortedSet().toList()
        if (meses.size < minimoDeMeses) continue

        val valores = txs.map { it.valor.absoluto.centavos }.sorted()
        val mediana = medianaDeCentavos(valores)
        val total = Dinheiro(valores.sum())
        val amplitude = if (mediana != 0.0) (valores.last() - valores.first()) / 100.0 / mediana else 9.0
        val porMes = txs.size.toDouble() / meses.size

        val tipo = when {
            amplitude <= 0.15 && porMes <= 1.4 -> "assinatura"
            porMes >= 3 -> "sangria"
            else -> "recorrente"
        }

        saida.add(
            Recorrencia(
                contraparte = contraparte,
                categoria = categoria,
                meses = meses,
                ocorrencias = txs.size,
                valorTipico = mediana,
                custoMensal = total.dividir(totalDeMeses),
                tipo = tipo,
            )
        )
    }
    // ordenação estável: empate mantém a ordem de aparição, como no Python
    return saida.sortedByDescending { it.custoMensal.centavos }
}

/**
 * Eventos atípicos — compra grande, repasse pontual.
 *
 * Eles não podem entrar na linha de base de consumo: uma viagem paga à vista
 * em março viraria "despesa média mensal" e a projeção inteira sairia errada.
 *
 * O piso de R$ 500 existe para que uma pessoa de gasto baixo não tenha metade
 * do extrato marcada como atípica.
 */
fun atipicos(transacoes: List<Transacao>, k: Double = 4.0): List<Transacao> {
    val relevantes = transacoes.filter {
        it.fluxo == Fluxos.DESPESA || it.fluxo == Fluxos.TRANSFERENCIA
    }
    if (relevantes.size < 8) return emptyList()

    val valores = relevantes.map { it.valor.absoluto.centavos }.sorted()
    val mediana = medianaDeCentavos(valores)
    val limite = if (mediana != 0.0) mediana * k else 500.0
    val piso = maxOf(limite, 500.0)

    return relevantes
        .filter { it.valor.absoluto.paraDouble() > piso }
        .sortedByDescending { it.valor.absoluto.centavos }
}

// --------------------------------------------------------------------------
// estatística
// --------------------------------------------------------------------------

/**
 * Mediana de uma lista **já ordenada** de centavos, devolvida em reais.
 *
 * Com contagem par o Python calcula `(a+b)/2` em `Decimal`, o que pode cair no
 * meio centavo — `(10.01 + 10.02)/2 = 10.015`. Guardar isso em `Dinheiro`
 * perderia a metade e mudaria a amplitude que decide se algo é assinatura.
 * Em `Double` a conta é exata, porque `(a+b)` é inteiro e dividir por dois é
 * exato em binário.
 */
internal fun medianaDeCentavos(ordenados: List<Long>): Double {
    if (ordenados.isEmpty()) return 0.0
    val n = ordenados.size
    val meio = n / 2
    return if (n % 2 == 1) ordenados[meio] / 100.0
           else (ordenados[meio - 1] + ordenados[meio]) / 2.0 / 100.0
}

/** Desvio padrão populacional, como o `statistics.pstdev` do Python. */
internal fun desvioPadraoPopulacional(valores: List<Double>): Double {
    if (valores.size < 2) return 0.0
    val media = valores.average()
    val soma = valores.sumOf { (it - media) * (it - media) }
    return sqrt(soma / valores.size)
}

/**
 * `round(numerador / denominador, casas)` em aritmética inteira.
 *
 * Fazer a divisão em `Double` e arredondar depois daria resultado diferente do
 * Python nos empates, porque o Python divide em `Decimal` de precisão cheia.
 * Escalando antes, a conta é exata e o arredondamento é o mesmo
 * meio-para-o-par.
 */
internal fun razaoArredondada(numerador: Long, denominador: Long, casas: Int): Double {
    if (denominador == 0L) return 0.0
    var escala = 1L
    repeat(casas) { escala *= 10 }
    val escalado = Dinheiro(numerador * escala).dividir(denominador).centavos
    return escalado.toDouble() / escala
}
