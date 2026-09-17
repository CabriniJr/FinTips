package com.fintips.motor

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Harness do score.
 *
 * Os casos do ouro foram escolhidos pelas fronteiras, não pela média: despesa
 * zero (divisão por zero), sem plano cadastrado, poupança acima do teto,
 * reserva muito acima do alvo, e quatro meses no vermelho — que zeram a
 * estabilidade por multiplicação, um caminho que ninguém escreve sem querer e
 * que nenhum extrato real de teste produziria.
 */
class OuroScoreTest {

    private val ouro by lazy {
        val r = javaClass.classLoader.getResourceAsStream("ouro/score.json")
            ?: fail("ouro/score.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        Json.parseToJsonElement(r.reader(Charsets.UTF_8).readText()).jsonObject
    }

    private fun texto(o: JsonObject, k: String) = o[k]?.jsonPrimitive?.content ?: ""
    private fun reais(o: JsonObject, k: String) =
        Dinheiro.de(o[k]?.jsonPrimitive?.content ?: "0")

    @Test
    fun pesos_batem_com_o_python() {
        val esperados = ouro["pesos"]!!.jsonObject.mapValues { it.value.jsonPrimitive.content.toInt() }
        val obtidos = PesosDoScore.TODOS.toMap()
        assertEquals(esperados, obtidos, "pesos das dimensões divergiram")
    }

    @Test
    fun score_bate_com_o_python_em_todos_os_casos() {
        val divergencias = mutableListOf<String>()

        for (caso in ouro["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = texto(c, "nome")
            val base = c["base"]!!.jsonObject
            val invis = c["invisivel"]!!.jsonObject

            val planos = c["planos"]!!.jsonArray.map { el ->
                val p = el.jsonObject
                AderenciaDePlano(
                    concluido = texto(p, "status") == "concluido",
                    aporteNecessarioMes = p["aporte_necessario_mes"]?.jsonPrimitive?.content?.toDouble() ?: 0.0,
                    capacidadeMensalReal = p["capacidade_mensal_real"]?.jsonPrimitive?.content?.toDouble() ?: 0.0,
                )
            }

            val r = calcularScore(
                taxaPoupanca = texto(base, "taxa_poupanca_media").toDouble(),
                volatilidadeDespesa = texto(base, "volatilidade_despesa").toDouble(),
                mesesNoVermelho = texto(base, "meses_no_vermelho").toInt(),
                rendaMediaMes = reais(base, "renda_media_mes"),
                despesaMediaMes = reais(base, "despesa_media_mes"),
                taxasEsegurosMes = reais(invis["taxas_e_seguros"]!!.jsonObject, "por_mes"),
                microGastosMes = reais(invis["micro_gastos"]!!.jsonObject, "por_mes"),
                planos = planos,
                patrimonioLiquido = reais(c, "patrimonio"),
            )

            val e = c["resultado"]!!.jsonObject
            fun confere(campo: String, esperado: String, obtido: String) {
                if (esperado != obtido) divergencias += "  [$nome] $campo: python $esperado, kotlin $obtido"
            }
            confere("score", texto(e, "score"), r.score.toString())
            confere("faixa", texto(e, "faixa"), r.faixa)
            confere("proximo_ponto", texto(e, "proximo_ponto"), r.proximoPonto)

            e["dimensoes"]!!.jsonArray.forEachIndexed { i, dEl ->
                val d = dEl.jsonObject
                val obtida = r.dimensoes[i]
                confere("dimensao[$i].nome", texto(d, "nome"), obtida.nome)
                confere("${obtida.nome}.pontos", texto(d, "pontos"), obtida.pontos.toString())
                confere("${obtida.nome}.maximo", texto(d, "maximo"), obtida.maximo.toString())
                confere("${obtida.nome}.pct", texto(d, "pct"), obtida.pct.toString())
            }

            val ind = e["indicadores"]!!.jsonObject
            val oi = r.indicadores
            confere("taxa_poupanca", texto(ind, "taxa_poupanca"), oi.taxaPoupanca.toString())
            confere("meses_de_reserva", texto(ind, "meses_de_reserva"), oi.mesesDeReserva.toString())
            confere("volatilidade", texto(ind, "volatilidade_despesa"), oi.volatilidadeDespesa.toString())
            confere("invisivel_mes", texto(ind, "gasto_invisivel_mes"), oi.gastoInvisivelMes.toString())
            confere("invisivel_pct", texto(ind, "gasto_invisivel_pct_despesa"), oi.gastoInvisivelPctDespesa.toString())
        }

        if (divergencias.isNotEmpty()) {
            fail("score divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun o_ouro_cobre_os_caminhos_que_extrato_real_nao_produz() {
        val nomes = ouro["casos"]!!.jsonArray.map { it.jsonObject["nome"]!!.jsonPrimitive.content }
        assertTrue("despesa_zero" in nomes, "falta divisão por zero")
        assertTrue("quatro_meses_no_vermelho" in nomes, "falta a multiplicação que zera a estabilidade")
        assertTrue("zerado" in nomes, "falta o extrato vazio")
        assertTrue("planos_variados" in nomes, "falta a média de aderência com plano concluído e sem aporte")
    }

    @Test
    fun mes_no_vermelho_multiplica_em_vez_de_subtrair() {
        // Quatro meses negativos zeram a estabilidade inteira. Subtrair deixaria
        // um resíduo, sugerindo previsibilidade onde não há nenhuma.
        fun comVermelhos(n: Int) = calcularScore(
            taxaPoupanca = 0.2, volatilidadeDespesa = 0.0, mesesNoVermelho = n,
            rendaMediaMes = Dinheiro.de("5000"), despesaMediaMes = Dinheiro.de("4000"),
            taxasEsegurosMes = Dinheiro.ZERO, microGastosMes = Dinheiro.ZERO,
            planos = emptyList(), patrimonioLiquido = Dinheiro.de("10000"),
        ).dimensoes.first { it.nome == "estabilidade" }.pontos

        assertEquals(15.0, comVermelhos(0))
        // 15 x 0,75 = 11,25, que meio-para-o-par vira 11,2 — conferido contra o Python
        assertEquals(11.2, comVermelhos(1))
        assertEquals(0.0, comVermelhos(4))
        assertEquals(0.0, comVermelhos(9), "não pode ficar negativo")
    }
}
