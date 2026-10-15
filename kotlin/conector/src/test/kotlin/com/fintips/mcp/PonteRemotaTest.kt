package com.fintips.mcp

import kotlinx.serialization.json.*
import okhttp3.*
import okhttp3.mockwebserver.*
import okhttp3.tls.HandshakeCertificates
import okhttp3.tls.HeldCertificate
import kotlin.test.*
import org.junit.jupiter.api.Test
import java.util.concurrent.*

class PonteRemotaTest {
    private val context = Json.parseToJsonElement("""{"schema_version":1,"leitura":{"estados":["estimado"],"fontes":["usuario"]}}""").jsonObject
    private val grant = "G".repeat(43)
    private val invite = "I".repeat(43)
    private val code = "ABCDEFGHJKLM"
    private class Fixture : AutoCloseable {
        val tls = HeldCertificate.Builder().commonName("localhost").addSubjectAlternativeName("localhost").build()
        val server = MockWebServer()
        val messages = LinkedBlockingQueue<JsonObject>()
        val requests = LinkedBlockingQueue<RecordedRequest>()
        val disconnected = CountDownLatch(1)
        lateinit var ws: WebSocket
        init {
            server.useHttps(HandshakeCertificates.Builder().heldCertificate(tls).build().sslSocketFactory(), false)
            server.dispatcher = object : okhttp3.mockwebserver.Dispatcher() {
                override fun dispatch(r: RecordedRequest): MockResponse {
                    requests.add(r)
                    fun json(s: String) = MockResponse().setHeader("Content-Type", "application/json").setBody(s)
                    return when (r.path) {
                        "/phone/enroll" -> json("""{"device":"${"D".repeat(43)}","token":"${"T".repeat(43)}","protocol":1,"expires_in":2592000}""")
                        "/phone/channel" -> MockResponse().addHeader("Sec-WebSocket-Protocol", "fintips-phone-v1").withWebSocketUpgrade(object : WebSocketListener() {
                            override fun onOpen(socket: WebSocket, response: Response) { ws = socket; socket.send("""{"type":"ready","protocol":1,"activated":[]}""") }
                            override fun onMessage(socket: WebSocket, text: String) { messages.add(Json.parseToJsonElement(text).jsonObject) }
                        })
                        "/phone/authorization" -> json("""{"provider":"chatgpt","callback_host":"chatgpt.com","expires_in":200}""")
                        "/phone/approve" -> {
                            ws.send("""{"type":"grant_activated","id":"${"G".repeat(43)}"}""")
                            json("""{"grant":"${"G".repeat(43)}","provider":"chatgpt","scopes":["leitura"],"status":"approved"}""")
                        }
                        "/phone/revoke" -> json("""{"status":"revoked"}""")
                        "/phone/disconnect" -> { disconnected.countDown(); json("""{"status":"revoked"}""") }
                        else -> MockResponse().setResponseCode(404)
                    }
                }
            }
            server.start()
        }
        val client = OkHttpClient.Builder().sslSocketFactory(
            HandshakeCertificates.Builder().addTrustedCertificate(tls.certificate).build().sslSocketFactory(),
            HandshakeCertificates.Builder().addTrustedCertificate(tls.certificate).build().trustManager)
            .followRedirects(false).followSslRedirects(false).build()
        val origin get() = "https://localhost:${server.port}"
        override fun close() { if (::ws.isInitialized) ws.close(1000, null); server.shutdown(); client.dispatcher.executorService.shutdown(); client.connectionPool.evictAll() }
    }
    private fun online(p: PonteRemota) {
        val until = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
        while (p.estado()["estado"] != JsonPrimitive("online") && System.nanoTime() < until) Thread.sleep(10)
        assertEquals(JsonPrimitive("online"), p.estado()["estado"])
    }
    private fun request(f: Fixture, grantId: String = grant, scopes: List<String> = listOf("leitura")): JsonObject {
        f.ws.send(buildJsonObject {
            put("type", "request"); put("id", "J".repeat(43)); put("nonce", "N".repeat(43)); put("grant", grantId)
            putJsonArray("scopes") { scopes.forEach { add(it) } }
        }.toString())
        return f.messages.poll(5, TimeUnit.SECONDS) ?: error("sem resposta do telefone")
    }
    @Test fun tls_websocket_consulta_o_mesmo_mcp_local_e_nunca_envia_tokens_no_contexto() {
        Fixture().use { f -> SessaoLocal().use { local ->
            val full = buildJsonObject {
                context.forEach { (k,v) -> put(k,v) }
                putJsonArray("rotina") { listOf("FOR", "AGI", "VIT", "INT", "FOC", "OURO").forEach { area -> addJsonObject {
                    put("area", area); put("evidencia", "sem_metas"); put("origem", "usuario")
                } } }
            }
            local.iniciar(full)
            PonteRemota.criar(f.origin, invite, local::contextoPara, local::podeEnviar, f.client).use { p ->
                online(p); p.autorizar(code, setOf("leitura"), "chatgpt")
                val r = request(f)
                assertEquals(context, r["contexto"])
                assertFalse(r.toString().contains("T".repeat(43)))
                assertFalse(r.toString().contains(local.credencial()))
                assertEquals(setOf("type", "id", "nonce", "contexto", "validade_restante_segundos"), r.keys)
                val enrollment = f.requests.first { it.path == "/phone/enroll" }.body.readUtf8()
                assertFalse(enrollment.contains("contexto")); assertFalse(enrollment.contains("leitura"))
            }
            assertTrue(f.disconnected.await(5, TimeUnit.SECONDS))
        } }
    }
    @Test fun relay_nao_pode_inventar_autorizacao_nem_ampliar_areas_e_pausa_omite_contexto() {
        Fixture().use { f -> SessaoLocal().use { local ->
            val state = local.iniciar(context)
            PonteRemota.criar(f.origin, invite, local::contextoPara, local::podeEnviar, f.client).use { p ->
                online(p)
                assertEquals(JsonPrimitive("autorizacao_indisponivel"), request(f)["error"])
                p.autorizar(code, setOf("leitura"), "chatgpt")
                val extra = request(f, scopes = listOf("rotina", "leitura"))
                assertEquals(JsonPrimitive("autorizacao_indisponivel"), extra["error"]); assertNull(extra["contexto"])
                local.pausar(state["sessao"]!!.jsonPrimitive.content)
                val paused = request(f); assertEquals(JsonPrimitive("contexto_indisponivel"), paused["error"]); assertNull(paused["contexto"])
            }
            assertTrue(f.disconnected.await(5, TimeUnit.SECONDS))
        } }
    }
    @Test fun pii_e_falha_de_fonte_nunca_se_tornam_resposta_compartilhada() {
        Fixture().use { f ->
            val invalid = buildJsonObject { put("contexto", buildJsonObject { context.forEach { (k,v) -> put(k,v) }; put("nome", "CANARY_PRIVADO") }); put("validade_restante_segundos", 100); put("sessao_local", "s") }
            PonteRemota.criar(f.origin, invite, { invalid }, { _, _ -> true }, f.client).use { p ->
                online(p); p.autorizar(code, setOf("leitura"), "chatgpt")
                val r = request(f); assertNull(r["contexto"]); assertFalse(r.toString().contains("CANARY_PRIVADO")); assertEquals(JsonPrimitive("contexto_indisponivel"), r["error"])
                p.revogar(grant); assertEquals(JsonPrimitive("autorizacao_indisponivel"), request(f)["error"])
            }
            assertTrue(f.disconnected.await(5, TimeUnit.SECONDS))
        }
    }
    @Test fun somente_https_sem_redirecionar_credenciais_e_sem_chave_na_url() {
        for (s in listOf("http://localhost", "https://user:pass@localhost", "https://localhost/x", "https://localhost?token=x", "https://localhost#x")) assertFails { PonteRemota.normalizarOrigem(s) }
        assertEquals("https://example.test:8443", PonteRemota.normalizarOrigem("https://example.test:8443/"))
    }
}
