package com.fintips.motor

/**
 * Score financeiro de 0 a 100.
 *
 * Cinco dimensões, pesos explícitos, cada ponto com uma fórmula visível. Não
 * há número mágico saído de modelo nenhum — e essa é a razão de o score existir
 * assim: um score opaco não muda comportamento, porque a pessoa não sabe o que
 * fazer com ele. Este diz quantos pontos faltam em qual dimensão e qual
 * alavanca rende mais.
 */

object PesosDoScore {
    const val POUPANCA = 30      // quanto da renda sobra
    const val RESERVA = 25       // meses de despesa cobertos pelo que está guardado
    const val ESTABILIDADE = 15  // previsibilidade do gasto mensal
    const val VAZAMENTOS = 10    // peso do gasto invisível
    const val PLANOS = 20        // aderência às metas cadastradas

    /** Na ordem em que aparecem no painel — e a ordem importa para o harness. */
    val TODOS = listOf(
        "poupanca" to POUPANCA,
        "reserva" to RESERVA,
        "estabilidade" to ESTABILIDADE,
        "vazamentos" to VAZAMENTOS,
        "planos" to PLANOS,
    )
}

/** Alvos de nota cheia. Ficam explícitos porque a alavanca é a distância até eles. */
private const val ALVO_TAXA_POUPANCA = 0.40
private const val ALVO_MESES_RESERVA = 6.0
private const val TETO_VOLATILIDADE = 0.5
private const val TETO_INVISIVEL = 0.15
private const val PENA_POR_MES_NO_VERMELHO = 0.25

data class DimensaoDoScore(val nome: String, val pontos: Double, val maximo: Int) {
    val pct: Int get() = arredondar(pontos / maximo * 100, 0).toInt()
}

data class IndicadoresDoScore(
    val taxaPoupanca: Double,
    val mesesDeReserva: Double,
    val volatilidadeDespesa: Double,
    val gastoInvisivelMes: Double,
    val gastoInvisivelPctDespesa: Double,
    val rendaMediaMes: Double,
    val despesaMediaMes: Double,
)

data class ResultadoDoScore(
    val score: Double,
    val faixa: String,
    val dimensoes: List<DimensaoDoScore>,
    val indicadores: IndicadoresDoScore,
    val proximoPonto: String,
)

/** Aderência de um plano, já avaliada. */
data class AderenciaDePlano(
    val concluido: Boolean,
    val aporteNecessarioMes: Double,
    val capacidadeMensalReal: Double,
)

private fun limitar(x: Double, minimo: Double = 0.0, maximo: Double = 1.0): Double =
    if (x < minimo) minimo else if (x > maximo) maximo else x

private fun faixaDe(score: Double): String = when {
    score >= 85 -> "excelente"
    score >= 70 -> "bom"
    score >= 55 -> "razoavel"
    score >= 40 -> "atencao"
    else -> "critico"
}

/**
 * Calcula o score.
 *
 * Três decisões que parecem detalhe e não são:
 *
 * - **despesa zero não é nota cheia de reserva.** Sem despesa não há quantos
 *   meses cobrir, então a dimensão fica em zero em vez de infinito. Um extrato
 *   sem gasto nenhum é dado incompleto, não saúde financeira.
 * - **mês no vermelho multiplica, não subtrai.** Quatro meses negativos zeram a
 *   estabilidade inteira. Subtrair deixaria um resíduo que sugeriria alguma
 *   previsibilidade onde não há.
 * - **sem plano cadastrado vale meia nota.** Não é prêmio nem castigo: o motor
 *   não sabe se a pessoa não tem metas ou só não as cadastrou, e fingir
 *   qualquer uma das duas seria pior.
 */
