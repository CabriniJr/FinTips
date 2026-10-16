package com.fintips.motor

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Paridade da fronteira de saída.
 *
 * Este é o único ouro do projeto que cobra o **registro inteiro**, e não só as
 * respostas das funções. O motivo é o tipo de erro que se quer impedir: abrir
 * um campo no Python e esquecer de abrir no Kotlin não produz número errado em
 * tela nenhuma — produz um campo que sai do aparelho num motor e não sai no
 * outro. Um ouro de respostas não pegaria isso; um ouro do registro pega.
 *
 * O caso `LOJA QUE NINGUEM CADASTROU` com sal e sem mapa prova a parte que
 * mais importa: sem entrada no mapa local, o aparelho emite um pseudônimo
 * estável, e os dois motores emitem o mesmo. Se divergirem, o mesmo destino
 * aparece como dois para o agente — e o conselho dele passa a ser sobre uma
 * vida que não existe.
 */
class OuroFronteiraTest {

    private val ouro: JsonObject by lazy {
        Json.parseToJsonElement(
            this::class.java.getResource("/ouro/fronteira.json")!!.readText()
        ).jsonObject
    }

    private val sal: String by lazy { ouro["sal"]!!.jsonPrimitive.content }

    private val mapa: Map<String, String> by lazy {
        ouro["mapa_de_identidades"]!!.jsonObject
            .mapValues { it.value.jsonPrimitive.content }
    }

    @Test
    fun o_registro_declara_os_mesmos_tipos_nos_dois_motores() {
        val doOuro = ouro["registro"]!!.jsonArray.map { it.jsonObject["tipo"]!!.jsonPrimitive.content }
        assertEquals(doOuro, TIPOS_DA_FRONTEIRA.map { it.nome })
    }

    @Test
    fun cada_campo_tem_a_mesma_politica_e_a_mesma_unidade() {
        for (t in ouro["registro"]!!.jsonArray) {
            val tipo = t.jsonObject["tipo"]!!.jsonPrimitive.content
            val aqui = TIPOS_DA_FRONTEIRA.first { it.nome == tipo }
            assertEquals(
                t.jsonObject["classe"]!!.jsonPrimitive.content, aqui.classe,
                "$tipo: classe de origem",
            )

            val abreDoOuro = t.jsonObject["abre"]!!.jsonArray.map { c ->
                Triple(
                    c.jsonObject["campo"]!!.jsonPrimitive.content,
                    c.jsonObject["politica"]!!.jsonPrimitive.content,
                    c.jsonObject["unidade"]!!.jsonPrimitive.content,
                )
            }
            assertEquals(
                abreDoOuro,
                aqui.abre.map { Triple(it.campo, it.politica.codigo, it.unidade) },
                "$tipo: campos abertos, política e unidade",
            )

            assertEquals(
                t.jsonObject["fecha"]!!.jsonArray.map { it.jsonPrimitive.content },
                aqui.fecha,
                "$tipo: campos que nunca saem",
            )
            assertEquals(
                t.jsonObject["projeta_a_parte"]!!.jsonArray.map { it.jsonPrimitive.content },
                aqui.projetaAParte,
                "$tipo: campos que saem pelo tipo próprio",
            )
        }
    }

    @Test
    fun campo_nao_declarado_fecha_nos_dois_motores() {
        for (c in ouro["politica_do_campo"]!!.jsonArray) {
            val tipo = c.jsonObject["tipo"]!!.jsonPrimitive.content
            val campo = c.jsonObject["campo"]!!.jsonPrimitive.content
            assertEquals(
                c.jsonObject["politica"]!!.jsonPrimitive.content,
                politicaDoCampo(tipo, campo).codigo,
                "$tipo.$campo",
            )
        }
    }

    @Test
    fun o_alias_da_identidade_financeira_bate_caractere_por_caractere() {
        for (c in ouro["alias"]!!.jsonArray) {
            val valor = c.jsonObject["valor"]!!.jsonPrimitive.content
            val usaMapa = c.jsonObject["usa_mapa"]!!.jsonPrimitive.boolean
            val salDoCaso = c.jsonObject["sal"]!!.jsonPrimitive.content
            assertEquals(
                c.jsonObject["alias"]!!.jsonPrimitive.content,
                aliasFinanceiro(valor, if (usaMapa) mapa else emptyMap(), salDoCaso),
                "alias de '$valor' (mapa=$usaMapa, sal='$salDoCaso')",
            )
        }
    }

    @Test
    fun o_nome_conhecido_sai_do_texto_de_planejamento() {
        for (c in ouro["texto_sem_identidades"]!!.jsonArray) {
            val texto = c.jsonObject["texto"]!!.jsonPrimitive.content
            val saida = textoSemIdentidades(texto, mapa)
            assertEquals(
                c.jsonObject["saida"]!!.jsonPrimitive.content, saida.texto, "texto: '$texto'",
            )
            assertEquals(
                c.jsonObject["trocou"]!!.jsonPrimitive.boolean, saida.trocou,
                "trocou: '$texto'",
            )
        }
    }

    @Test
    fun nenhum_nome_do_mapa_sobrevive_na_saida() {
        // A asserção que o ouro não faz sozinho: não basta a string bater, o
        // nome não pode estar lá. Um porte que devolvesse o texto cru passaria
        // nos casos sem identidade e falharia aqui.
        for (c in ouro["texto_sem_identidades"]!!.jsonArray) {
            if (!c.jsonObject["trocou"]!!.jsonPrimitive.boolean) continue
            val saida = textoSemIdentidades(c.jsonObject["texto"]!!.jsonPrimitive.content, mapa)
            for (bruto in mapa.keys) {
                assertTrue(
                    !saida.texto.contains(bruto, ignoreCase = true) &&
                        !saida.texto.contains(norm(bruto), ignoreCase = true),
                    "'$bruto' sobreviveu em '${saida.texto}'",
                )
            }
        }
    }

    @Test
    fun o_sal_do_ouro_e_o_mesmo_dos_dois_lados() {
        // Guarda contra um falso verde: se o teste usasse outro sal, os
        // pseudônimos não bateriam e a causa seria difícil de achar.
        assertEquals("PF:" + digest(norm("LOJA QUE NINGUEM CADASTROU"), sal, 6),
                     aliasFinanceiro("LOJA QUE NINGUEM CADASTROU", emptyMap(), sal))
    }
}
