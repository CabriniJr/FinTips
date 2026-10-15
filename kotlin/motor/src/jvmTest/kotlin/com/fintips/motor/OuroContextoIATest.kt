package com.fintips.motor

import kotlinx.serialization.json.*
import kotlin.test.*

class OuroContextoIATest {
    @Test fun projecao_de_privacidade_replica_python() {
        val gold = javaClass.classLoader.getResourceAsStream("ouro/contexto-ia.json")!!.reader().use { it.readText() }
        for (case in Json.parseToJsonElement(gold).jsonObject["casos"]!!.jsonArray) {
            val c = case.jsonObject
            val i = c["entrada"]!!.jsonObject
            val fronts = i["fronts"]!!.jsonArray.map { it.jsonObject.let { f ->
                FrenteParaIA(f["area"]!!.jsonPrimitive.content, f["total"]!!.jsonPrimitive.int, f["done"]!!.jsonPrimitive.int) } }
            val plans = i["plans"]!!.jsonArray.map { it.jsonObject.let { p -> PlanoParaIA(p["area"]!!.jsonPrimitive.content, p["done"]!!.jsonPrimitive.boolean) } }
            val reading = i["reading"]!!.jsonArray.map { it.jsonObject.let { r -> LeituraParaIA(r["state"]!!.jsonPrimitive.content, r["source"]!!.jsonPrimitive.content) } }
            assertEquals(c["resultado"], projetarContextoIA(fronts, plans, reading, i["scopes"]!!.jsonArray.map { it.jsonPrimitive.content }))
        }
    }
    @Test fun rejeita_texto_livre_e_contagem_inconsistente() {
        val fronts = listOf("FOR", "AGI", "VIT", "INT", "FOC", "OURO").map { FrenteParaIA(it, 0, 0) }
        assertFailsWith<IllegalArgumentException> { projetarContextoIA(fronts, emptyList(), emptyList(), listOf("nome")) }
        assertFailsWith<IllegalArgumentException> { projetarContextoIA(fronts, listOf(PlanoParaIA("texto privado", false)), emptyList(), listOf("planos")) }
        assertFailsWith<IllegalArgumentException> { projetarContextoIA(fronts.map { it.copy(feitas = 1) }, emptyList(), emptyList(), listOf("rotina")) }
        assertFailsWith<IllegalArgumentException> { projetarContextoIA(fronts, emptyList(), listOf(LeituraParaIA("texto privado", "usuario")), listOf("leitura")) }
    }
}
