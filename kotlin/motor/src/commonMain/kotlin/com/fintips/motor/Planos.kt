package com.fintips.motor

import kotlinx.datetime.LocalDate

/**
 * Planos financeiros: quanto falta, em que ritmo fecha, e o que o extrato já
 * gastou neles.
 *
 * O módulo é curto e tem três armadilhas de porte, todas silenciosas — erram
 * um número plausível em vez de estourar, que é o pior jeito de errar.
 *
 * **Zero e ausente são a mesma coisa no Python.** `months_until` devolve `0`
 * para prazo vencido, e o motor escreve `if meses` — em Python, `0` é falso.
 * O aporte necessário passa a ser o valor **inteiro** que falta, não uma
 * divisão por zero. Uma porta que teste `meses != null` divide por zero; uma
 * que teste `meses > 0` acerta por acidente e diverge no `meses_ate_alvo`
 * publicado, que continua sendo `0` e não `null`.
 *
 * **Os limiares são `<=`.** Aporte necessário exatamente em 60% da capacidade
 * é *confortável*; exatamente na capacidade é *apertado*. Trocar por `<`
 * empurra o plano uma faixa para baixo, e a pessoa lê "inviável" sobre algo
 * que fecha no centavo.
 *
 * **O ritmo arredonda para cima.** Faltando R$ 1.000,01 com aporte de
 * R$ 500,00 são três meses. Truncar promete uma data que não chega.
 */
object Planos {

    /** Faixas de viabilidade, na ordem em que o Python as decide. */
    object Status {
        const val CONCLUIDO = "concluido"
        const val PRONTO = "pronto"
        const val SEM_PRAZO = "sem_prazo"
        const val CONFORTAVEL = "confortavel"
        const val APERTADO = "apertado"
        const val INVIAVEL = "inviavel_no_ritmo_atual"
    }

    data class Plano(
        val id: String,
        val nome: String,
        val tipo: String = "outro",
        val custoAlvo: Dinheiro = Dinheiro.ZERO,
        val dataAlvo: LocalDate? = null,
        val prioridade: String = "media",
        /** Quanto a pessoa se comprometeu a guardar por mês. */
        val aporteMensal: Dinheiro = Dinheiro.ZERO,
        /** Quanto já separou para **este** plano. */
        val guardado: Dinheiro = Dinheiro.ZERO,
        val conta: String = "",
        /** Gastos que contam para o plano, casados por texto normalizado. */
        val merchants: List<String> = emptyList(),
        val categorias: List<String> = emptyList(),
        val notas: String = "",
    )

    data class CompraRelacionada(val dia: String, val onde: String, val valor: Dinheiro)

    data class Avaliacao(
        val id: String,
        val nome: String,
        val custoAlvo: Dinheiro,
        val guardado: Dinheiro,
        val falta: Dinheiro,
        val progressoPct: Double,
        val mesesAteAlvo: Int?,
        val aporteNecessarioMes: Dinheiro,
        val aportePlanejadoMes: Dinheiro,
        val capacidadeMensalReal: Dinheiro,
        val mesesNoRitmoPlanejado: Int?,
        val status: String,
        val viavel: Boolean,
        val jaGastoNoPlano: Dinheiro,
        val comprasRelacionadas: List<CompraRelacionada>,
    ) {
        fun paraMapa(): Map<String, Any?> = linkedMapOf(
            "id" to id,
            "nome" to nome,
            "custo_alvo" to custoAlvo.paraDouble(),
            "guardado" to guardado.paraDouble(),
            "falta" to falta.paraDouble(),
            "progresso_pct" to progressoPct,
            "meses_ate_alvo" to mesesAteAlvo,
            "aporte_necessario_mes" to aporteNecessarioMes.paraDouble(),
            "aporte_planejado_mes" to aportePlanejadoMes.paraDouble(),
            "capacidade_mensal_real" to capacidadeMensalReal.paraDouble(),
            "meses_no_ritmo_planejado" to mesesNoRitmoPlanejado,
            "status" to status,
            "viavel" to viavel,
            "ja_gasto_no_plano" to jaGastoNoPlano.paraDouble(),
            "compras_relacionadas" to comprasRelacionadas.map {
                linkedMapOf("data" to it.dia, "onde" to it.onde, "valor" to it.valor.paraDouble())
            },
        )
    }

