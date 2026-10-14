package com.fintips.motor.vida

import kotlinx.datetime.LocalDate

/**
 * O que a tela mostra, como dado.
 *
 * Nenhum pedaço disto sabe o que é Compose. É função pura de (catálogo,
 * histórico, hoje) para o que aparece — e por isso dá para testar a tela inteira
 * nesta máquina, sem SDK de Android, sem emulador e sem UI.
 *
 * O que sobra para a camada de Compose é desenho: barra, lista, toque. Se um
 * número estiver errado na tela, o erro está aqui, e aqui tem teste.
 */
data class LinhaDoDia(
    val missaoId: String,
    val titulo: String,
    val atributo: Atributo,
    val cumprida: Boolean,
    val sequencia: Int,
    val recorde: Int,
    /** `true` quando o cumprimento de hoje veio de medida de aparelho. */
    val medidoPorMaquina: Boolean,
    val comoMedir: String,
    val sensorPossivel: Boolean,
)

data class EstadoDaTela(
    val hoje: LocalDate,
    val semCatalogo: Boolean,
    val frentes: List<ForcaDoAtributo>,
    val doDia: List<LinhaDoDia>,
    val cobertura: Map<String, Any>,
    /** Quantas missões de hoje já foram cumpridas, e de quantas. */
    val feitasHoje: Int,
    val totalDeHoje: Int,
) {
    /**
     * A frase do topo.
     *
     * Deliberadamente **sem elogio e sem cobrança**. "Você está indo bem" é o
     * app opinando sobre a vida de alguém com base em quantas caixas foram
     * marcadas, e é o tipo de frase que faz desinstalar no primeiro dia ruim.
     * O número diz o que é; quem interpreta é a pessoa, e quem conversa é o
     * agente, que sabe o contexto.
     */
    val resumo: String get() = when {
        semCatalogo -> "nenhuma missão cadastrada"
        totalDeHoje == 0 -> "nada diário no catálogo"
        else -> "$feitasHoje de $totalDeHoje hoje"
    }
}

/** Monta a tela do dia. */
fun montarTela(vida: Vida, hoje: LocalDate): EstadoDaTela {
    val diarias = vida.missoes.filter { it.ativa && it.cadencia == Cadencia.DIARIA }
    val linhas = diarias.map { m ->
        val e = estadoDiario(m, vida.registros, hoje)
        LinhaDoDia(
            missaoId = m.id,
            titulo = m.titulo,
            atributo = m.atributo,
            cumprida = e.cumpridaNaJanela,
            sequencia = e.sequencia,
            recorde = e.recorde,
            medidoPorMaquina = vida.registros.any {
                it.missaoId == m.id && it.dia == hoje && it.origem == OrigemDoRegistro.SENSOR
            },
            comoMedir = m.comoMedir,
            sensorPossivel = m.sensorPossivel,
        )
    }
    return EstadoDaTela(
        hoje = hoje,
        semCatalogo = vida.vazia,
        frentes = forcaDosAtributos(vida.missoes, vida.registros, hoje),
        doDia = linhas,
        cobertura = coberturaDeEvidencia(vida.missoes, vida.registros),
        feitasHoje = linhas.count { it.cumprida },
        totalDeHoje = linhas.size,
    )
}
