package com.fintips.motor

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.fail

/**
 * Harness do YAML gravado.
 *
 * É o teste mais literal do porte: compara **texto**, não valor. Aqui não
 * existe "deu no mesmo" — os dois motores escrevem no mesmo arquivo, e uma
 * aspa a mais ou a menos muda o tipo que o outro lê de volta.
 */
class OuroYamlTest {

    private val ouro by lazy {
        val recurso = javaClass.classLoader.getResourceAsStream("ouro/yaml.json")
            ?: fail("ouro/yaml.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        Json.parseToJsonElement(recurso.reader(Charsets.UTF_8).readText()).jsonObject
    }

    @Test
    fun cada_escalar_e_citado_exatamente_como_o_python_cita() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["escalares"]!!.jsonArray) {
            val c = caso.jsonObject
            val valor = c["valor"]!!.jsonPrimitive.content
            val esperado = c["linha"]!!.jsonPrimitive.content
            val obtido = "k: " + Yaml.escalar(valor)
            if (esperado != obtido) {
                divergencias += "  ${escapar(valor)}: python «$esperado», kotlin «$obtido»"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail(
                "a citação de escalar divergiu do PyYAML — o outro motor leria " +
                    "outro tipo:\n" + divergencias.joinToString("\n"),
            )
        }
    }

    @Test
    fun cada_float_sai_como_o_repr_do_python() {
        // o ponto de virada para científica é 1e16 no Python e 1e7 no Kotlin:
        // um patrimônio de dez milhões sairia como `1.0E7` e viraria texto
        val divergencias = mutableListOf<String>()
        for (caso in ouro["floats"]!!.jsonArray) {
            val c = caso.jsonObject
            val valor = c["valor_repr"]!!.jsonPrimitive.content.toDouble()
            val esperado = c["linha"]!!.jsonPrimitive.content
            val obtido = "k: " + Yaml.escalar(valor)
            if (esperado != obtido) {
                divergencias += "  ${c["valor_repr"]!!.jsonPrimitive.content}: " +
                    "python «$esperado», kotlin «$obtido»"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("a emissão de float divergiu:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun os_outros_tipos_e_o_layout_batem() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["outros_tipos"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = c["nome"]!!.jsonPrimitive.content
            val esperado = c["texto"]!!.jsonPrimitive.content
            val obtido = Yaml.emitir(objetoDe(nome))
            if (esperado != obtido) {
                divergencias += "  [$nome]\n    python:\n${recuar(esperado)}" +
                    "    kotlin:\n${recuar(obtido)}"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("o layout divergiu do PyYAML:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun os_documentos_inteiros_saem_identicos() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["documentos"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = c["nome"]!!.jsonPrimitive.content
            val esperado = c["texto"]!!.jsonPrimitive.content
            val obtido = Yaml.emitir(deJson(c["objeto_json"]!!))
            if (esperado != obtido) {
                divergencias += "  [$nome]\n    python:\n${recuar(esperado)}" +
                    "    kotlin:\n${recuar(obtido)}"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("documento gravado divergiu:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun a_hora_do_extrato_sai_citada_e_a_outra_nao() {
        // o caso que existe hoje, lado a lado, no mesmo arquivo canônico
        assertEquals("'10:00'", Yaml.escalar("10:00"), "10:00 sem aspas vira o inteiro 600")
        assertEquals("08:00", Yaml.escalar("08:00"), "08:00 não casa o sexagesimal e não leva aspas")
    }

    @Test
    fun o_emissor_recusa_o_que_nao_sabe_escrever() {
        // preferir a exceção ao arquivo torto: quebras seguidas e lista dentro
        // de lista não aparecem nos arquivos do FinTips, e inventar layout para
        // elas seria arriscar o que o outro motor lê
        for (entrada in listOf("a\n\nb", "a\r\nb")) {
            val recusou = try {
                Yaml.escalar(entrada); false
            } catch (e: IllegalArgumentException) {
                true
            }
            assertEquals(true, recusou, "o emissor aceitou ${escapar(entrada)} em silêncio")
        }
        val recusouLista = try {
            Yaml.emitir(mapOf("k" to listOf(listOf("x")))); false
        } catch (e: IllegalArgumentException) {
            true
        }
        assertEquals(true, recusouLista, "o emissor inventou layout para lista em lista")
    }

    // ------------------------------------------------------------- auxílios

    private fun escapar(v: String) =
        "«" + v.replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r") + "»"

    private fun recuar(texto: String) =
        texto.split("\n").joinToString("\n") { if (it.isEmpty()) it else "      $it" }

    /** O JSON perde a distinção inteiro/float, então os documentos vêm daqui. */
    private fun deJson(el: JsonElement): Any? = when (el) {
        is JsonNull -> null
        is JsonObject -> el.mapValues { deJson(it.value) }
        is JsonArray -> el.map { deJson(it) }
        is JsonPrimitive -> when {
            el.isString -> el.content
            el.content == "true" -> true
            el.content == "false" -> false
            el.content.contains('.') || el.content.contains('e') ||
                el.content.contains('E') -> el.content.toDouble()
            else -> el.content.toLong()
        }
    }

    /** Os casos de `outros_tipos` são montados aqui, com os tipos certos. */
    private fun objetoDe(nome: String): Any? = when (nome) {
        "inteiro" -> mapOf("k" to 42L)
        "inteiro_negativo" -> mapOf("k" to -7L)
        "zero" -> mapOf("k" to 0L)
        "float" -> mapOf("k" to 1.5)
        "float_inteiro" -> mapOf("k" to 100.0)
        "float_negativo" -> mapOf("k" to -0.01)
        "float_longo" -> mapOf("k" to 0.9926)
        "bool_true" -> mapOf("k" to true)
        "bool_false" -> mapOf("k" to false)
        "nulo" -> mapOf("k" to null)
        "lista_vazia" -> mapOf("k" to emptyList<Any?>())
        "mapa_vazio" -> mapOf("k" to emptyMap<String, Any?>())
        "lista_de_texto" -> mapOf("k" to listOf("a", "b"))
        "lista_de_mapas" -> mapOf("k" to listOf(mapOf("a" to 1L), mapOf("a" to 2L)))
        "mapa_aninhado" -> mapOf("k" to mapOf("a" to mapOf("b" to mapOf("c" to 1L))))
        "lista_em_mapa_em_lista" -> mapOf(
            "k" to listOf(mapOf("a" to listOf("x", "y")), mapOf("a" to emptyList<Any?>())),
        )
        "chave_que_precisa_de_aspas" -> linkedMapOf("10:00" to "v", "sim" to 1L)
        "raiz_lista" -> listOf(mapOf("a" to 1L), mapOf("b" to 2L))
        "ordem_preservada" -> linkedMapOf("z" to 1L, "a" to 2L, "m" to 3L, "b" to 4L)
        else -> fail("caso '$nome' do ouro não tem objeto montado no teste")
    }
}
