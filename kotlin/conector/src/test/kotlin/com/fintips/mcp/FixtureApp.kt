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
    val ai=config["api_origin"]?.jsonPrimitive?.content?.let { OpenAITriagem(client,it+"/v1/responses") }
    var configured=false
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
                        "triagem.chave_status" -> buildJsonObject { put("configurada",configured) }
                        "triagem.configurar_chave" -> { configured=true; buildJsonObject { put("status","dialogo_solicitado") } }
                        "triagem.apagar_chave" -> { configured=false; ai?.cancelar(); buildJsonObject { put("configurada",false) } }
                        "triagem.cancelar" -> { ai?.cancelar(); buildJsonObject { put("status","cancelado") } }
                        "triagem.sugerir", "triagem.organizar" -> { check(configured); ai!!.sugerir(i["bundle"]!!.jsonObject,i["rascunhos"]!!.jsonArray,"sk-"+"T".repeat(40),i["autorizado"]==JsonPrimitive(true),string("hoje"),agente=op=="triagem.organizar") }

                        "extrato.contexto" -> com.fintips.motor.importacao.contextoExtratos(JsonArray(emptyList()),"fixture-local")
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
                } catch (e: Exception) { buildJsonObject { put("harness_error", true);put("harness_class",e.javaClass.simpleName);if(e is FalhaTriagem) put("code",e.codigo) } }
                println(result); System.out.flush()
            }
        } finally { ponte?.close(); ai?.cancelar() }
    }
    client.dispatcher.executorService.shutdown(); client.connectionPool.evictAll()
}
