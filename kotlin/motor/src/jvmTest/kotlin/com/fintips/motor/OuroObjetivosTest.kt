package com.fintips.motor

import com.fintips.motor.vida.Check
import com.fintips.motor.vida.CorrelacaoResumo
import com.fintips.motor.vida.Etapa
import com.fintips.motor.vida.Objetivo
import com.fintips.motor.vida.OrigemDoRegistro
import com.fintips.motor.vida.PESOS_DO_OBJETIVO
import com.fintips.motor.vida.TIPOS_DE_ETAPA
import com.fintips.motor.vida.cumprimento
import com.fintips.motor.vida.reajusteProposto
import com.fintips.motor.vida.scoreDoObjetivo
import com.fintips.motor.vida.situacaoDaEtapa
import com.fintips.motor.vida.statusDoObjetivo
import kotlinx.datetime.LocalDate
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.double
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * Harness diferencial dos objetivos.
 *
 * O que este arquivo protege não é "o score funciona" — é que **os dois
 * motores devolvem o mesmo número**. São coisas diferentes: uma fórmula pode
 * estar certa nos dois lados e ainda assim divergir na terceira casa, e
 * divergência de score não aparece em tela nenhuma. Aparece aqui ou não
 * aparece.
 *
 * A família `empates_de_arredondamento` é a parte afiada. Ela carrega os casos
 * em que o score cai exatamente em `.x5`, onde o HALF_EVEN do Python e a
 * divisão crua de `Double` discordam por um décimo. Alguns desses empates o
 * ponto flutuante resolve para cima e outros para baixo **dentro do mesmo
 * conjunto** — o que significa que nenhuma regra de desempate escrita à mão
 * passa aqui: só passa quem faz a mesma conta, na mesma ordem.
 */
class OuroObjetivosTest {

    private val ouro: JsonObject by lazy {
        val texto = this::class.java.getResource("/ouro/objetivos.json")!!.readText()
        Json.parseToJsonElement(texto).jsonObject
    }

    private fun dia(s: String?): LocalDate? = s?.let { LocalDate.parse(it) }

    private fun etapaDe(o: JsonObject): Etapa = Etapa(
        id = o["id"]!!.jsonPrimitive.content,
        titulo = o["titulo"]!!.jsonPrimitive.content,
        tipo = o["tipo"]!!.jsonPrimitive.content,
        prazo = dia(o["prazo"]?.jsonPrimitive?.contentOrNull),
        prazoOriginal = dia(o["prazo_original"]?.jsonPrimitive?.contentOrNull),
        adiamentos = o["adiamentos"]?.jsonPrimitive?.int ?: 0,
        custo = o["custo"]?.jsonPrimitive?.contentOrNull?.toDouble() ?: 0.0,
        dependeDe = o["depende_de"]?.jsonArray?.map { it.jsonPrimitive.content } ?: emptyList(),
        obrigatoria = o["obrigatoria"]?.jsonPrimitive?.content?.toBoolean() ?: true,
    )

    private fun objetivoDe(o: JsonObject): Objetivo = Objetivo(
        id = o["id"]!!.jsonPrimitive.content,
        titulo = o["titulo"]!!.jsonPrimitive.content,
        porque = o["porque"]?.jsonPrimitive?.content ?: "",
        comecouEm = dia(o["comecou_em"]?.jsonPrimitive?.contentOrNull),
        dataAlvo = dia(o["data_alvo"]?.jsonPrimitive?.contentOrNull),
        etapas = o["etapas"]!!.jsonArray.map { etapaDe(it.jsonObject) },
        // O ouro só carrega objetivo assinado: rascunho não chega a ter score.
        assinadoEm = LocalDate.parse("2026-09-01"),
    )

    private fun checksDe(caso: JsonObject, objetivoId: String): List<Check> =
        caso["feitos"]!!.jsonArray.map {
            val f = it.jsonObject
            Check(
                objetivoId = objetivoId,
                etapaId = f["etapa"]!!.jsonPrimitive.content,
                dia = LocalDate.parse(f["dia"]!!.jsonPrimitive.content),
                origem = OrigemDoRegistro.USUARIO,
            )
        }

