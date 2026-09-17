package com.fintips.motor

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * O harness diferencial.
 *
 * Aqui não há opinião sobre o que o motor deveria fazer: o arquivo de ouro é
 * gerado rodando o motor Python de verdade (`scripts/gerar-ouro.py`), e este
 * teste cobra do Kotlin exatamente a mesma resposta. Se um dia os dois
 * divergirem, este teste falha nomeando o caso — que é a única informação útil
 * no meio de uma porta de 7 mil linhas.
 *
 * Esta é a razão de a porta ser módulo a módulo. Cada módulo portado ganha seu
 * ouro, e o Python continua sendo o produto que funciona até o Kotlin
 * reproduzir tudo. O dia em que a troca acontecer não vai ser um salto de fé.
 *
 * Fica no `jvmTest` de propósito: ler arquivo é a única coisa aqui que precisa
 * de plataforma, e o motor em `commonMain` continua sem saber o que é disco.
 */
class OuroDinheiroTest {

    private val ouro by lazy {
        val recurso = javaClass.classLoader.getResourceAsStream("ouro/dinheiro.json")
            ?: fail(
                "ouro/dinheiro.json não encontrado. Gere com: python3 scripts/gerar-ouro.py"
            )
        Json.parseToJsonElement(recurso.reader(Charsets.UTF_8).readText()).jsonObject
    }

    @Test
    fun le_valor_igual_ao_motor_python() {
        val leituras = ouro["leituras"]!!.jsonArray
        assertTrue(leituras.size >= 20, "ouro magro demais para valer como harness")

        val divergencias = mutableListOf<String>()
        for (caso in leituras) {
            val o = caso.jsonObject
            val texto = o["texto"]!!.jsonPrimitive.content
            val esperado = o["centavos"]!!.jsonPrimitive.content.toLong()
            val obtido = Dinheiro.de(texto).centavos
            if (obtido != esperado) {
                val decimal = o["decimal"]!!.jsonPrimitive.content
                divergencias += "  \"$texto\" → python $esperado ($decimal), kotlin $obtido"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("leitura de valor divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun divide_igual_ao_motor_python() {
        val divisoes = ouro["divisoes"]!!.jsonArray
        val divergencias = mutableListOf<String>()
        for (caso in divisoes) {
            val o = caso.jsonObject
            val centavos = o["centavos"]!!.jsonPrimitive.content.toLong()
            val divisor = o["divisor"]!!.jsonPrimitive.content.toInt()
            val esperado = o["esperado"]!!.jsonPrimitive.content.toLong()
            val obtido = Dinheiro(centavos).dividir(divisor).centavos
            if (obtido != esperado) {
                divergencias += "  $centavos/$divisor → python $esperado, kotlin $obtido"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("arredondamento divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun o_ouro_cobre_os_casos_de_fronteira() {
        // Um harness que só testa o fácil passa sempre e não protege nada.
        val textos = ouro["leituras"]!!.jsonArray.map { it.jsonObject["texto"]!!.jsonPrimitive.content }
        assertTrue("1.005" in textos, "falta empate exato de arredondamento")
        assertTrue("1.234" in textos, "falta o caso ambíguo de separador")
        assertTrue("" in textos, "falta entrada vazia")
        assertTrue(textos.any { it.startsWith("(") }, "falta negativo em parênteses")
        assertTrue(textos.any { it.contains("R$") }, "falta valor com símbolo de moeda")
    }

    @Test
    fun empates_vao_para_lados_diferentes_conforme_a_paridade() {
        // 1.005 → 100 (par fica), 1.015 → 102 (sobe para o par).
        // Se alguém trocar por meio-para-cima, os dois viram 101 e 102 e este
        // teste é o que acusa.
        assertEquals(100L, Dinheiro.de("1.005").centavos)
        assertEquals(102L, Dinheiro.de("1.015").centavos)
    }
}
