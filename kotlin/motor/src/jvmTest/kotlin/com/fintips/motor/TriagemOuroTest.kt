package com.fintips.motor

import com.fintips.motor.triagem.pedidoOpenAITriagem
import kotlinx.serialization.json.*
import kotlin.test.*

class TriagemOuroTest {
    private fun gold()=Json.parseToJsonElement(javaClass.classLoader.getResourceAsStream("ouro/triagem-universal.json")!!.reader().readText()).jsonObject
    @Test fun contratos_e_aplicacao_reproduzem_a_referencia_python() {
        gold()["casos"]!!.jsonArray.forEach { el -> val c=el.jsonObject
            assertEquals(c["resultado"],executarMotorLocal(c["operacao"]!!.jsonPrimitive.content,c["entrada"]!!.jsonObject),c["nome"]!!.jsonPrimitive.content)
        }
    }
    @Test fun contratos_invalidos_nunca_retornam_bundle_parcial() {
        gold()["recusados"]!!.jsonArray.forEach { el -> val c=el.jsonObject
            assertFails(c["nome"]!!.jsonPrimitive.content) { executarMotorLocal(c["operacao"]!!.jsonPrimitive.content,c["entrada"]!!.jsonObject) }
        }
    }
    @Test fun agente_preenche_e_relaciona_com_referencias_conforme_python() {
        val g=Json.parseToJsonElement(javaClass.classLoader.getResourceAsStream("ouro/triagem-agente.json")!!.reader().readText()).jsonObject
        g["casos"]!!.jsonArray.forEach { el->val c=el.jsonObject
            val result=executarMotorLocal(c["operacao"]!!.jsonPrimitive.content,c["entrada"]!!.jsonObject)
            if(c["operacao"]==JsonPrimitive("triagem.agente_pedido")) {
                assertEquals(Json.parseToJsonElement(c["resultado"]!!.jsonObject["input"]!!.jsonPrimitive.content),Json.parseToJsonElement(result["input"]!!.jsonPrimitive.content))
                assertEquals(JsonObject(c["resultado"]!!.jsonObject.filterKeys { it!="input" }),JsonObject(result.filterKeys { it!="input" }))
            } else assertEquals(c["resultado"],result,c["nome"]!!.jsonPrimitive.content)
        }
        g["recusados"]!!.jsonArray.forEach { el->val c=el.jsonObject;assertFails(c["nome"]!!.jsonPrimitive.content) { executarMotorLocal(c["operacao"]!!.jsonPrimitive.content,c["entrada"]!!.jsonObject) } }
    }
    @Test fun request_openai_nao_contem_texto_ids_originais_nem_mapa_local() {
        val c=gold()["casos"]!!.jsonArray.first { it.jsonObject["operacao"]==JsonPrimitive("triagem.contexto") }.jsonObject
        val i=c["entrada"]!!.jsonObject
        val r=pedidoOpenAITriagem(i["bundle"]!!.jsonObject,i["rascunhos"]!!.jsonArray,i["hoje"]!!.jsonPrimitive.content)
        val request=r["pedido"]!!.toString()
        assertFalse(request.contains("CANARY"));assertFalse(request.contains("asset-local"));assertFalse(request.contains("mapa_local"))
        assertFalse(request.contains("origem_real"));assertFalse(request.contains("destino_real"))
        assertTrue(request.contains("123"));assertTrue(request.contains("razao_bp"))
        assertEquals(JsonPrimitive(false),r["pedido"]!!.jsonObject["store"])
    }
}
