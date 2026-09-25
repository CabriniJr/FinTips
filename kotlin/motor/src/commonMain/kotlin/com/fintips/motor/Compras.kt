package com.fintips.motor

import kotlinx.datetime.DatePeriod
import kotlinx.datetime.LocalDate
import kotlinx.datetime.minus

/**
 * Consultor de compras: o que é calculável sobre uma intenção de compra.
 *
 * O motor devolve impacto no caixa, custo em meses de sobra, atraso em cada
 * plano, sinais de arrependimento tirados do próprio histórico e as estratégias
 * com o trade-off de cada uma. **Nada aqui é conselho** — a recomendação é
 * escrita por quem conversou com a pessoa, em cima destes números.
 *
 * ## O que ainda não está portado
 *
 * `contexto_pessoal` e `precedentes` dependem de Perfil, Causas e Decisões, que
 * são o item 9 da ordem do porte. Ficam de fora até lá, e o ouro declara isso
 * em `fora_do_escopo` em vez de fingir que o módulo está inteiro.
 *
 * ## Onde a porta quase errou
 *
 * O múltiplo do ticket típico (`preço é Nx o seu ticket`) dispara com
 * `multiplo > 10`. A mediana de uma contagem par cai no meio centavo — 950,005
 * no ouro — e o Python a reconstrói com `Decimal(str(mediana))`, que é o
 * decimal exato `950.005`. Em `Double`, 950,005 é na verdade
 * 950,00499999999999545, e um preço de exatamente 9500,05 daria
 * `10.0000000000005`: o sinal dispararia no Kotlin e não no Python.
 *
 * A saída é aritmética inteira. Toda mediana de centavos é um inteiro (contagem
 * ímpar) ou um meio-inteiro (contagem par), então ela cabe em
 * [Arrependimento.tickerNumerador] — a soma dos dois centrais, com denominador
 * fixo 2. A comparação vira `preço × 2 > ticket × 10` em `Long`, exata.
 */
object Compras {

    /** Gasto de porte parecido: metade do preço, com `>=`. */
    private const val JANELA_DIAS = 60

    data class Intencao(
        val item: String,
        val preco: Dinheiro,
        val categoria: String = "compras",
        val urgencia: String = "media",
        val parcelasPossiveis: Int = 1,
        /** % ao mês; 0 = sem juros. */
        val jurosParcelamento: Double = 0.0,
        /** O que essa compra substitui, se substitui. */
        val substitui: String = "",
        val tags: List<String> = emptyList(),
    )

    data class CompraSemelhante(val dia: String, val onde: String, val valor: Dinheiro)

    data class Arrependimento(
        val risco: Int,
        val sinais: List<String>,
        val comprasSemelhantesRecentes: List<CompraSemelhante>,
        /**
         * Soma dos dois centrais em centavos (denominador 2). Zero quando não
         * há histórico. É o que mantém a comparação do múltiplo exata.
         */
        val tickerNumerador: Long,
    ) {
        val ticketMedioCategoria: Double get() = tickerNumerador / 200.0

        fun paraMapa(): Map<String, Any?> = linkedMapOf(
            "risco_arrependimento" to risco,
            "sinais" to sinais,
            "compras_semelhantes_recentes" to comprasSemelhantesRecentes.map {
                linkedMapOf("data" to it.dia, "onde" to it.onde, "valor" to it.valor.paraDouble())
            },
            "ticket_medio_categoria" to ticketMedioCategoria,
        )
    }

    /** As chaves mudam por estratégia, como no Python — por isso um mapa. */
    data class Estrategia(val nome: String, val viavel: Boolean, val campos: Map<String, Any?>)

    data class ImpactoNoPlano(
        val plano: String,
        val atrasoEmMeses: Double?,
        val folgaAposCompra: Double,
        val conflito: Boolean,
    ) {
        fun paraMapa(): Map<String, Any?> = linkedMapOf(
            "plano" to plano,
            "atraso_em_meses" to atrasoEmMeses,
            "folga_apos_compra" to folgaAposCompra,
            "conflito" to conflito,
        )
    }

    /** Um plano como o consultor o enxerga: só o que muda a conta da compra. */
    data class PlanoAvaliado(
        val nome: String,
        val status: String,
        val aporteNecessarioMes: Dinheiro,
    )

