package com.fintips.motor.vida

import kotlinx.datetime.LocalDate
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Testes do domínio de vida.
 *
 * As propriedades protegidas aqui não são de cálculo — são de produto, e todas
 * vêm de uma frase do plano. Quando uma delas quebrar, o app terá deixado de
 * fazer o que foi desenhado para fazer, mesmo que nenhum número esteja errado.
 */
class VidaTest {

    private val hoje = LocalDate(2026, 10, 14)

    private val semTela = Missao(
        id = "foc-sem-video-curto",
        titulo = "Zero Instagram, Reels e Shorts",
        atributo = Atributo.FOC,
        cadencia = Cadencia.DIARIA,
        comoMedir = "tempo de tela em redes sociais igual a zero",
        sensorPossivel = true,
        porque = "corte total, sem moderação — força de vontade sozinha já falhou",
    )

    private val leitura = Missao(
        id = "int-leitura-30min",
        titulo = "30 min de leitura",
        atributo = Atributo.INT,
        cadencia = Cadencia.DIARIA,
        comoMedir = "no trajeto ou na mesa",
        sensorPossivel = false,
    )

    private fun reg(missao: Missao, dia: Int, origem: OrigemDoRegistro, medida: String = "") =
        RegistroDeMissao(missao.id, LocalDate(2026, 10, dia), origem, medida)

    // ------------------------------------------------------- proveniência

    @Test
    fun medida_do_aparelho_vence_conclusao_do_agente() {
        // "Você ficou sem Reels?" é pergunta factual. Se o celular mediu, a
        // medida vale mais que a interpretação de quem conversou.
        assertTrue(OrigemDoRegistro.SENSOR.autoridade > OrigemDoRegistro.AGENTE.autoridade)
    }

    @Test
    fun a_pessoa_continua_acima_do_aparelho() {
        // O sensor erra de um jeito que a pessoa sabe explicar: celular em
        // casa, vídeo visto no computador, treino na rua.
        assertTrue(OrigemDoRegistro.USUARIO.autoridade > OrigemDoRegistro.SENSOR.autoridade)
    }

    @Test
    fun presumido_nunca_conta_como_cumprido() {
        // O app supor que você treinou não é você ter treinado.
        assertFalse(OrigemDoRegistro.PRESUMIDO.contaComoCumprido)
        assertTrue(OrigemDoRegistro.AGENTE.contaComoCumprido)
        assertTrue(OrigemDoRegistro.SENSOR.contaComoCumprido)
        assertTrue(OrigemDoRegistro.USUARIO.contaComoCumprido)
    }

    @Test
    fun registro_presumido_nao_entra_na_sequencia() {
        val registros = listOf(
            reg(leitura, 11, OrigemDoRegistro.USUARIO),
            reg(leitura, 12, OrigemDoRegistro.PRESUMIDO),   // buraco
            reg(leitura, 13, OrigemDoRegistro.USUARIO),
            reg(leitura, 14, OrigemDoRegistro.USUARIO),
        )
        val e = estadoDiario(leitura, registros, hoje)
        assertEquals(2, e.sequencia, "o dia presumido deveria quebrar a sequência")
    }

    // ---------------------------------------------------------- sequência

    @Test
    fun sequencia_conta_dias_consecutivos_ate_hoje() {
        val registros = (10..14).map { reg(semTela, it, OrigemDoRegistro.SENSOR, "0 min") }
        val e = estadoDiario(semTela, registros, hoje)
        assertEquals(5, e.sequencia)
        assertTrue(e.cumpridaNaJanela)
        assertEquals(LocalDate(2026, 10, 14), e.ultimoRegistro?.dia)
    }

    @Test
    fun hoje_ainda_nao_cumprido_nao_quebra_a_sequencia() {
        // O dia não acabou. Zerar a sequência às 9h da manhã seria punir
        // alguém por ainda não ter feito o que ainda dá tempo de fazer.
        val registros = (11..13).map { reg(semTela, it, OrigemDoRegistro.SENSOR) }
        val e = estadoDiario(semTela, registros, hoje)
        assertEquals(3, e.sequencia)
        assertFalse(e.cumpridaNaJanela)
    }

