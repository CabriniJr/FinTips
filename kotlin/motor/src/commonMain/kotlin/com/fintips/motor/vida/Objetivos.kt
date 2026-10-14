package com.fintips.motor.vida

import com.fintips.motor.arredondar
import kotlinx.datetime.DatePeriod
import kotlinx.datetime.LocalDate
import kotlinx.datetime.daysUntil
import kotlinx.datetime.plus

/**
 * O plano decomposto: etapas com prazo, o score delas e a cascata do reajuste.
 *
 * Porta `fintips/objetivos.py` — replica, não corrige. Onde o Python usa
 * `float`, aqui é `Double`, inclusive no custo: a correlação financeira do
 * Python devolve `float`, e divergir disso para "melhorar" quebraria a
 * paridade sem avisar ninguém.
 *
 * ## O que é fácil errar aqui, e o ouro cobra
 *
 * **A ordem das operações do score.** Os pontos de cada dimensão são
 * arredondados em 2 casas *antes* de somar, e o total é arredondado em 1 casa
 * depois de virar porcentagem. Somar os valores crus e arredondar no fim dá
 * outro número em vários casos — e nenhuma tela mostra a diferença.
 *
 * **Dimensão sem base não é zero.** Ela sai da conta e o peso aplicado
 * encolhe. Trocar `null` por `0.0` daria um score menor sem errar nenhuma
 * fórmula, que é o jeito mais silencioso possível de divergir.
 *
 * **A cascata do reajuste tem mais de um nível.** Um empurrão se propaga pela
 * cadeia inteira de dependências. Olhar só o vizinho direto acerta a cadeia de
 * dois e erra a de três.
 */

/** Pesos do score, em pontos. Somam 100. */
val PESOS_DO_OBJETIVO: Map<String, Int> = linkedMapOf(
    "prazo" to 30,
    "adiamento" to 15,
    "ritmo" to 25,
    "dinheiro" to 15,
    "constancia" to 15,
)

val TIPOS_DE_ETAPA: List<String> =
    listOf("curso", "prova", "leitura", "pratica", "compra", "entrega", "outro")

data class Etapa(
    val id: String,
    val titulo: String,
    val tipo: String = "outro",
    val prazo: LocalDate? = null,
    /** A data prometida da primeira vez. **Nunca muda** — é o que impede o
     *  reajuste de apagar a própria história. */
    val prazoOriginal: LocalDate? = null,
    val adiamentos: Int = 0,
    val custo: Double = 0.0,
    val dependeDe: List<String> = emptyList(),
    val obrigatoria: Boolean = true,
    val porque: String = "",
) {
    val diasAdiados: Int
        get() = if (prazo == null || prazoOriginal == null) 0
        else maxOf(prazoOriginal.daysUntil(prazo), 0)
}

data class Objetivo(
    val id: String,
    val titulo: String,
    val porque: String = "",
    val comecouEm: LocalDate? = null,
    val dataAlvo: LocalDate? = null,
    val planoId: String = "",
    val missoes: List<String> = emptyList(),
    val etapas: List<Etapa> = emptyList(),
    val assinadoEm: LocalDate? = null,
    val arquivado: Boolean = false,
) {
    val assinado: Boolean get() = assinadoEm != null
    fun etapa(etapaId: String): Etapa? = etapas.firstOrNull { it.id == etapaId }
    val custoTotal: Double get() = etapas.sumOf { it.custo }
}

data class Check(
    val objetivoId: String,
    val etapaId: String,
    val dia: LocalDate,
    val origem: OrigemDoRegistro,
    val nota: String = "",
) {
    // Mesma escada das missões, e de propósito: a pergunta é a mesma —
    // "como sabemos que isso foi feito". `presumido` nunca conta.
    val contaComoCumprido: Boolean get() = origem.contaComoCumprido
}

/**
 * O primeiro check válido de cada etapa.
 *
 * O primeiro, e não o último: quem marcou, marcou. Um segundo check — a pessoa
 * reabrindo o app e clicando de novo — não pode mover a data que decide se a
 * etapa entrou no prazo, ou marcar duas vezes pioraria a nota.
 */
fun cumprimento(objetivo: Objetivo, checks: List<Check>): Map<String, Check> {
    val saida = LinkedHashMap<String, Check>()
    checks.sortedBy { it.dia }
        .filter { it.objetivoId == objetivo.id && it.contaComoCumprido }
        .filter { objetivo.etapa(it.etapaId) != null }
        .forEach { saida.putIfAbsent(it.etapaId, it) }
    return saida
}

fun situacaoDaEtapa(etapa: Etapa, feito: Map<String, Check>, hoje: LocalDate): String = when {
    feito.containsKey(etapa.id) -> "feita"
    etapa.dependeDe.any { !feito.containsKey(it) } -> "bloqueada"
    etapa.prazo == null -> "sem_prazo"
    etapa.prazo < hoje -> "atrasada"
    etapa.prazo == hoje -> "hoje"
    else -> "a_vencer"
}

