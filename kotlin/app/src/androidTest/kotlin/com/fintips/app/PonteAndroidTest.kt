package com.fintips.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.fintips.mcp.PonteRemota
import com.fintips.mcp.SessaoLocal
import kotlinx.serialization.json.*
import okhttp3.*
import okhttp3.mockwebserver.*
import okhttp3.tls.HandshakeCertificates
import okhttp3.tls.HeldCertificate
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Cliente TLS/WSS do APK no Android; não substitui por implementação JS. */
@RunWith(AndroidJUnit4::class)
class PonteAndroidTest {
    @Test fun ponte_wss_android_consulta_mcp_local_e_respeita_pausa() {
        val certificate = HeldCertificate.Builder().commonName("localhost").addSubjectAlternativeName("localhost").build()
        val trust = HandshakeCertificates.Builder().addTrustedCertificate(certificate.certificate).build()
        val client = OkHttpClient.Builder().sslSocketFactory(trust.sslSocketFactory(), trust.trustManager).followRedirects(false).build()
        val messages = LinkedBlockingQueue<JsonObject>()
        val disconnected = CountDownLatch(1)
        val server = MockWebServer()
        var socket: WebSocket? = null
        val id = "G".repeat(43)
        server.useHttps(HandshakeCertificates.Builder().heldCertificate(certificate).build().sslSocketFactory(), false)
        server.dispatcher = object : okhttp3.mockwebserver.Dispatcher() {
            override fun dispatch(r: RecordedRequest): MockResponse {
                fun json(s: String) = MockResponse().setHeader("Content-Type", "application/json").setBody(s)
                return when (r.path) {
                    "/phone/enroll" -> json("""{"device":"${"D".repeat(43)}","token":"${"T".repeat(43)}","protocol":1,"expires_in":2592000}""")
                    "/phone/channel" -> MockResponse().addHeader("Sec-WebSocket-Protocol", "fintips-phone-v1").withWebSocketUpgrade(object : WebSocketListener() {
                        override fun onOpen(w: WebSocket, response: Response) { socket = w; w.send("""{"type":"ready","protocol":1,"activated":[]}""") }
                        override fun onMessage(w: WebSocket, text: String) { messages.add(Json.parseToJsonElement(text).jsonObject) }
                    })
                    "/phone/authorization" -> json("""{"provider":"claude","callback_host":"claude.ai","expires_in":200}""")
                    "/phone/approve" -> json("""{"grant":"$id","provider":"claude","scopes":["leitura"],"status":"approved"}""")
                    "/phone/disconnect" -> { disconnected.countDown(); json("""{"status":"revoked"}""") }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start()
        try {
            SessaoLocal().use { local ->
                val context = Json.parseToJsonElement("""{"schema_version":1,"leitura":{"estados":["estimado"],"fontes":["usuario"]}}""").jsonObject
                val state = local.iniciar(context)
                PonteRemota.criar("https://localhost:${server.port}", "I".repeat(43), local::contextoPara, local::podeEnviar, client).use { bridge ->
                    val until = System.nanoTime() + TimeUnit.SECONDS.toNanos(10)
                    while (bridge.estado()["estado"] != JsonPrimitive("online") && System.nanoTime() < until) Thread.sleep(10)
                    assertEquals(JsonPrimitive("online"), bridge.estado()["estado"])
                    bridge.autorizar("ABCDEFGHJKLM", setOf("leitura"), "claude")
                    fun query(): JsonObject {
                        socket!!.send("""{"type":"request","id":"${"J".repeat(43)}","nonce":"${"N".repeat(43)}","grant":"$id","scopes":["leitura"]}""")
                        return messages.poll(10, TimeUnit.SECONDS) ?: error("sem resposta MCP no Android")
                    }
                    val success = query()
                    assertEquals(context, success["contexto"])
                    assertFalse(success.toString().contains(local.credencial()))
                    local.pausar(state["sessao"]!!.jsonPrimitive.content)
                    val paused = query()
                    assertEquals(JsonPrimitive("contexto_indisponivel"), paused["error"])
                    assertNull(paused["contexto"])
                }
                assertTrue(disconnected.await(10, TimeUnit.SECONDS))
            }
        } finally {
            socket?.close(1000, null); server.shutdown()
            client.dispatcher.executorService.shutdown(); client.connectionPool.evictAll()
        }
    }
}
