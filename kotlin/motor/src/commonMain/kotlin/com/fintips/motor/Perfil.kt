package com.fintips.motor

import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.log10

/**
 * Perfil financeiro: arquétipos casados por número, assinados por gente.
 *
 * É a única parte do motor que tenta dizer **quem** a pessoa é, e por isso a
 * que mais precisa da disciplina de proveniência. O desenho separa duas coisas
 * que quase todo app de finanças confunde:
 *
 * - **sugestão** — o catálogo casado contra os indicadores do próprio extrato.
 *   Sai com origem `importacao`: é palpite, tem evidência anexada, e não é
 *   gravado em lugar nenhum;
 * - **perfil assinado** — o que o agente concluiu depois de conversar, ou o que
 *   a pessoa afirmou. Só isso o resto do motor pode tratar como verdade.
 *
 * A consequência prática: rodar a análise mil vezes nunca cria perfil. Um
 * extrato com sobra alta sugere `acumulacao`, mas quem sabe se aquilo foi um
 * mês de férias na casa da mãe é a pessoa.
 *
 * Os eixos são independentes de propósito. Perfil único — "o poupador", "o
 * gastador" — é horóscopo: descreve todo mundo e não muda conta nenhuma.
 *
 * ## O que ainda não está portado
 *
 * Carregar o catálogo do YAML é o item 10; aqui ele chega pronto, como dado.
 * `indicadores()` depende do contexto inteiro da análise, que ainda não existe
 * do lado Kotlin — o casamento recebe o mapa de indicadores.
 */
object Perfil {

    /**
     * Um sinal: a faixa que um indicador precisa ocupar para o arquétipo casar.
     *
     * Indicador ausente **não casa**. Sem isso, um extrato curto casaria
     * arquétipo por omissão, que é o jeito mais silencioso de o app inventar
     * quem a pessoa é.
     */
    data class Sinal(
        val indicador: String,
        val minimo: Double? = null,
        val maximo: Double? = null,
        val peso: Double = 1.0,
    ) {
        fun casa(valor: Double?): Boolean {
            if (valor == null) return false
            if (minimo != null && valor < minimo) return false
            if (maximo != null && valor > maximo) return false
            return true
        }

        /** Evidência legível: o número observado e a faixa que ele precisava ocupar. */
        fun descrever(valor: Double?): String {
            val obs = if (valor == null) "sem dado" else formatoG(valor)
            val faixa = when {
                minimo != null && maximo != null ->
                    "entre ${formatoG(minimo)} e ${formatoG(maximo)}"
                minimo != null -> "≥ ${formatoG(minimo)}"
                maximo != null -> "≤ ${formatoG(maximo)}"
                else -> "qualquer valor"
            }
            return "$indicador = $obs (esperado $faixa)"
        }
    }

    data class Avaliacao(
        val id: String,
        val nome: String,
        val descricao: String,
        val oQueMuda: String,
        val aderencia: Double,
        val evidencia: List<String>,
        val contra: List<String>,
    ) {
        fun paraMapa(): Map<String, Any?> = linkedMapOf(
            "id" to id,
            "nome" to nome,
            "descricao" to descricao,
            "o_que_muda" to oQueMuda,
            "aderencia" to aderencia,
            "evidencia" to evidencia,
            "contra" to contra,
        )
    }

    data class Arquetipo(
        val id: String,
        val nome: String,
        val descricao: String,
        val oQueMuda: String,
        val eixo: String,
        val sinais: List<Sinal> = emptyList(),
    ) {
        /** Casa os sinais contra os indicadores. Devolve aderência e evidência. */
        fun avaliar(ind: Map<String, Double?>): Avaliacao {
            val total = sinais.sumOf { it.peso }.let { if (it == 0.0) 1.0 else it }
            var casados = 0.0
            val evidencia = mutableListOf<String>()
            val contra = mutableListOf<String>()
            for (s in sinais) {
                val valor = ind[s.indicador]
                if (s.casa(valor)) {
                    casados += s.peso
                    evidencia += s.descrever(valor)
                } else {
                    contra += s.descrever(valor)
                }
            }
            return Avaliacao(
                id = id, nome = nome, descricao = descricao, oQueMuda = oQueMuda,
                aderencia = arredondar(casados / total, 2),
                evidencia = evidencia, contra = contra,
            )
        }
    }

