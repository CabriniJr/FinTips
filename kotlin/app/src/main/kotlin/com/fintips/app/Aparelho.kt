package com.fintips.app

import android.content.Context
import com.fintips.motor.vida.FormatoDeVida
import com.fintips.motor.vida.Guarda
import java.io.File

/**
 * A parte do Android, e ela é pequena de propósito.
 *
 * Três linhas de plataforma: onde o arquivo mora, como se lê, como se
 * acrescenta. Toda decisão — o que recusar, o que conta como cumprido, como a
 * sequência anda, o que a tela mostra — está em `commonMain` e tem teste
 * rodando em máquina sem SDK de Android.
 *
 * Essa fronteira não é estética. O que vive aqui não roda em teste nenhum do
 * repositório hoje, porque o alvo Android exige SDK e emulador. Então aqui não
 * pode morar regra.
 */
fun guardaDoAparelho(contexto: Context): Guarda {
    val pasta = File(contexto.filesDir, "vida").apply { mkdirs() }
    return Guarda(
        lerTexto = { nome -> File(pasta, nome).takeIf { it.exists() }?.readText() },
        acrescentarTexto = { nome, texto -> File(pasta, nome).appendText(texto) },
    )
}

/**
 * Instala o catálogo exportado pelo `fintips aparelho --saida`.
 *
 * Sobrescreve o catálogo e **não toca no histórico**: trocar a lista de missões
 * não apaga o que a pessoa já fez. Catálogo é intenção, histórico é fato.
 */
fun instalarCatalogo(contexto: Context, json: String) {
    // Lê antes de gravar: catálogo torto é recusado aqui, com o aparelho ainda
    // mostrando o catálogo antigo, em vez de gravar e quebrar na próxima
    // abertura — que é quando ninguém mais liga o erro à causa.
    FormatoDeVida.lerCatalogo(json)
    File(File(contexto.filesDir, "vida").apply { mkdirs() }, Guarda.CATALOGO)
        .writeText(json)
}