fun calcularScore(
    taxaPoupanca: Double,
    volatilidadeDespesa: Double,
    mesesNoVermelho: Int,
    rendaMediaMes: Dinheiro,
    despesaMediaMes: Dinheiro,
    taxasEsegurosMes: Dinheiro,
    microGastosMes: Dinheiro,
    planos: List<AderenciaDePlano>,
    patrimonioLiquido: Dinheiro,
): ResultadoDoScore {
    val despesa = despesaMediaMes.paraDouble()

    // 1. poupança — 40% da renda é o teto da nota
    val pPoupanca = limitar(taxaPoupanca / ALVO_TAXA_POUPANCA) * PesosDoScore.POUPANCA

    // 2. reserva — seis meses de despesa é nota cheia
    val mesesDeReserva = if (despesa > 0) patrimonioLiquido.paraDouble() / despesa else 0.0
    val pReserva = limitar(mesesDeReserva / ALVO_MESES_RESERVA) * PesosDoScore.RESERVA

    // 3. estabilidade — volatilidade de 50% zera; mês no vermelho pune por multiplicação
    var pEstabilidade = limitar(1 - volatilidadeDespesa / TETO_VOLATILIDADE) * PesosDoScore.ESTABILIDADE
    pEstabilidade *= maxOf(0.0, 1 - PENA_POR_MES_NO_VERMELHO * mesesNoVermelho)

    // 4. vazamentos — invisível acima de 15% da despesa zera a dimensão
    val invisivelMes = taxasEsegurosMes + microGastosMes
    val pctInvisivel = if (despesa > 0) invisivelMes.paraDouble() / despesa else 0.0
    val pVazamentos = limitar(1 - pctInvisivel / TETO_INVISIVEL) * PesosDoScore.VAZAMENTOS

    // 5. planos — média de aderência; sem plano cadastrado, metade da nota
    val pPlanos = if (planos.isNotEmpty()) {
        val aderencias = planos.map { p ->
            when {
                p.concluido -> 1.0
                p.aporteNecessarioMes <= 0 -> 0.5
                else -> limitar(p.capacidadeMensalReal / p.aporteNecessarioMes)
            }
        }
        aderencias.sum() / aderencias.size * PesosDoScore.PLANOS
    } else {
        PesosDoScore.PLANOS * 0.5
    }

    val partes = linkedMapOf(
        "poupanca" to arredondar(pPoupanca, 1),
        "reserva" to arredondar(pReserva, 1),
        "estabilidade" to arredondar(pEstabilidade, 1),
        "vazamentos" to arredondar(pVazamentos, 1),
        "planos" to arredondar(pPlanos, 1),
    )
    val total = arredondar(partes.values.sum(), 1)

    return ResultadoDoScore(
        score = total,
        faixa = faixaDe(total),
        dimensoes = PesosDoScore.TODOS.map { (nome, peso) ->
            DimensaoDoScore(nome, partes[nome]!!, peso)
        },
        indicadores = IndicadoresDoScore(
            taxaPoupanca = arredondar(taxaPoupanca * 100, 1),
            mesesDeReserva = arredondar(mesesDeReserva, 1),
            volatilidadeDespesa = arredondar(volatilidadeDespesa, 3),
            gastoInvisivelMes = invisivelMes.paraDouble(),
            gastoInvisivelPctDespesa = arredondar(pctInvisivel * 100, 1),
            rendaMediaMes = rendaMediaMes.paraDouble(),
            despesaMediaMes = despesa,
        ),
        proximoPonto = proximaAlavanca(partes),
    )
}

/**
 * A dimensão com maior ganho marginal — onde o esforço rende mais ponto.
 *
 * Empate fica com a primeira na ordem dos pesos, como no Python, onde o `max`
 * sobre o dicionário devolve a primeira chave de valor máximo. Parece
 * arbitrário e é: o importante é ser **o mesmo** arbitrário dos dois lados.
 */
private fun proximaAlavanca(partes: Map<String, Double>): String {
    val dicas = mapOf(
        "poupanca" to "aumentar a sobra mensal: o maior ganho de score está em guardar mais do que entra",
        "reserva" to "engordar a reserva até cobrir 6 meses de despesa",
        "estabilidade" to "reduzir a variação do gasto entre meses — orçamento por categoria",
        "vazamentos" to "cortar taxas, seguros e micro-gastos recorrentes",
        "planos" to "ajustar prazo ou aporte dos planos para caberem na capacidade real",
    )
    var alvo = PesosDoScore.TODOS.first().first
    var maiorLacuna = Double.NEGATIVE_INFINITY
    for ((nome, peso) in PesosDoScore.TODOS) {
        val lacuna = peso - (partes[nome] ?: 0.0)
        if (lacuna > maiorLacuna) {
            maiorLacuna = lacuna
            alvo = nome
        }
    }
    return dicas[alvo]!!
}
