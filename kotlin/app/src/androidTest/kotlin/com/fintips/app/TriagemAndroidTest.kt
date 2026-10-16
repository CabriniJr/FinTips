package com.fintips.app

import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.fintips.mcp.OpenAITriagem
import kotlinx.serialization.json.*
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.MockResponse
import okhttp3.tls.HeldCertificate
import okhttp3.tls.HandshakeCertificates
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.TimeUnit
import java.util.UUID
import java.io.File
import com.fintips.motor.importacao.contextoExtratos

@RunWith(AndroidJUnit4::class)
class TriagemAndroidTest {
    @Test fun chave_fica_cifrada_no_keystore_e_pode_ser_apagada() {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        check(context.packageName=="com.fintips.app.ci")
        val alias="fintips.test."+UUID.randomUUID().toString()
        val secret="sk-"+"S".repeat(40)
        val store=ChaveTriagem(context,alias)
        try {
            assertFalse(store.configurada());store.salvar(secret)
            assertEquals(secret,ChaveTriagem(context,alias).ler())
            val prefs=context.getSharedPreferences(alias,android.content.Context.MODE_PRIVATE)
            assertFalse(prefs.all.toString().contains(secret))
            assertTrue(prefs.contains("encrypted"));assertTrue(prefs.contains("iv"))
            store.apagar();assertNull(store.ler());assertTrue(prefs.all.isEmpty())
        } finally { store.apagar() }
    }
    @Test fun android_envia_valores_abstratos_por_https_sem_titulos_origem_destino_ou_chave_no_corpo() {
        val certificate=HeldCertificate.Builder().commonName("localhost").addSubjectAlternativeName("localhost").build()
        val trust=HandshakeCertificates.Builder().addTrustedCertificate(certificate.certificate).build()
        val client=OkHttpClient.Builder().sslSocketFactory(trust.sslSocketFactory(),trust.trustManager).callTimeout(15,TimeUnit.SECONDS).build()
        val server=MockWebServer().apply { useHttps(HandshakeCertificates.Builder().heldCertificate(certificate).build().sslSocketFactory(),false);start() }
        val ai=OpenAITriagem(client,server.url("/v1/responses").toString())
        try {
            val choice="""{"escolha":"opcao_0","valor":null,"motivo":"revisar_em_lote"}"""
            server.enqueue(MockResponse().setHeader("Content-Type","application/json").setBody(buildJsonObject {
                put("status","completed");putJsonArray("output") { addJsonObject { put("type","message");putJsonArray("content") { addJsonObject { put("type","output_text");put("text",choice) } } } }
            }.toString()))
            val bundle=Json.parseToJsonElement("""{"schema_version":1,"vida":{"schema_version":1,"tarefas":[],"registros":[],"planos":[],"medidas":[]},"leitura":{"schema_version":1,"livros":[]},"caderno":{"schema_version":1,"assets":[],"relacoes":[],"aplicacoes":[]}}""").jsonObject
            val drafts=Json.parseToJsonElement("""[{"id":"ID_ONLY_CANARY","tipo":"compromisso","campos":{"titulo":"NOME_ONLY_CANARY","valor_centavos":54321,"origem_real":"ORIGEM_ONLY_CANARY","destino_real":"DESTINO_ONLY_CANARY"},"porque":"PORQUE_ONLY_CANARY","acao":"criar"}]""").jsonArray
            val financial=contextoExtratos(buildJsonArray { addJsonObject { put("ofx",ofxSintetico());put("saldo_inicial",JsonNull) } },"sal-teste")
            val result=ai.sugerir(bundle,drafts,"sk-"+"T".repeat(40),true,"2026-10-15",financeiro=financial)
            assertEquals(JsonPrimitive("revisar"),result["opcao"]!!.jsonObject["acao"])
            val raw=server.takeRequest(5,TimeUnit.SECONDS)!!.body.readUtf8()
            assertTrue(raw.contains("financas_importadas"));assertTrue(raw.contains("75000"));assertTrue(raw.contains("nao_conferidos"));
            assertTrue(raw.contains("54321"));assertFalse(raw.contains("CANARY"));assertFalse(raw.contains("origem_real"));assertFalse(raw.contains("destino_real"));assertFalse(raw.contains("mapa_local"));assertFalse(raw.contains("sk-"))
            // O agente novo escreve vários campos e um vínculo, ainda sem texto no HTTPS.
            val agentDrafts=Json.parseToJsonElement("""[{"id":"PLAN_CANARY","tipo":"plano","campos":{"titulo":"Quero ler CANARY","atributo":"INT"},"porque":"Escolha sintética","acao":"criar"},{"id":"BOOK_CANARY","tipo":"livro","campos":{"titulo":"Estou lendo “TITLE_CANARY” 3 dias por semana e já li 25%"},"porque":"Escolha sintética","acao":"criar"}]""").jsonArray
            val public=com.fintips.motor.triagem.contextoAgente(bundle,agentDrafts,"2026-10-15")["publico"]!!.jsonObject
            fun value(field: String, short: Boolean=false)=public["valores_disponiveis"]!!.jsonArray.first { e->val v=e.jsonObject
                v["dono"]==JsonPrimitive("rascunho_1") && v["campo"]==JsonPrimitive(field) && (!short || v["papel"]==JsonPrimitive("titulo_curto"))
            }.jsonObject["ref"]!!
            val filled=buildJsonObject {
                putJsonArray("registros") { addJsonObject { put("ref","rascunho_1");put("tipo","livro");putJsonArray("campos") {
                    for(field in listOf("titulo","dias_semana","progresso_bp")) addJsonObject { put("campo",field);put("valor",value(field,field=="titulo")) }
                } } }
                putJsonArray("relacoes") { addJsonObject { put("de","rascunho_1");put("para","rascunho_0");put("tipo","apoia") } };put("pergunta",JsonNull)
            }
            server.enqueue(MockResponse().setHeader("Content-Type","application/json").setBody(buildJsonObject {
                put("status","completed");putJsonArray("output") { addJsonObject { put("type","message");putJsonArray("content") { addJsonObject { put("type","output_text");put("text",filled.toString()) } } } }
            }.toString()))
            val organized=ai.sugerir(bundle,agentDrafts,"sk-"+"T".repeat(40),true,"2026-10-15",agente=true)
            val fields=organized["rascunhos"]!!.jsonArray[1].jsonObject["campos"]!!.jsonObject
            assertEquals(JsonPrimitive("TITLE_CANARY"),fields["titulo"]);assertEquals(JsonPrimitive(3),fields["dias_semana"]);assertEquals(JsonPrimitive(2500),fields["progresso_bp"])
            assertEquals(1,organized["relacoes"]!!.jsonArray.size)
            val agentBody=server.takeRequest(5,TimeUnit.SECONDS)!!.body.readUtf8()
            assertFalse(agentBody.contains("CANARY"));assertFalse(agentBody.contains("valores_locais"));assertFalse(agentBody.contains("sk-"));assertTrue(agentBody.contains("fintips_agente_v2"))
        } finally { ai.cancelar();server.shutdown();client.dispatcher.executorService.shutdown();client.connectionPool.evictAll() }
    }
    private fun ofxSintetico() = "<OFX><ORG>BANCO_CANARY<BANKID>001<ACCTID>CONTA_CANARY<CURDEF>BRL<BANKTRANLIST><STMTTRN><DTPOSTED>20261001120000[-3:BRT]<TRNAMT>1000.00<FITID>FITID_CANARY_1<MEMO>ORIGEM_CANARY</STMTTRN><STMTTRN><DTPOSTED>20261002120000[-3:BRT]<TRNAMT>-250.00<FITID>FITID_CANARY_2<MEMO>DESTINO_CANARY</STMTTRN></BANKTRANLIST><LEDGERBAL><BALAMT>750.00<DTASOF>20261031</LEDGERBAL></OFX>"

