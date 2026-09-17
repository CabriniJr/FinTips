package com.fintips.motor

/**
 * O motor de regras.
 *
 * O agente escreve a regra; o app aplica de forma determinística. Duas
 * execuções sobre o mesmo extrato e o mesmo conjunto de regras dão exatamente
 * o mesmo resultado — condição para o número poder ser auditado depois.
 *
 * A precedência é decisão de produto, não detalhe técnico: **autoridade
 * primeiro**, depois especificidade, depois confiança. Uma regra genérica que
 * a pessoa afirmou vence uma regra detalhada que a heurística chutou. O
 * contrário deixaria o palpite mandar sempre que fosse mais minucioso, que é
 * exatamente o modo de falhar dos apps de finanças que decidem por você.
 */

/** Ordena por precedência. A primeira que casar vence. */
fun ativas(regras: List<Regra>): List<Regra> =
    regras.filter { it.ativa }.sortedWith(
        compareByDescending<Regra> { it.proveniencia.autoridade }
            .thenByDescending { it.quando.especificidade() }
            .thenByDescending { it.proveniencia.confianca }
    )

/**
 * A condição casa com a transação?
 *
 * Campo vazio não restringe — é por isso que uma condição vazia casaria com
 * tudo, e por isso o motor recusa gravar regra sem condição.
 */
fun casa(regra: Regra, tx: Transacao): Boolean {
    val c = regra.quando

    if (c.contraparteId.isNotEmpty() &&
        slug(nomeCanonico(tx.contraparte)) != c.contraparteId
    ) return false

    if (c.contraparteContem.isNotEmpty() &&
        !norm(tx.contraparte).contains(norm(c.contraparteContem))
    ) return false

    if (c.memoCasa.isNotEmpty()) {
        val re = try {
            Regex(c.memoCasa, RegexOption.IGNORE_CASE)
        } catch (e: IllegalArgumentException) {
            // regex inválida não derruba a importação inteira; a regra só não casa
            return false
        }
        if (!re.containsMatchIn(tx.memoBruto)) return false
    }

    if (c.canal.isNotEmpty() && tx.canal != c.canal) return false
    if (c.fluxo.isNotEmpty() && tx.fluxo != c.fluxo) return false
    if (c.categoriaAtual.isNotEmpty() && tx.categoria != c.categoriaAtual) return false

    val valor = tx.valor.absoluto.paraDouble()
    if (c.valorMin != null && valor < c.valorMin) return false
    if (c.valorMax != null && valor > c.valorMax) return false

    if (c.diasSemana.isNotEmpty() && diaDaSemanaPython(tx) !in c.diasSemana) return false
    if (c.horaMin != null && tx.momento.local.hour < c.horaMin) return false
    if (c.horaMax != null && tx.momento.local.hour > c.horaMax) return false

    return true
}

/**
 * Dia da semana no padrão do Python: segunda = 0, domingo = 6.
 *
 * O `DayOfWeek` do kotlinx-datetime começa em MONDAY, então o `ordinal` já é
 * o número que o Python usa. Um deslize de um aqui trocaria sábado por domingo
 * em toda regra que separa fim de semana, e uma categoria inteira sairia
 * classificada errado sem nenhum erro aparecer.
 */
internal fun diaDaSemanaPython(tx: Transacao): Int =
    tx.momento.local.date.dayOfWeek.ordinal

data class ResultadoDaAplicacao(
    val regrasAtivas: Int,
    val transacoesTocadas: Int,
    val porRegra: Map<String, Int>,
    val semRegra: Int,
)

/**
 * Aplica as regras sobre transações já classificadas pela heurística.
 *
 * A classificação anterior não é apagada: ela vira o piso, marcada como
 * palpite. Cada transação sai daqui sabendo **quem** decidiu o que ela é.
 *
 * Devolve transações novas em vez de mutar as recebidas — o Python muta, mas
 * aqui `Transacao` é imutável, e o resultado é o mesmo. Essa é uma mudança de
 * representação, não de comportamento: o harness compara o estado final.
 */
fun aplicar(regras: List<Regra>, transacoes: List<Transacao>): Pair<List<Transacao>, ResultadoDaAplicacao> {
    val ordenadas = ativas(regras)
    val porRegra = LinkedHashMap<String, Int>()
    var tocadas = 0

    val saida = transacoes.map { tx ->
        val regra = ordenadas.firstOrNull { casa(it, tx) } ?: return@map tx
        val e = regra.entao
        tocadas += 1
        porRegra[regra.id] = (porRegra[regra.id] ?: 0) + 1

        tx.copy(
            categoria = if (e.categoria.isNotEmpty()) e.categoria else tx.categoria,
            fluxo = if (e.fluxo.isNotEmpty()) e.fluxo else tx.fluxo,
            etiquetas = if (e.marcar.isEmpty()) tx.etiquetas
                        else tx.etiquetas + e.marcar.filterNot { it in tx.etiquetas },
            contraparte = if (e.rotulo.isNotEmpty()) e.rotulo else tx.contraparte,
            origemCategoria = regra.proveniencia.origem.chave,
            confiancaCategoria = regra.proveniencia.confianca,
            regraId = regra.id,
        )
    }

    return saida to ResultadoDaAplicacao(
        regrasAtivas = ordenadas.size,
        transacoesTocadas = tocadas,
        porRegra = porRegra,
        semRegra = transacoes.size - tocadas,
    )
}

data class Cobertura(
    val despesaTotal: Dinheiro,
    val porDecisao: Dinheiro,
    val porHeuristica: Dinheiro,
    val coberturaPct: Double,
)

/**
 * Quanto do dinheiro está classificado por decisão e quanto ainda é palpite.
 *
 * Começa em 0%, e é assim que tem que começar: no primeiro extrato importado,
 * ninguém decidiu nada ainda. Um app que mostrasse 100% aqui estaria chamando
 * a própria lista embutida de verdade sobre a vida de alguém.
 */
fun cobertura(transacoes: List<Transacao>): Cobertura {
    var total = Dinheiro.ZERO
    var decisao = Dinheiro.ZERO
    var palpite = Dinheiro.ZERO

    for (tx in transacoes) {
        if (tx.fluxo != Fluxos.DESPESA) continue
        val v = tx.valor.absoluto
        total += v
        if (tx.origemCategoria == Origens.USUARIO || tx.origemCategoria == Origens.AGENTE) {
            decisao += v
        } else {
            palpite += v
        }
    }

    val pct = if (total.centavos == 0L) 0.0
              else arredondar(decisao.centavos.toDouble() / total.centavos * 100, 1)
    return Cobertura(total, decisao, palpite, pct)
}
