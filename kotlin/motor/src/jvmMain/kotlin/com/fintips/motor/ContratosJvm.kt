package com.fintips.motor

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * O arredondamento do Python, na JVM.
 *
 * `BigDecimal(double)` — o construtor que recebe `Double`, não o que recebe
 * `String` — guarda a expansão decimal **exata** do binário, que é justamente
 * o que o `round()` do Python arredonda. Com `HALF_EVEN` em cima disso, os
 * dois motores decidem o empate sobre o mesmo número, e não sobre duas
 * aproximações diferentes dele.
 *
 * Usar `BigDecimal(valor.toString())` aqui seria o erro sutil: `toString()`
 * devolve a repr mais curta que faz round-trip ("2.675"), e arredondar aquilo
 * daria 2.68 onde o Python dá 2.67.
 */
internal actual fun arredondar(valor: Double, casas: Int): Double {
    if (valor.isNaN() || valor.isInfinite()) return valor
    return BigDecimal(valor).setScale(casas, RoundingMode.HALF_EVEN).toDouble()
}
