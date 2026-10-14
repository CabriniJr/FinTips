package com.fintips.motor

import com.fintips.motor.vida.Atributo
import com.fintips.motor.vida.Cadencia
import com.fintips.motor.vida.Missao
import com.fintips.motor.vida.OrigemDoRegistro
import com.fintips.motor.vida.RegistroDeMissao
import com.fintips.motor.vida.RegraDeclarada
import com.fintips.motor.vida.Vida
import com.fintips.motor.vida.FormatoDeVida
import com.fintips.motor.vida.coberturaDeEvidencia
import com.fintips.motor.vida.contextoDeCompra
import com.fintips.motor.vida.contextoDePlanos
import com.fintips.motor.vida.mesesDeAporte
import com.fintips.motor.vida.estadoDiario
import com.fintips.motor.vida.forcaDosAtributos
import kotlinx.datetime.LocalDate
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.fail

/**
 * Harness do domínio de vida.
 *
 * Este é o único módulo em que o Kotlin veio primeiro: as seis frentes nasceram
 * aqui, porque não existiam no motor Python. Agora que existem nos dois, o ouro
 * trava a paridade na direção de sempre — **o Python é a referência**, mesmo
 * tendo chegado depois.
 *
 * O caso que justifica o harness inteiro é o terço exato. Uma missão cumprida
 * de três dá 33.3 no Python (`round(x, 1)`) e 33.33333333333333 no Kotlin se a
 * divisão for crua. Nenhum teste de propriedade pegaria isso: as duas respostas
 * "parecem certas", e a diferença só apareceria quando alguém comparasse a
 * barra do app com o número do painel.
 */
class OuroVidaTest {

    private val ouro by lazy {
        val r = javaClass.classLoader.getResourceAsStream("ouro/vida.json")
            ?: fail("ouro/vida.json não encontrado. Gere com: python3 scripts/gerar-ouro.py")
        Json.parseToJsonElement(r.reader(Charsets.UTF_8).readText()).jsonObject
    }

    private fun dia(iso: String) = LocalDate.parse(iso)

    private fun missao(id: String, atributo: String, cadencia: String, sensor: Boolean) = Missao(
        id = id,
        titulo = id,
        atributo = Atributo.de(atributo) ?: fail("atributo '$atributo' não existe no Kotlin"),
        cadencia = Cadencia.de(cadencia) ?: fail("cadência '$cadencia' não existe no Kotlin"),
        sensorPossivel = sensor,
    )

    // ---------------------------------------------------------- vocabulário

    @Test
    fun as_seis_frentes_e_as_cinco_cadencias_batem_com_o_python() {
        assertEquals(
            ouro["atributos"]!!.jsonArray.map { it.jsonPrimitive.content },
            Atributo.entries.map { it.sigla },
            "as frentes divergiram do motor Python",
        )
        val cadencias = ouro["cadencias"]!!.jsonObject.mapValues { it.value.jsonPrimitive.content.toInt() }
        assertEquals(
            cadencias,
            Cadencia.entries.associate { it.chave to it.diasDaJanela },
            "as janelas de cadência divergiram",
        )
    }

    @Test
    fun a_escada_de_proveniencia_bate_com_o_python() {
        val autoridades = ouro["origens"]!!.jsonObject.mapValues { it.value.jsonPrimitive.content.toInt() }
        assertEquals(
            autoridades,
            OrigemDoRegistro.entries.associate { it.chave to it.autoridade },
            "a ordem de autoridade divergiu — é ela que decide o que conta como feito",
        )
        val conta = ouro["conta_como_cumprido"]!!.jsonObject
            .mapValues { it.value.jsonPrimitive.content.toBoolean() }
        assertEquals(
            conta,
            OrigemDoRegistro.entries.associate { it.chave to it.contaComoCumprido },
            "o corte do que conta como cumprido divergiu",
        )
    }

    // ------------------------------------------------- sequência e recorde