    @Test
    fun recorde_sobrevive_a_recaida() {
        // "Nunca dois dias seguidos. Caiu hoje, amanhã é dia limpo."
        // Zerar o recorde junto com a sequência transformaria um tropeço em
        // perda de tudo — exatamente o pensamento que o plano manda evitar.
        val registros = listOf(1, 2, 3, 4, 5, 6, 7, /* caiu no 8 */ 9, 10)
            .map { reg(semTela, it, OrigemDoRegistro.SENSOR) }
        val e = estadoDiario(semTela, registros, LocalDate(2026, 10, 10))
        assertEquals(2, e.sequencia, "a sequência atual recomeçou")
        assertEquals(7, e.recorde, "o recorde não pode ter sido perdido")
    }

    @Test
    fun sem_registro_nenhum_tudo_zera_sem_quebrar() {
        val e = estadoDiario(leitura, emptyList(), hoje)
        assertEquals(0, e.sequencia)
        assertEquals(0, e.recorde)
        assertFalse(e.cumpridaNaJanela)
        assertEquals(null, e.ultimoRegistro)
    }

    // ---------------------------------------------------------- atributos

    @Test
    fun as_seis_frentes_sempre_aparecem_mesmo_vazias() {
        // Uma frente sem missão cadastrada é informação: mostra o que a pessoa
        // não está treinando. Esconder a barra esconderia a lacuna.
        val forcas = forcaDosAtributos(listOf(semTela), emptyList(), hoje)
        assertEquals(6, forcas.size)
        assertEquals(Atributo.entries.toList(), forcas.map { it.atributo })
        val ouro = forcas.first { it.atributo == Atributo.OURO }
        assertEquals(0, ouro.missoes)
        assertEquals(0.0, ouro.pct)
    }

    @Test
    fun forca_conta_so_a_janela_da_cadencia() {
        val registros = listOf(
            reg(semTela, 14, OrigemDoRegistro.SENSOR, "0 min"),
            reg(leitura, 1, OrigemDoRegistro.USUARIO),   // fora da janela diária
        )
        val forcas = forcaDosAtributos(listOf(semTela, leitura), registros, hoje)
        assertEquals(100.0, forcas.first { it.atributo == Atributo.FOC }.pct)
        assertEquals(0.0, forcas.first { it.atributo == Atributo.INT }.pct)
    }

    @Test
    fun evidencia_de_maquina_e_contada_separado_da_palavra() {
        val registros = listOf(
            reg(semTela, 14, OrigemDoRegistro.SENSOR, "0 min"),
            reg(leitura, 14, OrigemDoRegistro.USUARIO),
        )
        val forcas = forcaDosAtributos(listOf(semTela, leitura), registros, hoje)
        assertEquals(1, forcas.first { it.atributo == Atributo.FOC }.comEvidenciaDeMaquina)
        assertEquals(0, forcas.first { it.atributo == Atributo.INT }.comEvidenciaDeMaquina)
    }

    @Test
    fun cobertura_de_evidencia_mostra_quanto_ainda_e_memoria() {
        val registros = listOf(reg(semTela, 14, OrigemDoRegistro.SENSOR, "0 min"))
        val c = coberturaDeEvidencia(listOf(semTela, leitura), registros)
        assertEquals(2, c["missoes_ativas"])
        assertEquals(1, c["mensuraveis_por_aparelho"])
        assertEquals(1, c["com_medida_registrada"])
        assertEquals(50.0, c["pct_medido"])
    }

    // ------------------------------------------------------- vocabulário

    @Test
    fun as_siglas_do_plano_sao_lidas_direto() {
        // Ler o plano e gerar missão sem passo de tradução no meio: é no passo
        // de tradução que o erro se esconde.
        assertEquals(Atributo.FOR, Atributo.de("FOR"))
        assertEquals(Atributo.OURO, Atributo.de("ouro"))
        assertEquals(Atributo.VIT, Atributo.de(" VIT "))
        assertEquals(null, Atributo.de("XP"))
        assertEquals(Cadencia.SEMANAL, Cadencia.de("semanal"))
        assertEquals(null, Cadencia.de("quinzenal"))
    }

    @Test
    fun dinheiro_e_uma_das_seis_frentes_e_nao_a_unica() {
        // O motor financeiro inteiro vira uma barra. É a mudança de escopo
        // inteira, expressa em um assert.
        assertTrue(Atributo.OURO in Atributo.entries)
        assertEquals(6, Atributo.entries.size)
    }
}