    data class Veredito(
        val item: String,
        val preco: Dinheiro,
        val veredito: String,
        val scorePrudencia: Int,
        val custoEmMesesDeSobra: Double?,
        val reservaAlvoMeses: Double,
        val reservaAlvoValor: Dinheiro,
        val excedenteDisponivel: Dinheiro,
        val compraFuraReserva: Boolean,
        val arrependimento: Arrependimento,
        val estrategias: List<Estrategia>,
        val impactoNosPlanos: List<ImpactoNoPlano>,
        val melhorEstrategia: String,
    ) {
        fun paraMapa(): Map<String, Any?> = linkedMapOf(
            "item" to item,
            "preco" to preco.paraDouble(),
            "veredito" to veredito,
            "score_prudencia" to scorePrudencia,
            "custo_em_meses_de_sobra" to custoEmMesesDeSobra,
            "reserva" to linkedMapOf(
                "alvo_meses" to reservaAlvoMeses,
                "alvo_valor" to reservaAlvoValor.paraDouble(),
                "excedente_disponivel" to excedenteDisponivel.paraDouble(),
                "compra_fura_reserva" to compraFuraReserva,
            ),
            "arrependimento" to arrependimento.paraMapa(),
            "estrategias" to estrategias.map { it.campos },
            "impacto_nos_planos" to impactoNosPlanos.map { it.paraMapa() },
            "melhor_estrategia" to melhorEstrategia,
        )
    }

    // ----------------------------------------------------------- histórico

    private fun historicoDaCategoria(
        extrato: Extrato, categoria: String, palavrasChave: List<String>,
    ): List<Transacao> {
        val chaves = palavrasChave.filter { it.isNotEmpty() }.map { norm(it) }
        return extrato.transacoes.filter { t ->
            t.fluxo == Fluxos.DESPESA && (
                t.categoria == categoria ||
                    (chaves.isNotEmpty() && chaves.any { it in norm(t.contraparte) })
                )
        }
    }

    /**
     * Mediana em centavos, devolvida como numerador sobre 2.
     *
     * Contagem ímpar dobra o valor central; par soma os dois. Nos dois casos o
     * resultado é exato, e é essa exatidão que evita o falso positivo do
     * múltiplo de 10x.
     */
    private fun medianaDobrada(valores: List<Long>): Long {
        if (valores.isEmpty()) return 0
        val ordenados = valores.sorted()
        val meio = ordenados.size / 2
        return if (ordenados.size % 2 == 1) ordenados[meio] * 2
        else ordenados[meio - 1] + ordenados[meio]
    }

    fun sinaisDeArrependimento(
        intencao: Intencao, extrato: Extrato, despesaMediaMes: Dinheiro,
    ): Arrependimento {
        val hist = historicoDaCategoria(extrato, intencao.categoria, intencao.tags)
        val corte = extrato.periodoFim.minus(DatePeriod(days = JANELA_DIAS))
        // `>=`: o gasto que cai exatamente no limite da janela entra
        val ultimos60 = hist.filter { it.dia >= corte }
        // `abs(valor) >= preço * 0.5`, multiplicado cruzado para não sair dos inteiros
        val grandesRecentes = ultimos60.filter { it.valor.absoluto.centavos * 2 >= intencao.preco.centavos }

        val estornos = extrato.transacoes.filter {
            it.fluxo == Fluxos.ESTORNO && it.valor.absoluto >= Dinheiro.deReais(50)
        }

        val tickerNumerador = medianaDobrada(hist.map { it.valor.absoluto.centavos })

        val sinais = mutableListOf<String>()
        if (grandesRecentes.isNotEmpty()) {
            sinais += "${grandesRecentes.size} compra(s) de porte parecido na mesma " +
                "categoria nos últimos 60 dias"
        }
        // `multiplo > 10` exato: preço × 2 contra ticket × 10
        if (tickerNumerador > 0 && intencao.preco.centavos * 2 > tickerNumerador * 10) {
            val multiplo = 2.0 * intencao.preco.centavos / tickerNumerador
            val arredondado = arredondar(multiplo, 0).toLong()
            sinais += "preço é ${arredondado}x o seu ticket típico nessa categoria"
        }
        if (despesaMediaMes > Dinheiro.ZERO && intencao.preco > despesaMediaMes) {
            sinais += "o item custa mais que um mês inteiro da sua despesa média"
        }
        if (intencao.urgencia == "alta" && intencao.substitui.isEmpty()) {
            sinais += "marcada como urgente sem substituir nada — típico de compra por impulso"
        }
        if (estornos.size >= 3) {
            sinais += "${estornos.size} estornos/devoluções no período (histórico de compra revertida)"
        }

        return Arrependimento(
            risco = minOf(100, 20 * sinais.size),
            sinais = sinais,
            comprasSemelhantesRecentes = grandesRecentes
                .sortedByDescending { it.momento.instante }
                .take(5)
                .map { CompraSemelhante(it.dia.toString(), it.contraparte, it.valor.absoluto) },
            tickerNumerador = tickerNumerador,
        )
    }