    @Test
    fun os_pesos_e_os_tipos_sao_os_mesmos() {
        val pesos = ouro["pesos"]!!.jsonObject
        assertEquals(pesos.size, PESOS_DO_OBJETIVO.size)
        pesos.forEach { (k, v) ->
            assertEquals(v.jsonPrimitive.int, PESOS_DO_OBJETIVO[k], "peso de $k")
        }
        assertEquals(
            ouro["tipos_de_etapa"]!!.jsonArray.map { it.jsonPrimitive.content },
            TIPOS_DE_ETAPA,
        )
    }

    @Test
    fun a_situacao_de_cada_etapa_bate() {
        for (c in ouro["situacoes"]!!.jsonArray) {
            val caso = c.jsonObject
            val nome = caso["nome"]!!.jsonPrimitive.content
            val obj = Objetivo(
                id = "o1", titulo = "o1",
                comecouEm = LocalDate.parse("2026-09-01"),
                dataAlvo = LocalDate.parse("2026-12-01"),
                assinadoEm = LocalDate.parse("2026-09-01"),
                etapas = listOf(
                    Etapa("a", "a", prazo = LocalDate.parse("2026-09-30")),
                    Etapa("b", "b", prazo = LocalDate.parse("2026-10-14"), dependeDe = listOf("a")),
                    Etapa("c", "c", prazo = LocalDate.parse("2026-10-20"), dependeDe = listOf("b")),
                    Etapa("sem-prazo", "sem-prazo"),
                ),
            )
            val checks = checksDe(caso, "o1")
            val hoje = LocalDate.parse(caso["hoje"]!!.jsonPrimitive.content)
            val feito = cumprimento(obj, checks)
            for ((id, esperado) in caso["etapas"]!!.jsonObject) {
                assertEquals(
                    esperado.jsonPrimitive.content,
                    situacaoDaEtapa(obj.etapa(id)!!, feito, hoje),
                    "$nome: etapa $id",
                )
            }
            assertEquals(
                caso["status"]!!.jsonPrimitive.content,
                statusDoObjetivo(obj, checks, hoje),
                "$nome: status",
            )
        }
    }

    private fun conferirScore(caso: JsonObject, rotulo: String) {
        val obj = objetivoDe(caso["objetivo"]!!.jsonObject)
        val checks = checksDe(caso, obj.id)
        val hoje = LocalDate.parse(caso["hoje"]!!.jsonPrimitive.content)
        val corrJson = caso["correlacao"]?.jsonObject
        val corr = if (corrJson == null) CorrelacaoResumo() else CorrelacaoResumo(
            custoRestante = corrJson["custo_restante"]?.jsonPrimitive?.doubleOrNull ?: 0.0,
            disponivelAteLa = corrJson["disponivel_ate_la"]?.jsonPrimitive?.doubleOrNull,
            missoesLigadas = corrJson["missoes_ligadas"]?.jsonPrimitive?.int ?: 0,
            missoesDePe = corrJson["missoes_de_pe"]?.jsonPrimitive?.int ?: 0,
        )
        val sc = scoreDoObjetivo(obj, checks, hoje, corr)
        val esperado = caso["esperado"]!!.jsonObject

        assertEquals(esperado["score"]!!.jsonPrimitive.double, sc.score, "$rotulo: score")
        assertEquals(
            esperado["peso_aplicado"]!!.jsonPrimitive.int, sc.pesoAplicado,
            "$rotulo: peso aplicado",
        )
        esperado["faixa"]?.let {
            assertEquals(it.jsonPrimitive.content, sc.faixa, "$rotulo: faixa")
        }
        val comps = esperado["componentes"]!!.jsonArray.map { it.jsonObject }
        assertEquals(comps.size, sc.componentes.size, "$rotulo: número de componentes")
        comps.zip(sc.componentes).forEach { (esp, got) ->
            val dim = esp["dimensao"]!!.jsonPrimitive.content
            assertEquals(dim, got.dimensao, "$rotulo: ordem das dimensões")
            // `null` é parte do contrato: dimensão sem base não vira zero.
            assertEquals(
                esp["valor"]!!.jsonPrimitive.doubleOrNull, got.valor,
                "$rotulo: valor de $dim",
            )
            assertEquals(
                esp["pontos"]!!.jsonPrimitive.doubleOrNull, got.pontos,
                "$rotulo: pontos de $dim",
            )
        }
    }

    @Test
    fun o_score_bate_em_todas_as_dimensoes() {
        for (c in ouro["scores"]!!.jsonArray) {
            val caso = c.jsonObject
            conferirScore(caso, caso["nome"]!!.jsonPrimitive.content)
        }
    }

