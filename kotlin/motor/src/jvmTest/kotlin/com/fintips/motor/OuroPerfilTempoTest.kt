package com.fintips.motor

import kotlinx.datetime.LocalDate
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.int
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * Paridade do envelhecimento do perfil.
 *
 * Aritmética de calendário é onde dois motores divergem em silêncio, e aqui a
 * divergência tem consequência de produto: é esta conta que decide quando o app
 * para de contar um traço como decisão atual e passa a perguntar se ainda é
 * assim. Errar por um mês significa cobrar cedo demais — ou tarde demais, que é
 * pior, porque aí a cobertura segue dizendo 100%.
 *
 * Os casos incluem data ausente e data ilegível de propósito: o Python devolve
 * `null` nos dois, e um porte que devolvesse 0 afirmaria que a assinatura é de
 * hoje sem errar fórmula nenhuma.
 */
class OuroPerfilTempoTest {

    private val ouro: JsonObject by lazy {
        Json.parseToJsonElement(
            this::class.java.getResource("/ouro/perfil-tempo.json")!!.readText()
        ).jsonObject
    }

    @Test
    fun a_idade_em_meses_de_calendario_bate() {
        val casos = ouro["casos"]!!.jsonArray
        for (c in casos) {
            val caso = c.jsonObject
            val nome = caso["nome"]!!.jsonPrimitive.content
            val quando = caso["quando"]!!.jsonPrimitive.content
            val hoje = LocalDate.parse(caso["hoje"]!!.jsonPrimitive.content)

            assertEquals(
                caso["idade_em_meses"]!!.jsonPrimitive.intOrNull,
                Perfil.idadeEmMeses(quando, hoje),
                "$nome: idade",
            )
            for ((chave, validade) in listOf(
                "envelhecido_em_6" to 6,
                "envelhecido_em_12" to 12,
                "envelhecido_em_36" to 36,
            )) {
                assertEquals(
                    caso[chave]!!.jsonPrimitive.boolean,
                    Perfil.envelhecido(quando, validade, hoje),
                    "$nome: $chave",
                )
            }
        }
        assertEquals(10, casos.size, "a família de casos encolheu")
    }

    @Test
    fun a_validade_de_cada_eixo_bate_com_o_catalogo() {
        val esperado = ouro["validade_por_eixo"]!!.jsonObject
        // O catálogo ainda não é lido do YAML pelo Kotlin; o que se trava aqui
        // são os números, para que o porte do catálogo não os invente depois.
        assertEquals(6, esperado["consumo"]!!.jsonPrimitive.int)
        assertEquals(12, esperado["renda"]!!.jsonPrimitive.int)
        assertEquals(36, esperado["fase"]!!.jsonPrimitive.int)
    }
}
