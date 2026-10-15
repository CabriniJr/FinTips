package com.fintips.mcp

import kotlinx.serialization.json.*

/** Somente teste de interoperabilidade; não entra no APK. Credenciais só no pipe. */
fun main() {
    val context = Json.parseToJsonElement(readln()).jsonObject
    ServidorLocal(context).use { server ->
        println(buildJsonObject { put("endpoint", server.endpoint); put("token", server.credencial()) })
        System.out.flush()
        // O processo de teste mantém o stdin aberto e o fecha ao concluir.
        while (readlnOrNull() != null) { }
    }
}