    @Test fun extrato_persiste_reabre_deduplica_e_falha_nao_apaga_historico() {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        check(context.packageName=="com.fintips.app.ci")
        val nome="extratos-test-"+UUID.randomUUID().toString()+".json"
        val file=File(context.noBackupFilesDir,nome)
        try {
            val repo=ExtratosLocais(context,nome)
            assertEquals(JsonPrimitive(0),repo.contexto()["transacoes"])
            val raw=ofxSintetico();val first=repo.importar(raw,null)
            assertEquals(JsonPrimitive(2),first["novas_transacoes"])
            assertEquals(JsonPrimitive(2),ExtratosLocais(context,nome).contexto()["transacoes"])
            assertFalse(repo.contexto().toString().contains("CANARY"))
            val repeat=repo.importar(raw,"0")
            assertEquals(JsonPrimitive(true),repeat["duplicado"]);assertEquals(JsonPrimitive(0),repeat["novas_transacoes"])
            assertEquals(JsonPrimitive(1),repeat["contexto"]!!.jsonObject["arquivos"])
            assertEquals(JsonPrimitive(1),repeat["contexto"]!!.jsonObject["conciliacao"]!!.jsonObject["conferidos"])
            val before=file.readBytes()
            try { repo.importar("invalid",null);fail("arquivo inválido aceito") } catch(_:IllegalArgumentException) { }
            assertArrayEquals(before,file.readBytes())
            val subset=raw.replace(Regex("<STMTTRN><DTPOSTED>20261001.*?</STMTTRN>"),"")
            assertEquals(JsonPrimitive(0),repo.importar(subset,null)["novas_transacoes"])
            assertEquals(JsonPrimitive(2),repo.contexto()["transacoes"])
            assertTrue(repo.copia().contains("DESTINO_CANARY")) // cópia local preserva fonte, contexto não.
            file.writeText("corrompido")
            try { repo.importar(raw,null);fail("sobrescreveu histórico ilegível") } catch(_:Exception) { }
            assertEquals("corrompido",file.readText())
            assertTrue(repo.copia().contains("fintips_extratos_recuperacao"))
        } finally { file.delete();File(file.path+".bak").delete();File(file.path+".new").delete() }
    }

}
