package com.fintips.app

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fintips.motor.vida.ForcaDoAtributo
import java.text.NumberFormat
import kotlin.math.cos
import kotlin.math.sin

/** Contrato de desenho. Valor, base e pesos vêm do motor; não calcular score aqui. */
data class GaugeVisual(
    val chave: String,
    val rotulo: String,
    val valor: Double?,
    val legenda: String,
    val fonte: String,
    val semBase: Boolean = valor == null,
    val faixa: String? = null,
    val pesoAplicado: Int? = null,
    val pesoTotal: Int? = null,
    val cor: Color = Color(0xFFA4EC8C),
)

private val TintaGauge = Color(0xFFF1EFE6)
private val MutedGauge = Color(0xFFBDAD99)
private val BordaGauge = Color(0xFF55432E)
private val FundoGauge = Color(0xFF0D0C0B)

/** Visão agregada fica sem base enquanto não houver composição definida pelo motor. */
@Composable
fun PainelDeGauges(
    frentes: List<ForcaDoAtributo>,
    agregado: GaugeVisual? = null,
    objetivos: List<GaugeVisual> = emptyList(),
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        GaugeDeVida(agregado ?: GaugeVisual(
            chave = "agregado", rotulo = "VISÃO AGREGADA", valor = null,
            legenda = "Ainda sem metas combinadas",
            fonte = "Escolha de metas e pesos ainda não disponível nesta tela.",
        ), destaque = true)
        Text("CUMPRIMENTO REGISTRADO · HOJE", color = MutedGauge,
            fontFamily = FontFamily.Monospace, fontSize = 11.sp)
        frentes.chunked(2).forEach { par ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                par.forEach { frente ->
                    GaugeDeVida(GaugeVisual(
                        chave = frente.atributo.sigla,
                        rotulo = frente.atributo.nome,
                        valor = if (frente.missoes == 0) null else frente.pct,
                        legenda = if (frente.missoes == 0) "Sem missão nesta janela"
                                  else "${frente.cumpridas} de ${frente.missoes} hoje",
                        fonte = "${frente.comEvidenciaDeMaquina} de ${frente.cumpridas} cumprimentos com medida de aparelho",
                        cor = when (frente.atributo.sigla) {
                            "FOR" -> Color(0xFFFFA342)
                            "AGI" -> Color(0xFFA4EC8C)
                            "VIT" -> Color(0xFFCEACF0)
                            "INT" -> Color(0xFFA1C5EB)
                            "FOC" -> Color(0xFFE8D46F)
                            else -> Color(0xFF9CE4DA)
                        },
                    ), Modifier.weight(1f))
                }
                if (par.size == 1) Box(Modifier.weight(1f))
            }
        }
        objetivos.forEach { GaugeDeVida(it, destaque = true) }
    }
}

/**
 * Arco segmentado e ponteiro. Animação finita; Compose respeita a escala de
 * duração do Android. O número e a semântica mostram imediatamente o valor real.
 * Sem base: arco interrompido, sem ponteiro, sem semântica de progresso zero.
 */
@Composable
fun GaugeDeVida(dado: GaugeVisual, modifier: Modifier = Modifier, destaque: Boolean = false) {
    var aberto by remember(dado.chave) { mutableStateOf(false) }
    val valido = dado.valor?.let { it.isFinite() && it in 0.0..100.0 } == true
    val comBase = !dado.semBase && valido
    val inconsistente = !dado.semBase && dado.valor != null && !valido
    val numero = remember(dado.valor) {
        NumberFormat.getNumberInstance().apply { maximumFractionDigits = 1 }
            .format(dado.valor ?: 0.0)
    }
    val descricao = when {
        inconsistente -> "Dado inconsistente"
        !comBase -> "Sem base"
        else -> "$numero de 100"
    }
    val animado by animateFloatAsState(
        targetValue = if (comBase) dado.valor!!.toFloat() else 0f,
        animationSpec = tween(600, easing = FastOutSlowInEasing), label = "gauge-${dado.chave}",
    )
    Column(modifier.fillMaxWidth().background(FundoGauge)
        .border(1.dp, if (aberto) dado.cor else BordaGauge)
        .clickable(role = Role.Button, onClickLabel = if (aberto) "Ocultar detalhes" else "Mostrar detalhes") { aberto = !aberto }
        .semantics(mergeDescendants = true) {
            stateDescription = descricao
            if (comBase) progressBarRangeInfo = ProgressBarRangeInfo(dado.valor!!.toFloat(), 0f..100f)
        }.animateContentSize().padding(if (destaque) 18.dp else 12.dp),
        verticalArrangement = Arrangement.spacedBy(7.dp)) {
        Text(dado.rotulo.uppercase(), color = dado.cor,
            fontFamily = FontFamily.Monospace, fontSize = if (destaque) 13.sp else 11.sp,
            fontWeight = FontWeight.Bold)
        Box(Modifier.fillMaxWidth().aspectRatio(if (destaque) 2.2f else 1.45f),
            contentAlignment = Alignment.BottomCenter) {
            Canvas(Modifier.matchParentSize().clearAndSetSemantics {}) {
                val raio = minOf(size.width / 2.15f, size.height * .52f)
                val centro = Offset(size.width / 2f, size.height * .58f)
                val origem = Offset(centro.x - raio, centro.y - raio)
                val arco = Size(raio * 2, raio * 2)
                val stroke = Stroke(width = 5.dp.toPx(), cap = StrokeCap.Butt)
                repeat(24) { i ->
                    drawArc(BordaGauge, 150f + i * 10f, if (comBase) 7f else 4f,
                        false, origem, arco, style = stroke)
                }
                if (comBase) {
                    // Geometria do gauge, sem arredondar ou modificar o score.
                    val alcance = animado / 100f * 240f
                    repeat(24) { i ->
                        val segmento = (alcance - i * 10f).coerceIn(0f, 7f)
                        if (segmento > 0f) drawArc(dado.cor, 150f + i * 10f,
                            segmento, false, origem, arco, style = stroke)
                    }
                    val angulo = Math.toRadians((150f + alcance).toDouble())
                    val ponta = Offset(centro.x + cos(angulo).toFloat() * raio * .83f,
                        centro.y + sin(angulo).toFloat() * raio * .83f)
                    drawLine(TintaGauge, centro, ponta, 2.dp.toPx(), StrokeCap.Round)
                    drawCircle(dado.cor, 4.dp.toPx(), centro)
                }
            }
            Text(if (comBase) numero else "—", color = if (comBase) TintaGauge else MutedGauge,
                fontSize = if (destaque) 38.sp else 26.sp, fontWeight = FontWeight.Black,
                modifier = Modifier.clearAndSetSemantics {})
        }
        if (!comBase) Text(descricao, color = MutedGauge, fontSize = 12.sp)
        Text(dado.legenda, color = TintaGauge, fontSize = 12.sp)
        if (dado.pesoAplicado != null && dado.pesoTotal != null) {
            Text("Base: ${dado.pesoAplicado} de ${dado.pesoTotal} em peso",
                color = if (dado.pesoAplicado < dado.pesoTotal) Color(0xFFFFA342) else MutedGauge,
                fontFamily = FontFamily.Monospace, fontSize = 10.sp)
        }
        AnimatedVisibility(aberto) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(dado.fonte, color = MutedGauge, fontSize = 12.sp)
                dado.faixa?.let { Text(it.replace('_', ' '), color = MutedGauge, fontSize = 12.sp) }
            }
        }
    }
}