    @Test
    fun os_empates_de_arredondamento_batem() {
        val casos = ouro["empates_de_arredondamento"]!!.jsonArray
        for (c in casos) {
            val caso = c.jsonObject
            val nome = caso["nome"]!!.jsonPrimitive.content
            val n = caso["etapas"]!!.jsonPrimitive.int
            val feitas = caso["cumpridas_no_prazo"]!!.jsonPrimitive.int
            val adiadas = caso["adiadas"]!!.jsonPrimitive.int

            val etapas = (0 until n).map { i ->
                val adi = if (i < adiadas) 1 else 0
                Etapa(
                    id = "e$i", titulo = "e$i",
                    prazo = LocalDate.parse("2026-09-10"),
                    prazoOriginal = LocalDate.parse(if (adi > 0) "2026-09-09" else "2026-09-10"),
                    adiamentos = adi,
                )
            }
            val obj = Objetivo(
                id = "t$n-$feitas-$adiadas", titulo = "t",
                comecouEm = LocalDate.parse("2026-09-01"),
                dataAlvo = LocalDate.parse("2026-12-01"),
                assinadoEm = LocalDate.parse("2026-09-01"),
                etapas = etapas,
            )
            val checks = (0 until feitas).map {
                Check(obj.id, "e$it", LocalDate.parse("2026-09-09"), OrigemDoRegistro.USUARIO)
            }
            val sc = scoreDoObjetivo(obj, checks, LocalDate.parse("2026-10-14"))
            val esperado = caso["esperado"]!!.jsonObject
            assertEquals(esperado["score"]!!.jsonPrimitive.double, sc.score, "$nome: score")
            assertEquals(
                esperado["peso_aplicado"]!!.jsonPrimitive.int, sc.pesoAplicado,
                "$nome: peso aplicado",
            )
            esperado["componentes"]!!.jsonArray.map { it.jsonObject }
                .zip(sc.componentes).forEach { (esp, got) ->
                    assertEquals(
                        esp["pontos"]!!.jsonPrimitive.doubleOrNull, got.pontos,
                        "$nome: pontos de ${got.dimensao}",
                    )
                }
        }
        // Se a família encolher, o teste continua verde sem provar nada.
        assertEquals(10, casos.size, "a família de empates perdeu casos")
    }

    @Test
    fun a_cascata_do_reajuste_bate() {
        for (c in ouro["reajustes"]!!.jsonArray) {
            val caso = c.jsonObject
            val nome = caso["nome"]!!.jsonPrimitive.content
            val obj = objetivoDe(caso["objetivo"]!!.jsonObject)
            val checks = checksDe(caso, obj.id)
            val hoje = LocalDate.parse(caso["hoje"]!!.jsonPrimitive.content)
            val p = reajusteProposto(obj, checks, hoje)
            val esperado = caso["esperado"]!!.jsonObject

            val movs = esperado["movimentos"]!!.jsonArray.map { it.jsonObject }
            assertEquals(movs.size, p.movimentos.size, "$nome: quantos movimentos")
            movs.zip(p.movimentos).forEach { (esp, got) ->
                assertEquals(esp["etapa"]!!.jsonPrimitive.content, got.etapa, "$nome: etapa")
                assertEquals(
                    esp["de"]!!.jsonPrimitive.content, got.de.toString(), "$nome: de",
                )
                assertEquals(
                    esp["para"]!!.jsonPrimitive.content, got.para.toString(),
                    "$nome: para (${got.etapa})",
                )
                assertEquals(esp["dias"]!!.jsonPrimitive.int, got.dias, "$nome: dias")
                assertEquals(
                    esp["motivo"]!!.jsonPrimitive.content, got.motivo, "$nome: motivo",
                )
            }
            assertEquals(
                esperado["folga_antes_em_dias"]!!.jsonPrimitive.contentOrNull?.toInt(),
                p.folgaAntesEmDias, "$nome: folga antes",
            )
            assertEquals(
                esperado["folga_depois_em_dias"]!!.jsonPrimitive.contentOrNull?.toInt(),
                p.folgaDepoisEmDias, "$nome: folga depois",
            )
            assertEquals(
                esperado["estoura_o_alvo"]!!.jsonPrimitive.content.toBoolean(),
                p.estouraOAlvo, "$nome: estoura o alvo",
            )
            assertEquals(false, p.assinado, "$nome: proposta nasce sem assinatura")
        }
    }
}
