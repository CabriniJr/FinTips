package com.fintips.motor

import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalDateTime
import kotlinx.datetime.UtcOffset
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.fail

/**
 * Harness do consultor de compras.
 *
 * A comparação é recursiva e campo a campo contra o JSON do Python, porque a
 * saída tem forma variável: cada estratégia publica chaves diferentes, e é
 * justamente aí que uma porta distraída inventa ou perde um campo.
 *
 * `contexto_pessoal` e `precedentes` não entram — dependem do item 9 do porte,
 * e o ouro declara isso em `fora_do_escopo`. Um teste confere que a lista de
 * exclusões continua sendo exatamente essa, para a dívida não crescer calada.
 */
class OuroComprasTest {

    private val ouro by lazy {
        val recurso = javaClass.classLoader.getResourceAsStream("ouro/compras.json")
            ?: fail("ouro/compras.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        Json.parseToJsonElement(recurso.reader(Charsets.UTF_8).readText()).jsonObject
    }

    private val extrato by lazy {
        val fuso = UtcOffset(hours = -3)
        val fim = LocalDate.parse(ouro["periodo_fim"]!!.jsonPrimitive.content)
        val txs = ouro["extrato"]!!.jsonArray.map { it.jsonObject }.map { t ->
            val dia = LocalDate.parse(t["dia"]!!.jsonPrimitive.content)
            Transacao(
                id = t["id"]!!.jsonPrimitive.content,
                momento = Momento(
                    LocalDateTime(dia.year, dia.monthNumber, dia.dayOfMonth, 12, 0), fuso,
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
            periodoInicio = LocalDate(2026, 1, 1),
            periodoFim = fim,
            saldoDeclarado = Dinheiro.ZERO,
            saldoEm = fim,
            transacoes = txs,
            origem = "sintetico",
        )
    }

    private fun avaliar(e: JsonObject): Compras.Veredito {
        val base = e["baseline"]!!.jsonObject
        val intencao = Compras.Intencao(
            item = e["item"]!!.jsonPrimitive.content,
            preco = Dinheiro.de(e["preco"]!!.jsonPrimitive.content),
            categoria = e["categoria"]!!.jsonPrimitive.content,
            urgencia = e["urgencia"]!!.jsonPrimitive.content,
            parcelasPossiveis = e["parcelas_possiveis"]!!.jsonPrimitive.content.toInt(),
            jurosParcelamento = e["juros_parcelamento"]!!.jsonPrimitive.content.toDouble(),
            substitui = e["substitui"]!!.jsonPrimitive.content,
            tags = e["tags"]!!.jsonArray.map { it.jsonPrimitive.content },
        )
        val planos = e["planos"]!!.jsonArray.map { it.jsonObject }.map { p ->
            Compras.PlanoAvaliado(
                nome = p["nome"]!!.jsonPrimitive.content,
                status = p["status"]!!.jsonPrimitive.content,
                aporteNecessarioMes = Dinheiro.de(p["aporte_necessario_mes"]!!.jsonPrimitive.content),
            )
        }
        return Compras.avaliar(
            intencao = intencao,
            extrato = extrato,
            despesaMediaMes = Dinheiro.de(base["despesa_media_mes"]!!.jsonPrimitive.content),
            sobraMediaMes = Dinheiro.de(base["sobra_media_mes"]!!.jsonPrimitive.content),
            planos = planos,
            saldoConta = Dinheiro.de(e["saldo_conta"]!!.jsonPrimitive.content),
            patrimonio = Dinheiro.de(e["patrimonio"]!!.jsonPrimitive.content),
            reservaAlvoMeses = e["reserva_alvo_meses"]!!.jsonPrimitive.content.toDouble(),
        )
    }

    /** Compara o mapa do Kotlin contra o JSON do Python, entrando nos aninhados. */
    private fun confere(
        caminho: String, esperado: JsonElement, obtido: Any?, divergencias: MutableList<String>,
    ) {
        when (esperado) {
            is JsonNull -> if (obtido != null) divergencias += "  $caminho: python null, kotlin $obtido"

            is JsonObject -> {
                @Suppress("UNCHECKED_CAST")
                val mapa = obtido as? Map<String, Any?>
                if (mapa == null) {
                    divergencias += "  $caminho: python objeto, kotlin ${obtido?.let { it::class.simpleName }}"
                    return
                }
                if (esperado.keys != mapa.keys) {
                    divergencias += "  $caminho chaves: python ${esperado.keys}, kotlin ${mapa.keys}"
                    return
                }
                for ((k, v) in esperado) confere("$caminho.$k", v, mapa[k], divergencias)
            }

            is JsonArray -> {
                val lista = obtido as? List<*>
                if (lista == null || lista.size != esperado.size) {
                    divergencias += "  $caminho: python ${esperado.size} itens, " +
                        "kotlin ${(obtido as? List<*>)?.size}"
                    return
                }
                esperado.forEachIndexed { i, v -> confere("$caminho[$i]", v, lista[i], divergencias) }
            }

            else -> {
                val alvo = esperado.jsonPrimitive.content
                val valor = obtido?.toString() ?: "null"
                // o JSON serializa booleano e número sem aspas; comparar texto
                // basta, e evita decidir o tipo errado no meio do caminho
                if (alvo != valor) divergencias += "  $caminho: python $alvo, kotlin $valor"
            }
        }
    }

    @Test
    fun cada_caso_bate_campo_a_campo_com_o_python() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = c["nome"]!!.jsonPrimitive.content
            confere("[$nome]", c["saida"]!!, avaliar(c["entrada"]!!.jsonObject).paraMapa(), divergencias)
        }
        if (divergencias.isNotEmpty()) {
            fail("consultor de compras divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun os_seis_vereditos_aparecem_no_ouro() {
        // se um veredito sumir do ouro, a escada de decisão deixa de ser testada
        // no ramo que ele cobre — e é uma escada de seis degraus com ordem fixa
        val vistos = ouro["casos"]!!.jsonArray
            .map { it.jsonObject["saida"]!!.jsonObject["veredito"]!!.jsonPrimitive.content }
            .toSet()
        for (v in listOf(
            "nao_agora", "espere_30_dias", "juntar_antes",
            "escolha_entre_plano_e_compra", "pode_comprar", "cabe_com_planejamento",
        )) {
            assertEquals(true, v in vistos, "o ouro não exercita mais o veredito '$v'")
        }
    }

    @Test
    fun a_borda_do_multiplo_de_dez_vezes_fica_dos_dois_lados() {
        // a mediana do ouro cai no meio centavo (950,005). Em Double, 10x
        // exatos dariam 10.0000000000005 e o sinal dispararia no Kotlin e não
        // no Python — este teste é o que trava a aritmética inteira
        fun sinaisDe(nome: String): List<String> {
            val caso = ouro["casos"]!!.jsonArray.map { it.jsonObject }
                .first { it["nome"]!!.jsonPrimitive.content == nome }
            return avaliar(caso["entrada"]!!.jsonObject).arrependimento.sinais
        }
        for (nome in listOf("multiplo_exatamente_10x", "multiplo_10x_que_o_double_erraria")) {
            assertEquals(
                false, sinaisDe(nome).any { "ticket típico" in it },
                "[$nome] 10x exatos não podem disparar: a comparação é `> 10`, e em " +
                    "Double 5,70 ÷ 0,57 dá 10.000000000000002",
            )
        }
        for (nome in listOf("multiplo_um_centavo_acima_de_10x", "multiplo_um_centavo_acima_no_miudo")) {
            assertEquals(
                true, sinaisDe(nome).any { "ticket típico" in it },
                "[$nome] um centavo acima de 10x tem que disparar",
            )
        }
    }

    @Test
    fun a_parcela_sem_juros_divide_como_o_decimal_e_nao_como_o_double() {
        // 2599,99 ÷ 2 = 1299,995. O Decimal do Python arredonda para o par e dá
        // 1300,00; arredondar o Double daria 1299,99
        val caso = ouro["casos"]!!.jsonArray.map { it.jsonObject }
            .first { it["nome"]!!.jsonPrimitive.content == "parcela_sem_juros_no_meio_centavo" }
        val parcelado = avaliar(caso["entrada"]!!.jsonObject).estrategias
            .first { it.nome == "parcelado" }
        assertEquals(1300.0, parcelado.campos["valor_parcela"])
    }

    @Test
    fun o_ouro_cobre_as_bordas_que_um_caso_redondo_esconde() {
        val nomes = ouro["casos"]!!.jsonArray.map { it.jsonObject["nome"]!!.jsonPrimitive.content }
        for (obrigatorio in listOf(
            "multiplo_10x_que_o_double_erraria",     // a comparação inteira do múltiplo
            "porte_parecido_na_borda_exata",         // o `>=` da metade do preço
            "preco_zero_e_o_ramo_falso_do_python",   // zero é falso: custo e atraso saem nulos
            "parcela_sem_juros_no_meio_centavo",     // o quantize do Decimal
        )) {
            assertEquals(true, obrigatorio in nomes, "o ouro perdeu o caso '$obrigatorio'")
        }
    }

    @Test
    fun o_que_ficou_de_fora_do_porte_continua_declarado() {
        // dívida técnica que não some de vista: se alguém portar `contexto_pessoal`
        // e esquecer de tirar daqui, ou acrescentar uma exclusão nova sem dizer,
        // este teste acusa
        assertEquals(
            listOf("contexto_pessoal", "precedentes"),
            ouro["fora_do_escopo"]!!.jsonArray.map { it.jsonPrimitive.content },
        )
    }
}
