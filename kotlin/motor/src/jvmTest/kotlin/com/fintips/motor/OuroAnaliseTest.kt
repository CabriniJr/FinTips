package com.fintips.motor

import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalDateTime
import kotlinx.datetime.UtcOffset
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Harness da análise.
 *
 * As séries são sintéticas de propósito. O fixture tem um mês só, e com um mês
 * a volatilidade é sempre 0.0 — o cálculo mais delicado do baseline nunca
 * seria exercitado. É a mesma lição de `ouro/datas.json`, aplicada antes de
 * doer: harness é tão bom quanto o dado que ele compara.
 *
 * As séries cobrem: um mês, dois meses idênticos (volatilidade zero), três
 * meses variando, mês no vermelho, renda zero (divisão por zero), divisão que
 * não fecha em centavo exato, e cinco meses com números feios.
 */
class OuroAnaliseTest {

    private val ouro by lazy {
        val r = javaClass.classLoader.getResourceAsStream("ouro/analise.json")
            ?: fail("ouro/analise.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        Json.parseToJsonElement(r.reader(Charsets.UTF_8).readText()).jsonObject
    }

    private fun texto(o: JsonObject, k: String) = o[k]?.jsonPrimitive?.content ?: ""
    private val fuso = UtcOffset(hours = -3)

    /** Reconstrói o mesmo extrato que o gerador montou do lado Python. */
    private fun extratoDe(meses: List<JsonObject>, inicioDia: Int = 1, fimDia: Int = 28): Extrato {
        val txs = mutableListOf<Transacao>()
        meses.forEachIndexed { i, m ->
            val (ano, mes) = texto(m, "mes").split("-").map { it.toInt() }
            val renda = texto(m, "renda_centavos").toLongOrNull() ?: 0L
            val despesa = texto(m, "despesa_centavos").toLongOrNull() ?: 0L
            if (renda != 0L) {
                txs.add(
                    Transacao(
                        id = "i$i", momento = Momento(LocalDateTime(ano, mes, 5, 10, 0), fuso),
                        valor = Dinheiro(renda), memoBruto = "renda",
                        fluxo = Fluxos.RECEITA, categoria = "renda", contraparte = "Empregador",
                    )
                )
            }
            if (despesa != 0L) {
                txs.add(
                    Transacao(
                        id = "e$i", momento = Momento(LocalDateTime(ano, mes, 15, 10, 0), fuso),
                        valor = Dinheiro(-despesa), memoBruto = "gasto",
                        fluxo = Fluxos.DESPESA, categoria = "outros", contraparte = "Loja",
                    )
                )
            }
        }
        val primeiro = txs.minOf { it.dia }
        val ultimo = txs.maxOf { it.dia }
        return Extrato(
            conta = Conta(idHash = "acct:teste"),
            periodoInicio = LocalDate(primeiro.year, primeiro.monthNumber, inicioDia),
            periodoFim = LocalDate(ultimo.year, ultimo.monthNumber, fimDia),
            saldoDeclarado = Dinheiro.ZERO,
            saldoEm = ultimo,
            transacoes = txs,
            origem = "sintetico",
        )
    }

    @Test
    fun baseline_bate_com_o_python_em_todas_as_series() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = texto(c, "nome")
            val extrato = extratoDe(c["entrada"]!!.jsonArray.map { it.jsonObject })
            val b = baseline(extrato)
            val e = c["baseline"]!!.jsonObject

            fun confere(campo: String, esperado: String, obtido: String) {
                if (esperado != obtido) divergencias += "  [$nome] $campo: python $esperado, kotlin $obtido"
            }
            confere("renda_media", texto(e, "renda_media_mes"), b.rendaMediaMes.paraDouble().toString())
            confere("despesa_media", texto(e, "despesa_media_mes"), b.despesaMediaMes.paraDouble().toString())
            confere("sobra_media", texto(e, "sobra_media_mes"), b.sobraMediaMes.paraDouble().toString())
            confere("taxa_poupanca", texto(e, "taxa_poupanca_media"), b.taxaPoupancaMedia.toString())
            confere("volatilidade", texto(e, "volatilidade_despesa"), b.volatilidadeDespesa.toString())
            confere("meses_no_vermelho", texto(e, "meses_no_vermelho"), b.mesesNoVermelho.toString())

            val mesesEsperados = e["meses_considerados"]!!.jsonArray.map { it.jsonPrimitive.content }
            if (mesesEsperados != b.mesesConsiderados) {
                divergencias += "  [$nome] meses: python $mesesEsperados, kotlin ${b.mesesConsiderados}"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("baseline divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun mes_a_mes_bate_com_o_python() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = texto(c, "nome")
            val extrato = extratoDe(c["entrada"]!!.jsonArray.map { it.jsonObject })
            val obtidos = mensal(extrato.transacoes)
            val esperados = c["meses"]!!.jsonArray.map { it.jsonObject }

            if (obtidos.size != esperados.size) {
                divergencias += "  [$nome] número de meses: python ${esperados.size}, kotlin ${obtidos.size}"
                continue
            }
            esperados.forEachIndexed { i, e ->
                val m = obtidos[i]
                if (texto(e, "mes") != m.mes) divergencias += "  [$nome] mes[$i] divergiu"
                if (texto(e, "renda_centavos").toLong() != m.renda.centavos) {
                    divergencias += "  [$nome] ${m.mes} renda: python ${texto(e, "renda_centavos")}, kotlin ${m.renda.centavos}"
                }
                if (texto(e, "despesa_centavos").toLong() != m.despesa.centavos) {
                    divergencias += "  [$nome] ${m.mes} despesa: python ${texto(e, "despesa_centavos")}, kotlin ${m.despesa.centavos}"
                }
                if (texto(e, "sobra_centavos").toLong() != m.sobra.centavos) {
                    divergencias += "  [$nome] ${m.mes} sobra: python ${texto(e, "sobra_centavos")}, kotlin ${m.sobra.centavos}"
                }
                if (texto(e, "taxa_poupanca").toDouble() != m.taxaPoupanca) {
                    divergencias += "  [$nome] ${m.mes} taxa: python ${texto(e, "taxa_poupanca")}, kotlin ${m.taxaPoupanca}"
                }
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("mês a mês divergiu:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun recorte_de_ponta_bate_com_o_python() {
        // Um mês pela metade nas pontas derruba a média e faz despesa estável
        // parecer volátil — o score pioraria por artefato de recorte.
        val entrada = listOf(
            mapOf("mes" to "2026-01", "renda" to 500000L, "despesa" to 300000L),
            mapOf("mes" to "2026-02", "renda" to 500000L, "despesa" to 320000L),
            mapOf("mes" to "2026-03", "renda" to 500000L, "despesa" to 310000L),
        )
        val divergencias = mutableListOf<String>()
        for (caso in ouro["recortes_de_ponta"]!!.jsonArray) {
            val c = caso.jsonObject
            val inicioDia = texto(c, "inicio_dia").toInt()
            val fimDia = texto(c, "fim_dia").toInt()
            val txs = mutableListOf<Transacao>()
            entrada.forEachIndexed { i, m ->
                val (ano, mes) = (m["mes"] as String).split("-").map { it.toInt() }
                txs.add(Transacao("i$i", Momento(LocalDateTime(ano, mes, 5, 10, 0), fuso),
                    Dinheiro(m["renda"] as Long), "renda", fluxo = Fluxos.RECEITA,
                    categoria = "renda", contraparte = "Empregador"))
                txs.add(Transacao("e$i", Momento(LocalDateTime(ano, mes, 15, 10, 0), fuso),
                    Dinheiro(-(m["despesa"] as Long)), "gasto", fluxo = Fluxos.DESPESA,
                    categoria = "outros", contraparte = "Loja"))
            }
            val extrato = Extrato(
                conta = Conta("acct:teste"),
                periodoInicio = LocalDate(2026, 1, inicioDia),
                periodoFim = LocalDate(2026, 3, fimDia),
                saldoDeclarado = Dinheiro.ZERO, saldoEm = LocalDate(2026, 3, fimDia),
                transacoes = txs, origem = "sintetico",
            )
            val esperados = c["meses_completos"]!!.jsonArray.map { it.jsonPrimitive.content }
            val obtidos = mesesCompletos(extrato).map { it.mes }
            if (esperados != obtidos) {
                divergencias += "  início dia $inicioDia, fim dia $fimDia: python $esperados, kotlin $obtidos"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("recorte de ponta divergiu:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun recorrencias_batem_com_o_python() {
        val bloco = ouro["recorrencias"]!!.jsonObject
        val txs = bloco["entrada"]!!.jsonArray.map { el ->
            val o = el.jsonObject
            val (ano, mes) = texto(o, "mes").split("-").map { it.toInt() }
            Transacao(
                id = texto(o, "id"),
                momento = Momento(LocalDateTime(ano, mes, 12, 12, 0), fuso),
                valor = Dinheiro(texto(o, "centavos").toLong()),
                memoBruto = "", fluxo = Fluxos.DESPESA,
                categoria = texto(o, "categoria"), contraparte = texto(o, "contraparte"),
            )
        }

        val obtidas = recorrencias(txs)
        val esperadas = bloco["saida"]!!.jsonArray.map { it.jsonObject }

        assertEquals(esperadas.size, obtidas.size, "número de recorrências divergiu")

        val divergencias = mutableListOf<String>()
        esperadas.forEachIndexed { i, e ->
            val r = obtidas[i]
            fun confere(campo: String, esperado: String, obtido: String) {
                if (esperado != obtido) {
                    divergencias += "  [${r.contraparte}] $campo: python $esperado, kotlin $obtido"
                }
            }
            confere("contraparte", texto(e, "contraparte"), r.contraparte)
            confere("categoria", texto(e, "categoria"), r.categoria)
            confere("tipo", texto(e, "tipo"), r.tipo)
            confere("vezes", texto(e, "vezes"), r.ocorrencias.toString())
            confere("valor_tipico", texto(e, "valor_tipico"), r.valorTipico.toString())
            confere("custo_mensal", texto(e, "custo_mensal_centavos"), r.custoMensal.centavos.toString())
            val mesesEsperados = e["meses"]!!.jsonArray.map { it.jsonPrimitive.content }
            if (mesesEsperados != r.meses) {
                divergencias += "  [${r.contraparte}] meses: python $mesesEsperados, kotlin ${r.meses}"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("recorrências divergiram:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun as_tres_cadencias_aparecem_no_ouro() {
        // Assinatura, sangria e recorrente pedem conselhos diferentes. Um ouro
        // que só tivesse uma delas deixaria as outras duas sem proteção.
        val tipos = ouro["recorrencias"]!!.jsonObject["saida"]!!.jsonArray
            .map { it.jsonObject["tipo"]!!.jsonPrimitive.content }.toSet()
        assertEquals(setOf("assinatura", "sangria", "recorrente"), tipos)
    }

    @Test
    fun mediana_de_contagem_par_cai_no_meio_centavo() {
        // Guardar isso em Dinheiro perderia a metade e mudaria a amplitude que
        // decide se algo é assinatura. Em Double a conta é exata.
        assertEquals(10.015, medianaDeCentavos(listOf(1001L, 1002L)))
        assertEquals(10.01, medianaDeCentavos(listOf(1001L)))
        assertEquals(0.0, medianaDeCentavos(emptyList()))
        assertEquals(107.5, medianaDeCentavos(listOf(8000L, 9500L, 12000L, 15000L)))
    }

    @Test
    fun serie_com_volatilidade_existe_no_ouro() {
        // A armadilha que o fixture escondia: com um mês só, volatilidade é
        // sempre zero e o cálculo nunca é testado.
        val volatilidades = ouro["casos"]!!.jsonArray.map {
            it.jsonObject["baseline"]!!.jsonObject["volatilidade_despesa"]!!.jsonPrimitive.content.toDouble()
        }
        assertTrue(volatilidades.any { it > 0.0 }, "nenhuma série exercita a volatilidade")
        assertTrue(volatilidades.any { it == 0.0 }, "nenhuma série exercita o caso de volatilidade zero")
    }
}
