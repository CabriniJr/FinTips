package com.fintips.motor

import java.text.Normalizer

/**
 * NFKD da JVM, que o Android também usa.
 *
 * O filtro remove a categoria Unicode Mn (mark, nonspacing) — exatamente o que
 * `unicodedata.combining(c)` testa no Python. Filtrar por faixa de código em
 * vez de por categoria pegaria acento latino e deixaria passar o resto.
 */
actual fun semAcento(texto: String): String =
    Normalizer.normalize(texto, Normalizer.Form.NFKD)
        .filterNot { c -> Character.getType(c) == Character.NON_SPACING_MARK.toInt() }