fun statusDoObjetivo(objetivo: Objetivo, checks: List<Check>, hoje: LocalDate): String {
    if (!objetivo.assinado) return "rascunho"
    val feito = cumprimento(objetivo, checks)
    val obrigatorias = objetivo.etapas.filter { it.obrigatoria }
    if (obrigatorias.isNotEmpty() && obrigatorias.all { feito.containsKey(it.id) }) {
        return "concluido"
    }
    if (objetivo.etapas.any { situacaoDaEtapa(it, feito, hoje) == "atrasada" }) return "atrasado"
    return "em_andamento"
}

/**
 * O que a correlação já resolveu, entrando no score como número.
 *
 * O score não busca plano nem missão: ele recebe o resultado. É a mesma
 * fronteira do Python, e ela existe para que a fórmula possa ser conferida
 * sem arrastar a resolução dos laços junto.
 */
data class CorrelacaoResumo(
    val custoRestante: Double = 0.0,
    val disponivelAteLa: Double? = null,
    val missoesLigadas: Int = 0,
    val missoesDePe: Int = 0,
)

data class ComponenteDoScore(
    val dimensao: String,
    val peso: Int,
    val valor: Double?,
    val pontos: Double?,
)

data class ScoreDoObjetivo(
    val objetivo: String,
    val status: String,
    val score: Double,
    val faixa: String,
    val pesoAplicado: Int,
    val pesoTotal: Int,
    val componentes: List<ComponenteDoScore>,
)

private fun clamp(x: Double, lo: Double = 0.0, hi: Double = 1.0): Double =
    maxOf(lo, minOf(hi, x))

private fun faixa(score: Double): String = when {
    score >= 85 -> "em_dia"
    score >= 70 -> "bom"
    score >= 55 -> "atencao"
    score >= 40 -> "em_risco"
    else -> "travado"
}

fun scoreDoObjetivo(
    objetivo: Objetivo,
    checks: List<Check>,
    hoje: LocalDate,
    correlacao: CorrelacaoResumo = CorrelacaoResumo(),
): ScoreDoObjetivo {
    val feito = cumprimento(objetivo, checks)
    val componentes = mutableListOf<ComponenteDoScore>()

    fun dim(nome: String, valor: Double?) {
        val peso = PESOS_DO_OBJETIVO.getValue(nome)
        componentes.add(
            ComponenteDoScore(
                dimensao = nome,
                peso = peso,
                valor = valor?.let { arredondar(clamp(it), 4) },
                // Os pontos saem do valor CRU e são arredondados em 2 casas
                // antes de entrar na soma — igual ao Python. Arredondar o
                // valor antes mudaria o total em vários casos.
                pontos = valor?.let { arredondar(clamp(it) * peso, 2) },
            )
        )
    }

    // 1. prazo — do que já venceu, quanto venceu feito
    val cobraveis = objetivo.etapas.filter {
        feito.containsKey(it.id) || (it.prazo != null && it.prazo < hoje)
    }
    val noPrazo = cobraveis.filter {
        feito.containsKey(it.id) && (it.prazo == null || feito.getValue(it.id).dia <= it.prazo)
    }
    dim("prazo", if (cobraveis.isNotEmpty()) noPrazo.size.toDouble() / cobraveis.size else null)

    // 2. adiamento — quantas vezes a data foi empurrada
    val comPrazo = objetivo.etapas.filter { it.prazoOriginal != null }
    val totalAdiamentos = comPrazo.sumOf { it.adiamentos }
    dim(
        "adiamento",
        if (comPrazo.isNotEmpty()) 1 - (totalAdiamentos.toDouble() / comPrazo.size) else null,
    )

    // 3. ritmo — o progresso acompanha o tempo gasto
    val obrigatorias = objetivo.etapas.filter { it.obrigatoria }
    var ritmo: Double? = null
    if (objetivo.comecouEm != null && objetivo.dataAlvo != null && obrigatorias.isNotEmpty()) {
        val span = objetivo.comecouEm.daysUntil(objetivo.dataAlvo)
        val corrido = objetivo.comecouEm.daysUntil(hoje)
        if (span > 0 && corrido > 0) {
            val tempo = clamp(corrido.toDouble() / span)
            val progresso =
                obrigatorias.count { feito.containsKey(it.id) }.toDouble() / obrigatorias.size
            if (tempo > 0) ritmo = progresso / tempo
        }
    }
    dim("ritmo", ritmo)

    // 4. dinheiro — o plano ligado cobre o que falta
    val disponivel = correlacao.disponivelAteLa
    dim(
        "dinheiro",
        if (disponivel != null && correlacao.custoRestante > 0) {
            disponivel / correlacao.custoRestante
        } else null,
    )

    // 5. constância — as missões declaradas estão de pé
    dim(
        "constancia",
        if (correlacao.missoesLigadas > 0) {
            correlacao.missoesDePe.toDouble() / correlacao.missoesLigadas
        } else null,
    )

    val comBase = componentes.filter { it.valor != null }
    val pesoAplicado = comBase.sumOf { it.peso }
    val bruto = comBase.sumOf { it.pontos!! }
    val score = if (pesoAplicado > 0) arredondar(bruto / pesoAplicado * 100, 1) else 0.0

    return ScoreDoObjetivo(
        objetivo = objetivo.id,
        status = statusDoObjetivo(objetivo, checks, hoje),
        score = score,
        faixa = if (pesoAplicado > 0) faixa(score) else "sem_base",
        pesoAplicado = pesoAplicado,
        pesoTotal = PESOS_DO_OBJETIVO.values.sum(),
        componentes = componentes,
    )
}

