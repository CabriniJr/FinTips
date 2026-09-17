package com.fintips.motor

import com.fintips.motor.ofx.lerOfx
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * O harness do leitor OFX — o ouro que pega de verdade.
 *
 * Ele cobre, de uma vez: tag SGML sem fechamento, data com fuso, valor em
 * pt-BR com símbolo, deduplicação por (FITID, valor, data), desambiguação de
 * FITID repetido, ordenação por instante e conciliação contra o saldo
 * declarado. Cada um desses foi um detalhe que alguém descobriu apanhando de
 * um extrato real, e é exatamente o tipo de coisa que uma porta perde sem
 * ninguém notar.
 */
class OuroOfxTest {

    private fun ouro(nome: String): JsonObject {
        val recurso = javaClass.classLoader.getResourceAsStream("ouro/$nome")
            ?: fail("ouro/$nome não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        return Json.parseToJsonElement(recurso.reader(Charsets.UTF_8).readText()).jsonObject
    }

    private fun texto(o: JsonObject, chave: String) = o[chave]!!.jsonPrimitive.content

    private val fixture by lazy {
        // O mesmo arquivo que o Python leu para gerar o ouro.
        val caminho = File("../../tests/fixture.ofx").let {
            if (it.exists()) it else File("tests/fixture.ofx")
        }
        assertTrue(caminho.exists(), "fixture.ofx não encontrado em ${caminho.absolutePath}")
        caminho.readText(Charsets.UTF_8)
    }

    @Test
    fun conta_periodo_e_saldo_batem_com_o_python() {
        val o = ouro("ofx.json")
        val extrato = lerOfx(fixture, sal = texto(o, "sal"))

        val conta = o["conta"]!!.jsonObject
        assertEquals(texto(conta, "id_hash"), extrato.conta.idHash, "hash da conta divergiu")
        assertEquals(texto(conta, "instituicao"), extrato.conta.instituicao)
        assertEquals(texto(conta, "id_banco"), extrato.conta.idBanco)
        assertEquals(texto(conta, "tipo"), extrato.conta.tipo)
        assertEquals(texto(conta, "moeda"), extrato.conta.moeda)
        assertEquals(texto(o, "origem"), extrato.origem)

        val periodo = o["periodo"]!!.jsonObject
        assertEquals(texto(periodo, "inicio"), extrato.periodoInicio.toString())
        assertEquals(texto(periodo, "fim"), extrato.periodoFim.toString())

        val saldo = o["saldo"]!!.jsonObject
        assertEquals(texto(saldo, "centavos").toLong(), extrato.saldoDeclarado.centavos)
        assertEquals(texto(saldo, "em"), extrato.saldoEm.toString())
    }

    @Test
    fun cada_transacao_bate_com_o_python() {
        val o = ouro("ofx.json")
        val extrato = lerOfx(fixture, sal = texto(o, "sal"))
        val esperadas = o["transacoes"]!!.jsonArray

        assertEquals(esperadas.size, extrato.transacoes.size, "número de transações divergiu")

        val divergencias = mutableListOf<String>()
        esperadas.forEachIndexed { i, esperadaEl ->
            val e = esperadaEl.jsonObject
            val obtida = extrato.transacoes[i]
            fun confere(campo: String, esperado: String, obtido: String) {
                if (esperado != obtido) {
                    divergencias += "  [$i ${texto(e, "id")}] $campo: python '$esperado', kotlin '$obtido'"
                }
            }
            confere("id", texto(e, "id"), obtida.id)
            confere("data", texto(e, "data"), obtida.momento.dataIso())
            confere("hora", texto(e, "hora"), obtida.momento.horaMinuto())
            confere("mes", texto(e, "mes"), obtida.mes)
            confere("centavos", texto(e, "centavos"), obtida.valor.centavos.toString())
            confere("memo", texto(e, "memo"), obtida.memoBruto)
            confere("conta_id", texto(e, "conta_id"), obtida.contaId)
        }
        if (divergencias.isNotEmpty()) {
            fail("o canônico divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun conciliacao_bate_com_o_python() {
        val o = ouro("ofx.json")
        val extrato = lerOfx(fixture, sal = texto(o, "sal"))
        val esperada = o["conciliacao"]!!.jsonObject
        val obtida = extrato.concilia()

        assertEquals(texto(esperada, "bate").toBoolean(), obtida.bate)
        assertEquals(texto(esperada, "diferenca_centavos").toLong(), obtida.diferenca.centavos)
    }

    @Test
    fun o_fixture_exercita_os_casos_dificeis() {
        // Um ouro sobre um extrato trivial não protege nada. Estes são os
        // detalhes que o parser existe para aguentar.
        val o = ouro("ofx.json")
        val extrato = lerOfx(fixture, sal = texto(o, "sal"))

        assertTrue(extrato.transacoes.size >= 5, "fixture pequeno demais para valer como ouro")
        assertTrue(extrato.transacoes.any { it.valor.negativo }, "faltou saída")
        assertTrue(extrato.transacoes.any { !it.valor.negativo }, "faltou entrada")
        assertTrue(
            extrato.transacoes.map { it.momento.instante } ==
                extrato.transacoes.map { it.momento.instante }.sorted(),
            "transações fora de ordem",
        )
        assertEquals(
            extrato.transacoes.size, extrato.transacoes.map { it.id }.toSet().size,
            "id repetido — a desambiguação de FITID falhou",
        )
    }

    @Test
    fun hash_de_conta_bate_digito_por_digito() {
        // Se divergir, a mesma conta vira duas no workspace de quem migrar.
        val o = ouro("privacidade.json")
        val sal = texto(o, "sal")
        val divergencias = mutableListOf<String>()
        for (caso in o["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            val valor = texto(c, "valor")
            val esperadoDigest = texto(c, "digest")
            val obtidoDigest = digest(valor, sal)
            if (esperadoDigest != obtidoDigest) {
                divergencias += "  digest('$valor') → python $esperadoDigest, kotlin $obtidoDigest"
            }
            val esperadoHash = texto(c, "hash_conta")
            val obtidoHash = hashConta(valor, sal)
            if (esperadoHash != obtidoHash) {
                divergencias += "  hashConta('$valor') → python $esperadoHash, kotlin $obtidoHash"
            }
            // o pseudônimo normaliza antes do hash: "José" e "JOSE" precisam
            // dar o mesmo apelido, senão a mesma pessoa aparece duas vezes
            val esperadoPseudo = texto(c, "pseudonimo")
            val obtidoPseudo = pseudonimo(valor, sal)
            if (esperadoPseudo != obtidoPseudo) {
                divergencias += "  pseudonimo('$valor') → python $esperadoPseudo, kotlin $obtidoPseudo"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("pseudonimização divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }
}

/**
 * Leitura de data, isolada do fixture.
 *
 * Este teste existe por causa de uma lacuna encontrada na prática: todo
 * `DTPOSTED` do fixture traz `[-3:BRT]`, então trocar o fuso padrão do leitor
 * de -3 para -2 não quebrava nada. O harness não estava cego — o fixture é que
 * não fazia a pergunta. Harness é tão bom quanto o dado que ele compara.
 */
class OuroDatasTest {

    @Test
    fun le_data_igual_ao_python_inclusive_sem_fuso() {
        val recurso = javaClass.classLoader.getResourceAsStream("ouro/datas.json")
            ?: fail("ouro/datas.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        val ouro = Json.parseToJsonElement(recurso.reader(Charsets.UTF_8).readText()).jsonObject

        val divergencias = mutableListOf<String>()
        for (caso in ouro["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            fun campo(k: String) = c[k]!!.jsonPrimitive.content
            val bruto = campo("bruto")
            val momento = com.fintips.motor.ofx.lerMomento(bruto)

            if (campo("data") != momento.dataIso()) {
                divergencias += "  '$bruto' data: python ${campo("data")}, kotlin ${momento.dataIso()}"
            }
            if (campo("hora") != momento.horaMinuto()) {
                divergencias += "  '$bruto' hora: python ${campo("hora")}, kotlin ${momento.horaMinuto()}"
            }
            if (campo("mes") != momento.mes) {
                divergencias += "  '$bruto' mês: python ${campo("mes")}, kotlin ${momento.mes}"
            }
            val esperadoDesl = campo("deslocamento_segundos").toInt()
            if (esperadoDesl != momento.deslocamento.totalSeconds) {
                divergencias += "  '$bruto' fuso: python $esperadoDesl s, kotlin ${momento.deslocamento.totalSeconds} s"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("leitura de data divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun o_ouro_de_datas_cobre_o_que_o_fixture_nao_cobre() {
        val recurso = javaClass.classLoader.getResourceAsStream("ouro/datas.json")!!
        val ouro = Json.parseToJsonElement(recurso.reader(Charsets.UTF_8).readText()).jsonObject
        val brutos = ouro["casos"]!!.jsonArray.map { it.jsonObject["bruto"]!!.jsonPrimitive.content }

        assertTrue(brutos.any { !it.contains("[") }, "falta data sem fuso — a lacuna que motivou este ouro")
        assertTrue(brutos.any { it.contains("/") }, "falta data em dd/mm/aaaa")
        assertTrue(brutos.any { it.contains(".") }, "falta fuso fracionário")
        assertTrue(brutos.any { it.length == 8 }, "falta data sem hora")
    }
}