    @Test
    fun sequencia_e_recorde_batem_caso_a_caso() {
        val problemas = mutableListOf<String>()
        for (caso in ouro["sequencias"]!!.jsonArray) {
            val o = caso.jsonObject
            val nome = o["caso"]!!.jsonPrimitive.content
            val m = missao("x", "FOC", "diaria", false)
            val registros = o["dias"]!!.jsonArray.map {
                val par = it.jsonArray
                val d = par[0].jsonPrimitive.content.toInt()
                val origem = par[1].jsonPrimitive.content
                RegistroDeMissao(
                    missaoId = "x",
                    dia = LocalDate(2026, 10, d),
                    origem = OrigemDoRegistro.de(origem) ?: fail("origem '$origem' não existe"),
                )
            }
            val e = estadoDiario(m, registros, dia(o["ate"]!!.jsonPrimitive.content))
            val esperadoSeq = o["sequencia"]!!.jsonPrimitive.content.toInt()
            val esperadoRec = o["recorde"]!!.jsonPrimitive.content.toInt()
            val esperadoHoje = o["cumprida_na_janela"]!!.jsonPrimitive.content.toBoolean()
            if (e.sequencia != esperadoSeq) {
                problemas += "[$nome] sequência: python $esperadoSeq, kotlin ${e.sequencia}"
            }
            if (e.recorde != esperadoRec) {
                problemas += "[$nome] recorde: python $esperadoRec, kotlin ${e.recorde}"
            }
            if (e.cumpridaNaJanela != esperadoHoje) {
                problemas += "[$nome] cumprida: python $esperadoHoje, kotlin ${e.cumpridaNaJanela}"
            }
        }
        if (problemas.isNotEmpty()) {
            fail("sequência divergiu do motor Python:\n  " + problemas.joinToString("\n  "))
        }
    }

    // ------------------------------------------------------------- barras

    @Test
    fun as_barras_batem_frente_por_frente() {
        val problemas = mutableListOf<String>()
        for (caso in ouro["barras"]!!.jsonArray) {
            val o = caso.jsonObject
            val nome = o["caso"]!!.jsonPrimitive.content
            val cadencia = o["cadencia"]!!.jsonPrimitive.content

            // O ouro guarda o resultado, não o cenário: reconstruir o
            // cenário aqui é o que mantém o JSON legível e o que obriga quem
            // adiciona caso lá a dizer aqui o que ele é.
            val missoes = mutableListOf<Missao>()
            val registros = mutableListOf<RegistroDeMissao>()
            montarCenario(nome, cadencia, missoes, registros)

            val obtido = forcaDosAtributos(missoes, registros, dia("2026-10-14"), Cadencia.de(cadencia)!!)
            for ((i, f) in o["frentes"]!!.jsonArray.withIndex()) {
                val e = f.jsonObject
                val atributo = e["atributo"]!!.jsonPrimitive.content
                val k = obtido[i]
                if (k.atributo.sigla != atributo) {
                    problemas += "[$nome] ordem das frentes: python $atributo, kotlin ${k.atributo.sigla}"
                    continue
                }
                val pares = listOf(
                    "missoes" to Pair(e["missoes"]!!.jsonPrimitive.content.toInt(), k.missoes),
                    "cumpridas" to Pair(e["cumpridas"]!!.jsonPrimitive.content.toInt(), k.cumpridas),
                    "com_evidencia_de_maquina" to
                        Pair(e["com_evidencia_de_maquina"]!!.jsonPrimitive.content.toInt(), k.comEvidenciaDeMaquina),
                )
                for ((campo, v) in pares) {
                    if (v.first != v.second) {
                        problemas += "[$nome/$atributo] $campo: python ${v.first}, kotlin ${v.second}"
                    }
                }
                val pctPy = e["pct"]!!.jsonPrimitive.content.toDouble()
                if (pctPy != k.pct) {
                    problemas += "[$nome/$atributo] pct: python $pctPy, kotlin ${k.pct}"
                }
            }
        }
        if (problemas.isNotEmpty()) {
            fail("barras divergiram do motor Python:\n  " + problemas.joinToString("\n  "))
        }
    }

    /** Reconstrói o cenário do ouro a partir do nome do caso. */
    private fun montarCenario(
        nome: String,
        cadencia: String,
        missoes: MutableList<Missao>,
        registros: MutableList<RegistroDeMissao>,
    ) {
        fun reg(id: String, d: Int, origem: String) = RegistroDeMissao(
            missaoId = id,
            dia = LocalDate(2026, 10, d),
            origem = OrigemDoRegistro.de(origem)!!,
        )
        when (nome) {
            "um_de_tres_e_um_terco", "dois_de_tres", "tudo_vazio",
            "presumido_nao_enche_barra", "fora_da_janela_diaria" -> {
                missoes += missao("a", "FOC", "diaria", true)
                missoes += missao("b", "FOC", "diaria", false)
                missoes += missao("c", "FOC", "diaria", false)
                when (nome) {
                    "um_de_tres_e_um_terco" -> registros += reg("a", 14, "sensor")
                    "dois_de_tres" -> {
                        registros += reg("a", 14, "sensor"); registros += reg("b", 14, "usuario")
                    }
                    "presumido_nao_enche_barra" -> registros += reg("a", 14, "presumido")
                    "fora_da_janela_diaria" -> registros += reg("a", 1, "usuario")
                }
            }
            "janela_semanal_pega_sete_dias" -> {
                missoes += missao("s", "AGI", "semanal", true); registros += reg("s", 8, "sensor")
            }
            "janela_semanal_nao_pega_o_oitavo" -> {
                missoes += missao("s", "AGI", "semanal", true); registros += reg("s", 7, "sensor")
            }
            "janela_mensal" -> {
                missoes += missao("o", "OURO", "mensal", false); registros += reg("o", 1, "usuario")
            }
            else -> fail("caso '$nome' está no ouro e não foi montado aqui")
        }
        require(cadencia.isNotEmpty())
    }