data class Movimento(
    val etapa: String,
    val titulo: String,
    val de: LocalDate,
    val para: LocalDate,
    val dias: Int,
    val motivo: String,
    val seraOAdiamento: Int,
)

data class ReajusteProposto(
    val objetivo: String,
    val calculadoEm: LocalDate,
    val movimentos: List<Movimento>,
    val dataAlvo: LocalDate?,
    val folgaAntesEmDias: Int?,
    val folgaDepoisEmDias: Int?,
    val estouraOAlvo: Boolean,
    /** Nasce sem assinatura, sempre: aplicar é outro ato, e é da pessoa. */
    val assinado: Boolean = false,
)

/**
 * "Não deu para fazer" vira aritmética, não negociação.
 *
 * Cada etapa atrasada vai para hoje, e tudo que depende dela anda o mesmo
 * tanto de dias — **pela cadeia inteira**, não só um nível. O motor não corta
 * etapa nem renegocia a data alvo: ele diz quanto da folga sobrou.
 */
fun reajusteProposto(
    objetivo: Objetivo,
    checks: List<Check>,
    hoje: LocalDate,
): ReajusteProposto {
    val feito = cumprimento(objetivo, checks)
    val empurrao = HashMap<String, Int>()

    for (e in objetivo.etapas) {
        if (feito.containsKey(e.id) || e.prazo == null) continue
        if (e.prazo < hoje) empurrao[e.id] = e.prazo.daysUntil(hoje)
    }

    // Propaga pela cadeia. No máximo uma passada por etapa: a cada volta ou
    // algo mudou, ou o ponto fixo já foi alcançado.
    for (passada in objetivo.etapas.indices) {
        var mudou = false
        for (e in objetivo.etapas) {
            if (feito.containsKey(e.id) || e.prazo == null) continue
            val herdado = e.dependeDe.maxOfOrNull { empurrao[it] ?: 0 } ?: 0
            if (herdado > (empurrao[e.id] ?: 0)) {
                empurrao[e.id] = herdado
                mudou = true
            }
        }
        if (!mudou) break
    }

    val movimentos = objetivo.etapas.mapNotNull { e ->
        val d = empurrao[e.id] ?: 0
        if (d <= 0 || e.prazo == null) return@mapNotNull null
        Movimento(
            etapa = e.id,
            titulo = e.titulo,
            de = e.prazo,
            para = e.prazo.plus(DatePeriod(days = d)),
            dias = d,
            motivo = if (e.prazo < hoje && !feito.containsKey(e.id)) {
                "venceu sem check"
            } else "depende de etapa que atrasou",
            seraOAdiamento = e.adiamentos + 1,
        )
    }

    val ultimoAtual = objetivo.etapas.mapNotNull { it.prazo }.maxOrNull()
    val ultimoDepois = objetivo.etapas.mapNotNull { e ->
        e.prazo?.plus(DatePeriod(days = empurrao[e.id] ?: 0))
    }.maxOrNull()
    val folgaAntes = if (objetivo.dataAlvo != null && ultimoAtual != null) {
        ultimoAtual.daysUntil(objetivo.dataAlvo)
    } else null
    val folgaDepois = if (objetivo.dataAlvo != null && ultimoDepois != null) {
        ultimoDepois.daysUntil(objetivo.dataAlvo)
    } else null

    return ReajusteProposto(
        objetivo = objetivo.id,
        calculadoEm = hoje,
        movimentos = movimentos,
        dataAlvo = objetivo.dataAlvo,
        folgaAntesEmDias = folgaAntes,
        folgaDepoisEmDias = folgaDepois,
        estouraOAlvo = folgaDepois != null && folgaDepois < 0,
    )
}
