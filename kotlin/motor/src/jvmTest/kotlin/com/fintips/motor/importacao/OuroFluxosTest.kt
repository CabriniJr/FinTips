package com.fintips.motor.importacao

import kotlinx.serialization.json.*
import kotlin.test.*

class OuroFluxosTest {
    @Test fun investimentos_estornos_pix_e_sinais_replicam_python() {
        val ouro = Json.parseToJsonElement(javaClass.getResourceAsStream("/ouro/fluxos-importados.json")!!.reader().readText()).jsonObject
        for (el in ouro["casos"]!!.jsonArray) {
            val c = el.jsonObject
            val (observed, flows) = contextosExtratos(c["arquivos"]!!.jsonArray, c["sal"]!!.jsonPrimitive.content)
            assertEquals(c["esperado"], flows, c["nome"].toString())
            assertEquals(flows, validarFluxosImportados(flows))
            assertEquals(observed["transacoes"], flows["transacoes"])
            for (k in listOf("entradas_centavos", "saidas_centavos")) {
                assertEquals(observed[k]!!.jsonPrimitive.long, flows["grupos"]!!.jsonArray.sumOf { it.jsonObject[k]!!.jsonPrimitive.long })
            }
            assertFalse(flows.toString().contains("CANARY"))
        }
        for (el in ouro["validacoes"]!!.jsonArray) {
            val c = el.jsonObject
            assertEquals(c["aceito"]!!.jsonPrimitive.boolean, runCatching { validarFluxosImportados(c["entrada"]!!.jsonObject) }.isSuccess)
        }
    }
}