    // --------------------------------------------------------- cobertura

    @Test
    fun cobertura_de_evidencia_bate_com_o_python() {
        val problemas = mutableListOf<String>()
        for (caso in ouro["coberturas"]!!.jsonArray) {
            val o = caso.jsonObject
            val nome = o["caso"]!!.jsonPrimitive.content
            val missoes = mutableListOf<Missao>()
            val registros = mutableListOf<RegistroDeMissao>()
            fun reg(id: String, origem: String) = RegistroDeMissao(
                missaoId = id, dia = LocalDate(2026, 10, 14),
                origem = OrigemDoRegistro.de(origem)!!,
            )
            when (nome) {
                "uma_de_duas_medida" -> {
                    missoes += missao("a", "FOC", "diaria", true)
                    missoes += missao("b", "INT", "diaria", false)
                    registros += reg("a", "sensor")
                }
                "uma_de_tres_e_um_terco" -> {
                    missoes += missao("a", "FOC", "diaria", true)
                    missoes += missao("b", "INT", "diaria", false)
                    missoes += missao("c", "VIT", "diaria", true)
                    registros += reg("a", "sensor")
                }
                "sensor_possivel_mas_sem_medida" -> {
                    missoes += missao("a", "FOC", "diaria", true)
                    registros += reg("a", "usuario")
                }
                "catalogo_vazio" -> Unit
                else -> fail("caso '$nome' está no ouro e não foi montado aqui")
            }
            val k = coberturaDeEvidencia(missoes, registros)
            val esperado = mapOf(
                "missoes_ativas" to o["missoes_ativas"]!!.jsonPrimitive.content.toInt(),
                "mensuraveis_por_aparelho" to o["mensuraveis_por_aparelho"]!!.jsonPrimitive.content.toInt(),
                "com_medida_registrada" to o["com_medida_registrada"]!!.jsonPrimitive.content.toInt(),
            )
            for ((campo, v) in esperado) {
                if (k[campo] != v) problemas += "[$nome] $campo: python $v, kotlin ${k[campo]}"
            }
            val pctPy = o["pct_medido"]!!.jsonPrimitive.content.toDouble()
            if (pctPy != k["pct_medido"]) {
                problemas += "[$nome] pct_medido: python $pctPy, kotlin ${k["pct_medido"]}"
            }
        }
        if (problemas.isNotEmpty()) {
            fail("cobertura divergiu do motor Python:\n  " + problemas.joinToString("\n  "))
        }
    }

    // ------------------------------------------- a ponte com o dinheiro

    @Test
    fun o_empate_de_meio_centesimo_bate_com_o_decimal_do_python() {
        // O caso que justifica o harness desta seção. O Python divide em
        // `Decimal` exato e o empate de meio centésimo acontece de verdade.
        // Em `Double` ele nunca existe — 0.005 não é representável, o valor
        // cai um fio acima ou abaixo, e o meio-para-o-par nunca se aplica.
        // Divergia em metade dos empates, nos dois sentidos.
        val problemas = mutableListOf<String>()
        for (caso in ouro["empates_de_meio_centesimo"]!!.jsonArray) {
            val o = caso.jsonObject
            val preco = Dinheiro(o["preco_centavos"]!!.jsonPrimitive.content.toLong())
            val aporte = Dinheiro(o["aporte_centavos"]!!.jsonPrimitive.content.toLong())
            val esperado = o["meses_de_aporte"]!!.jsonPrimitive.content.toDouble()
            val obtido = mesesDeAporte(preco, aporte)
            if (esperado != obtido) {
                problemas += "preco=${preco.centavos} aporte=${aporte.centavos}: " +
                    "python $esperado, kotlin $obtido"
            }
        }
        if (problemas.isNotEmpty()) {
            fail(
                "razão em meses de aporte divergiu do motor Python:\n  " +
                    problemas.joinToString("\n  "),
            )
        }
    }