    /**
     * Meses até o alvo, nunca negativo.
     *
     * Prazo vencido devolve `0`, e é esse `0` que o resto do módulo trata como
     * "sem prazo útil" — sem deixar de publicá-lo como `0`.
     */
    fun mesesAte(alvo: LocalDate?, hoje: LocalDate): Int? {
        if (alvo == null) return null
        val meses = (alvo.year - hoje.year) * 12 + (alvo.monthNumber - hoje.monthNumber)
        return maxOf(meses, 0)
    }

    fun avaliar(plano: Plano, extrato: Extrato, sobraMediaMes: Dinheiro, hoje: LocalDate): Avaliacao {
        val chaves = plano.merchants.map { norm(it) }
        val categorias = plano.categorias.toSet()
        val gastos = extrato.transacoes.filter { t ->
            t.fluxo == Fluxos.DESPESA && (
                (chaves.isNotEmpty() && chaves.any { it in norm(t.contraparte) }) ||
                    (categorias.isNotEmpty() && t.categoria in categorias)
                )
        }
        val jaGasto = gastos.map { it.valor.absoluto }.somar()

        val faltam = maxOf(plano.custoAlvo - plano.guardado, Dinheiro.ZERO)
        val meses = mesesAte(plano.dataAlvo, hoje)
        // `if meses` do Python: nulo **e** zero caem aqui, e o necessário vira
        // o valor inteiro que falta
        val necessario = if (meses != null && meses != 0) faltam.dividir(meses) else faltam

        val capacidade = if (sobraMediaMes > Dinheiro.ZERO) sobraMediaMes else Dinheiro.ZERO

        val status: String
        val viavel: Boolean
        when {
            faltam.zero -> {
                status = Status.CONCLUIDO; viavel = true
            }
            meses == null || meses == 0 -> {
                // o ramo "pronto" do Python é inalcançável — `faltam <= 0` já
                // foi tratado acima. Fica replicado para a porta não inventar
                // uma faixa que o motor de referência não produz.
                status = if (faltam <= Dinheiro.ZERO) Status.PRONTO else Status.SEM_PRAZO
                viavel = faltam <= capacidade
            }
            // `necessario <= capacidade * 0.6` sem tocar em Double: multiplicar
            // cruzado mantém a comparação exata em centavos inteiros
            necessario.centavos * 10 <= capacidade.centavos * 6 -> {
                status = Status.CONFORTAVEL; viavel = true
            }
            necessario <= capacidade -> {
                status = Status.APERTADO; viavel = true
            }
            else -> {
                status = Status.INVIAVEL; viavel = false
            }
        }

        val mesesNoRitmo = if (plano.aporteMensal > Dinheiro.ZERO) {
            // teto da divisão: faltar um centavo já custa um mês inteiro
            val f = faltam.centavos
            val a = plano.aporteMensal.centavos
            ((f + a - 1) / a).toInt()
        } else null

        return Avaliacao(
            id = plano.id,
            nome = plano.nome,
            custoAlvo = plano.custoAlvo,
            guardado = plano.guardado,
            falta = faltam,
            progressoPct = if (!plano.custoAlvo.zero) {
                arredondar(
                    plano.guardado.centavos.toDouble() / plano.custoAlvo.centavos * 100, 1,
                )
            } else 0.0,
            mesesAteAlvo = meses,
            aporteNecessarioMes = necessario,
            aportePlanejadoMes = plano.aporteMensal,
            capacidadeMensalReal = capacidade,
            mesesNoRitmoPlanejado = mesesNoRitmo,
            status = status,
            viavel = viavel,
            jaGastoNoPlano = jaGasto,
            comprasRelacionadas = gastos
                .sortedByDescending { it.momento.instante }
                .take(10)
                .map { CompraRelacionada(it.dia.toString(), it.contraparte, it.valor.absoluto) },
        )
    }

    fun avaliarTodos(
        planos: List<Plano>,
        extrato: Extrato,
        sobraMediaMes: Dinheiro,
        hoje: LocalDate,
    ): List<Avaliacao> = planos.map { avaliar(it, extrato, sobraMediaMes, hoje) }
}
