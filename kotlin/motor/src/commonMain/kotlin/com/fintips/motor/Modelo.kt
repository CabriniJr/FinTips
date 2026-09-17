package com.fintips.motor

import kotlinx.datetime.Instant
import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalDateTime
import kotlinx.datetime.UtcOffset
import kotlinx.datetime.toInstant

/**
 * O modelo canônico.
 *
 * Tudo que entra — OFX hoje, Open Finance amanhã — vira isto antes de qualquer
 * análise. A porta mantém os nomes das taxonomias em inglês (`expense`,
 * `debit_card`) porque eles são **dados**, não código: aparecem no YAML no
 * disco do usuário e nas respostas do MCP. Traduzir aqui quebraria todo
 * arquivo já gerado pelo motor Python, que é justamente o que a porta não pode
 * fazer.
 */

const val VERSAO_SCHEMA = 1

/**
 * Como o dinheiro se moveu, do ponto de vista do patrimônio.
 *
 * É a distinção que sustenta o resto do motor: mandar dinheiro para o CDB não
 * é despesa, e transferência entre contas próprias não é receita nem gasto.
 * Sem isso, taxa de poupança é ficção.
 */
object Fluxos {
    const val DESPESA = "expense"
    const val RECEITA = "income"
    const val APORTE = "savings_out"
    const val RESGATE = "savings_in"
    const val TRANSFERENCIA = "transfer"
    const val ESTORNO = "refund"

    val TODOS = listOf(DESPESA, RECEITA, APORTE, RESGATE, TRANSFERENCIA, ESTORNO)
}

/** O instrumento usado. */
object Canais {
    val TODOS = listOf(
        "debit_card", "pix", "pix_qr", "pix_auto", "salary", "yield",
        "fixed_income", "fund", "fee", "transit_topup", "reversal", "other",
    )
    const val OUTRO = "other"
}

/**
 * Sugestões da partida a frio, não a taxonomia real.
 *
 * A taxonomia que vale vive em `data/taxonomia.yaml` e pertence ao usuário.
 * Esta lista existe para o motor ter onde pousar na primeira importação, e é
 * marcada como heurística — ou seja, palpite.
 */
val CATEGORIAS_SUGERIDAS = listOf(
    "alimentacao", "mercado", "transporte", "moradia", "saude", "vestuario",
    "lazer", "educacao", "assinaturas", "servicos", "compras", "doacoes",
    "taxas", "viagem", "pessoas", "investimento", "renda", "outros",
)

/** Origens da classificação, em ordem de autoridade. */
object Origens {
    const val HEURISTICA = "heuristica"
    const val IMPORTACAO = "importacao"
    const val AGENTE = "agente"
    const val USUARIO = "usuario"
}

/**
 * Momento de uma transação.
 *
 * Guarda a hora de parede como veio do banco **mais** o deslocamento, em vez de
 * converter tudo para UTC. Não é preciosismo: o motor Python usa `datetime`
 * com timezone e nunca converte — o mês de uma transação sai de
 * `ts.strftime("%Y-%m")`, ou seja, do horário local. Normalizar para UTC aqui
 * jogaria uma compra da meia-noite e meia para o mês anterior.
 *
 * A ordenação, essa sim, usa o instante absoluto, porque é o que o `sort` do
 * Python faz com datas conscientes de fuso.
 */
data class Momento(val local: LocalDateTime, val deslocamento: UtcOffset) {
    val instante: Instant get() = local.toInstant(deslocamento)
    val dia: LocalDate get() = local.date

    /** "2026-06" — o mês do horário local, como no Python. */
    val mes: String get() = "${local.year}-${dois(local.monthNumber)}"

    fun dataIso(): String = "${local.year}-${dois(local.monthNumber)}-${dois(local.dayOfMonth)}"
    fun horaMinuto(): String = "${dois(local.hour)}:${dois(local.minute)}"

    private fun dois(n: Int) = n.toString().padStart(2, '0')
}

data class Conta(
    /** Hash do número — o número em si nunca entra no modelo. */
    val idHash: String,
    val instituicao: String = "",
    val idBanco: String = "",
    val tipo: String = "CHECKING",
    val moeda: String = "BRL",
)

data class Transacao(
    /** FITID do banco, desambiguado quando repete no mesmo arquivo. */
    val id: String,
    val momento: Momento,
    /** Negativo = saída. */
    val valor: Dinheiro,
    /** Texto original do banco. Fica local, nunca sai da máquina. */
    val memoBruto: String,
    val canal: String = Canais.OUTRO,
    val fluxo: String = Fluxos.DESPESA,
    val categoria: String = "outros",
    val contraparte: String = "",
    val tipoContraparte: String = "",
    val cidade: String = "",
    val etiquetas: List<String> = emptyList(),
    val contaId: String = "",
    val origemCategoria: String = Origens.HEURISTICA,
    val confiancaCategoria: Double = 0.4,
    val regraId: String = "",
) {
    val dia: LocalDate get() = momento.dia
    val mes: String get() = momento.mes
}

data class Extrato(
    val conta: Conta,
    val periodoInicio: LocalDate,
    val periodoFim: LocalDate,
    val saldoDeclarado: Dinheiro,
    val saldoEm: LocalDate,
    val transacoes: List<Transacao> = emptyList(),
    val origem: String = "",
) {
    /**
     * Confere se a soma das transações bate com o saldo declarado.
     *
     * O motor recusa analisar antes disso fechar: número que não concilia vira
     * conclusão errada com aparência de precisão, que é pior do que não ter
     * número nenhum.
     */
    fun concilia(saldoInicial: Dinheiro = Dinheiro.ZERO): Conciliacao {
        val soma = transacoes.map { it.valor }.somar()
        val diferenca = (saldoInicial + soma) - saldoDeclarado
        // "menor que um centavo" no Python; em centavos inteiros, é zero
        return Conciliacao(bate = diferenca.centavos == 0L, diferenca = diferenca)
    }
}

data class Conciliacao(val bate: Boolean, val diferenca: Dinheiro)
