package com.fintips.motor.vida

import com.fintips.motor.Dinheiro
import kotlinx.datetime.LocalDate
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * O lado do aparelho: formato, guarda e tela.
 *
 * Tudo aqui roda nesta máquina, sem SDK de Android, porque toda decisão mora em
 * `commonMain` e a parte de plataforma é só ler e acrescentar texto. O que o
 * Android acrescenta é desenho — e desenho errado se vê na tela; número errado,
 * não.
 */
class AparelhoTest {

    private val hoje = LocalDate(2026, 10, 14)

    /** Guarda em memória, do mesmo jeito que o aparelho usaria arquivos. */
    private class Memoria {
        val arquivos = mutableMapOf<String, String>()
        fun guarda() = Guarda(
            lerTexto = { arquivos[it] },
            acrescentarTexto = { nome, texto -> arquivos[nome] = (arquivos[nome] ?: "") + texto },
        )
    }

    private val catalogo = """
        {"schema_version":1,
         "missoes":[
           {"id":"foc-tela","titulo":"Tela zero","atributo":"FOC","cadencia":"diaria",
            "como_medir":"tempo de tela em zero","sensor_possivel":true,
            "porque":"corte total em vez de moderação","colide_com":["tablet"]},
           {"id":"int-ler","titulo":"Ler um bloco","atributo":"INT","cadencia":"diaria"},
           {"id":"ouro-aporte","titulo":"Aporte","atributo":"OURO","cadencia":"mensal",
            "valor_mensal":"4300.00"}
         ],
         "regras":[
           {"id":"espera","tipo":"espera_antes_de_comprar","acima_de":"300.00",
            "dias":30,"porque":"lista de desejos e 30 dias"}
         ]}
    """.trimIndent()

    // ------------------------------------------------------------- formato

    @Test
    fun o_catalogo_chega_inteiro() {
        val v = FormatoDeVida.lerCatalogo(catalogo)
        assertEquals(3, v.missoes.size)
        val tela = v.missoes.first { it.id == "foc-tela" }
        assertEquals(Atributo.FOC, tela.atributo)
        assertTrue(tela.sensorPossivel)
        assertEquals(listOf("tablet"), tela.colideCom)
        assertEquals(Dinheiro.de("4300"), v.missoes.first { it.id == "ouro-aporte" }.valorMensal)
        assertEquals(30, v.regras.single().dias)
    }

    @Test
    fun ida_e_volta_do_catalogo_nao_perde_nada() {
        val v = FormatoDeVida.lerCatalogo(catalogo)
        val volta = FormatoDeVida.lerCatalogo(FormatoDeVida.escreverCatalogo(v))
        assertEquals(v.missoes, volta.missoes)
        assertEquals(v.regras, volta.regras)
    }

    @Test
    fun atributo_fora_das_seis_frentes_e_recusado_em_vez_de_virar_padrao() {
        // Catálogo torto que carrega é pior que catálogo que recusa: o app
        // mostraria barra de uma frente que a pessoa não pediu.
        val e = assertFailsWith<IllegalStateException> {
            FormatoDeVida.lerCatalogo("""{"missoes":[{"id":"x","atributo":"XP","cadencia":"diaria"}]}""")
        }
        assertTrue("XP" in (e.message ?: ""), "a mensagem precisa nomear o atributo errado")
    }

    @Test
    fun cadencia_inexistente_e_recusada() {
        assertFailsWith<IllegalStateException> {
            FormatoDeVida.lerCatalogo("""{"missoes":[{"id":"x","atributo":"VIT","cadencia":"semestral"}]}""")
        }
    }

    @Test
    fun regra_sem_porque_e_recusada_no_formato_tambem() {
        assertFailsWith<IllegalArgumentException> {
            FormatoDeVida.lerCatalogo(
                """{"regras":[{"id":"x","tipo":"espera_antes_de_comprar","acima_de":"300","dias":30,"porque":""}]}""",
            )
        }
    }

    @Test
    fun chave_desconhecida_nao_quebra_app_velho() {
        // Catálogo exportado por versão nova não pode derrubar quem ainda não
        // atualizou: o campo novo é ignorado, o resto carrega.
        val v = FormatoDeVida.lerCatalogo(
            """{"missoes":[{"id":"x","atributo":"VIT","cadencia":"diaria","campo_do_futuro":42}]}""",
        )
        assertEquals(1, v.missoes.size)
    }

    @Test
    fun origem_invalida_no_historico_e_recusada() {
        val e = assertFailsWith<IllegalStateException> {
            FormatoDeVida.lerRegistros("""{"missao_id":"x","dia":"2026-10-14","origem":"palpite"}""")
        }
        assertTrue("palpite" in (e.message ?: ""))
    }

    @Test
    fun registro_orfao_e_recusado_quando_ha_catalogo() {
        assertFailsWith<IllegalArgumentException> {
            FormatoDeVida.lerRegistros(
                """{"missao_id":"fantasma","dia":"2026-10-14","origem":"usuario"}""",
                missoesConhecidas = setOf("foc-tela"),
            )
        }
    }

    // -------------------------------------------------------------- guarda

