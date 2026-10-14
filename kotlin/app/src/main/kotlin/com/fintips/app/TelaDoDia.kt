package com.fintips.app

import com.fintips.motor.vida.ForcaDoAtributo
import com.fintips.motor.vida.Guarda
import com.fintips.motor.vida.LinhaDoDia
import com.fintips.motor.vida.OrigemDoRegistro
import com.fintips.motor.vida.montarTela
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.datetime.Clock
import kotlinx.datetime.TimeZone
import kotlinx.datetime.todayIn

/**
 * As seis barras e a lista do dia.
 *
 * ## A linguagem visual
 *
 * Monocromática, canto reto, sombra deslocada, maiúscula em mono. É a mesma do
 * painel, e a razão de ser assim num app de hábito é prática: cor que comemora
 * e ícone que celebra são o app opinando sobre o dia de alguém. A barra sobe
 * porque a pessoa fez; não há confete.
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
 * Este arquivo **não foi compilado**. O alvo Android exige SDK e `dl.google.com`
 * está bloqueado na máquina onde isto foi escrito. Toda a lógica que ele usa
 * tem teste (`AparelhoTest`, 16 casos); o que está aqui é desenho, e desenho
 * errado se vê na tela.
 */

private val TINTA = Color(0xFF1B1E24)
private val PAPEL = Color(0xFFEDEEF1)
private val LINHA = Color(0xFFB9BEC8)
private val CARTAO = Color(0xFFFFFFFF)

@Composable
fun TelaDoDia(guarda: Guarda, hojeFixo: kotlinx.datetime.LocalDate? = null) {
    val hoje = hojeFixo ?: Clock.System.todayIn(TimeZone.currentSystemDefault())
    var vida by mutableStateOf(guarda.carregar())
    var estado by mutableStateOf(montarTela(vida, hoje))

    fun marcar(missaoId: String) {
        // Origem `usuario`: quem tocou foi a pessoa. O app nunca marca sozinho
        // — `presumido` existe exatamente para não contar.
        guarda.marcar(vida, missaoId, hoje, OrigemDoRegistro.USUARIO)
        vida = guarda.carregar()
        estado = montarTela(vida, hoje)
    }

    Column(
        Modifier.fillMaxSize().background(PAPEL).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            estado.resumo.uppercase(),
            fontFamily = FontFamily.Monospace,
            fontSize = 12.sp,
            letterSpacing = 1.sp,
            color = TINTA,
        )

        SeisBarras(estado.frentes)

        if (estado.semCatalogo) {
            Cartao {
                Text(
                    "Nenhuma missão neste aparelho.\n\n" +
                        "No computador: fintips aparelho --saida missoes.json\n" +
                        "Depois copie o arquivo para cá.",
                    fontSize = 14.sp, color = TINTA,
                )
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(estado.doDia, key = { it.missaoId }) { linha ->
                    LinhaDeMissao(linha) { marcar(linha.missaoId) }
                }
            }
        }

        Spacer(Modifier.height(8.dp))
        val pct = estado.cobertura["pct_medido"]
        Text(
            "evidência de aparelho: $pct%".uppercase(),
            fontFamily = FontFamily.Monospace, fontSize = 10.sp, color = TINTA,
        )
    }
}

/** As seis, sempre as seis. */
@Composable
private fun SeisBarras(frentes: List<ForcaDoAtributo>) {
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        frentes.forEach { f ->
            Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                Box(
                    Modifier.fillMaxWidth().height(72.dp).background(CARTAO),
                    contentAlignment = Alignment.BottomCenter,
                ) {
                    val altura = (72 * (f.pct / 100.0)).dp
                    Box(Modifier.fillMaxWidth().height(altura).background(TINTA))
                }
                Text(
                    f.atributo.sigla,
                    fontFamily = FontFamily.Monospace, fontSize = 10.sp,
                    fontWeight = FontWeight.Bold, color = TINTA,
                    textAlign = TextAlign.Center,
                )
                // Frente sem missão não fica vazia em silêncio: ela diz que
                // está vazia, porque isso é informação.
                Text(
                    if (f.missoes == 0) "—" else "${f.cumpridas}/${f.missoes}",
                    fontFamily = FontFamily.Monospace, fontSize = 9.sp, color = TINTA,
                )
            }
        }
    }
}

@Composable
private fun LinhaDeMissao(linha: LinhaDoDia, aoTocar: () -> Unit) {
    Cartao(Modifier.clickable(enabled = !linha.cumprida) { aoTocar() }) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.width(22.dp).height(22.dp)
                    .background(if (linha.cumprida) TINTA else CARTAO),
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
                    fontFamily = FontFamily.Monospace, fontSize = 9.sp, color = TINTA,
                )
            }
        }
    }
}

/** Cartão de canto reto com sombra deslocada, como no painel. */
@Composable
private fun Cartao(modifier: Modifier = Modifier, conteudo: @Composable () -> Unit) {
    Box(modifier.fillMaxWidth()) {
        Box(Modifier.fillMaxWidth().padding(start = 3.dp, top = 3.dp).background(LINHA)) {
            Box(Modifier.fillMaxWidth().background(CARTAO).padding(14.dp)) { conteudo() }
        }
    }
}
