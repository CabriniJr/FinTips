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
 * Harness das causas.
 *
 * O que se protege aqui é mais regra de produto do que aritmética. As recusas
 * de gravação são o desenho do FinTips em código: se a porta aceitar uma causa
 * de origem `importacao`, o app passa a deduzir motivo do extrato — o erro que
 * o projeto inteiro existe para não cometer, e que nenhum teste de número
 * pegaria.
 */
class OuroCausasTest {

    private val ouro by lazy {
        val recurso = javaClass.classLoader.getResourceAsStream("ouro/causas.json")
            ?: fail("ouro/causas.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        Json.parseToJsonElement(recurso.reader(Charsets.UTF_8).readText()).jsonObject
    }

    private val hoje by lazy { LocalDate.parse(ouro["hoje_fixo"]!!.jsonPrimitive.content) }

    private val extrato by lazy {
        val fuso = UtcOffset(hours = -3)
        val txs = ouro["extrato"]!!.jsonArray.map { it.jsonObject }.map { t ->
            val dia = LocalDate.parse(t["dia"]!!.jsonPrimitive.content)
            Transacao(
                id = t["id"]!!.jsonPrimitive.content,
                momento = Momento(
                    LocalDateTime(dia.year, dia.monthNumber, dia.dayOfMonth, 10, 0), fuso,
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

    private fun causaDe(d: JsonObject): Causa {
        val efeito = d["efeito"]!!.jsonObject
        return Causa(
            id = d["id"]!!.jsonPrimitive.content,
            efeitoTipo = efeito["tipo"]!!.jsonPrimitive.content,
            efeitoRef = efeito["ref"]!!.jsonPrimitive.content,
            natureza = d["natureza"]!!.jsonPrimitive.content,
            enunciado = d["enunciado"]!!.jsonPrimitive.content,
            atitude = Atitude.de(d["atitude"]!!.jsonPrimitive.content)!!,
            atitudeNota = d["atitude_nota"]!!.jsonPrimitive.content,
            revisarEm = d["revisar_em"]!!.let {
                if (it is JsonNull) null else it.jsonPrimitive.content
            },
            criadoEm = d["criado_em"]!!.jsonPrimitive.content,
        )
    }

    private val causas by lazy {
        ouro["causas"]!!.jsonArray.map { causaDe(it.jsonObject) }
    }

    @Test
    fun os_efeitos_possiveis_batem_com_o_python() {
        assertEquals(
            ouro["efeitos"]!!.jsonArray.map { it.jsonPrimitive.content },
            Causas.EFEITOS,
            "a lista de efeitos divergiu — o índice do dossiê correlaciona por ela",
        )
    }

    @Test
    fun as_oito_recusas_de_gravacao_continuam_recusando() {
        // cada uma fecha um caminho diferente de o app passar a inventar motivo
        val prov = Proveniencia(
            origem = Origem.USUARIO, confianca = 1.0, porque = "a pessoa contou",
        )
        val tentativas = mapOf<String, () -> Unit>(
            "origem_heuristica" to {
                registro().gravar(
                    "categoria", "alimentacao", "gatilho", "peço delivery",
                    prov.copy(origem = Origem.HEURISTICA), hoje = hoje,
                )
            },
            "origem_importacao" to {
                registro().gravar(
                    "categoria", "alimentacao", "gatilho", "peço delivery",
                    prov.copy(origem = Origem.IMPORTACAO), hoje = hoje,
                )
            },
            "porque_vazio" to {
                registro().gravar(
                    "categoria", "alimentacao", "gatilho", "peço delivery",
                    prov.copy(porque = ""), hoje = hoje,
                )
            },
            "enunciado_vazio" to {
                registro().gravar("categoria", "alimentacao", "gatilho", "   ", prov, hoje = hoje)
            },
            "efeito_tipo_invalido" to {
                registro().gravar("chute", "alimentacao", "gatilho", "peço delivery", prov, hoje = hoje)
            },
            "efeito_ref_vazio" to {
                registro().gravar("categoria", "  ", "gatilho", "peço delivery", prov, hoje = hoje)
            },
            "natureza_vazia" to {
                registro().gravar("categoria", "alimentacao", " ", "peço delivery", prov, hoje = hoje)
            },
        )

        val esperadas = ouro["recusas"]!!.jsonArray.map { it.jsonObject }
            .filter { it["recusou"]!!.jsonPrimitive.booleanOrNull == true }
            .map { it["caso"]!!.jsonPrimitive.content }

        val divergencias = mutableListOf<String>()
        for (caso in esperadas) {
            // `atitude_invalida` não tem como acontecer no Kotlin: a atitude é
            // enum e o compilador recusa antes de qualquer teste rodar. É a
            // única mudança que a porta se permite — representação, não regra
            if (caso == "atitude_invalida") continue
            val tentativa = tentativas[caso] ?: run {
                divergencias += "  o ouro pede a recusa '$caso' e o teste não a exercita"
                return@run null
            } ?: continue
            val recusou = try {
                tentativa(); false
            } catch (e: IllegalArgumentException) {
                true
            }
            if (!recusou) divergencias += "  '$caso' foi aceita, e o Python recusa"
        }
        if (divergencias.isNotEmpty()) {
            fail("recusas de gravação divergiram:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun o_id_da_causa_bate_digito_por_digito() {
        val divergencias = mutableListOf<String>()
        for (caso in ouro["ids_estaveis"]!!.jsonArray) {
            val c = caso.jsonObject
            val obtido = novoId(
                "causa",
                c["efeito_tipo"]!!.jsonPrimitive.content,
                c["efeito_ref"]!!.jsonPrimitive.content,
                c["natureza"]!!.jsonPrimitive.content,
            )
            val esperado = c["id"]!!.jsonPrimitive.content
            if (esperado != obtido) {
                divergencias += "  ${c["efeito_ref"]!!.jsonPrimitive.content}/" +
                    "${c["natureza"]!!.jsonPrimitive.content}: python $esperado, kotlin $obtido"
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("id de causa divergiu:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun cobertura_e_filtros_batem_em_todos_os_cenarios() {
        val divergencias = mutableListOf<String>()
        for (cenario in ouro["cenarios"]!!.jsonArray) {
            val c = cenario.jsonObject
            val nome = c["nome"]!!.jsonPrimitive.content
            val quando = LocalDate.parse(c["hoje"]!!.jsonPrimitive.content)
            val ids = c["causas"]!!.jsonArray.map { it.jsonPrimitive.content }.toSet()
            val reg = Causas.Registro(causas.filter { it.id in ids })
            val saida = c["saida"]!!.jsonObject

            val esperada = saida["cobertura"]!!.jsonObject
            val obtida = reg.cobertura(extrato, quando).paraMapa()
            if (esperada.keys != obtida.keys) {
                divergencias += "  [$nome] chaves: python ${esperada.keys}, kotlin ${obtida.keys}"
                continue
            }
            for ((campo, valor) in esperada) {
                if (campo == "maiores_sem_causa") {
                    val esperadas = valor.jsonArray.map { it.jsonObject }
                    @Suppress("UNCHECKED_CAST")
                    val obtidas = obtida[campo] as List<Map<String, Any?>>
                    if (esperadas.size != obtidas.size) {
                        divergencias += "  [$nome] maiores_sem_causa: python ${esperadas.size}, " +
                            "kotlin ${obtidas.size}"
                        continue
                    }
                    esperadas.forEachIndexed { i, e ->
                        for ((k, v) in e) {
                            val alvo = v.jsonPrimitive.content
                            val obt = obtidas[i][k].toString()
                            if (alvo != obt) {
                                divergencias += "  [$nome] maiores_sem_causa[$i].$k: " +
                                    "python $alvo, kotlin $obt"
                            }
                        }
                    }
                    continue
                }
                val alvo = valor.jsonPrimitive.content
                val obt = obtida[campo].toString()
                if (alvo != obt) divergencias += "  [$nome] $campo: python $alvo, kotlin $obt"
            }

            for ((campo, obtidos) in listOf(
                "ativas" to reg.ativas(quando).map { it.id }.sorted(),
                "vencidas" to reg.vencidas(quando).map { it.id }.sorted(),
                "sem_atitude" to reg.semAtitude(quando).map { it.id }.sorted(),
            )) {
                val esperados = saida[campo]!!.jsonArray.map { it.jsonPrimitive.content }
                if (esperados != obtidos) {
                    divergencias += "  [$nome] $campo: python $esperados, kotlin $obtidos"
                }
            }
        }
        if (divergencias.isNotEmpty()) {
            fail("causas divergiram do motor Python:\n" + divergencias.joinToString("\n"))
        }
    }

    @Test
    fun a_causa_vencida_para_de_explicar_dinheiro() {
        // o par de cenários que trava a regra: a mesma causa, antes e depois do
        // prazo. Se a porta ignorar o vencimento, a cobertura não cai e a
        // triagem nunca volta a perguntar
        fun coberturaDe(nome: String): Double {
            val c = ouro["cenarios"]!!.jsonArray.map { it.jsonObject }
                .first { it["nome"]!!.jsonPrimitive.content == nome }
            val ids = c["causas"]!!.jsonArray.map { it.jsonPrimitive.content }.toSet()
            return Causas.Registro(causas.filter { it.id in ids })
                .cobertura(extrato, LocalDate.parse(c["hoje"]!!.jsonPrimitive.content))
                .coberturaPct
        }
        assertEquals(100.0, coberturaDe("a_mesma_antes_de_vencer"))
        assertEquals(
            57.1, coberturaDe("so_a_vencida_explica_o_transporte"),
            "a causa vencida continuou explicando dinheiro",
        )
    }

    @Test
    fun nao_existe_deteccao_de_causa_no_modulo_portado() {
        // o espelho do teste que o Python tem: se um dia alguém escrever
        // `detectarCausas()` aqui, é este teste que diz que o produto quebrou,
        // e não um teste de cálculo
        val fonte = java.io.File(
            "src/commonMain/kotlin/com/fintips/motor/Causas.kt",
        ).readText()
        for (proibido in listOf("fun detectar", "fun inferirCausa", "fun deduzir")) {
            assertEquals(
                false, proibido in fonte,
                "'$proibido' apareceu em Causas.kt — causa não se deriva do extrato",
            )
        }
    }

    private fun registro() = Causas.Registro()
}