    // --------------------------------------------------------- estratégias

    fun estrategias(
        intencao: Intencao, sobraMediaMes: Dinheiro, saldoDisponivel: Dinheiro,
    ): List<Estrategia> {
        val out = mutableListOf<Estrategia>()

        val cabeAVista = saldoDisponivel >= intencao.preco
        out += Estrategia(
            nome = "a_vista_agora", viavel = cabeAVista,
            campos = linkedMapOf(
                "estrategia" to "a_vista_agora",
                "custo_total" to intencao.preco.paraDouble(),
                "impacto_caixa_imediato" to intencao.preco.paraDouble(),
                "saldo_apos" to (saldoDisponivel - intencao.preco).paraDouble(),
                "viavel" to cabeAVista,
                "observacao" to "sem juros; derruba a liquidez imediata",
            ),
        )

        // teto da divisão: sobrar um centavo já custa um mês inteiro de espera
        val meses = if (sobraMediaMes > Dinheiro.ZERO) {
            ((intencao.preco.centavos + sobraMediaMes.centavos - 1) / sobraMediaMes.centavos).toInt()
        } else null
        out += Estrategia(
            nome = "juntar_e_comprar", viavel = meses != null,
            campos = linkedMapOf(
                "estrategia" to "juntar_e_comprar",
                "custo_total" to intencao.preco.paraDouble(),
                "meses_necessarios" to meses,
                "aporte_mensal" to
                    (if (sobraMediaMes > Dinheiro.ZERO) sobraMediaMes.paraDouble() else 0.0),
                "viavel" to (meses != null),
                // repare na diferença, que é do Python e é fácil de perder: a
                // viabilidade testa `meses is not None`, e o texto testa `if
                // meses` — onde zero é falso. Com preço zero, o cenário é viável
                // e mesmo assim diz que a sobra não financia a compra
                "observacao" to (
                    if (meses != null && meses != 0)
                        "no ritmo atual de sobra, o item se paga em $meses mês(es) sem tocar na reserva"
                    else "sobra mensal atual não financia a compra"
                    ),
            ),
        )

        if (intencao.parcelasPossiveis > 1) {
            val n = intencao.parcelasPossiveis
            val i = intencao.jurosParcelamento / 100
            val parcela = if (i > 0) {
                // fórmula Price. O Python calcula em Decimal; em Double o valor
                // bateu nas 105 combinações do teste que precedeu esta porta,
                // e o ouro cobra cada uma das que ficaram
                val potencia = pot(1 + i, n)
                val fator = (i * potencia) / (potencia - 1)
                deReaisDouble(intencao.preco.paraDouble() * fator)
            } else {
                // sem juros o Python divide em Decimal: 2599,99 ÷ 2 dá 1300,00,
                // e não 1299,99 como sairia arredondando o Double
                intencao.preco.dividir(n)
            }
            val total = parcela * n
            val viavel = sobraMediaMes > parcela
            out += Estrategia(
                nome = "parcelado", viavel = viavel,
                campos = linkedMapOf(
                    "estrategia" to "parcelado",
                    "parcelas" to n,
                    "valor_parcela" to parcela.paraDouble(),
                    "custo_total" to total.paraDouble(),
                    "custo_do_credito" to (total - intencao.preco).paraDouble(),
                    "pct_da_sobra_mensal" to (
                        if (sobraMediaMes > Dinheiro.ZERO)
                            arredondar(parcela.centavos.toDouble() / sobraMediaMes.centavos * 100, 1)
                        else null
                        ),
                    "viavel" to viavel,
                    "observacao" to
                        "compromete sobra futura; só vale se o dinheiro parado render mais que o juro",
                ),
            )
        }
        return out
    }

    fun impactoNosPlanos(
        intencao: Intencao, planos: List<PlanoAvaliado>, sobraMediaMes: Dinheiro,
    ): List<ImpactoNoPlano> = planos
        .filter { it.status != Planos.Status.CONCLUIDO }
        .map { p ->
            val aporte = p.aporteNecessarioMes
            val atraso = if (aporte > Dinheiro.ZERO) {
                intencao.preco.centavos.toDouble() / aporte.centavos
            } else null
            ImpactoNoPlano(
                plano = p.nome,
                // `round(atraso, 1) if atraso else None`: zero é falso em Python,
                // então um atraso de 0.0 também sai como nulo
                atrasoEmMeses = if (atraso != null && atraso != 0.0) arredondar(atraso, 1) else null,
                // `if aporte` — mesmo detalhe: aporte zero cai no ramo do else
                folgaAposCompra = if (!aporte.zero) (sobraMediaMes - aporte).paraDouble()
                else sobraMediaMes.paraDouble(),
                conflito = atraso != null && atraso != 0.0 && atraso >= 1 &&
                    p.status in setOf(Planos.Status.APERTADO, Planos.Status.INVIAVEL),
            )
        }