    data class Eixo(
        val id: String,
        val nome: String,
        val oQueE: String,
        val minimo: Double,
        val arquetipos: List<Arquetipo>,
    )

    data class Leitura(
        val eixo: String,
        val nome: String,
        val oQueE: String,
        val minimo: Double,
        val sugerido: Avaliacao?,
        val candidatos: List<Avaliacao>,
        val semLeituraPorque: String?,
    ) {
        fun paraMapa(): Map<String, Any?> = linkedMapOf(
            "eixo" to eixo,
            "nome" to nome,
            "o_que_e" to oQueE,
            "minimo" to minimo,
            "sugerido" to sugerido?.paraMapa(),
            "candidatos" to candidatos.map { it.paraMapa() },
            "sem_leitura_porque" to semLeituraPorque,
        )
    }

    /**
     * Sugere um arquétipo por eixo, com aderência e evidência.
     *
     * O resultado é sempre palpite derivado dos dados. Abaixo do mínimo do
     * eixo, ou havendo empate no topo, devolve `sugerido = null` em vez de
     * forçar o menos ruim: **não ter leitura é um estado honesto**, e a triagem
     * prefere perguntar a chutar.
     *
     * A ordenação é estável de propósito. Com ordenação instável, dois
     * arquétipos empatados devolveriam um vencedor diferente a cada execução —
     * e o empate, que é a informação útil, nunca seria acusado.
     */
    fun casar(indicadores: Map<String, Double?>, catalogo: List<Eixo>): List<Leitura> =
        catalogo.map { eixo ->
            val avaliados = eixo.arquetipos.map { it.avaliar(indicadores) }
                .sortedByDescending { it.aderencia }
            val melhor = avaliados.firstOrNull()
            val empate = avaliados.size > 1 && melhor != null &&
                avaliados[1].aderencia == melhor.aderencia
            val sugerido =
                if (melhor != null && melhor.aderencia >= eixo.minimo && !empate) melhor else null
            Leitura(
                eixo = eixo.id, nome = eixo.nome, oQueE = eixo.oQueE, minimo = eixo.minimo,
                sugerido = sugerido, candidatos = avaliados,
                semLeituraPorque = when {
                    sugerido != null -> null
                    empate -> "empate entre arquétipos"
                    else -> "nenhum arquétipo atingiu a aderência mínima"
                },
            )
        }

    // ------------------------------------------------------- perfil assinado

    /** Um eixo do perfil, assinado por quem tem autoridade para isso. */
    data class Traco(
        val eixo: String,
        /** Id do catálogo, ou "personalizado". */
        val arquetipo: String,
        val nome: String,
        val descricao: String = "",
        val proveniencia: Proveniencia = Proveniencia(),
        val substituiu: String? = null,
    ) {
        fun paraMapa(): Map<String, Any?> = linkedMapOf(
            "eixo" to eixo,
            "arquetipo" to arquetipo,
            "nome" to nome,
            "descricao" to descricao,
            "substituiu" to substituiu,
            "proveniencia" to proveniencia.paraMapa(),
        )
    }

    const val PERSONALIZADO = "personalizado"

    /**
     * O perfil que vale — um traço por eixo, cada um com quem assinou.
     *
     * Guarda apenas o que foi concluído ou afirmado. A sugestão heurística não
     * entra nem por engano: se entrasse, bastaria importar um extrato para o
     * app "saber" quem a pessoa é.
     *
     * Em memória — a persistência é o item 10 da ordem do porte.
     */
    class Registro(tracos: List<Traco> = emptyList()) {
        private val porEixo = LinkedHashMap<String, Traco>()

