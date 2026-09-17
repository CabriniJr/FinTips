package com.fintips.motor

import java.security.MessageDigest

/**
 * SHA-256 da JVM, que o Android também usa.
 *
 * `toHexString` sai em minúsculas, como o `hexdigest()` do Python — se saísse
 * em maiúsculas, todo hash de conta mudaria e o workspace de quem já usa o
 * motor Python viraria lixo na primeira importação pelo Kotlin.
 */
actual fun sha256Hex(texto: String): String =
    MessageDigest.getInstance("SHA-256")
        .digest(texto.encodeToByteArray())
        .joinToString("") { b -> ((b.toInt() and 0xFF) + 0x100).toString(16).substring(1) }