    // ------------------------------------------------------------ veredito

    fun avaliar(
        intencao: Intencao,
        extrato: Extrato,
        despesaMediaMes: Dinheiro,
        sobraMediaMes: Dinheiro,
        planos: List<PlanoAvaliado>,
        saldoConta: Dinheiro,
        patrimonio: Dinheiro,
        reservaAlvoMeses: Double = 6.0,
    ): Veredito {
        // a reserva-alvo pode ter sub-centavo quando os meses são fracionários
        // (o traço de renda variável sugere 9,0; um dia pode sugerir 9,5)
        val mesesCentesimos = arredondar(reservaAlvoMeses * 100, 0).toLong()
        val reservaAlvoE = despesaMediaMes.centavos * mesesCentesimos
        val excedenteE = (patrimonio.centavos + saldoConta.centavos) * 100 - reservaAlvoE

        val arrependimento = sinaisDeArrependimento(intencao, extrato, despesaMediaMes)
        val cen = estrategias(intencao, sobraMediaMes, saldoConta + patrimonio)
        val impacto = impactoNosPlanos(intencao, planos, sobraMediaMes)

        val custoEmMeses = if (sobraMediaMes > Dinheiro.ZERO) {
            intencao.preco.centavos.toDouble() / sobraMediaMes.centavos
        } else null
        val furaReserva = intencao.preco.centavos * 100 > excedenteE
        val temConflito = impacto.any { it.conflito }

        val veredito = when {
            furaReserva && (custoEmMeses ?: 0.0) > 3 -> "nao_agora"
            arrependimento.risco >= 60 -> "espere_30_dias"
            furaReserva -> "juntar_antes"
            temConflito -> "escolha_entre_plano_e_compra"
            (custoEmMeses ?: 0.0) <= 1 -> "pode_comprar"
            else -> "cabe_com_planejamento"
        }

        val prudencia = maxOf(
            0,
            100 - arrependimento.risco - (if (furaReserva) 25 else 0) -
                (if (temConflito) 15 else 0),
        )

        return Veredito(
            item = intencao.item,
            preco = intencao.preco,
            veredito = veredito,
            scorePrudencia = prudencia,
            // `round(custo, 2) if custo else None`: zero é falso, de novo
            custoEmMesesDeSobra =
                if (custoEmMeses != null && custoEmMeses != 0.0) arredondar(custoEmMeses, 2) else null,
            reservaAlvoMeses = reservaAlvoMeses,
            reservaAlvoValor = Dinheiro(reservaAlvoE).dividir(100),
            excedenteDisponivel = Dinheiro(excedenteE).dividir(100),
            compraFuraReserva = furaReserva,
            arrependimento = arrependimento,
            estrategias = cen,
            impactoNosPlanos = impacto,
            melhorEstrategia = melhorEstrategia(cen, furaReserva, arrependimento.risco),
        )
    }

    fun melhorEstrategia(cen: List<Estrategia>, furaReserva: Boolean, risco: Int): String {
        val viaveis = cen.filter { it.viavel }
        if (viaveis.isEmpty()) return "juntar_e_comprar"
        if (risco >= 60) return "juntar_e_comprar"      // tempo é o melhor filtro de impulso
        if (furaReserva) return "juntar_e_comprar"
        val aVista = viaveis.firstOrNull { it.nome == "a_vista_agora" }
        val parcelado = viaveis.firstOrNull { it.nome == "parcelado" }
        if (parcelado != null && parcelado.campos["custo_do_credito"] == 0.0 && aVista != null) {
            return "parcelado"                           // sem juros, mantém a liquidez rendendo
        }
        return aVista?.nome ?: viaveis.first().nome
    }

    // ------------------------------------------------------------ auxílios

    /** Potência inteira, sem depender de `Math.pow` de nenhum alvo. */
    private fun pot(base: Double, expoente: Int): Double {
        var r = 1.0
        repeat(expoente) { r *= base }
        return r
    }

    /**
     * Reais em `Double` para centavos, meio-para-o-par sobre o valor exato.
     *
     * Em dois passos de propósito: o primeiro reproduz o `quantize` do Python
     * sobre o valor cheio; o segundo só tira o resto binário de multiplicar por
     * cem um número que já tem duas casas.
     */
    private fun deReaisDouble(reais: Double): Dinheiro =
        Dinheiro(arredondar(arredondar(reais, 2) * 100, 0).toLong())
}
