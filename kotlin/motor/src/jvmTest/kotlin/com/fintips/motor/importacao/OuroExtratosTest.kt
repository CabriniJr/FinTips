package com.fintips.motor.importacao

import kotlinx.serialization.json.*
import kotlin.test.*

class OuroExtratosTest {
    @Test fun contexto_observado_replica_python_e_nao_inclui_identidades() {
        val input=javaClass.getResourceAsStream("/ouro/extratos-contexto.json")!!.reader().readText()
        val ouro=Json.parseToJsonElement(input).jsonObject
        for(check in ouro["validacoes"]!!.jsonArray) {
            val c=check.jsonObject
            assertEquals(c["aceito"]!!.jsonPrimitive.boolean,runCatching { validarContextoExtratos(c["entrada"]!!.jsonObject) }.isSuccess)
        }
        for(el in ouro["casos"]!!.jsonArray) {
            val c=el.jsonObject;val out=contextoExtratos(c["arquivos"]!!.jsonArray,c["sal"]!!.jsonPrimitive.content)
            assertEquals(c["esperado"],out,c["nome"].toString());assertEquals(out,validarContextoExtratos(out))
            assertFalse(out.toString().contains("CANARY"))
        }
    }
    @Test fun contexto_de_saida_recusa_texto_extra_e_troca_de_unidade() {
        val empty=contextoExtratos(JsonArray(emptyList()),"test")
        assertFails { validarContextoExtratos(JsonObject(empty+("memo" to JsonPrimitive("CANARY")))) }
        assertFails { validarContextoExtratos(JsonObject(empty+("entradas_centavos" to JsonPrimitive("2")))) }
    }
}
