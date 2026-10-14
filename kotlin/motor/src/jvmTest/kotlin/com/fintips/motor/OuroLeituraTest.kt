package com.fintips.motor

import com.fintips.motor.vida.PosicaoDeLeitura
import com.fintips.motor.vida.ritmoDeLeitura
import kotlinx.datetime.LocalDate
import kotlinx.serialization.json.*
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue
import kotlin.test.fail

class OuroLeituraTest {
    private val ouro by lazy {
        val r = javaClass.classLoader.getResourceAsStream("ouro/leitura.json")
            ?: fail("Gere o ouro com python scripts/gerar-ouro.py")
        Json.parseToJsonElement(r.reader(Charsets.UTF_8).use { it.readText() }).jsonObject
    }

    @Test
    fun todas_as_decisoes_de_pacing_batem_com_a_referencia_python() {
        for (el in ouro["casos"]!!.jsonArray) {
            val c = el.jsonObject
            val input = c["entrada"]!!.jsonObject
            fun nullable(k: String) = input[k]?.jsonPrimitive?.contentOrNull
            val points = input["points"]!!.jsonArray.map {
                val p = it.jsonObject
                PosicaoDeLeitura(LocalDate.parse(p["dia"]!!.jsonPrimitive.content), p["progresso_bp"]!!.jsonPrimitive.int)
            }
            val r = ritmoDeLeitura(points, LocalDate.parse(nullable("today")!!),
                nullable("deadline")?.let { LocalDate.parse(it) }, nullable("reading_days")?.toInt())
            val obtained = buildJsonObject {
                put("estado", r.estado)
                put("progresso_bp", r.progressoBp?.let { JsonPrimitive(it) } ?: JsonNull)
                put("amostras", r.amostras)
                put("intervalo_dias", r.intervaloDias)
                put("avanco_bp", r.avancoBp)
                put("previsao_dias", r.previsaoDias?.let { JsonPrimitive(it) } ?: JsonNull)
                put("prazo_dias", r.prazoDias?.let { JsonPrimitive(it) } ?: JsonNull)
                put("necessario_bp_dia", r.necessarioBpDia?.let { JsonPrimitive(it) } ?: JsonNull)
                put("meta_bp_sessao", r.metaBpSessao?.let { JsonPrimitive(it) } ?: JsonNull)
                put("historico_reiniciado", r.historicoReiniciado)
                put("preliminar", r.preliminar)
            }
            assertEquals(c["resultado"]!!.jsonObject, obtained, "pacing divergiu: ${c["nome"]}")
        }
    }

    @Test
    fun o_ouro_exercita_recuo_dados_antigos_e_divisao_nao_exata() {
        val names = ouro["casos"]!!.jsonArray.map { it.jsonObject["nome"]!!.jsonPrimitive.content }.toSet()
        assertTrue(names.containsAll(setOf("recuo", "recuo_e_retomada", "arquivo_antigo",
            "limite_sete_dias", "divisao_nao_exata", "avanco_minimo", "prazo_hoje", "prazo_vencido")))
    }

    @Test
    fun posicoes_futuras_duplicadas_e_fora_da_escala_nao_sao_aceitas() {
        val today = LocalDate.parse("2026-10-14")
        assertFailsWith<IllegalArgumentException> { ritmoDeLeitura(listOf(PosicaoDeLeitura(LocalDate.parse("2026-10-15"), 3000)), today) }
        assertFailsWith<IllegalArgumentException> { ritmoDeLeitura(listOf(PosicaoDeLeitura(today, 10001)), today) }
        assertFailsWith<IllegalArgumentException> { ritmoDeLeitura(listOf(PosicaoDeLeitura(today, 1000), PosicaoDeLeitura(today, 2000)), today) }
    }
}
