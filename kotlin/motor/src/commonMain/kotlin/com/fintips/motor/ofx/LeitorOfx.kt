package com.fintips.motor.ofx

import com.fintips.motor.Conta
import com.fintips.motor.Dinheiro
import com.fintips.motor.Extrato
import com.fintips.motor.Momento
import com.fintips.motor.Transacao
import com.fintips.motor.hashConta
import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalDateTime
import kotlinx.datetime.UtcOffset

/**
 * Leitor de OFX — SGML 1.x e XML 2.x — tolerante às variações brasileiras.
 *
 * Porte de `parsers/ofx.py`, replicando inclusive o que parece descuido.
 * As particularidades que este arquivo existe para aguentar:
 *
 * - SGML sem tag de fechamento nos campos (`<TRNAMT>-23.21` e acabou).
 * - Data com fuso no formato OFX: `20260504191415[-3:BRT]`.
 * - PagBank escrevendo `<BALAMT>` em pt-BR e com símbolo: `R$ 1.234,56`.
 * - `<DTASOF>` vindo às vezes como `dd/mm/aaaa`.
 *
 * O que mais dá trabalho não é o formato: é o FITID. O PagBank reaproveita o
 * mesmo FITID no estorno da compra, então deduplicar só por ele apagaria o
 * estorno e deixaria a conta sem fechar.
 */

class ErroOfx(mensagem: String) : Exception(mensagem)

private val TAG = Regex("<([A-Z0-9.]+)>([^<\\r\\n]*)", RegexOption.IGNORE_CASE)
private val STMTTRN = Regex(
    "<STMTTRN>(.*?)</STMTTRN>",
    setOf(RegexOption.DOT_MATCHES_ALL, RegexOption.IGNORE_CASE),
)
private val OFX_DT = Regex("^(\\d{4})(\\d{2})(\\d{2})(\\d{2})?(\\d{2})?(\\d{2})?")
private val FUSO = Regex("\\[([+-]?\\d+(?:\\.\\d+)?):?([A-Z]*)\\]")

/** Fuso padrão quando o OFX omite — Brasília, como no motor Python. */
private val FUSO_PADRAO = UtcOffset(hours = -3)

fun lerMomento(bruto: String): Momento {
    var s = bruto.trim()
    var deslocamento = FUSO_PADRAO

    FUSO.find(s)?.let { m ->
        val horas = m.groupValues[1].toDouble()
        deslocamento = UtcOffset(seconds = (horas * 3600).toInt())
        s = s.substring(0, m.range.first)
    }

    if ("/" in s) { // dd/mm/aaaa
        val partes = s.split("/")
        if (partes.size < 3) throw ErroOfx("data OFX inválida: '$bruto'")
        val (d, mes, ano) = partes
        return Momento(
            LocalDateTime(ano.toInt(), mes.toInt(), d.toInt(), 0, 0, 0),
            deslocamento,
        )
    }

    val m = OFX_DT.find(s) ?: throw ErroOfx("data OFX inválida: '$bruto'")
    val g = m.groupValues
    return Momento(
        LocalDateTime(
            year = g[1].toInt(),
            monthNumber = g[2].toInt(),
            dayOfMonth = g[3].toInt(),
            hour = g[4].ifEmpty { "0" }.toInt(),
            minute = g[5].ifEmpty { "0" }.toInt(),
            second = g[6].ifEmpty { "0" }.toInt(),
        ),
        deslocamento,
    )
}

/**
 * Campos de um bloco. **A primeira ocorrência de cada tag vence** — é o que o
 * Python faz, e trocar por "a última vence" mudaria silenciosamente o valor
 * lido em arquivos com tag repetida.
 */
private fun campos(bloco: String): Map<String, String> {
    val saida = LinkedHashMap<String, String>()
    for (m in TAG.findAll(bloco)) {
        val tag = m.groupValues[1].uppercase()
        val valor = m.groupValues[2].trim()
        if (valor.isNotEmpty() && tag !in saida) saida[tag] = valor
    }
    return saida
}

fun lerOfx(texto: String, sal: String = ""): Extrato {
    val corpo = texto.substringAfter("<OFX>", texto)

    val cabecalho = campos(corpo.substringBefore("<BANKTRANLIST>"))
    val conta = Conta(
        idHash = hashConta(cabecalho["ACCTID"] ?: "desconhecida", sal),
        instituicao = cabecalho["ORG"] ?: "",
        idBanco = cabecalho["BANKID"] ?: "",
        tipo = cabecalho["ACCTTYPE"] ?: "CHECKING",
        moeda = cabecalho["CURDEF"] ?: "BRL",
    )

    val transacoes = mutableListOf<Transacao>()
    val vistos = HashSet<Triple<String, String, String>>()
    val idsUsados = HashSet<String>()

    for (m in STMTTRN.findAll(corpo)) {
        val f = campos(m.groupValues[1])
        val fitid = f["FITID"] ?: ""
        if (fitid.isEmpty()) continue

        // A chave de deduplicação é (fitid, valor, data), e não só o fitid:
        // o estorno da mesma compra chega com o FITID repetido, e sumir com
        // ele deixaria o extrato sem conciliar.
        val chave = Triple(fitid, f["TRNAMT"] ?: "", f["DTPOSTED"] ?: "")
        if (!vistos.add(chave)) continue

        var uid = fitid
        var n = 1
        while (uid in idsUsados) {
            n += 1
            uid = "$fitid#$n"
        }
        idsUsados.add(uid)

        val dtposted = f["DTPOSTED"] ?: throw ErroOfx("transação sem DTPOSTED: $fitid")
        val trnamt = f["TRNAMT"] ?: throw ErroOfx("transação sem TRNAMT: $fitid")

        transacoes.add(
            Transacao(
                id = uid,
                momento = lerMomento(dtposted),
                valor = Dinheiro.de(trnamt),
                memoBruto = (f["MEMO"] ?: f["NAME"] ?: "").trim(),
                contaId = conta.idHash,
            )
        )
    }

    transacoes.sortBy { it.momento.instante }
    if (transacoes.isEmpty()) throw ErroOfx("nenhuma transação encontrada no arquivo")

    val rodape = campos(corpo.substringAfter("</BANKTRANLIST>", corpo))
    return Extrato(
        conta = conta,
        periodoInicio = dataSegura(cabecalho["DTSTART"], transacoes.first().dia),
        periodoFim = dataSegura(cabecalho["DTEND"], transacoes.last().dia),
        saldoDeclarado = Dinheiro.de(rodape["BALAMT"] ?: "0"),
        saldoEm = dataSegura(rodape["DTASOF"], dataSegura(cabecalho["DTEND"], transacoes.last().dia)),
        transacoes = transacoes,
        origem = "ofx:" + (conta.instituicao.ifEmpty { "desconhecido" }),
    )
}

/** Data que não derruba a importação inteira quando vem torta. */
private fun dataSegura(bruto: String?, alternativa: LocalDate): LocalDate {
    if (bruto.isNullOrEmpty()) return alternativa
    return try {
        lerMomento(bruto).dia
    } catch (e: ErroOfx) {
        alternativa
    } catch (e: IllegalArgumentException) {
        // kotlinx-datetime recusa 30/02; o Python cairia no mesmo lugar
        alternativa
    }
}