    @Test
    fun aparelho_sem_catalogo_abre_em_vez_de_estourar() {
        // É o estado inicial de todo mundo.
        val g = Memoria().guarda()
        val v = g.carregar()
        assertTrue(v.vazia)
        assertEquals(emptyList(), v.registros)
        val t = montarTela(v, hoje)
        assertTrue(t.semCatalogo)
        assertEquals("nenhuma missão cadastrada", t.resumo)
        assertEquals(6, t.frentes.size, "as seis barras aparecem mesmo sem catálogo")
    }

    @Test
    fun a_marcacao_sobrevive_a_fechar_o_app() {
        // O critério de pronto do app, em um teste. "Fechar e abrir" aqui é
        // construir uma Guarda nova sobre o mesmo armazenamento.
        val mem = Memoria()
        mem.arquivos[Guarda.CATALOGO] = catalogo

        val primeiraSessao = mem.guarda()
        val v1 = primeiraSessao.carregar()
        primeiraSessao.marcar(v1, "foc-tela", hoje)

        val depoisDeFechar = mem.guarda()
        val v2 = depoisDeFechar.carregar()
        val t = montarTela(v2, hoje)
        assertTrue(t.doDia.first { it.missaoId == "foc-tela" }.cumprida)
        assertEquals(1, t.feitasHoje)
        assertEquals(2, t.totalDeHoje)
    }

    @Test
    fun marcar_missao_fora_do_catalogo_e_recusado() {
        val mem = Memoria()
        mem.arquivos[Guarda.CATALOGO] = catalogo
        val g = mem.guarda()
        val v = g.carregar()
        assertFailsWith<IllegalArgumentException> { g.marcar(v, "nao-existe", hoje) }
    }

    @Test
    fun historico_cresce_e_nao_e_reescrito() {
        val mem = Memoria()
        mem.arquivos[Guarda.CATALOGO] = catalogo
        val g = mem.guarda()
        val v = g.carregar()
        g.marcar(v, "foc-tela", LocalDate(2026, 10, 13))
        g.marcar(v, "foc-tela", hoje, medida = "0 min")
        assertEquals(2, mem.arquivos[Guarda.HISTORICO]!!.trim().lines().size)
        assertEquals(2, g.registros(v).size)
    }

    @Test
    fun marcar_duas_vezes_no_mesmo_dia_nao_distorce_numero() {
        // Deliberado: duas marcações do mesmo dia são dois fatos, e a segunda
        // pode trazer medida melhor. A sequência trabalha com conjunto de dias.
        val mem = Memoria()
        mem.arquivos[Guarda.CATALOGO] = catalogo
        val g = mem.guarda()
        val v0 = g.carregar()
        g.marcar(v0, "foc-tela", hoje)
        g.marcar(v0, "foc-tela", hoje, origem = OrigemDoRegistro.SENSOR, medida = "0 min")
        val t = montarTela(g.carregar(), hoje)
        val linha = t.doDia.first { it.missaoId == "foc-tela" }
        assertEquals(1, linha.sequencia)
        assertTrue(linha.medidoPorMaquina, "a medida do sensor precisa aparecer na linha")
    }

    // ----------------------------------------------------------------- tela

    @Test
    fun a_tela_mostra_sequencia_recorde_e_o_que_e_so_palavra() {
        val mem = Memoria()
        mem.arquivos[Guarda.CATALOGO] = catalogo
        val g = mem.guarda()
        val v = g.carregar()
        for (d in 10..13) g.marcar(v, "foc-tela", LocalDate(2026, 10, d), OrigemDoRegistro.SENSOR)
        g.marcar(v, "int-ler", hoje)

        val t = montarTela(g.carregar(), hoje)
        val tela = t.doDia.first { it.missaoId == "foc-tela" }
        assertEquals(4, tela.sequencia, "ontem fecha a sequência; hoje ainda não acabou")
        assertFalse(tela.cumprida)
        assertFalse(tela.medidoPorMaquina, "não houve medida HOJE")

        val ler = t.doDia.first { it.missaoId == "int-ler" }
        assertTrue(ler.cumprida)
        assertFalse(ler.sensorPossivel, "leitura não tem aparelho que meça")

        assertEquals("1 de 2 hoje", t.resumo)
    }

    @Test
    fun o_resumo_nao_elogia_nem_cobra() {
        // "Você está indo bem" é o app opinando sobre a vida de alguém com base
        // em caixas marcadas. O número diz o que é; quem interpreta é a pessoa.
        val mem = Memoria()
        mem.arquivos[Guarda.CATALOGO] = catalogo
        val t = montarTela(mem.guarda().carregar(), hoje)
        assertEquals("0 de 2 hoje", t.resumo)
        for (proibido in listOf("bem", "parabéns", "ruim", "falhou", "você")) {
            assertFalse(proibido in t.resumo.lowercase(), "o resumo não deve dizer '$proibido'")
        }
    }

    @Test
    fun missao_mensal_nao_aparece_na_lista_do_dia_mas_conta_na_frente() {
        val mem = Memoria()
        mem.arquivos[Guarda.CATALOGO] = catalogo
        val t = montarTela(mem.guarda().carregar(), hoje)
        assertFalse(t.doDia.any { it.missaoId == "ouro-aporte" })
        assertEquals(0, t.frentes.first { it.atributo == Atributo.OURO }.missoes)
    }
}
