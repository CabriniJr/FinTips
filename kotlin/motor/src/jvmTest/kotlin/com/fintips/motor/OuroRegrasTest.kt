package com.fintips.motor

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
 * Harness da normalização de texto.
 *
 * Parece o mais bobo da lista e é um dos que mais importam: `norm` é a base de
 * toda comparação de nome do motor. Divergir num acento faz a mesma padaria
 * virar duas contrapartes, e o custo mensal dela se parte ao meio sem nenhum
 * erro aparecer em lugar nenhum.
 */
class OuroTextoTest {

    private fun ouro(): JsonObject {
        val r = javaClass.classLoader.getResourceAsStream("ouro/texto.json")
            ?: fail("ouro/texto.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        return Json.parseToJsonElement(r.reader(Charsets.UTF_8).readText()).jsonObject
    }

    @Test
    fun norm_slug_e_canonico_batem_com_o_python() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro()["casos"]!!.jsonArray) {
            val c = caso.jsonObject
            fun campo(k: String) = c[k]!!.jsonPrimitive.content
            val texto = campo("texto")

            if (campo("norm") != norm(texto)) {
                divergencias += "  norm('$texto') → python '${campo("norm")}', kotlin '${norm(texto)}'"
            }
            if (campo("slug") != slug(texto)) {
                divergencias += "  slug('$texto') → python '${campo("slug")}', kotlin '${slug(texto)}'"
            }
            if (campo("canonico") != nomeCanonico(texto)) {
                divergencias += "  canonico('$texto') → python '${campo("canonico")}', kotlin '${nomeCanonico(texto)}'"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("normalização divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun o_ouro_cobre_acento_sufixo_e_vazio() {
        val textos = ouro()["casos"]!!.jsonArray.map { it.jsonObject["texto"]!!.jsonPrimitive.content }
        assertTrue(textos.any { it.contains("ç") || it.contains("Ç") }, "falta cedilha")
        assertTrue(textos.any { it.contains("ã") || it.contains("õ") }, "falta til")
        assertTrue(textos.any { it.contains("LJ") }, "falta sufixo de loja")
        assertTrue(textos.any { it.contains("*") }, "falta código de adquirente")
        assertTrue(textos.any { it.startsWith("PF:") }, "falta pseudônimo, que passa intacto")
        assertTrue(textos.any { it.isBlank() }, "falta texto vazio")
    }
}

/**
 * Harness do motor de regras.
 *
 * O estado inicial das transações vem escrito no ouro, não da heurística — que
 * ainda não foi portada. Um ouro que dependesse dela testaria duas coisas ao
 * mesmo tempo, e quando falhasse ninguém saberia qual das duas quebrou.
 */
class OuroRegrasTest {

    private val ouro by lazy {
        val r = javaClass.classLoader.getResourceAsStream("ouro/regras.json")
            ?: fail("ouro/regras.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        Json.parseToJsonElement(r.reader(Charsets.UTF_8).readText()).jsonObject
    }

    private fun texto(o: JsonObject, k: String) = o[k]?.jsonPrimitive?.content ?: ""

    private val regras: List<Regra> by lazy {
        ouro["regras"]!!.jsonArray.map { el ->
            val o = el.jsonObject
            val q = o["quando"]!!.jsonObject
            val e = o["entao"]!!.jsonObject
            Regra(
                id = texto(o, "id"),
                quando = Condicao(
                    contraparteId = texto(q, "contraparte_id"),
                    contraparteContem = texto(q, "contraparte_contem"),
                    memoCasa = texto(q, "memo_casa"),
                    canal = texto(q, "canal"),
                    fluxo = texto(q, "fluxo"),
                    categoriaAtual = texto(q, "categoria_atual"),
                    valorMin = q["valor_min"]?.jsonPrimitive?.content?.toDoubleOrNull(),
                    valorMax = q["valor_max"]?.jsonPrimitive?.content?.toDoubleOrNull(),
                    diasSemana = q["dias_semana"]?.jsonArray?.map { it.jsonPrimitive.content.toInt() }
                        ?: emptyList(),
                    horaMin = q["hora_min"]?.jsonPrimitive?.content?.toIntOrNull(),
                    horaMax = q["hora_max"]?.jsonPrimitive?.content?.toIntOrNull(),
                ),
                entao = Efeito(
                    categoria = texto(e, "categoria"),
                    fluxo = texto(e, "fluxo"),
                    marcar = e["marcar"]?.jsonArray?.map { it.jsonPrimitive.content } ?: emptyList(),
                    rotulo = texto(e, "rotulo"),
                ),
                proveniencia = Proveniencia(
                    origem = Origem.de(texto(o, "origem")),
                    confianca = texto(o, "confianca").toDouble(),
                    porque = "ouro",
                ),
            )
        }
    }

    /** As transações no estado que o ouro registra, antes de aplicar as regras. */
    private val transacoes: List<Transacao> by lazy {
        val fixture = java.io.File("../../tests/fixture.ofx").let {
            if (it.exists()) it else java.io.File("tests/fixture.ofx")
        }
        val extrato = com.fintips.motor.ofx.lerOfx(fixture.readText(Charsets.UTF_8), texto(ouro, "sal"))
        val estados = ouro["estado_inicial"]!!.jsonArray.map { it.jsonObject }
        assertEquals(estados.size, extrato.transacoes.size, "fixture mudou desde a geração do ouro")

        extrato.transacoes.mapIndexed { i, tx ->
            val e = estados[i]
            assertEquals(texto(e, "id"), tx.id, "ordem das transações divergiu")
            tx.copy(
                contraparte = texto(e, "contraparte"),
                categoria = texto(e, "categoria"),
                canal = texto(e, "canal"),
                fluxo = texto(e, "fluxo"),
                origemCategoria = Origens.HEURISTICA,
                confiancaCategoria = 0.4,
                etiquetas = emptyList(),
            )
        }
    }

    @Test
    fun dia_da_semana_e_hora_batem_com_o_python() {
        // Um deslize de um aqui trocaria sábado por domingo em toda regra de
        // fim de semana, e uma categoria inteira sairia errada sem erro algum.
        val divergencias = mutableListOf<String>()
        ouro["estado_inicial"]!!.jsonArray.forEachIndexed { i, el ->
            val e = el.jsonObject
            val tx = transacoes[i]
            val diaEsperado = texto(e, "dia_semana").toInt()
            if (diaDaSemanaPython(tx) != diaEsperado) {
                divergencias += "  ${tx.id} dia: python $diaEsperado, kotlin ${diaDaSemanaPython(tx)}"
            }
            val horaEsperada = texto(e, "hora").toInt()
            if (tx.momento.local.hour != horaEsperada) {
                divergencias += "  ${tx.id} hora: python $horaEsperada, kotlin ${tx.momento.local.hour}"
            }
        }
        if (divergencias.isNotEmpty()) fail("calendário divergiu:\n" + divergencias.joinToString("\n"))
    }

    @Test
    fun precedencia_bate_com_o_python() {
        val esperada = ouro["precedencia"]!!.jsonArray.map { texto(it.jsonObject, "id") }
        val obtida = ativas(regras).map { it.id }
        assertEquals(esperada, obtida, "ordem de precedência divergiu")
    }

    @Test
    fun casamento_campo_a_campo_bate_com_o_python() {
        val divergencias = mutableListOf<String>()
        for ((i, caso) in ouro["casamentos"]!!.jsonArray.withIndex()) {
            val c = caso.jsonObject
            val tx = transacoes[i]
            val esperadas = c["casa_com"]!!.jsonArray.map { it.jsonPrimitive.content }.toSet()
            val obtidas = regras.filter { casa(it, tx) }.map { it.id }.toSet()
            if (esperadas != obtidas) {
                divergencias += "  ${tx.id}: python $esperadas, kotlin $obtidas"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("casamento de condição divergiu:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun aplicacao_e_estado_final_batem_com_o_python() {
        val (depois, resultado) = aplicar(regras, transacoes)

        val esperadoResultado = ouro["resultado"]!!.jsonObject
        assertEquals(texto(esperadoResultado, "regras_ativas").toInt(), resultado.regrasAtivas)
        assertEquals(texto(esperadoResultado, "transacoes_tocadas").toInt(), resultado.transacoesTocadas)
        assertEquals(texto(esperadoResultado, "sem_regra").toInt(), resultado.semRegra)

        val porRegraEsperado = esperadoResultado["por_regra"]!!.jsonObject
            .mapValues { it.value.jsonPrimitive.content.toInt() }
        assertEquals(porRegraEsperado, resultado.porRegra, "contagem por regra divergiu")

        val divergencias = mutableListOf<String>()
        ouro["transacoes_depois"]!!.jsonArray.forEachIndexed { i, el ->
            val e = el.jsonObject
            val tx = depois[i]
            fun confere(campo: String, esperado: String, obtido: String) {
                if (esperado != obtido) {
                    divergencias += "  [${tx.id}] $campo: python '$esperado', kotlin '$obtido'"
                }
            }
            confere("categoria", texto(e, "categoria"), tx.categoria)
            confere("fluxo", texto(e, "fluxo"), tx.fluxo)
            confere("contraparte", texto(e, "contraparte"), tx.contraparte)
            confere("origem_categoria", texto(e, "origem_categoria"), tx.origemCategoria)
            confere("confianca", texto(e, "confianca"), arredondar(tx.confiancaCategoria, 2).toString())
            confere("regra", texto(e, "regra"), tx.regraId)
            val etiquetasEsperadas = e["etiquetas"]!!.jsonArray.map { it.jsonPrimitive.content }
            if (etiquetasEsperadas != tx.etiquetas.sorted()) {
                divergencias += "  [${tx.id}] etiquetas: python $etiquetasEsperadas, kotlin ${tx.etiquetas.sorted()}"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("estado final divergiu:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun cobertura_bate_com_o_python() {
        val (depois, _) = aplicar(regras, transacoes)
        val cob = cobertura(depois)
        val esperada = ouro["cobertura"]!!.jsonObject

        assertEquals(texto(esperada, "despesa_total").toDouble(), cob.despesaTotal.paraDouble())
        assertEquals(
            texto(esperada, "classificado_por_decisao").toDouble(), cob.porDecisao.paraDouble(),
        )
        assertEquals(
            texto(esperada, "classificado_por_heuristica").toDouble(), cob.porHeuristica.paraDouble(),
        )
        assertEquals(texto(esperada, "cobertura_pct").toDouble(), cob.coberturaPct)
    }

    @Test
    fun autoridade_vence_especificidade() {
        // A propriedade de produto que o motor inteiro existe para garantir:
        // regra ampla do usuário ganha de regra detalhada da heurística.
        val ordem = ativas(regras).map { it.id }
        val usuarioAmpla = ordem.indexOf("r-usuario-ampla")
        val heuristicaAmpla = ordem.indexOf("r-heuristica-ampla")
        val agenteEspecifica = ordem.indexOf("r-agente-especifica")

        assertTrue(usuarioAmpla < agenteEspecifica, "usuário deveria vir antes do agente")
        assertTrue(agenteEspecifica < heuristicaAmpla, "agente deveria vir antes da heurística")
    }
}