        init {
            tracos.forEach { porEixo[it.eixo] = it }
        }

        val todos: List<Traco> get() = porEixo.values.sortedBy { it.eixo }

        fun de(eixo: String): Traco? = porEixo[eixo]

        /**
         * Grava o traço de um eixo, ou recusa.
         *
         * Heurística e importação não assinam perfil, por definição: o
         * casamento por número é sugestão. E um traço de autoridade menor não
         * derruba um maior — o palpite do agente não apaga o que a pessoa
         * afirmou, mas a correção dela derruba o palpite dele.
         */
        fun assinar(
            eixo: String,
            arquetipo: String,
            proveniencia: Proveniencia,
            catalogo: List<Eixo>,
            nome: String = "",
            descricao: String = "",
        ): Traco {
            require(proveniencia.eVerdade) {
                "perfil só aceita origem 'agente' ou 'usuario': o casamento por " +
                    "número é sugestão, não assinatura"
            }
            require(proveniencia.porque.isNotEmpty()) {
                "assinar um traço de perfil exige `porque`"
            }
            val doEixo = catalogo.firstOrNull { it.id == eixo }
            requireNotNull(doEixo) {
                "eixo desconhecido: $eixo. Conhecidos: ${catalogo.map { it.id }.sorted()}"
            }
            val arqs = doEixo.arquetipos.associateBy { it.id }
            require(arquetipo == PERSONALIZADO || arquetipo in arqs) {
                "arquétipo '$arquetipo' não existe no eixo '$eixo'. " +
                    "Use um de ${arqs.keys.sorted()} ou 'personalizado' com nome e " +
                    "descrição próprios"
            }
            require(arquetipo != PERSONALIZADO || (nome.isNotEmpty() && descricao.isNotEmpty())) {
                "arquétipo personalizado exige nome e descrição"
            }

            val atual = porEixo[eixo]
            if (atual != null && atual.proveniencia.autoridade > proveniencia.autoridade) {
                return atual
            }

            val base = arqs[arquetipo]
            val traco = Traco(
                eixo = eixo,
                arquetipo = arquetipo,
                nome = nome.ifEmpty { base?.nome ?: arquetipo },
                descricao = descricao.ifEmpty { base?.descricao ?: "" },
                proveniencia = proveniencia,
                substituiu = if (atual != null && atual.arquetipo != arquetipo) atual.arquetipo
                else null,
            )
            porEixo[eixo] = traco
            return traco
        }

        fun esquecer(eixo: String): Boolean = porEixo.remove(eixo) != null
    }

    // ------------------------------------ a visão que as interfaces consomem

    data class EixoMontado(val leitura: Leitura, val assinado: Traco?, val divergeDaSugestao: Boolean) {
        fun paraMapa(): Map<String, Any?> = LinkedHashMap(leitura.paraMapa()).apply {
            put("assinado", assinado?.paraMapa())
            put("diverge_da_sugestao", divergeDaSugestao)
        }
    }

    data class Montado(
        val eixos: List<EixoMontado>,
        val assinados: Int,
        val coberturaPct: Double,
        val divergencias: List<String>,
    ) {
        fun paraMapa(indicadores: Map<String, Double?>): Map<String, Any?> = linkedMapOf(
            "indicadores" to indicadores,
            "eixos" to eixos.map { it.paraMapa() },
            "cobertura" to linkedMapOf(
                "eixos" to eixos.size,
                "assinados" to assinados,
                "pct" to coberturaPct,
                "explicacao" to (
                    "percentual dos eixos do perfil que alguém decidiu. O resto é " +
                        "sugestão do catálogo contra os seus números — palpite, não perfil"
                    ),
            ),
            "divergencias" to divergencias,
        )
    }

