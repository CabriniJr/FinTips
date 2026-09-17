package com.fintips.motor

import kotlinx.datetime.LocalDate
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Harness dos contratos.
 *
 * Duas coisas diferentes são protegidas aqui, e vale separar:
 *
 * - **Comportamento** — autoridade, id estável, especificidade, prioridade.
 *   Se divergir, o motor Kotlin classifica transação diferente do Python.
 * - **Formato de gravação** — as chaves e a ordem do `to_dict`. Se divergir, o
 *   YAML que um motor grava deixa de ser legível pelo outro, e quem migrar
 *   perde o histórico de decisões. Este é o tipo de quebra que não aparece em
 *   nenhum cálculo: aparece como arquivo corrompido semanas depois.
 */
class OuroContratosTest {

    private val ouro by lazy {
        val recurso = javaClass.classLoader.getResourceAsStream("ouro/contratos.json")
            ?: fail("ouro/contratos.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        Json.parseToJsonElement(recurso.reader(Charsets.UTF_8).readText()).jsonObject
    }

    private val hoje = LocalDate(2026, 6, 15)

    // -------------------------------------------------------- comportamento

    @Test
    fun autoridade_e_verdade_batem_com_o_python() {
        for (caso in ouro["autoridade"]!!.jsonArray) {
            val c = caso.jsonObject
            val chave = c["origem"]!!.jsonPrimitive.content
            val origem = Origem.de(chave)
            assertEquals(chave, origem.chave, "origem não reconhecida: $chave")
            assertEquals(
                c["autoridade"]!!.jsonPrimitive.content.toInt(), origem.autoridade,
                "autoridade de $chave divergiu",
            )
            assertEquals(
                c["e_verdade"]!!.jsonPrimitive.booleanOrNull, origem.eVerdade,
                "e_verdade de $chave divergiu",
            )
        }
    }

    @Test
    fun id_estavel_bate_digito_por_digito() {
        // Se divergir, regravar a mesma causa cria uma segunda em vez de
        // atualizar a primeira.
        val divergencias = mutableListOf<String>()
        for (caso in ouro["ids"]!!.jsonArray) {
            val c = caso.jsonObject
            val prefixo = c["prefixo"]!!.jsonPrimitive.content
            val partes = c["partes"]!!.jsonArray.map { it.jsonPrimitive.content }
            val esperado = c["id"]!!.jsonPrimitive.content
            val obtido = novoId(prefixo, *partes.toTypedArray())
            if (esperado != obtido) {
                divergencias += "  novoId($prefixo, $partes) → python $esperado, kotlin $obtido"
            }
        }
        if (divergencias.isNotEmpty()) fail("id divergiu:\n" + divergencias.joinToString("\n"))
    }

    @Test
    fun especificidade_e_serializacao_de_condicao_batem() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["especificidade"]!!.jsonArray) {
            val c = caso.jsonObject
            val quando = c["quando"]!!.jsonObject
            val cond = condicaoDe(quando)

            val esperada = c["especificidade"]!!.jsonPrimitive.content.toInt()
            if (cond.especificidade() != esperada) {
                divergencias += "  $quando especificidade: python $esperada, kotlin ${cond.especificidade()}"
            }
            val vazia = c["vazia"]!!.jsonPrimitive.booleanOrNull
            if (cond.vazia() != vazia) {
                divergencias += "  $quando vazia: python $vazia, kotlin ${cond.vazia()}"
            }
            val serializadoEsperado = c["serializado"]!!.jsonObject
            val chavesEsperadas = serializadoEsperado.keys.toList()
            val chavesObtidas = cond.paraMapa().keys.toList()
            if (chavesEsperadas != chavesObtidas) {
                divergencias += "  $quando chaves: python $chavesEsperadas, kotlin $chavesObtidas"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("condição divergiu:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun prioridade_de_regra_bate_com_o_python() {
        // A ordem é a decisão de produto: autoridade vence especificidade, que
        // vence confiança. Uma regra genérica que a pessoa afirmou ganha de uma
        // regra detalhada que a heurística chutou.
        val divergencias = mutableListOf<String>()
        for (caso in ouro["prioridade_de_regra"]!!.jsonArray) {
            val c = caso.jsonObject
            val regra = Regra(
                id = "r-teste",
                quando = condicaoDe(c["quando"]!!.jsonObject),
                entao = Efeito(categoria = "lazer"),
                proveniencia = Proveniencia(
                    origem = Origem.de(c["origem"]!!.jsonPrimitive.content),
                    confianca = c["confianca"]!!.jsonPrimitive.content.toDouble(),
                    porque = "ouro",
                ),
            )
            val esperada = c["prioridade"]!!.jsonArray.map { it.jsonPrimitive.content }
            val (a, e, cf) = regra.prioridade()
            val obtida = listOf(a.toString(), e.toString(), cf.toString())
            if (esperada.map { it.toDouble() } != obtida.map { it.toDouble() }) {
                divergencias += "  ${c["origem"]} → python $esperada, kotlin $obtida"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("prioridade de regra divergiu:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun prioridade_de_triagem_bate_inclusive_no_tipo_desconhecido() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["prioridade_de_triagem"]!!.jsonArray) {
            val c = caso.jsonObject
            val tipo = c["tipo"]!!.jsonPrimitive.content
            val impacto = c["impacto_mensal"]!!.jsonPrimitive.content.toDouble()
            val esperada = c["prioridade"]!!.jsonPrimitive.content.toDouble()
            val item = ItemDeTriagem(
                id = "t", tipo = tipo, titulo = "", impactoMensal = impacto, porqueImporta = "",
            )
            if (item.prioridade != esperada) {
                divergencias += "  $tipo/$impacto → python $esperada, kotlin ${item.prioridade}"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("prioridade de triagem divergiu:\n" + divergencias.joinToString("\n"))
        }
    }

    // ---------------------------------------------------- formato de arquivo

    @Test
    fun serializacao_mantem_chaves_e_ordem() {
        val s = ouro["serializacao"]!!.jsonObject
        val quando = ouro["quando_fixo"]!!.jsonPrimitive.content

        val prov = Proveniencia(
            origem = Origem.USUARIO, confianca = 1.0, porque = "a pessoa afirmou",
            evidencia = listOf("tx-1", "tx-2"), quando = quando, porQuem = "claude",
        )
        confereMapa("proveniencia", s["proveniencia"]!!.jsonObject, prov.paraMapa())

        val causa = Causa(
            id = "causa-abc", efeitoTipo = "categoria", efeitoRef = "alimentacao",
            natureza = "gatilho", enunciado = "peço delivery depois do plantão",
            atitude = Atitude.ACEITAR, atitudeNota = "é o custo de trabalhar à noite",
            evidencia = listOf("tx-9"), proveniencia = prov,
            revisarEm = "2027-01-01", criadoEm = quando,
        )
        confereMapa("causa", s["causa"]!!.jsonObject, causa.paraMapa(hoje))

        val custo = CustoFixo(
            id = "cf-abc", rotulo = "Transporte trabalho", baseTipo = "categoria",
            baseRef = "transporte-trabalho", valorMensal = 79.5,
            metodo = "mediana_meses_completos", natureza = "rotina", proveniencia = prov,
        )
        confereMapa("custo_fixo", s["custo_fixo"]!!.jsonObject, custo.paraMapa())

        val fato = Fato(
            chave = "moradia.situacao", valor = "com_familia", tipo = "texto",
            proveniencia = prov,
        )
        confereMapa("fato", s["fato"]!!.jsonObject, fato.paraMapa(hoje))
    }

    @Test
    fun vocabulario_de_atitude_bate_com_o_python() {
        // Lista fechada: o dossiê e as alavancas calculam em cima dela.
        val esperadas = ouro["atitudes"]!!.jsonArray.map { it.jsonPrimitive.content }
        val obtidas = Atitude.entries.map { it.chave }
        assertEquals(esperadas, obtidas, "vocabulário de atitude divergiu")
        for (chave in esperadas) {
            assertTrue(Atitude.de(chave) != null, "atitude '$chave' não reconhecida")
        }
        assertTrue(Atitude.de("dar_um_jeito") == null, "atitude inventada deveria ser recusada")
    }

    // ------------------------------------------------------------ auxiliares

    private fun condicaoDe(o: JsonObject) = Condicao(
        contraparteId = texto(o, "contraparte_id"),
        contraparteContem = texto(o, "contraparte_contem"),
        memoCasa = texto(o, "memo_casa"),
        canal = texto(o, "canal"),
        fluxo = texto(o, "fluxo"),
        categoriaAtual = texto(o, "categoria_atual"),
        valorMin = o["valor_min"]?.jsonPrimitive?.content?.toDoubleOrNull(),
        valorMax = o["valor_max"]?.jsonPrimitive?.content?.toDoubleOrNull(),
        diasSemana = o["dias_semana"]?.jsonArray?.map { it.jsonPrimitive.content.toInt() } ?: emptyList(),
        horaMin = o["hora_min"]?.jsonPrimitive?.content?.toIntOrNull(),
        horaMax = o["hora_max"]?.jsonPrimitive?.content?.toIntOrNull(),
    )

    private fun texto(o: JsonObject, chave: String) = o[chave]?.jsonPrimitive?.content ?: ""

    /** Compara chaves, ordem e valores — os três importam para o arquivo. */
    private fun confereMapa(nome: String, esperado: JsonObject, obtido: Map<String, Any?>) {
        assertEquals(
            esperado.keys.toList(), obtido.keys.toList(),
            "$nome: chaves ou ordem divergiram",
        )
        for ((chave, valorEsperado) in esperado) {
            val valorObtido = obtido[chave]
            val iguais = when (valorEsperado) {
                is JsonNull -> valorObtido == null
                is JsonPrimitive -> comparaPrimitivo(valorEsperado, valorObtido)
                is JsonObject -> {
                    @Suppress("UNCHECKED_CAST")
                    val mapa = valorObtido as? Map<String, Any?>
                    mapa != null && valorEsperado.keys.toList() == mapa.keys.toList() &&
                        valorEsperado.all { (k, v) -> comparaLivre(v, mapa[k]) }
                }
                is JsonArray -> {
                    val lista = valorObtido as? List<*>
                    lista != null && valorEsperado.size == lista.size &&
                        valorEsperado.zip(lista).all { (v, o) -> comparaLivre(v, o) }
                }
                else -> false
            }
            if (!iguais) {
                fail("$nome.$chave: python $valorEsperado, kotlin $valorObtido")
            }
        }
    }

    private fun comparaLivre(esperado: Any?, obtido: Any?): Boolean = when (esperado) {
        is JsonNull -> obtido == null
        is JsonPrimitive -> comparaPrimitivo(esperado, obtido)
        is JsonObject -> {
            @Suppress("UNCHECKED_CAST")
            val mapa = obtido as? Map<String, Any?>
            mapa != null && esperado.all { (k, v) -> comparaLivre(v, mapa[k]) }
        }
        is JsonArray -> {
            val lista = obtido as? List<*>
            lista != null && esperado.size == lista.size &&
                esperado.zip(lista).all { (v, o) -> comparaLivre(v, o) }
        }
        else -> esperado == obtido
    }

    private fun comparaPrimitivo(esperado: JsonPrimitive, obtido: Any?): Boolean {
        if (esperado is JsonNull) return obtido == null
        val texto = esperado.content
        return when (obtido) {
            null -> false
            is String -> texto == obtido
            is Boolean -> texto.toBooleanStrictOrNull() == obtido
            is Double -> texto.toDoubleOrNull() == obtido
            is Int -> texto.toIntOrNull() == obtido
            is Long -> texto.toLongOrNull() == obtido
            else -> texto == obtido.toString()
        }
    }
}
