package com.fintips.motor

import kotlinx.datetime.LocalDate

/**
 * Causas: por que o dinheiro sai, e o que se decidiu sobre isso.
 *
 * O motor sempre soube **o quê** e **quanto**. Faltava o **porquê** — e sem ele
 * qualquer conselho é palpite bem calculado. Duas pessoas gastam R$ 400 por mês
 * em delivery: uma tem jornada dupla e chega às 22h, a outra tem tédio de
 * domingo. Mesmo número, mesma categoria, respostas opostas — e nenhum extrato
 * do mundo distingue as duas.
 *
 * Por isso **este arquivo não tem detecção, e não deve ter**. Não existe
 * `detectarCausas()` aqui. O que ele faz é guardar a causa ligada ao dinheiro
 * que ela explica, recusar o que não pode ser afirmado, cobrar revisão quando
 * ela envelhece, e medir quanto da despesa ainda não tem explicação nenhuma.
 *
 * ## O que ainda não está portado
 *
 * A persistência em YAML é o item 10 da ordem do porte. Este registro vive em
 * memória: a validação, os filtros por prazo e a cobertura são a parte que
 * decide comportamento, e é ela que o ouro cobra.
 */
object Causas {

    /** O que uma causa pode explicar. Fechado: o índice do dossiê conta com isso. */
    val EFEITOS = listOf("categoria", "contraparte", "padrao", "mes", "plano", "compromisso")

    /** Quantas categorias sem causa entram na lista do que perguntar primeiro. */
    private const val MAIORES_SEM_CAUSA = 8

    data class LinhaSemCausa(val categoria: String, val total: Dinheiro, val porMes: Dinheiro) {
        fun paraMapa(): Map<String, Any?> = linkedMapOf(
            "categoria" to categoria,
            "total" to total.paraDouble(),
            "por_mes" to porMes.paraDouble(),
        )
    }

    data class Cobertura(
        val despesaTotal: Dinheiro,
        val comCausa: Dinheiro,
        val semCausa: Dinheiro,
        val coberturaPct: Double,
        val causas: Int,
        val semAtitude: Int,
        val aRevisar: Int,
        val maioresSemCausa: List<LinhaSemCausa>,
    ) {
        fun paraMapa(): Map<String, Any?> = linkedMapOf(
            "despesa_total" to despesaTotal.paraDouble(),
            "com_causa" to comCausa.paraDouble(),
            "sem_causa" to semCausa.paraDouble(),
            "cobertura_pct" to coberturaPct,
            "causas" to causas,
            "sem_atitude" to semAtitude,
            "a_revisar" to aRevisar,
            "maiores_sem_causa" to maioresSemCausa.map { it.paraMapa() },
            "explicacao" to (
                "percentual da despesa que alguém explicou. O resto é dinheiro " +
                    "saindo por um motivo que ninguém escreveu ainda"
                ),
        )
    }

    /**
     * As causas gravadas, indexadas pelo que explicam.
     *
     * Em memória por enquanto — ver a nota sobre o item 10 acima.
     */
    class Registro(causas: List<Causa> = emptyList()) {
        private val porId = LinkedHashMap<String, Causa>()

        init {
            causas.forEach { porId[it.id] = it }
        }

        val todas: List<Causa> get() = porId.values.sortedBy { it.alvo }

        /**
         * Grava uma causa, ou recusa.
         *
         * As recusas **são** o produto em código, e cada uma fecha um jeito
         * diferente de o app passar a inventar motivo:
         *
         * - origem sem autoridade — causa não se deriva de dado nenhum;
         * - `porque` vazio — sem isso a decisão não é auditável depois;
         * - enunciado vazio — causa sem frase é rótulo;
         * - efeito desconhecido ou sem referência — causa que não aponta para
         *   dinheiro nenhum não explica nada;
         * - atitude fora da lista — o dossiê e as alavancas calculam em cima
         *   dela, e uma atitude inventada no meio da conversa não entraria em
         *   conta nenhuma.
         *
         * A natureza, ao contrário da atitude, é lista **aberta**: o motor
         * valida a forma, não o conteúdo, porque a vida de alguém pode pedir
         * uma palavra que não está no catálogo.
         */
        fun gravar(
            efeitoTipo: String,
            efeitoRef: String,
            natureza: String,
            enunciado: String,
            proveniencia: Proveniencia,
            atitude: Atitude = Atitude.NENHUMA,
            atitudeNota: String = "",
            evidencia: List<String> = emptyList(),
            revisarEm: String? = null,
            criadoEm: String = "",
            /**
             * Data de referência do desempate abaixo. O Python lê o relógio da
             * máquina nesse ponto; a porta recebe a data, que é o que torna o
             * caso reproduzível nos dois motores — e o que evita um relógio
             * escondido dentro de uma regra de negócio.
             */
            hoje: LocalDate,
        ): Causa {
            require(proveniencia.eVerdade) {
                "causa só aceita origem 'agente' ou 'usuario'. Não existe causa " +
                    "derivada dos dados: o extrato mostra o gasto, nunca o motivo"
            }
            require(proveniencia.porque.isNotEmpty()) {
                "gravar uma causa exige `porque` — o que te fez concluir isso"
            }
            require(enunciado.isNotBlank()) {
                "causa sem enunciado é rótulo; escreva a frase que a pessoa disse"
            }
            require(efeitoTipo in EFEITOS) { "efeito_tipo deve ser um de $EFEITOS" }
            require(efeitoRef.isNotBlank()) {
                "causa precisa apontar o que ela explica (efeito_ref)"
            }
            require(natureza.isNotBlank()) {
                "causa precisa de natureza — ver NATUREZAS_SUGERIDAS, mas a lista é aberta"
            }

            val id = novoId("causa", efeitoTipo, efeitoRef, natureza)
            val atual = porId[id]
            // autoridade maior não é derrubada por menor — o palpite do agente
            // não apaga o que a pessoa afirmou. Causa vencida, porém, cede
            if (atual != null &&
                atual.proveniencia.autoridade > proveniencia.autoridade &&
                !atual.vencida(hoje)
            ) {
                return atual
            }

            val causa = Causa(
                id = id,
                efeitoTipo = efeitoTipo,
                efeitoRef = efeitoRef,
                natureza = natureza.trim(),
                enunciado = enunciado.trim(),
                atitude = atitude,
                atitudeNota = atitudeNota,
                evidencia = evidencia,
                proveniencia = proveniencia,
                revisarEm = revisarEm,
                criadoEm = atual?.criadoEm ?: criadoEm,
            )
            porId[id] = causa
            return causa
        }

