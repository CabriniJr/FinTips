package com.fintips.motor

import kotlinx.datetime.LocalDate

/**
 * Projeção de caixa: doze meses à frente, com cenário, planos e reserva.
 *
 * Separar custo fixo de variável só vale a pena se alguém usar a separação. É
 * aqui: o fixo se repete como compromisso, o variável entra como média com
 * folga, os planos consomem a sobra na ordem da prioridade, e cada meta ganha
 * o mês provável de fechar — que é a pergunta que a pessoa realmente faz.
 *
 * ## A parte que exige cuidado na porta: quando se arredonda
 *
 * O módulo Python multiplica a renda pelo fator do cenário em `Decimal` de
 * precisão cheia e só arredonda **na saída de cada mês**. O patrimônio, porém,
 * acumula o valor não arredondado ao longo dos doze meses. Com renda de
 * R$ 3.333,33 e cenário conservador:
 *
 *     renda   = 3333.33 * 0.90 = 2999.997        (não fecha em centavo)
 *     sobra   = 2999.997 - 1111.11 - 1277.7765 = 611.1105
 *     mês 12  = 1000 + 12 * 611.1105 = 8333.326  → sai como 8833.33
 *
 * Uma porta que arredondasse a sobra para 611,11 antes do laço acertaria o
 * primeiro mês e erraria o décimo segundo por um centavo. Não é um erro que
 * apareça revisando código: aparece como saldo estranho no app, meses depois.
 *
 * Por isso o laço inteiro roda numa escala mais fina que o centavo. Como os
 * fatores de cenário têm duas casas e o dinheiro tem duas, todo produto cabe
 * em quatro casas decimais — exatamente [ESCALA] centésimos de centavo. Nada
 * se arredonda no meio; arredonda-se só ao montar cada linha, que é onde o
 * Python arredonda.
 */
object Projecao {

    /** Centésimos de centavo por centavo: a escala em que o laço trabalha. */
    private const val ESCALA = 100L

    /**
     * Os fatores em pontos percentuais inteiros, e não como `Double`.
     *
     * `0.90` não existe em binário, e multiplicar centavos por ele reintroduz
     * justamente o erro que os centavos inteiros existem para evitar. Como
     * todos os fatores do Python têm duas casas, o inteiro é exato.
     */
    data class Cenario(val nome: String, val rendaPct: Int, val variavelPct: Int)

    val CENARIOS = listOf(
        Cenario("base", rendaPct = 100, variavelPct = 100),
        Cenario("conservador", rendaPct = 90, variavelPct = 115),
        Cenario("otimista", rendaPct = 105, variavelPct = 90),
    )

    /** Cenário desconhecido cai no base, como o `CENARIOS.get(…, base)` do Python. */
    fun cenarioDe(nome: String): Cenario =
        CENARIOS.firstOrNull { it.nome == nome } ?: CENARIOS.first()

    /** Um plano como a projeção o enxerga: quanto falta, com que prioridade. */
    data class PlanoEmProjecao(
        val id: String,
        val nome: String,
        val falta: Dinheiro,
        val prioridade: String = "media",
        val aportePlanejado: Dinheiro = Dinheiro.ZERO,
        val status: String = "em_andamento",
    )

    data class Linha(
        val mes: String,
        val renda: Dinheiro,
        val custoFixo: Dinheiro,
        val custoVariavel: Dinheiro,
        val sobra: Dinheiro,
        val aportesEmPlanos: Dinheiro,
        val patrimonioProjetado: Dinheiro,
    ) {
        fun paraMapa(): Map<String, Any?> = linkedMapOf(
            "mes" to mes,
            "renda" to renda.paraDouble(),
            "custo_fixo" to custoFixo.paraDouble(),
            "custo_variavel" to custoVariavel.paraDouble(),
            "sobra" to sobra.paraDouble(),
            "aportes_em_planos" to aportesEmPlanos.paraDouble(),
            "patrimonio_projetado" to patrimonioProjetado.paraDouble(),
        )
    }