    /**
     * Junta sugestão e assinatura, eixo a eixo, e mede quanto do perfil é decisão.
     *
     * A cobertura responde à mesma pergunta que a cobertura da classificação
     * responde para o dinheiro: quanto disto aqui alguém decidiu, e quanto ainda
     * é o app achando coisa. Começa em 0%.
     */
    fun montar(
        indicadores: Map<String, Double?>,
        registro: Registro,
        catalogo: List<Eixo>,
    ): Montado {
        val eixos = casar(indicadores, catalogo).map { leitura ->
            val traco = registro.de(leitura.eixo)
            val sugerido = leitura.sugerido
            val diverge = traco != null && sugerido != null &&
                traco.arquetipo != sugerido.id && traco.arquetipo != PERSONALIZADO
            EixoMontado(leitura, traco, diverge)
        }
        val assinados = eixos.count { it.assinado != null }
        return Montado(
            eixos = eixos,
            assinados = assinados,
            coberturaPct = if (eixos.isNotEmpty()) {
                arredondar(assinados.toDouble() / eixos.size * 100, 1)
            } else 0.0,
            divergencias = eixos.filter { it.divergeDaSugestao }.map { it.leitura.eixo },
        )
    }

    // -------------------------------------------------------------- formato

    /**
     * O `:g` do Python, que é como a evidência imprime número.
     *
     * Seis dígitos significativos, zeros à direita cortados, e notação
     * científica quando o expoente sai de `[-4, 6)`. Parece detalhe de
     * formatação e não é: a evidência vai para a tela e para o agente, e uma
     * aproximação do tipo "tira o `.0` do fim" escreve `99.99999` onde o Python
     * escreve `100`, e `1000000` onde ele escreve `1e+06`.
     *
     * O arredondamento é conferido duas vezes de propósito: arredondar
     * `99.99999` para seis dígitos dá `100`, que **muda o expoente** e, com ele,
     * quantas casas decimais sobram.
     */
    fun formatoG(valor: Double, precisao: Int = 6): String {
        if (valor == 0.0) return "0"
        if (valor.isNaN()) return "nan"
        if (valor.isInfinite()) return if (valor > 0) "inf" else "-inf"

        val negativo = valor < 0
        val a = abs(valor)
        var exp = floor(log10(a)).toInt()
        var arred = arredondar(a, precisao - 1 - exp)
        val expDepois = floor(log10(arred)).toInt()
        if (expDepois != exp) {
            exp = expDepois
            arred = arredondar(a, precisao - 1 - exp)
        }

        val corpo = if (exp < -4 || exp >= precisao) {
            val mantissa = arred / potencia(10.0, exp)
            val sinal = if (exp < 0) "-" else "+"
            val expTexto = abs(exp).toString().padStart(2, '0')
            "${semZerosAtoa(fixo(mantissa, precisao - 1))}e$sinal$expTexto"
        } else {
            semZerosAtoa(fixo(arred, maxOf(precisao - 1 - exp, 0)))
        }
        return if (negativo) "-$corpo" else corpo
    }

    private fun potencia(base: Double, expoente: Int): Double {
        var r = 1.0
        repeat(abs(expoente)) { r *= base }
        return if (expoente < 0) 1.0 / r else r
    }

    /**
     * Casas fixas sem passar por formatador de plataforma.
     *
     * Depois do arredondamento para seis dígitos o valor escalado cabe folgado
     * num `Long`, então montar o texto pelos inteiros é exato — e igual em todos
     * os alvos, que é o ponto.
     */
    private fun fixo(valor: Double, casas: Int): String {
        var escala = 1L
        repeat(casas) { escala *= 10 }
        val n = arredondar(valor * escala, 0).toLong()
        if (casas == 0) return n.toString()
        val inteiro = n / escala
        val frac = (n % escala).toString().padStart(casas, '0')
        return "$inteiro.$frac"
    }

    private fun semZerosAtoa(texto: String): String {
        if (!texto.contains('.')) return texto
        return texto.trimEnd('0').trimEnd('.')
    }
}