    @Test
    fun o_contexto_de_compra_bate_caso_a_caso() {
        val problemas = mutableListOf<String>()
        for (caso in ouro["compras"]!!.jsonArray) {
            val o = caso.jsonObject
            val nome = o["caso"]!!.jsonPrimitive.content

            val tela = Missao(
                id = "foc-tela", titulo = "Tela zero", atributo = Atributo.FOC,
                cadencia = Cadencia.DIARIA, sensorPossivel = true,
                porque = "corte total em vez de moderação",
                colideCom = listOf("tablet", "assinatura de video"),
            )
            val aporte = Missao(
                id = "ouro-aporte", titulo = "Aporte do mês", atributo = Atributo.OURO,
                cadencia = Cadencia.MENSAL, valorMensal = Dinheiro.de("4300"),
            )
            val idsDoOuro = o["missoes"]!!.jsonArray.map { it.jsonPrimitive.content }
            val missoes = listOf(tela, aporte).filter { it.id in idsDoOuro }
            val registros = if (missoes.contains(tela)) {
                (10..14).map {
                    RegistroDeMissao("foc-tela", LocalDate(2026, 10, it), OrigemDoRegistro.SENSOR)
                }
            } else {
                emptyList()
            }
            val regras = if (o["tem_regra"]!!.jsonPrimitive.content.toBoolean()) {
                listOf(
                    RegraDeclarada(
                        id = "espera", tipo = "espera_antes_de_comprar",
                        acimaDe = Dinheiro.de("300"), dias = 30,
                        porque = "lista de desejos e 30 dias",
                    ),
                )
            } else {
                emptyList()
            }

            val ctx = contextoDeCompra(
                Vida(missoes = missoes, registros = registros, regras = regras),
                item = o["item"]!!.jsonPrimitive.content,
                preco = Dinheiro.de(o["preco"]!!.jsonPrimitive.content),
                categoria = o["categoria"]!!.jsonPrimitive.content,
                tags = o["tags"]!!.jsonArray.map { it.jsonPrimitive.content },
                hoje = dia("2026-10-14"),
            )

            fun diga(campo: String, py: Any?, kt: Any?) {
                if (py.toString() != kt.toString()) problemas += "[$nome] $campo: python $py, kotlin $kt"
            }

            diga(
                "sem_missoes_cadastradas",
                o["sem_missoes_cadastradas"]!!.jsonPrimitive.content,
                ctx.semMissoesCadastradas,
            )
            val aplicaPy = o["regra_aplica"]!!.jsonPrimitive.contentOrNull
            diga("regra_aplica", aplicaPy, ctx.regraDeclarada?.aplica)
            diga(
                "regra_liberada_em",
                o["regra_liberada_em"]!!.jsonPrimitive.contentOrNull,
                ctx.regraDeclarada?.liberadaEm,
            )
            diga(
                "meses_de_aporte",
                o["meses_de_aporte"]!!.jsonPrimitive.contentOrNull?.toDouble(),
                ctx.custoEmAportes?.mesesDeAporte,
            )

            val emJogoPy = o["missoes_em_jogo"]!!.jsonArray.map { it.jsonObject }
            diga("quantas_em_jogo", emJogoPy.size, ctx.missoesEmJogo.size)
            for ((i, m) in emJogoPy.withIndex()) {
                if (i >= ctx.missoesEmJogo.size) break
                val k = ctx.missoesEmJogo[i]
                diga("em_jogo[$i].missao", m["missao"]!!.jsonPrimitive.content, k.missao)
                diga(
                    "em_jogo[$i].colisao",
                    m["colisao_declarada"]!!.jsonPrimitive.contentOrNull,
                    k.colisaoDeclarada,
                )
                diga(
                    "em_jogo[$i].sequencia",
                    m["sequencia_em_risco"]!!.jsonPrimitive.contentOrNull?.toInt(),
                    k.sequenciaEmRisco,
                )
            }
        }
        if (problemas.isNotEmpty()) {
            fail("contexto de compra divergiu do motor Python:\n  " + problemas.joinToString("\n  "))
        }
    }

