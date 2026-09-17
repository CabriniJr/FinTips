package com.fintips.motor

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

/**
 * A propriedade que estes testes protegem: **o Kotlin arredonda igual ao
 * Python**. Se `Dinheiro.dividir` divergir de `Decimal.quantize`, toda média
 * mensal, custo fixo e projeção sai um centavo diferente do motor atual — e um
 * centavo é o suficiente para o harness diferencial acusar tudo como quebrado,
 * escondendo as diferenças que importam.
 *
 * Os casos de arredondamento abaixo foram conferidos contra o Python:
 * `Decimal(x).quantize(Decimal("1"))` com o contexto padrão (ROUND_HALF_EVEN).
 */
class DinheiroTest {

    @Test
    fun soma_e_subtracao_sao_exatas() {
        val a = Dinheiro.de("0.10")
        val b = Dinheiro.de("0.20")
        // o caso que o Double erra: 0.1 + 0.2 != 0.3
        assertEquals(Dinheiro.de("0.30"), a + b)
        assertEquals(30L, (a + b).centavos)
        assertEquals(Dinheiro.de("-0.10"), a - b)
    }

    @Test
    fun divisao_arredonda_meio_para_o_par() {
        // 5 centavos / 2 = 2,5 → par → 2
        assertEquals(2L, Dinheiro(5).dividir(2).centavos)
        // 7 centavos / 2 = 3,5 → par → 4
        assertEquals(4L, Dinheiro(7).dividir(2).centavos)
        // 3 / 2 = 1,5 → par → 2
        assertEquals(2L, Dinheiro(3).dividir(2).centavos)
        // 1 / 2 = 0,5 → par → 0
        assertEquals(0L, Dinheiro(1).dividir(2).centavos)
        // sem empate, arredonda para o mais perto (conferido contra o Python)
        assertEquals(3L, Dinheiro(10).dividir(3).centavos)   // 3,33 → 3
        assertEquals(4L, Dinheiro(11).dividir(3).centavos)   // 3,67 → 4
    }

    @Test
    fun divisao_de_negativo_espelha_o_positivo() {
        assertEquals(-2L, Dinheiro(-5).dividir(2).centavos)
        assertEquals(-4L, Dinheiro(-7).dividir(2).centavos)
        assertEquals(-3L, Dinheiro(-10).dividir(3).centavos) // -3,33 → -3
    }

    @Test
    fun divisao_por_zero_falha_alto() {
        assertFailsWith<IllegalArgumentException> { Dinheiro(100).dividir(0) }
    }

    @Test
    fun le_os_formatos_que_aparecem_em_extrato() {
        assertEquals(123456L, Dinheiro.de("1234.56").centavos)
        assertEquals(123456L, Dinheiro.de("1.234,56").centavos)
        assertEquals(123456L, Dinheiro.de("1,234.56").centavos)
        assertEquals(-123456L, Dinheiro.de("-1.234,56").centavos)
        assertEquals(1230L, Dinheiro.de("R$ 12,30").centavos)
        assertEquals(500L, Dinheiro.de("5").centavos)
        assertEquals(550L, Dinheiro.de("5,5").centavos)
        assertEquals(0L, Dinheiro.de("").centavos)
    }

    @Test
    fun ponto_e_sempre_decimal_como_no_motor_python() {
        // Este caso é uma armadilha, e o teste existe para documentá-la.
        //
        // "1.234" parece mil duzentos e trinta e quatro, e não é: o motor
        // Python faz `Decimal("1.234")`, ou seja um real e vinte e três
        // centavos e meio, que arredonda para 1,23. A porta replica isso de
        // propósito — se a regra é ruim, ela muda nos dois motores ao mesmo
        // tempo, com este teste mudando junto.
        assertEquals(123L, Dinheiro.de("1.234").centavos)
        assertEquals(123L, Dinheiro.de("1.23").centavos)
        // já com vírgula o separador é claro, e milhar é descartado
        assertEquals(123456L, Dinheiro.de("1.234,56").centavos)
    }

    @Test
    fun sub_centavo_arredonda_meio_para_o_par() {
        assertEquals(100L, Dinheiro.de("1.005").centavos)  // empate: par fica
        assertEquals(102L, Dinheiro.de("1.015").centavos)  // empate: sobe ao par
        assertEquals(124L, Dinheiro.de("1.235").centavos)
        assertEquals(123L, Dinheiro.de("1.2345").centavos)
    }

    @Test
    fun media_divide_uma_vez_so() {
        // 3 meses de 10,00 / 20,00 / 30,01 → 20,00 e um terço → 20,00
        val valores = listOf(Dinheiro.de("10.00"), Dinheiro.de("20.00"), Dinheiro.de("30.01"))
        assertEquals(6001L, valores.somar().centavos)
        assertEquals(2000L, valores.media().centavos)
        assertEquals(Dinheiro.ZERO, emptyList<Dinheiro>().media())
    }

    @Test
    fun texto_canonico_tem_sempre_duas_casas() {
        assertEquals("0.05", Dinheiro(5).toString())
        assertEquals("12.30", Dinheiro(1230).toString())
        assertEquals("-1.00", Dinheiro(-100).toString())
        assertEquals("0.00", Dinheiro.ZERO.toString())
        assertEquals("1234.56", Dinheiro(123456).toString())
    }

    @Test
    fun double_so_na_saida_para_comparar_com_o_python() {
        assertEquals(12.30, Dinheiro(1230).paraDouble())
        assertEquals(-0.05, Dinheiro(-5).paraDouble())
    }
}