    data class PlanoProjetado(
        val id: String,
        val nome: String,
        /**
         * Sai **sem** arredondar para centavo, porque o Python serializa
         * `float(Decimal)` sem `quantize` aqui. Um plano que consome sobra de
         * 611,1105 por mês termina devendo 2666,674 — três casas, e o harness
         * cobra as três.
         */
        val faltaAoFim: Double,
        val concluiEm: String?,
    ) {
        fun paraMapa(): Map<String, Any?> = linkedMapOf(
            "id" to id,
            "nome" to nome,
            "falta_ao_fim" to faltaAoFim,
            "conclui_em" to concluiEm,
        )
    }

    data class Resultado(
        val cenario: String,
        val rendaMensal: Dinheiro,
        val custoFixo: Dinheiro,
        val custoVariavel: Dinheiro,
        val sobraMensal: Dinheiro,
        val fixoPctDaRenda: Double,
        val linhas: List<Linha>,
        val planos: List<PlanoProjetado>,
        val reservaAlvo: Dinheiro,
        val reservaAtingidaEm: String?,
    ) {
        fun paraMapa(): Map<String, Any?> = linkedMapOf(
            "cenario" to cenario,
            "premissas" to linkedMapOf(
                "renda_mensal" to rendaMensal.paraDouble(),
                "custo_fixo" to custoFixo.paraDouble(),
                "custo_variavel" to custoVariavel.paraDouble(),
                "sobra_mensal" to sobraMensal.paraDouble(),
                "fixo_pct_da_renda" to fixoPctDaRenda,
            ),
            "linhas" to linhas.map { it.paraMapa() },
            "planos" to planos.map { it.paraMapa() },
            "reserva" to linkedMapOf(
                "alvo" to reservaAlvo.paraDouble(),
                "atingida_em" to reservaAtingidaEm,
            ),
        )
    }

    /** Ordem em que os planos comem a sobra. Desconhecido vale como média. */
    private val ORDEM = mapOf("alta" to 0, "media" to 1, "baixa" to 2)

