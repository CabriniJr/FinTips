package com.fintips.motor.vida

import kotlinx.datetime.LocalDate
import kotlinx.datetime.daysUntil

/** Posição registrada, sem título, arquivo ou trecho do livro no cálculo. */
data class PosicaoDeLeitura(val dia: LocalDate, val progressoBp: Int)

data class RitmoDeLeitura(
    val estado: String,
    val progressoBp: Int?,
    val amostras: Int,
    val intervaloDias: Int,
    val avancoBp: Int,
    val previsaoDias: Int?,
    val prazoDias: Int?,
    val necessarioBpDia: Int?,
    val metaBpSessao: Int?,
    val historicoReiniciado: Boolean,
    val preliminar: Boolean,
)

/**
 * Replica fintips.reading.pacing. 10000 bp = 100%; as razões são inteiras.
 * Uma posição final por dia, com janela de 28 dias. Recuar abre uma nova
 * base de observação; posição antiga não vira previsão de leitura atual.
 */
fun ritmoDeLeitura(
    pontos: List<PosicaoDeLeitura>, hoje: LocalDate,
    prazo: LocalDate? = null, diasDeLeitura: Int? = null,
): RitmoDeLeitura {
    require(diasDeLeitura == null || diasDeLeitura in 1..7)
    require(pontos.map { it.dia }.toSet().size == pontos.size)
    require(pontos.all { it.dia <= hoje && it.progressoBp in 0..10000 })
    val todos = pontos.sortedBy { it.dia }
    var recentes = todos.filter { it.dia.daysUntil(hoje) <= 28 }
    var reinicio = 0
    for (i in 1 until recentes.size) {
        if (recentes[i].progressoBp < recentes[i - 1].progressoBp) reinicio = i
    }
    recentes = recentes.drop(reinicio)
    val atual = todos.lastOrNull()?.progressoBp
    val ultimo = todos.lastOrNull()?.dia
    val intervalo = if (recentes.size >= 2) recentes.first().dia.daysUntil(recentes.last().dia) else 0
    val avanco = if (recentes.size >= 2) recentes.last().progressoBp - recentes.first().progressoBp else 0
    val falta = atual?.let { 10000 - it }
    val diasPrazo = prazo?.let { hoje.daysUntil(it) }
    var previsao: Int? = null
    val estado = when {
        atual == null -> "sem_dados"
        atual == 10000 -> { previsao = 0; "no_fim" }
        ultimo != null && ultimo.daysUntil(hoje) > 7 -> "desatualizado"
        recentes.size < 2 -> "calibrando"
        avanco == 0 -> "sem_avanco"
        else -> {
            previsao = dividirAcima(falta!!.toLong() * intervalo, avanco)
            "estimado"
        }
    }
    var necessario: Int? = null
    var meta: Int? = null
    if (falta != null && diasPrazo != null && diasPrazo >= 0) {
        val disponiveis = maxOf(1, diasPrazo)
        necessario = dividirAcima(falta.toLong(), disponiveis)
        if (diasDeLeitura != null) {
            val sessoes = maxOf(1, dividirAcima(disponiveis.toLong() * diasDeLeitura, 7))
            meta = dividirAcima(falta.toLong(), sessoes)
        }
    } else if (diasPrazo == null && diasDeLeitura != null && estado == "estimado") {
        meta = dividirAcima(avanco.toLong() * 7, intervalo * diasDeLeitura)
    }
    return RitmoDeLeitura(estado, atual, recentes.size, intervalo, avanco, previsao,
        diasPrazo, necessario, meta, reinicio > 0, estado == "estimado" && recentes.size < 3)
}

private fun dividirAcima(n: Long, d: Int) = ((n + d - 1) / d).toInt()
