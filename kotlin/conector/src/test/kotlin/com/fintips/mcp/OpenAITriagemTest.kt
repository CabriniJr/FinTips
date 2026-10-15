package com.fintips.mcp

import kotlinx.serialization.json.*
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.tls.HandshakeCertificates
import okhttp3.tls.HeldCertificate
import java.util.concurrent.TimeUnit
import kotlin.test.*

class OpenAITriagemTest {
    private val bundle=Json.parseToJsonElement("""{"schema_version":1,"vida":{"schema_version":1,"tarefas":[],"registros":[],"planos":[],"medidas":[]},"leitura":{"schema_version":1,"livros":[]},"caderno":{"schema_version":1,"assets":[],"relacoes":[],"aplicacoes":[]}}""").jsonObject
    private val drafts=Json.parseToJsonElement("""[{"id":"ID_LOCAL_CANARY","tipo":"compromisso","campos":{"titulo":"TITULO_LOCAL_CANARY","valor_centavos":12345,"origem_real":"ORIGEM_LOCAL_CANARY","destino_real":"DESTINO_LOCAL_CANARY"},"porque":"MOTIVO_LOCAL_CANARY","acao":"criar"}]""").jsonArray
    private class Fixture: AutoCloseable {
        val certificate=HeldCertificate.Builder().commonName("localhost").addSubjectAlternativeName("localhost").build()
        val trust=HandshakeCertificates.Builder().addTrustedCertificate(certificate.certificate).build()
        val server=MockWebServer().apply { useHttps(HandshakeCertificates.Builder().heldCertificate(certificate).build().sslSocketFactory(),false);start() }
        val client=OkHttpClient.Builder().sslSocketFactory(trust.sslSocketFactory(),trust.trustManager).callTimeout(5,TimeUnit.SECONDS).build()
        val ai=OpenAITriagem(client,server.url("/v1/responses").toString())
        override fun close() { ai.cancelar();server.shutdown();client.dispatcher.executorService.shutdown();client.connectionPool.evictAll() }
    }
    private fun response(text:String)=MockResponse().setHeader("Content-Type","application/json").setBody(buildJsonObject {
        put("status","completed");putJsonArray("output") { addJsonObject { put("type","message");putJsonArray("content") { addJsonObject { put("type","output_text");put("text",text) } } } }
    }.toString())
    @Test fun envia_valores_com_labels_abstratas_sem_texto_ids_ou_origem_destino() {
        Fixture().use { f ->
            f.server.enqueue(response("""{"escolha":"opcao_0","valor":null,"motivo":"revisar_em_lote"}"""))
            val r=f.ai.sugerir(bundle,drafts,"sk-"+"T".repeat(40),true,"2026-10-15")
            assertEquals(JsonPrimitive("revisar"),r["opcao"]!!.jsonObject["acao"])
            val request=f.server.takeRequest(2,TimeUnit.SECONDS)!!;val body=request.body.readUtf8()
            assertTrue(body.contains("12345"));assertFalse(body.contains("CANARY"));assertFalse(body.contains("origem_real"));assertFalse(body.contains("destino_real"));assertFalse(body.contains("mapa_local"));assertFalse(body.contains("sk-"))
            assertEquals("Bearer sk-"+"T".repeat(40),request.getHeader("Authorization"))
            assertEquals(JsonPrimitive(false),Json.parseToJsonElement(body).jsonObject["store"])
        }
    }
    @Test fun nao_envia_sem_consentimento_e_recusa_resposta_fora_do_contrato() {
        Fixture().use { f ->
            assertFails { f.ai.sugerir(bundle,drafts,"sk-"+"T".repeat(40),false,"2026-10-15") }
            assertNull(f.server.takeRequest(100,TimeUnit.MILLISECONDS))
            f.server.enqueue(response("""{"escolha":"opcao_inventada","valor":null,"motivo":"revisar_em_lote"}"""))
            assertFailsWith<FalhaTriagem> { f.ai.sugerir(bundle,drafts,"sk-"+"T".repeat(40),true,"2026-10-15") }
        }
    }
    @Test fun nao_segue_redirect_com_a_chave_e_nao_reflete_erro_remoto() {
        Fixture().use { f ->
            f.server.enqueue(MockResponse().setResponseCode(302).setHeader("Location",f.server.url("/vazar")).setBody("PII_REMOTA_CANARY"))
            val e=assertFailsWith<FalhaTriagem> { f.ai.sugerir(bundle,drafts,"sk-"+"T".repeat(40),true,"2026-10-15") }
            assertFalse(e.message!!.contains("CANARY"));f.server.takeRequest();assertNull(f.server.takeRequest(100,TimeUnit.MILLISECONDS))
        }
    }
}
