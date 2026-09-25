package com.fintips.motor

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
 * Harness do perfil.
 *
 * Três garantias diferentes, e vale separar:
 *
 * - **formato** — a evidência imprime número com o `:g` do Python. Detalhe de
 *   texto que vira divergência visível na tela e no que o agente lê.
 * - **casamento** — aderência, empate e piso por eixo. Empate devolve "sem
 *   leitura", que é estado honesto e não pode virar um arquétipo qualquer.
 * - **assinatura** — quem pode assinar, e quem derruba quem.
 */
class OuroPerfilTest {

    private val ouro by lazy {
        val recurso = javaClass.classLoader.getResourceAsStream("ouro/perfil.json")
            ?: fail("ouro/perfil.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        Json.parseToJsonElement(recurso.reader(Charsets.UTF_8).readText()).jsonObject
    }

    private val catalogo by lazy {
        ouro["catalogo"]!!.jsonArray.map { it.jsonObject }.map { e ->
            Perfil.Eixo(
                id = e["id"]!!.jsonPrimitive.content,
                nome = e["nome"]!!.jsonPrimitive.content,
                oQueE = e["o_que_e"]!!.jsonPrimitive.content,
                minimo = e["minimo"]!!.jsonPrimitive.content.toDouble(),
                arquetipos = e["arquetipos"]!!.jsonArray.map { it.jsonObject }.map { a ->
                    Perfil.Arquetipo(
                        id = a["id"]!!.jsonPrimitive.content,
                        nome = a["nome"]!!.jsonPrimitive.content,
                        descricao = a["descricao"]!!.jsonPrimitive.content,
                        oQueMuda = a["o_que_muda"]!!.jsonPrimitive.content,
                        eixo = a["eixo"]!!.jsonPrimitive.content,
                        sinais = a["sinais"]!!.jsonArray.map { it.jsonObject }.map { s ->
                            Perfil.Sinal(
                                indicador = s["indicador"]!!.jsonPrimitive.content,
                                minimo = s["min"]!!.let {
                                    if (it is JsonNull) null else it.jsonPrimitive.content.toDouble()
                                },
                                maximo = s["max"]!!.let {
                                    if (it is JsonNull) null else it.jsonPrimitive.content.toDouble()
                                },
                                peso = s["peso"]!!.jsonPrimitive.content.toDouble(),
                            )
                        },
                    )
                },
            )
        }
    }

    private fun indicadoresDe(o: JsonObject): Map<String, Double?> =
        o.mapValues { (_, v) -> if (v is JsonNull) null else v.jsonPrimitive.content.toDouble() }

    @Test
    fun o_formato_g_bate_com_o_python_inclusive_na_cientifica() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["formato_g"]!!.jsonArray) {
            val c = caso.jsonObject
            val valor = c["valor"]!!.jsonPrimitive.content.toDouble()
            val esperado = c["texto"]!!.jsonPrimitive.content
            val obtido = Perfil.formatoG(valor)
            if (esperado != obtido) divergencias += "  $valor: python '$esperado', kotlin '$obtido'"
        }
        if (divergencias.isNotEmpty()) {
            fail("o formato :g divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun o_casamento_bate_eixo_a_eixo_em_todos_os_conjuntos() {
        val divergencias = mutableListOf<String>()
        for (conjunto in ouro["casamentos"]!!.jsonArray) {
            val c = conjunto.jsonObject
            val nome = c["nome"]!!.jsonPrimitive.content
            val ind = indicadoresDe(c["indicadores"]!!.jsonObject)
            val esperados = c["eixos"]!!.jsonArray
            val obtidos = Perfil.casar(ind, catalogo)

            if (esperados.size != obtidos.size) {
                divergencias += "  [$nome] eixos: python ${esperados.size}, kotlin ${obtidos.size}"
                continue
            }
            esperados.forEachIndexed { i, esperadoEl ->
                val esperado = esperadoEl.jsonObject
                val obtido = obtidos[i].paraMapa()
                confere("[$nome].${esperado["eixo"]!!.jsonPrimitive.content}",
                    esperado, obtido, divergencias)
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("casamento de arquétipo divergiu do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    private fun confere(
        caminho: String, esperado: kotlinx.serialization.json.JsonElement,
        obtido: Any?, divergencias: MutableList<String>,
    ) {
        when (esperado) {
            is JsonNull -> if (obtido != null) divergencias += "  $caminho: python null, kotlin $obtido"
            is JsonObject -> {
                @Suppress("UNCHECKED_CAST")
                val mapa = obtido as? Map<String, Any?>
                if (mapa == null) {
                    divergencias += "  $caminho: python objeto, kotlin $obtido"
                    return
                }
                if (esperado.keys != mapa.keys) {
                    divergencias += "  $caminho chaves: python ${esperado.keys}, kotlin ${mapa.keys}"
                    return
                }
                for ((k, v) in esperado) confere("$caminho.$k", v, mapa[k], divergencias)
            }
            is kotlinx.serialization.json.JsonArray -> {
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
                if (alvo != valor) divergencias += "  $caminho: python $alvo, kotlin $valor"
            }
        }
    }

    @Test
    fun o_empate_devolve_sem_leitura_em_vez_de_um_arquetipo_qualquer() {
        // com todos os indicadores ausentes, nenhum sinal casa e todos os
        // arquétipos empatam em zero. Uma ordenação instável devolveria um
        // vencedor diferente a cada execução, e nunca acusaria o empate
        val conjunto = ouro["casamentos"]!!.jsonArray.map { it.jsonObject }
            .first { it["nome"]!!.jsonPrimitive.content == "tudo_ausente" }
        val leituras = Perfil.casar(indicadoresDe(conjunto["indicadores"]!!.jsonObject), catalogo)
        for (l in leituras) {
            assertEquals(null, l.sugerido, "[${l.eixo}] empate virou sugestão")
            assertEquals("empate entre arquétipos", l.semLeituraPorque)
        }
    }

    @Test
    fun as_recusas_de_assinatura_continuam_recusando() {
        val prov = Proveniencia(
            origem = Origem.USUARIO, confianca = 1.0, porque = "sou PJ e recebo por projeto",
        )
        val tentativas = mapOf<String, () -> Unit>(
            "origem_heuristica" to {
                Perfil.Registro().assinar("renda", "variavel", prov.copy(origem = Origem.HEURISTICA), catalogo)
            },
            "origem_importacao" to {
                Perfil.Registro().assinar("renda", "variavel", prov.copy(origem = Origem.IMPORTACAO), catalogo)
            },
            "porque_vazio" to {
                Perfil.Registro().assinar("renda", "variavel", prov.copy(porque = ""), catalogo)
            },
            "eixo_desconhecido" to {
                Perfil.Registro().assinar("signo", "variavel", prov, catalogo)
            },
            "arquetipo_fora_do_eixo" to {
                Perfil.Registro().assinar("renda", "acumulacao", prov, catalogo)
            },
            "personalizado_sem_nome" to {
                Perfil.Registro().assinar("renda", "personalizado", prov, catalogo)
            },
            "personalizado_sem_descricao" to {
                Perfil.Registro().assinar("renda", "personalizado", prov, catalogo, nome = "Meu jeito")
            },
            "personalizado_completo" to {
                Perfil.Registro().assinar(
                    "renda", "personalizado", prov, catalogo,
                    nome = "Meu jeito", descricao = "recebo por projeto e por aluguel",
                )
            },
        )

        val divergencias = mutableListOf<String>()
        for (caso in ouro["recusas"]!!.jsonArray) {
            val c = caso.jsonObject
            val nome = c["caso"]!!.jsonPrimitive.content
            val deviaRecusar = c["recusou"]!!.jsonPrimitive.booleanOrNull!!
            val tentativa = tentativas[nome] ?: run {
                divergencias += "  o ouro pede o caso '$nome' e o teste não o exercita"
                return@run null
            } ?: continue
            val recusou = try {
                tentativa(); false
            } catch (e: IllegalArgumentException) {
                true
            }
            if (recusou != deviaRecusar) {
                divergencias += "  '$nome': python recusou=$deviaRecusar, kotlin recusou=$recusou"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("recusas de assinatura divergiram:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun autoridade_menor_nao_derruba_maior_e_maior_derruba_menor() {
        val autoridade = ouro["autoridade"]!!.jsonObject

        val reg = Perfil.Registro()
        reg.assinar(
            "renda", "variavel",
            Proveniencia(origem = Origem.USUARIO, confianca = 1.0, porque = "a pessoa afirmou"),
            catalogo,
        )
        val depoisDoAgente = reg.assinar(
            "renda", "fixa",
            Proveniencia(origem = Origem.AGENTE, confianca = 1.0, porque = "o agente concluiu"),
            catalogo,
        )
        assertEquals(
            autoridade["agente_nao_derruba_usuario"]!!.jsonObject["arquetipo"]!!.jsonPrimitive.content,
            depoisDoAgente.arquetipo,
            "o palpite do agente apagou o que a pessoa afirmou",
        )

        val reg2 = Perfil.Registro()
        reg2.assinar(
            "renda", "variavel",
            Proveniencia(origem = Origem.AGENTE, confianca = 1.0, porque = "o agente concluiu"),
            catalogo,
        )
        val depoisDoUsuario = reg2.assinar(
            "renda", "fixa",
            Proveniencia(origem = Origem.USUARIO, confianca = 1.0, porque = "a pessoa corrigiu"),
            catalogo,
        )
        assertEquals(
            autoridade["usuario_derruba_agente"]!!.jsonObject["arquetipo"]!!.jsonPrimitive.content,
            depoisDoUsuario.arquetipo,
            "a correção da pessoa não derrubou o palpite do agente",
        )
        assertEquals("variavel", depoisDoUsuario.substituiu)

        // autoridade IGUAL substitui: a pessoa muda de ideia sobre o próprio
        // perfil, e a segunda afirmação vale. Com `>=` no lugar de `>`, a
        // primeira assinatura trancaria o eixo para sempre
        val reg3 = Perfil.Registro()
        reg3.assinar(
            "renda", "variavel",
            Proveniencia(origem = Origem.USUARIO, confianca = 1.0, porque = "achei que era isso"),
            catalogo,
        )
        val mesma = reg3.assinar(
            "renda", "mista",
            Proveniencia(
                origem = Origem.USUARIO, confianca = 1.0, porque = "pensando melhor, é mista",
            ),
            catalogo,
        )
        assertEquals(
            autoridade["mesma_autoridade_substitui"]!!.jsonObject["arquetipo"]!!
                .jsonPrimitive.content,
            mesma.arquetipo,
            "a pessoa não conseguiu corrigir a própria assinatura",
        )
    }

    @Test
    fun empate_acima_do_minimo_tambem_devolve_sem_leitura() {
        // o empate que importa: as faixas do catálogo são inclusivas dos dois
        // lados, então 35,0 casa com 'enxuto' e 'carregado' ao mesmo tempo, com
        // aderência 1.0. É o único empate capaz de virar sugestão falsa, porque
        // passa do mínimo do eixo
        val conjunto = ouro["casamentos"]!!.jsonArray.map { it.jsonObject }
            .first { it["nome"]!!.jsonPrimitive.content == "empate_acima_do_minimo" }
        val leituras = Perfil.casar(indicadoresDe(conjunto["indicadores"]!!.jsonObject), catalogo)
        val custo = leituras.first { it.eixo == "custo" }
        assertEquals(1.0, custo.candidatos[0].aderencia)
        assertEquals(1.0, custo.candidatos[1].aderencia)
        assertEquals(null, custo.sugerido, "empate com aderência cheia virou sugestão")
        assertEquals("empate entre arquétipos", custo.semLeituraPorque)
    }

    @Test
    fun a_cobertura_do_perfil_comeca_em_zero() {
        val conjunto = ouro["casamentos"]!!.jsonArray.map { it.jsonObject }
            .first { it["nome"]!!.jsonPrimitive.content == "poupador_disciplinado" }
        val ind = indicadoresDe(conjunto["indicadores"]!!.jsonObject)

        val vazio = Perfil.montar(ind, Perfil.Registro(), catalogo)
        assertEquals(0.0, vazio.coberturaPct, "perfil sem assinatura não começa em 0%")
        assertEquals(0, vazio.assinados)

        val reg = Perfil.Registro()
        reg.assinar(
            "renda", "variavel",
            Proveniencia(origem = Origem.USUARIO, confianca = 1.0, porque = "sou PJ"),
            catalogo,
        )
        val comUm = Perfil.montar(ind, reg, catalogo)
        assertEquals(20.0, comUm.coberturaPct, "um eixo de cinco tem que dar 20%")
        // o conjunto sugere 'fixa' para renda e a pessoa assinou 'variavel'
        assertEquals(listOf("renda"), comUm.divergencias)
    }
}
