package com.fintips.mcp

import com.fintips.motor.executarMotorLocal
import kotlinx.serialization.json.*
import okhttp3.OkHttpClient
import okhttp3.tls.HandshakeCertificates
import java.io.File
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate

/** Harness da UI: mesmas classes de produção, CA efêmera só em teste. */
fun main() {
    val config = Json.parseToJsonElement(readln()).jsonObject
    val cert = File(config["certificate"]!!.jsonPrimitive.content).inputStream().use {
        CertificateFactory.getInstance("X.509").generateCertificate(it) as X509Certificate
    }
    val trust = HandshakeCertificates.Builder().addTrustedCertificate(cert).build()
    val client = OkHttpClient.Builder().sslSocketFactory(trust.sslSocketFactory(), trust.trustManager).build()
    var ponte: PonteRemota? = null
    fun ponteState() = ponte?.estado() ?: buildJsonObject { put("ativo", false) }
    SessaoLocal().use { local ->
        try {
            while (true) {
                val line = readlnOrNull() ?: break
                val result = try {
                    val r = Json.parseToJsonElement(line).jsonObject
                    val op = r["operation"]!!.jsonPrimitive.content
                    val i = r["input"]!!.jsonObject
                    fun string(key: String) = i[key]!!.jsonPrimitive.content
                    when (op) {
                        "servidor.status" -> local.estado()
                        "servidor.iniciar" -> { val s = local.iniciar(i["context"]!!.jsonObject); local.verificar(s["sessao"]!!.jsonPrimitive.content) }
                        "servidor.encerrar" -> { ponte?.close(); ponte = null; local.encerrar() }
                        "servidor.pausar" -> local.pausar(string("sessao"))
                        "servidor.atualizar" -> local.atualizar(string("sessao"), i["context"]!!.jsonObject)
                        "servidor.invalidar" -> local.atualizar(string("sessao"), null)
                        "servidor.testar" -> local.verificar(string("sessao"))
                        "ponte.status" -> ponteState()
                        "ponte.iniciar" -> { check(local.ativo() && ponte == null); ponte = PonteRemota.criar(string("origem"), string("convite"), local::contextoPara, local::podeEnviar, client); ponteState() }
                        "ponte.encerrar" -> { ponte?.close(); ponte = null; ponteState() }
                        "ponte.consultar" -> ponte!!.consultarCodigo(string("codigo"))
                        "ponte.autorizar" -> { val scopes = i["context"]!!.jsonObject.keys - "schema_version"; local.contextoPara(scopes); ponte!!.autorizar(string("codigo"), scopes, string("provedor")) }
                        "ponte.revogar" -> ponte!!.revogar(string("id"))
                        "ponte.negar" -> ponte!!.negar(string("codigo"))
                        "ponte.copiar_endpoint", "ponte.abrir_cliente" -> buildJsonObject { put("status", "ok") }
                        else -> executarMotorLocal(op, i)
                    }
                } catch (_: Exception) { buildJsonObject { put("harness_error", true) } }
                println(result); System.out.flush()
            }
        } finally { ponte?.close() }
    }
    client.dispatcher.executorService.shutdown(); client.connectionPool.evictAll()
}
