package com.fintips.mcp

import kotlinx.serialization.json.*
import okhttp3.OkHttpClient
import okhttp3.tls.HandshakeCertificates
import java.io.File
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit

/** Só teste: confiança na CA efêmera pelo pipe, nunca no APK. */
fun main() {
    val config = Json.parseToJsonElement(readln()).jsonObject
    val cert = File(config["certificate"]!!.jsonPrimitive.content).inputStream().use {
        CertificateFactory.getInstance("X.509").generateCertificate(it) as X509Certificate
    }
    val trust = HandshakeCertificates.Builder().addTrustedCertificate(cert).build()
    val client = OkHttpClient.Builder().sslSocketFactory(trust.sslSocketFactory(), trust.trustManager)
        .followRedirects(false).followSslRedirects(false).build()
    SessaoLocal().use { local ->
        local.iniciar(config["context"]!!.jsonObject)
        PonteRemota.criar(config["origin"]!!.jsonPrimitive.content, config["invite"]!!.jsonPrimitive.content,
            local::contextoPara, local::podeEnviar, client).use { ponte ->
            val until = System.nanoTime() + TimeUnit.SECONDS.toNanos(10)
            while (ponte.estado()["estado"] != JsonPrimitive("online") && System.nanoTime() < until) Thread.sleep(10)
            check(ponte.estado()["estado"] == JsonPrimitive("online"))
            println("{\"ready\":true}"); System.out.flush()
            while (true) {
                val line = readlnOrNull() ?: break
                val r = Json.parseToJsonElement(line).jsonObject
                val result = try {
                    when (r["op"]!!.jsonPrimitive.content) {
                        "approve" -> ponte.autorizar(r["code"]!!.jsonPrimitive.content, r["scopes"]!!.jsonArray.map { it.jsonPrimitive.content }.toSet(), r["provider"]!!.jsonPrimitive.content)
                        "update" -> { val s = local.estado(); local.atualizar(s["sessao"]!!.jsonPrimitive.content, r["context"]!!.jsonObject) }
                        "pause" -> local.pausar(local.estado()["sessao"]!!.jsonPrimitive.content)
                        "status" -> ponte.estado()
                        "disconnect" -> { ponte.close(); ponte.estado() }
                        else -> error("unsupported fixture op")
                    }
                } catch (_: Exception) { buildJsonObject { put("fixture_error", true) } }
                println(result.toString()); System.out.flush()
            }
        }
    }
    client.dispatcher.executorService.shutdown(); client.connectionPool.evictAll()
}
