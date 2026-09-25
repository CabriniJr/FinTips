package com.fintips.motor

import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalDateTime
import kotlinx.datetime.UtcOffset
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.fail

/**
 * Harness dos planos.
 *
 * Os três testes que importam aqui cobrem armadilhas que erram **um número
 * plausível** em vez de estourar: o zero que é falso em Python, os limiares
 * `<=` e o teto da divisão do ritmo. Nenhuma delas apareceria num teste feito
 * com números redondos — por isso o ouro traz as bordas exatas.
 */
class OuroPlanosTest {

    private val ouro by lazy {
        val recurso = javaClass.classLoader.getResourceAsStream("ouro/planos.json")
            ?: fail("ouro/planos.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        Json.parseToJsonElement(recurso.reader(Charsets.UTF_8).readText()).jsonObject
    }

    private val hoje by lazy { LocalDate.parse(ouro["hoje_fixo"]!!.jsonPrimitive.content) }

    /** O mesmo extrato sintético que o gerador usou, remontado dos dados do ouro. */
    private val extrato by lazy {
        val fuso = UtcOffset(hours = -3)
        val txs = ouro["extrato"]!!.jsonArray.map { it.jsonObject }.map { t ->
            val dia = LocalDate.parse(t["dia"]!!.jsonPrimitive.content)
            val hora = if (t["fluxo"]!!.jsonPrimitive.content == Fluxos.RECEITA) 10 else 10
            Transacao(
                id = t["id"]!!.jsonPrimitive.content,
                momento = Momento(
                    LocalDateTime(dia.year, dia.monthNumber, dia.dayOfMonth, hora, 0), fuso,
                ),
                valor = Dinheiro(t["valor_centavos"]!!.jsonPrimitive.content.toLong()),
                memoBruto = "",
                fluxo = t["fluxo"]!!.jsonPrimitive.content,
                categoria = t["categoria"]!!.jsonPrimitive.content,
                contraparte = t["contraparte"]!!.jsonPrimitive.content,
            )
        }
        Extrato(
            conta = Conta(idHash = "acct:teste"),
            periodoInicio = txs.minOf { it.dia },
            periodoFim = txs.maxOf { it.dia },
            saldoDeclarado = Dinheiro.ZERO,
            saldoEm = txs.maxOf { it.dia },
            transacoes = txs,
            origem = "sintetico",
        )
    }

    private fun planoDe(p: JsonObject): Planos.Plano = Planos.Plano(
        id = p["id"]!!.jsonPrimitive.content,
        nome = p["nome"]?.jsonPrimitive?.content ?: p["id"]!!.jsonPrimitive.content,
        tipo = p["tipo"]?.jsonPrimitive?.content ?: "outro",
        custoAlvo = p["custo_alvo"]?.let { Dinheiro.de(it.jsonPrimitive.content) } ?: Dinheiro.ZERO,
        dataAlvo = p["data_alvo"]?.let { LocalDate.parse(it.jsonPrimitive.content) },
        prioridade = p["prioridade"]?.jsonPrimitive?.content ?: "media",
        aporteMensal = p["aporte_mensal"]?.let { Dinheiro.de(it.jsonPrimitive.content) }
            ?: Dinheiro.ZERO,
        guardado = p["guardado"]?.let { Dinheiro.de(it.jsonPrimitive.content) } ?: Dinheiro.ZERO,
        merchants = p["merchants"]?.jsonArray?.map { it.jsonPrimitive.content } ?: emptyList(),
        categorias = p["categorias"]?.jsonArray?.map { it.jsonPrimitive.content } ?: emptyList(),
    )

    private fun avaliar(entrada: JsonObject): Planos.Avaliacao = Planos.avaliar(
        plano = planoDe(entrada["plano"]!!.jsonObject),
        extrato = extrato,
        sobraMediaMes = Dinheiro.de(entrada["sobra_media_mes"]!!.jsonPrimitive.content),
        hoje = hoje,
    )

    @Test
    fun meses_ate_o_alvo_nunca_e_negativo_e_conta_mes_nao_dia() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["meses_ate_o_alvo"]!!.jsonArray) {
            val c = caso.jsonObject
            val alvoJson = c["alvo"]!!
            val alvo = if (alvoJson is JsonNull) null else LocalDate.parse(alvoJson.jsonPrimitive.content)
            val esperado = c["meses"]!!.let {
                if (it is JsonNull) null else it.jsonPrimitive.content.toInt()
            }
            val obtido = Planos.mesesAte(alvo, hoje)
            if (esperado != obtido) {
                divergencias += "  $alvo: python $esperado, kotlin $obtido"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("meses até o alvo divergiram do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun cada_campo_da_avaliacao_bate_com_o_python() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = c["nome"]!!.jsonPrimitive.content
            val esperada = c["saida"]!!.jsonObject
            val obtida = avaliar(c["entrada"]!!.jsonObject).paraMapa()

            // compara chave a chave: se o Python ganhar um campo novo e a porta
            // não, o harness precisa acusar em vez de ignorar
            if (esperada.keys != obtida.keys) {
                divergencias += "  [$nome] campos: python ${esperada.keys}, kotlin ${obtida.keys}"
                continue
            }
            for ((campo, valorEsperado) in esperada) {
                if (campo == "compras_relacionadas") continue   // tem teste próprio
                val alvo = if (valorEsperado is JsonNull) "null" else valorEsperado.jsonPrimitive.content
                val valor = obtida[campo]?.toString() ?: "null"
                if (alvo != valor) {
                    divergencias += "  [$nome] $campo: python $alvo, kotlin $valor"
                }
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("avaliação de plano divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun as_compras_do_plano_batem_em_ordem_e_valor() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = c["nome"]!!.jsonPrimitive.content
            val esperadas = c["saida"]!!.jsonObject["compras_relacionadas"]!!.jsonArray
            val obtidas = avaliar(c["entrada"]!!.jsonObject).comprasRelacionadas

            if (esperadas.size != obtidas.size) {
                divergencias += "  [$nome] compras: python ${esperadas.size}, kotlin ${obtidas.size}"
                continue
            }
            for ((i, esperadaEl) in esperadas.withIndex()) {
                val e = esperadaEl.jsonObject
                val o = obtidas[i]
                val alvo = listOf(
                    e["data"]!!.jsonPrimitive.content,
                    e["onde"]!!.jsonPrimitive.content,
                    e["valor"]!!.jsonPrimitive.content,
                )
                val valor = listOf(o.dia, o.onde, o.valor.paraDouble().toString())
                if (alvo != valor) divergencias += "  [$nome] compra $i: python $alvo, kotlin $valor"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("compras do plano divergiram do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun o_ouro_cobre_as_bordas_que_um_numero_redondo_esconde() {
        val nomes = ouro["casos"]!!.jsonArray.map { it.jsonObject["nome"]!!.jsonPrimitive.content }
        for (obrigatorio in listOf(
            "borda_exata_dos_60_pct",
            "borda_exata_da_capacidade",
            "um_centavo_alem_da_capacidade",
            "prazo_vencido_nao_divide_por_zero",
            "aporte_necessario_nao_fecha_em_centavo",
            "ritmo_arredonda_para_cima",
            "custo_alvo_zero",
            "sobra_negativa_zera_a_capacidade",
            "casa_por_contraparte_com_acento",
        )) {
            assertEquals(true, obrigatorio in nomes, "o ouro perdeu o caso '$obrigatorio'")
        }
    }

    @Test
    fun os_dois_limiares_ficam_de_lados_opostos_da_mesma_fronteira() {
        // lido direto do ouro: 600,00 em 60% da capacidade é confortável, e o
        // mesmo 600,00 igual à capacidade é apertado. Se a porta trocar `<=`
        // por `<`, os dois caem uma faixa
        fun statusDe(nome: String): String {
            val caso = ouro["casos"]!!.jsonArray
                .map { it.jsonObject }
                .first { it["nome"]!!.jsonPrimitive.content == nome }
            return avaliar(caso["entrada"]!!.jsonObject).status
        }
        assertEquals(Planos.Status.CONFORTAVEL, statusDe("borda_exata_dos_60_pct"))
        assertEquals(Planos.Status.APERTADO, statusDe("borda_exata_da_capacidade"))
        assertEquals(Planos.Status.INVIAVEL, statusDe("um_centavo_alem_da_capacidade"))
    }

    @Test
    fun viavel_acompanha_o_status_como_no_python() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = c["nome"]!!.jsonPrimitive.content
            val esperado = c["saida"]!!.jsonObject["viavel"]!!.jsonPrimitive.booleanOrNull
            val obtido = avaliar(c["entrada"]!!.jsonObject).viavel
            if (esperado != obtido) divergencias += "  [$nome] viavel: python $esperado, kotlin $obtido"
        }
        if (divergencias.isNotEmpty()) {
            fail("viabilidade divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }
}