        /**
         * Registra a atitude sobre uma causa já entendida.
         *
         * Separado de [gravar] porque entender e decidir acontecem em momentos
         * diferentes — às vezes com semanas entre um e outro, que é o tempo
         * normal de mudar de ideia sobre o próprio comportamento.
         */
        fun decidir(causaId: String, atitude: Atitude, nota: String = ""): Causa {
            val causa = porId[causaId] ?: throw IllegalArgumentException(
                "causa '$causaId' não existe",
            )
            val nova = causa.copy(atitude = atitude, atitudeNota = nota)
            porId[causaId] = nova
            return nova
        }

        fun esquecer(causaId: String): Boolean = porId.remove(causaId) != null

        fun para(efeitoTipo: String, efeitoRef: String): List<Causa> =
            porId.values.filter { it.efeitoTipo == efeitoTipo && it.efeitoRef == efeitoRef }

        fun ativas(hoje: LocalDate): List<Causa> = porId.values.filter { !it.vencida(hoje) }

        fun vencidas(hoje: LocalDate): List<Causa> = porId.values.filter { it.vencida(hoje) }

        /** Entendidas e sem decisão: diagnóstico sem tratamento. */
        fun semAtitude(hoje: LocalDate): List<Causa> =
            ativas(hoje).filter { it.atitude == Atitude.NENHUMA }

        /** Índice pronto para correlação: alvo → causas que o explicam. */
        fun porAlvo(): Map<String, List<Causa>> =
            porId.values.groupBy { it.alvo }

        /**
         * Quanto da despesa tem causa, e quanto ainda é dinheiro sem explicação.
         *
         * Espelha a cobertura da classificação, e a diferença entre as duas é a
         * pergunta que cada uma responde: aquela diz se o dinheiro está no
         * balde certo, esta diz se alguém sabe por que ele saiu. As duas
         * começam em 0%, e é assim que deve ser.
         *
         * Causa vencida **não** entra: quando o prazo de revisão passa, a
         * cobertura cai sozinha e a fila de triagem volta a cobrar. Continuar
         * contando com ela seria supor que a vida não mudou.
         */
        fun cobertura(extrato: Extrato, hoje: LocalDate): Cobertura {
            val ativas = ativas(hoje)
            val cats = ativas.filter { it.efeitoTipo == "categoria" }.map { it.efeitoRef }.toSet()
            val cps = ativas.filter { it.efeitoTipo == "contraparte" }.map { it.efeitoRef }.toSet()

            var total = 0L
            var explicado = 0L
            val semCausaPorCategoria = LinkedHashMap<String, Long>()
            for (t in extrato.transacoes) {
                if (t.fluxo != Fluxos.DESPESA) continue
                val v = t.valor.absoluto.centavos
                total += v
                if (t.categoria in cats || t.contraparte in cps) {
                    explicado += v
                } else {
                    semCausaPorCategoria[t.categoria] =
                        (semCausaPorCategoria[t.categoria] ?: 0L) + v
                }
            }

            // meses **distintos** do extrato, não o período em dias
            val nMeses = maxOf(extrato.transacoes.map { it.mes }.toSet().size, 1)

            return Cobertura(
                despesaTotal = Dinheiro(total),
                comCausa = Dinheiro(explicado),
                semCausa = Dinheiro(total - explicado),
                coberturaPct = if (total != 0L) {
                    arredondar(explicado.toDouble() / total * 100, 1)
                } else 0.0,
                causas = porId.size,
                semAtitude = semAtitude(hoje).size,
                aRevisar = vencidas(hoje).size,
                maioresSemCausa = semCausaPorCategoria.entries
                    .sortedByDescending { it.value }
                    .take(MAIORES_SEM_CAUSA)
                    .map {
                        LinhaSemCausa(
                            categoria = it.key,
                            total = Dinheiro(it.value),
                            porMes = Dinheiro(it.value).dividir(nMeses),
                        )
                    },
            )
        }
    }
}
