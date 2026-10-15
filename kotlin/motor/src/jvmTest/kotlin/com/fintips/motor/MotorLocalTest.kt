package com.fintips.motor

import kotlinx.serialization.json.*
import kotlin.test.*

class MotorLocalTest {
    private fun gold(name: String) = Json.parseToJsonElement(javaClass.classLoader.getResourceAsStream("ouro/$name.json")!!.reader().use { it.readText() }).jsonObject

    @Test fun o_contrato_do_apk_reproduz_todos_os_casos_de_leitura() {
        for (el in gold("leitura")["casos"]!!.jsonArray) {
            val c = el.jsonObject
            assertEquals(c["resultado"], executarMotorLocal("leitura.ritmo", c["entrada"]!!.jsonObject))
        }
    }

    @Test fun o_contrato_do_apk_reproduz_a_projecao_com_e_sem_escopos() {
        for (el in gold("contexto-ia")["casos"]!!.jsonArray) {
            val c = el.jsonObject
            val result = executarMotorLocal("ia.contexto", c["entrada"]!!.jsonObject)
            assertEquals(c["resultado"], result)
            if (result.size > 1) assertEquals(result, validarContextoIA(result))
        }
    }

    @Test fun a_ponte_usa_montar_tela_e_preserva_frentes_sem_metas() {
        val result = executarMotorLocal("vida.frentes", Json.parseToJsonElement("""{
            "today":"2026-10-14", "tasks":[
                {"id":"1","area":"FOR","done":true},
                {"id":"2","area":"FOR","done":false},
                {"id":"3","area":"INT","done":true}]
        }""").jsonObject)
        assertEquals(2, result["done"]!!.jsonPrimitive.int)
        assertEquals(3, result["total"]!!.jsonPrimitive.int)
        val f = result["fronts"]!!.jsonArray.map { it.jsonObject }
        assertEquals(50.0, f[0]["pct"]!!.jsonPrimitive.double)
        assertEquals(0, f[1]["total"]!!.jsonPrimitive.int)
        assertEquals(100.0, f[3]["pct"]!!.jsonPrimitive.double)
        assertFalse(result.toString().contains("titulo"))
    }

    @Test fun conferenca_ofx_nao_devolve_memorandos_ou_identificadores() {
        // Mesmo arquivo sintético que rege o ouro do parser.
        val raw = java.io.File("../../tests/fixture.ofx").readText()
        val input = buildJsonObject { put("ofx", raw); put("saldo_inicial", "0") }
        val result = executarMotorLocal("extrato.conferir", input)
        assertEquals(gold("ofx")["saldo"]!!.jsonObject["centavos"], result["saldo_centavos"])
        assertEquals(true, result["conciliado"]!!.jsonPrimitive.boolean)
        assertEquals(setOf("inicio", "fim", "saldo_centavos", "transacoes", "conciliado", "diferenca_centavos"), result.keys)
        val mismatch = executarMotorLocal("extrato.conferir", buildJsonObject { put("ofx", raw); put("saldo_inicial", "10,25") })
        assertEquals(false, mismatch["conciliado"]!!.jsonPrimitive.boolean)
        assertEquals(1025, mismatch["diferenca_centavos"]!!.jsonPrimitive.int)
        assertFails { executarMotorLocal("extrato.conferir", buildJsonObject { put("ofx", raw); put("saldo_inicial", "") }) }
        assertFails { executarMotorLocal("extrato.conferir", buildJsonObject { put("ofx", raw) }) }
    }

    @Test fun nenhuma_operacao_escreve_ou_aceita_contagens_ambiguas() {
        assertFails { executarMotorLocal("gravar_fato", buildJsonObject {}) }
        assertFails { executarMotorLocal("vida.frentes", Json.parseToJsonElement("""{"today":"2026-10-14","tasks":[{"id":"1","area":"FOR","done":"true"}]}""").jsonObject) }
        assertFails { executarMotorLocal("vida.frentes", Json.parseToJsonElement("""{"today":"2026-10-14","tasks":[{"id":"1","area":"FOR","done":true},{"id":"1","area":"FOR","done":true}]}""").jsonObject) }
        assertFails { executarMotorLocal("leitura.ritmo", Json.parseToJsonElement("""{"today":"2026-10-14","points":[{"dia":"2026-10-14","progresso_bp":"100"}]}""").jsonObject) }
    }

    @Test fun a_saida_recusa_pii_em_todos_os_niveis() {
        val valid = gold("contexto-ia")["casos"]!!.jsonArray.last().jsonObject["resultado"]!!.jsonObject
        val extra = buildJsonObject { valid.forEach { (k,v) -> put(k,v) }; put("nome", "Pessoa inventada") }
        assertFails { validarContextoIA(extra) }
        val nested = buildJsonObject { valid.forEach { (k,v) -> put(k,v) }; putJsonObject("leitura") { putJsonArray("estados") { add("estimado") }; putJsonArray("fontes") { add("usuario") }; put("titulo", "Livro de exemplo") } }
        assertFails { validarContextoIA(nested) }
        val outOfOrder = buildJsonObject { put("schema_version", 1); putJsonObject("leitura") { putJsonArray("estados") { add("estimado"); add("calibrando") }; putJsonArray("fontes") { add("usuario") } } }
        assertFails { validarContextoIA(outOfOrder) }
        assertFails { validarContextoIA(buildJsonObject { put("schema_version", 1) }) }
    }
}