    fun projetar(
        rendaMediaMes: Dinheiro,
        despesaMediaMes: Dinheiro,
        custoFixoMensal: Dinheiro,
        saldoConta: Dinheiro,
        patrimonio: Dinheiro,
        planos: List<PlanoEmProjecao>,
        inicio: LocalDate,
        meses: Int = 12,
        cenario: String = "base",
        /**
         * Inteiro porque é o que o workspace guarda. Se um dia virar fracionário
         * (o perfil de renda variável sugere 9,0 meses para *compras*, não para
         * a projeção), ele entra aqui na mesma escala dos outros valores.
         */
        reservaAlvoMeses: Int = 6,
    ): Resultado {
        val fator = cenarioDe(cenario)

        // tudo abaixo em centésimos de centavo, e nada se arredonda até a saída
        val rendaE = rendaMediaMes.centavos * fator.rendaPct
        val fixoE = custoFixoMensal.centavos * ESCALA
        // `max(despesa - fixo, 0)`: custo fixo maior que a despesa total zera o
        // variável, em vez de virar um variável negativo que daria sobra falsa
        val variavelE =
            maxOf(despesaMediaMes.centavos - custoFixoMensal.centavos, 0L) * fator.variavelPct
        val sobraE = rendaE - fixoE - variavelE

        var caixaE = saldoConta.centavos * ESCALA
        var guardadoE = patrimonio.centavos * ESCALA - caixaE

        val trilhas = planos
            .filter { it.status != "concluido" }
            .map { Trilha(it) }
            // `sortedBy` é estável, como o `list.sort` do Python: dois planos de
            // mesma prioridade mantêm a ordem em que chegaram
            .sortedBy { ORDEM[it.plano.prioridade] ?: 1 }

        val linhas = ArrayList<Linha>(meses)
        for (i in 0 until meses) {
            val mes = mesDe(inicio, i)
            var destinadoE = 0L

            for (t in trilhas) {
                if (t.faltaE <= 0) continue
                val disponivelE = maxOf(sobraE - destinadoE, 0L)
                val desejadoE = if (t.aporteE > 0) t.aporteE else disponivelE
                val aporteE = minOf(desejadoE, disponivelE, t.faltaE)
                if (aporteE <= 0) continue
                t.faltaE -= aporteE
                destinadoE += aporteE
                if (t.faltaE <= 0 && t.concluidoEm == null) t.concluidoEm = mes
            }

            val livreE = sobraE - destinadoE
            guardadoE += destinadoE + maxOf(livreE, 0L)
            // só mês negativo mexe no caixa; o positivo já foi para o guardado
            caixaE += minOf(livreE, 0L)

            linhas += Linha(
                mes = mes,
                renda = emCentavos(rendaE),
                custoFixo = emCentavos(fixoE),
                custoVariavel = emCentavos(variavelE),
                sobra = emCentavos(sobraE),
                aportesEmPlanos = emCentavos(destinadoE),
                patrimonioProjetado = emCentavos(guardadoE + caixaE),
            )
        }

        val reservaAlvoE = (fixoE + variavelE) * reservaAlvoMeses
        // o Python compara o patrimônio **já arredondado** da linha contra o
        // alvo **não arredondado**. Trocar um pelo outro muda o mês em que a
        // meta fecha, que é a resposta que a pessoa leva da tela
        val atingidaEm = linhas
            .firstOrNull { it.patrimonioProjetado.centavos * ESCALA >= reservaAlvoE }?.mes

        return Resultado(
            cenario = cenario,
            rendaMensal = emCentavos(rendaE),
            custoFixo = emCentavos(fixoE),
            custoVariavel = emCentavos(variavelE),
            sobraMensal = emCentavos(sobraE),
            fixoPctDaRenda = if (rendaE != 0L) {
                arredondar(fixoE.toDouble() / rendaE.toDouble() * 100, 1)
            } else 0.0,
            linhas = linhas,
            planos = trilhas.map {
                PlanoProjetado(
                    id = it.plano.id,
                    nome = it.plano.nome,
                    faltaAoFim = maxOf(it.faltaE, 0L) / (ESCALA * 100.0),
                    concluiEm = it.concluidoEm,
                )
            },
            reservaAlvo = emCentavos(reservaAlvoE),
            reservaAtingidaEm = atingidaEm,
        )
    }

    /** Todos os cenários de uma vez, como o `all_scenarios` do Python. */
    fun todosOsCenarios(
        rendaMediaMes: Dinheiro,
        despesaMediaMes: Dinheiro,
        custoFixoMensal: Dinheiro,
        saldoConta: Dinheiro,
        patrimonio: Dinheiro,
        planos: List<PlanoEmProjecao>,
        inicio: LocalDate,
        meses: Int = 12,
        reservaAlvoMeses: Int = 6,
    ): Map<String, Resultado> = CENARIOS.associate { c ->
        c.nome to projetar(
            rendaMediaMes, despesaMediaMes, custoFixoMensal, saldoConta, patrimonio,
            planos, inicio, meses, c.nome, reservaAlvoMeses,
        )
    }

    private class Trilha(val plano: PlanoEmProjecao) {
        var faltaE: Long = plano.falta.centavos * ESCALA
        val aporteE: Long = plano.aportePlanejado.centavos * ESCALA
        var concluidoEm: String? = null
    }

    /**
     * Da escala fina para centavos, meio-para-o-par.
     *
     * Reaproveita a divisão de [Dinheiro] em vez de repetir a regra de empate:
     * o valor escalado cabe num `Long` e dividi-lo por [ESCALA] devolve o mesmo
     * que o `quantize(Decimal("0.01"))` do Python.
     */
    private fun emCentavos(escalado: Long): Dinheiro = Dinheiro(escalado).dividir(ESCALA)

    /** "2026-06" somando `n` meses ao início, como `_add_months` + `strftime`. */
    private fun mesDe(inicio: LocalDate, n: Int): String {
        val total = inicio.year * 12 + (inicio.monthNumber - 1) + n
        val ano = total / 12
        val mes = total % 12 + 1
        return "$ano-${mes.toString().padStart(2, '0')}"
    }
}
