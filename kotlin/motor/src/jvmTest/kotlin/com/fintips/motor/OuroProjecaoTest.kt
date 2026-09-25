package com.fintips.motor

import kotlinx.datetime.LocalDate
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.fail

/**
 * Harness da projeção.
 *
 * O que este teste protege não é a fórmula — ela é quatro linhas — e sim o
 * **momento do arredondamento**. O Python mantém renda, variável e sobra em
 * precisão cheia durante os doze meses e só arredonda ao montar cada linha; o
 * patrimônio acumula o valor não arredondado. Uma porta que arredonde antes do
 * laço passa no primeiro mês e erra no décimo segundo, por centavos.
 *
 * Por isso o ouro traz `fator_nao_fecha_em_centavo` (3333,33 × 0,90 =
 * 2999,997) e `resto_de_plano_com_mais_de_duas_casas` (um resto de 2666,674).
 * Sem esses dois casos, um porte errado passaria limpo.
 */
class OuroProjecaoTest {

    private val ouro by lazy {
        val recurso = javaClass.classLoader.getResourceAsStream("ouro/projecao.json")
            ?: fail("ouro/projecao.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        Json.parseToJsonElement(recurso.reader(Charsets.UTF_8).readText()).jsonObject
    }

    private val inicio by lazy {
        LocalDate.parse(ouro["inicio_fixo"]!!.jsonPrimitive.content)
    }

    /** O JSON traz reais como "3333.33"; ler pelo texto evita passar por Double. */
    private fun dinheiro(o: JsonObject, chave: String): Dinheiro =
        Dinheiro.de(o[chave]!!.jsonPrimitive.content)

    private fun rodar(entrada: JsonObject): Projecao.Resultado {
        val base = entrada["baseline"]!!.jsonObject
        val planos = entrada["planos"]!!.jsonArray.map { it.jsonObject }.map { p ->
            Projecao.PlanoEmProjecao(
                id = p["id"]!!.jsonPrimitive.content,
                nome = p["nome"]!!.jsonPrimitive.content,
                falta = dinheiro(p, "falta"),
                prioridade = p["prioridade"]!!.jsonPrimitive.content,
                aportePlanejado = p["aporte_planejado_mes"]
                    ?.let { Dinheiro.de(it.jsonPrimitive.content) } ?: Dinheiro.ZERO,
                status = p["status"]!!.jsonPrimitive.content,
            )
        }
        return Projecao.projetar(
            rendaMediaMes = dinheiro(base, "renda_media_mes"),
            despesaMediaMes = dinheiro(base, "despesa_media_mes"),
            custoFixoMensal = dinheiro(entrada, "fixed_monthly"),
            saldoConta = dinheiro(entrada, "saldo_conta"),
            patrimonio = dinheiro(entrada, "patrimonio"),
            planos = planos,
            inicio = inicio,
            meses = entrada["meses"]!!.jsonPrimitive.content.toInt(),
            cenario = entrada["cenario"]!!.jsonPrimitive.content,
            reservaAlvoMeses = base["reserva_alvo_meses"]!!.jsonPrimitive.content.toInt(),
        )
    }

    @Test
    fun os_fatores_de_cenario_batem_com_o_python() {
        val esperados = ouro["cenarios"]!!.jsonObject
        assertEquals(esperados.keys, Projecao.CENARIOS.map { it.nome }.toSet())
        for ((nome, fatores) in esperados) {
            val c = Projecao.cenarioDe(nome)
            val f = fatores.jsonObject
            assertEquals(
                f["renda"]!!.jsonPrimitive.content.toDouble(), c.rendaPct / 100.0,
                "fator de renda do cenário '$nome' divergiu",
            )
            assertEquals(
                f["variavel"]!!.jsonPrimitive.content.toDouble(), c.variavelPct / 100.0,
                "fator de variável do cenário '$nome' divergiu",
            )
        }
    }

    @Test
    fun premissas_e_reserva_batem_com_o_python() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = c["nome"]!!.jsonPrimitive.content
            val saida = c["saida"]!!.jsonObject
            val obtido = rodar(c["entrada"]!!.jsonObject)

            val premissas = saida["premissas"]!!.jsonObject
            for ((campo, esperado, valor) in listOf(
                Triple("renda_mensal", premissas["renda_mensal"]!!, obtido.rendaMensal.paraDouble()),
                Triple("custo_fixo", premissas["custo_fixo"]!!, obtido.custoFixo.paraDouble()),
                Triple("custo_variavel", premissas["custo_variavel"]!!, obtido.custoVariavel.paraDouble()),
                Triple("sobra_mensal", premissas["sobra_mensal"]!!, obtido.sobraMensal.paraDouble()),
                Triple("fixo_pct_da_renda", premissas["fixo_pct_da_renda"]!!, obtido.fixoPctDaRenda),
            )) {
                val alvo = esperado.jsonPrimitive.content.toDouble()
                if (alvo != valor) divergencias += "  [$nome] $campo: python $alvo, kotlin $valor"
            }

            val reserva = saida["reserva"]!!.jsonObject
            val alvoReserva = reserva["alvo"]!!.jsonPrimitive.content.toDouble()
            if (alvoReserva != obtido.reservaAlvo.paraDouble()) {
                divergencias += "  [$nome] reserva.alvo: python $alvoReserva, " +
                    "kotlin ${obtido.reservaAlvo.paraDouble()}"
            }
            val atingida = reserva["atingida_em"]!!.let {
                if (it is JsonNull) null else it.jsonPrimitive.content
            }
            if (atingida != obtido.reservaAtingidaEm) {
                divergencias += "  [$nome] reserva.atingida_em: python $atingida, " +
                    "kotlin ${obtido.reservaAtingidaEm}"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("premissas/reserva divergiram do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun cada_mes_bate_com_o_python_inclusive_no_decimo_segundo() {
        // o mês 12 é o que pega arredondamento antecipado: o erro de um
        // centavo por mês só aparece depois de acumular
        val divergencias = mutableListOf<String>()
        for (caso in ouro["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = c["nome"]!!.jsonPrimitive.content
            val esperadas = c["saida"]!!.jsonObject["linhas"]!!.jsonArray
            val obtidas = rodar(c["entrada"]!!.jsonObject).linhas

            if (esperadas.size != obtidas.size) {
                divergencias += "  [$nome] meses: python ${esperadas.size}, kotlin ${obtidas.size}"
                continue
            }
            for ((i, esperadaEl) in esperadas.withIndex()) {
                val esperada = esperadaEl.jsonObject
                val obtida = obtidas[i].paraMapa()
                for ((campo, valorEsperado) in esperada) {
                    val alvo = valorEsperado.jsonPrimitive.content
                    val valor = obtida[campo].toString()
                    if (alvo != valor) {
                        divergencias += "  [$nome] mês ${i + 1} $campo: python $alvo, kotlin $valor"
                    }
                }
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("projeção mês a mês divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun planos_consomem_a_sobra_na_mesma_ordem_e_fecham_no_mesmo_mes() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = c["nome"]!!.jsonPrimitive.content
            val esperados = c["saida"]!!.jsonObject["planos"]!!.jsonArray
            val obtidos = rodar(c["entrada"]!!.jsonObject).planos

            if (esperados.size != obtidos.size) {
                divergencias += "  [$nome] planos: python ${esperados.size}, kotlin ${obtidos.size}"
                continue
            }
            for ((i, esperadoEl) in esperados.withIndex()) {
                val esperado = esperadoEl.jsonObject
                val obtido = obtidos[i]
                // a posição importa: é ela que diz quem comeu a sobra primeiro
                if (esperado["id"]!!.jsonPrimitive.content != obtido.id) {
                    divergencias += "  [$nome] posição $i: python " +
                        "${esperado["id"]!!.jsonPrimitive.content}, kotlin ${obtido.id}"
                    continue
                }
                val falta = esperado["falta_ao_fim"]!!.jsonPrimitive.content.toDouble()
                if (falta != obtido.faltaAoFim) {
                    divergencias += "  [$nome] ${obtido.id} falta_ao_fim: python $falta, " +
                        "kotlin ${obtido.faltaAoFim}"
                }
                val conclui = esperado["conclui_em"]!!.let {
                    if (it is JsonNull) null else it.jsonPrimitive.content
                }
                if (conclui != obtido.concluiEm) {
                    divergencias += "  [$nome] ${obtido.id} conclui_em: python $conclui, " +
                        "kotlin ${obtido.concluiEm}"
                }
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("planos na projeção divergiram do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun a_virada_de_ano_soma_mes_e_nao_dia() {
        // começar em 30 de novembro e somar 14 meses: se a porta somar 30 dias
        // por mês, fevereiro aparece duas vezes e dezembro some
        val v = ouro["virada_de_ano"]!!.jsonObject
        val esperados = v["meses"]!!.jsonArray.map { it.jsonPrimitive.content }
        val obtidos = Projecao.projetar(
            rendaMediaMes = Dinheiro.de("4000.00"),
            despesaMediaMes = Dinheiro.de("2000.00"),
            custoFixoMensal = Dinheiro.de("800.00"),
            saldoConta = Dinheiro.ZERO,
            patrimonio = Dinheiro.ZERO,
            planos = emptyList(),
            inicio = LocalDate.parse(v["inicio"]!!.jsonPrimitive.content),
            meses = esperados.size,
        ).linhas.map { it.mes }
        assertEquals(esperados, obtidos, "a sequência de meses divergiu na virada de ano")
    }

    @Test
    fun o_ouro_cobre_os_casos_que_escondem_arredondamento() {
        // harness é tão bom quanto o dado que ele compara: se estes casos
        // sumirem do ouro, um porte que arredonde cedo volta a passar
        val nomes = ouro["casos"]!!.jsonArray.map { it.jsonObject["nome"]!!.jsonPrimitive.content }
        for (obrigatorio in listOf(
            "fator_nao_fecha_em_centavo",
            "resto_de_plano_com_mais_de_duas_casas",
            "reserva_no_fio_do_sub_centavo",
            "sobra_negativa",
            "renda_zero",
            "fixo_maior_que_despesa",
            "cenario_desconhecido",
            "prioridade_ordena_e_empate_mantem_ordem",
        )) {
            assertEquals(true, obrigatorio in nomes, "o ouro perdeu o caso '$obrigatorio'")
        }
    }
}