    @Test
    fun o_aporte_contra_os_planos_bate() {
        val problemas = mutableListOf<String>()
        for (caso in ouro["planos"]!!.jsonArray) {
            val o = caso.jsonObject
            val nome = o["caso"]!!.jsonPrimitive.content
            val temAporte = o["tem_missao_de_aporte"]!!.jsonPrimitive.content.toBoolean()
            val missoes = if (temAporte) {
                listOf(
                    Missao(
                        id = "ouro-aporte", titulo = "Aporte do mês",
                        atributo = Atributo.OURO, cadencia = Cadencia.MENSAL,
                        valorMensal = Dinheiro.de("4300"),
                    ),
                )
            } else {
                listOf(missao("foc-tela", "FOC", "diaria", true))
            }
            val c = contextoDePlanos(
                Vida(missoes = missoes),
                Dinheiro.de(o["exigido"]!!.jsonPrimitive.content),
            )
            if (temAporte) {
                val folgaPy = Dinheiro.de(o["folga_mensal"]!!.jsonPrimitive.content)
                if (folgaPy != c.folgaMensal) {
                    problemas += "[$nome] folga: python ${folgaPy.centavos}, kotlin ${c.folgaMensal.centavos}"
                }
                val cabePy = o["planos_cabem_no_aporte"]!!.jsonPrimitive.content.toBoolean()
                if (cabePy != c.planosCabemNoAporte) {
                    problemas += "[$nome] cabem: python $cabePy, kotlin ${c.planosCabemNoAporte}"
                }
            } else if (c.missaoDeAporte != null) {
                problemas += "[$nome] python não achou missão de aporte e o kotlin achou"
            }
        }
        if (problemas.isNotEmpty()) {
            fail("aporte contra planos divergiu do motor Python:\n  " + problemas.joinToString("\n  "))
        }
    }

    // ------------------------------------- o formato que vai para o aparelho

    @Test
    fun o_kotlin_le_o_catalogo_que_o_python_exporta() {
        // O texto do ouro é exatamente o que `fintips aparelho` escreve. Se uma
        // chave for renomeada de um lado só, o erro aparece aqui — e não como
        // "o app não carrega o catálogo" semanas depois, na mão do usuário.
        val ap = ouro["aparelho"]!!.jsonObject
        val vida = FormatoDeVida.lerCatalogo(ap["catalogo_json"]!!.jsonPrimitive.content)

        val esperadas = ap["esperado"]!!.jsonArray.map { it.jsonObject }
        assertEquals(esperadas.size, vida.missoes.size, "número de missões divergiu")

        val problemas = mutableListOf<String>()
        for ((e, k) in esperadas.zip(vida.missoes)) {
            fun diga(campo: String, py: Any?, kt: Any?) {
                if (py.toString() != kt.toString()) {
                    problemas += "[${k.id}] $campo: python $py, kotlin $kt"
                }
            }
            diga("id", e["id"]!!.jsonPrimitive.content, k.id)
            diga("titulo", e["titulo"]!!.jsonPrimitive.content, k.titulo)
            diga("atributo", e["atributo"]!!.jsonPrimitive.content, k.atributo.sigla)
            diga("cadencia", e["cadencia"]!!.jsonPrimitive.content, k.cadencia.chave)
            diga(
                "sensor_possivel",
                e["sensor_possivel"]!!.jsonPrimitive.content,
                k.sensorPossivel,
            )
            diga(
                "colide_com",
                e["colide_com"]!!.jsonArray.map { it.jsonPrimitive.content },
                k.colideCom,
            )
            diga(
                "valor_mensal_centavos",
                e["valor_mensal_centavos"]!!.jsonPrimitive.contentOrNull?.toLong(),
                k.valorMensal?.centavos,
            )
        }

        for ((e, k) in ap["regras_esperadas"]!!.jsonArray.map { it.jsonObject }.zip(vida.regras)) {
            val acima = e["acima_de_centavos"]!!.jsonPrimitive.content.toLong()
            if (acima != k.acimaDe.centavos) {
                problemas += "[${k.id}] acima_de: python $acima, kotlin ${k.acimaDe.centavos}"
            }
            if (e["porque"]!!.jsonPrimitive.content != k.porque) {
                problemas += "[${k.id}] porque divergiu"
            }
        }

        if (problemas.isNotEmpty()) {
            fail(
                "catálogo do aparelho divergiu do que o Python exporta:\n  " +
                    problemas.joinToString("\n  "),
            )
        }
    }

    @Test
    fun o_kotlin_le_o_historico_no_formato_que_o_python_grava() {
        val ap = ouro["aparelho"]!!.jsonObject
        val registros = FormatoDeVida.lerRegistros(
            ap["historico_jsonl"]!!.jsonPrimitive.content,
        )
        assertEquals(2, registros.size)
        assertEquals(OrigemDoRegistro.SENSOR, registros[0].origem)
        assertEquals("0 min", registros[0].medida)
        assertEquals(LocalDate(2026, 10, 14), registros[1].dia)
        assertEquals(OrigemDoRegistro.USUARIO, registros[1].origem)
    }
}
