package com.fintips.app

import com.fintips.motor.vida.Guarda
import com.fintips.motor.vida.LinhaDoDia
import com.fintips.motor.vida.OrigemDoRegistro
import com.fintips.motor.vida.montarTela
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.datetime.Clock
import kotlinx.datetime.TimeZone
import kotlinx.datetime.todayIn

/**
 * Os seis gauges e a lista do dia.
 *
 * ## A linguagem visual
 *
 * Neon Genesis Evangelion, conforme escolha do usuário: preto, âmbar,
 * títulos vermelhos e dados verdes. Tokens em docs/LINGUAGEM-VISUAL.md.
 * A barra sobe por registro; o desenho não conclui nem inventa medidas.
 *
 * ## O que esta tela NÃO faz
 *
 * - não calcula nada: tudo vem de `montarTela`, que é função pura e testada;
 * - não elogia nem cobra: o resumo é "1 de 2 hoje", e existe teste proibindo
 *   as palavras de elogio;
 * - não esconde frente vazia: as seis aparecem sempre, porque frente sem missão
 *   mostra o que a pessoa não está treinando.
 *
 * ## Aviso honesto
 *
 * `assembleDebug` passou em 14/10/2026 após instalar SDK/JDK e corrigir
 * a configuração. Ainda não foi executado no aparelho. A lógica tem testes
 * (`AparelhoTest`); aparência, toque e lifecycle exigem verificação Android.
 */

private val TINTA = Color(0xFFF1EFE6)
private val PAPEL = Color(0xFF080808)
private val LINHA = Color(0xFFFFA342)
private val CARTAO = Color(0xFF0D0C0B)
private val SINAL = Color(0xFFFF4B35)
private val DADO = Color(0xFFA4EC8C)
private val SECUNDARIO = Color(0xFFBDAD99)
private val TITULO = FontFamily(Font(R.font.barlow_condensed_black, FontWeight.Black))

@Composable
fun TelaDoDia(guarda: Guarda, hojeFixo: kotlinx.datetime.LocalDate? = null) {
    val hoje = hojeFixo ?: Clock.System.todayIn(TimeZone.currentSystemDefault())
    var tentativa by remember { mutableStateOf(0) }
    val inicial = remember(guarda, tentativa) { runCatching { guarda.carregar() } }
    if (inicial.isFailure) {
        Column(Modifier.fillMaxSize().background(PAPEL).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp)) {
            Text("FINTIPS / HOJE", fontFamily = TITULO, fontSize = 36.sp, color = SINAL)
            Text("Não foi possível abrir os registros locais. Nenhum arquivo foi substituído.",
                fontSize = 16.sp, color = TINTA)
            Text("Tentar novamente", color = LINHA, fontSize = 16.sp,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)
                    .clickable { tentativa++ }.border(1.dp, LINHA).padding(14.dp))
        }
        return
    }
    var vida by remember(guarda, tentativa) { mutableStateOf(inicial.getOrThrow()) }
    val estado = remember(vida, hoje) { montarTela(vida, hoje) }
    var erro by remember { mutableStateOf("") }

    fun marcar(missaoId: String) {
        // Origem `usuario`: quem tocou foi a pessoa. O app nunca marca sozinho
        // — `presumido` existe exatamente para não contar.
        try {
            guarda.marcar(vida, missaoId, hoje, OrigemDoRegistro.USUARIO)
            vida = guarda.carregar()
            erro = ""
        } catch (_: Exception) {
            erro = "Não foi possível confirmar a marcação. Tente reabrir os registros locais."
        }
    }

    LazyColumn(
        Modifier.fillMaxSize().background(PAPEL).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("FINTIPS / 01", fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp, color = LINHA)
                Text("HOJE", fontFamily = TITULO, fontSize = 64.sp, color = SINAL)
                Text(estado.resumo.uppercase(), fontFamily = FontFamily.Monospace,
                    fontSize = 12.sp, letterSpacing = 1.sp, color = DADO)
            }
        }
        if (erro.isNotEmpty()) item { Text(erro, fontSize = 14.sp, color = TINTA) }

        item { PainelDeGauges(estado.frentes) }

        if (estado.semCatalogo) {
            item {
                Cartao {
                    Text(
                    "Nenhuma missão neste aparelho.\n\n" +
                        "Adicione um catálogo local para começar. " +
                        "A seleção de arquivo ainda não está disponível nesta tela.",
                    fontSize = 14.sp, color = TINTA,
                    )
                }
            }
        } else {
            items(estado.doDia, key = { "missao-${it.missaoId}" }) { linha ->
                LinhaDeMissao(linha) { marcar(linha.missaoId) }
            }
        }

        item {
            val pct = estado.cobertura["pct_medido"]
            Text("evidência de aparelho: $pct%".uppercase(),
                fontFamily = FontFamily.Monospace, fontSize = 10.sp, color = SECUNDARIO)
        }
    }
}

@Composable
private fun LinhaDeMissao(linha: LinhaDoDia, aoTocar: () -> Unit) {
    Cartao(Modifier.clickable(enabled = !linha.cumprida) { aoTocar() }) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.width(22.dp).height(22.dp)
                    .background(if (linha.cumprida) DADO else CARTAO),
                contentAlignment = Alignment.Center,
            ) {
                if (!linha.cumprida) {
                    Box(Modifier.fillMaxSize().background(LINHA))
                    Box(Modifier.width(20.dp).height(20.dp).background(CARTAO))
                }
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(linha.titulo, fontSize = 15.sp, color = TINTA)
                val detalhe = buildList {
                    add(linha.atributo.sigla)
                    if (linha.sequencia > 0) add("${linha.sequencia} dias")
                    if (linha.recorde > linha.sequencia) add("recorde ${linha.recorde}")
                    // O que é só palavra aparece como só palavra.
                    if (linha.medidoPorMaquina) add("medido")
                    else if (linha.sensorPossivel) add("sem medida")
                }.joinToString(" · ")
                Text(
                    detalhe.uppercase(),
                    fontFamily = FontFamily.Monospace, fontSize = 10.sp, color = SECUNDARIO,
                )
            }
        }
    }
}

/** Painel reto: moldura em âmbar, sem elevação Material. */
@Composable
private fun Cartao(modifier: Modifier = Modifier, conteudo: @Composable () -> Unit) {
    Box(modifier.fillMaxWidth().background(CARTAO).border(1.dp, LINHA).padding(14.dp)) { conteudo() }
}
