package com.fintips.mcp

import kotlinx.serialization.json.*
import java.net.Socket
import java.net.URI
import java.util.concurrent.TimeUnit
import kotlin.test.*
import org.junit.jupiter.api.Test

class ServidorLocalTest {
    private val context = Json.parseToJsonElement("""{"schema_version":1,"leitura":{"estados":["estimado"],"fontes":["usuario"]}}""").jsonObject
    private fun request(s: ServidorLocal, body: String, headers: String = "", token: String? = s.credencial(), verb: String = "POST", host: String = s.host): Pair<Int, String> {
        val bytes = body.toByteArray(Charsets.UTF_8)
        val auth = token?.let { "Authorization: Bearer $it\r\n" } ?: ""
        val raw = "$verb /mcp HTTP/1.1\r\nHost: $host\r\n$auth" + "Content-Type: application/json\r\nContent-Length: ${bytes.size}\r\n$headers\r\n"
        return raw(s, raw.toByteArray(Charsets.US_ASCII) + bytes)
    }
    private fun raw(s: ServidorLocal, bytes: ByteArray): Pair<Int, String> = Socket("127.0.0.1", URI(s.endpoint).port).use {
        it.soTimeout = 4000
        it.getOutputStream().write(bytes); it.getOutputStream().flush()
        val response = it.getInputStream().readBytes().toString(Charsets.UTF_8)
        response.substringBefore('\r').split(' ')[1].toInt() to response.substringAfter("\r\n\r\n")
    }
    private fun call(method: String = "tools/call", params: String = """{"name":"ler_contexto_revisado","arguments":{}}""") = """{"jsonrpc":"2.0","id":1,"method":"$method","params":$params}"""

    @Test fun somente_loopback_e_token_em_todas_as_chamadas(): Unit = ServidorLocal(context).use { s ->
        assertTrue(s.endpoint.startsWith("http://127.0.0.1:"))
        assertEquals(43, s.credencial().length)
        assertEquals(401, request(s, call(), token = null).first)
        assertEquals(401, request(s, call(), token = "incorreto").first)
        assertEquals(403, request(s, call(), host = "evil.example").first)
        assertEquals(403, request(s, call(), headers = "Origin: https://evil.example\r\n").first)
        assertEquals(200, request(s, call()).first)
    }

    @Test fun initialize_discovery_e_consulta_compartilham_contrato_mcp(): Unit = ServidorLocal(context).use { s ->
        val init = Json.parseToJsonElement(request(s, call("initialize", """{"protocolVersion":"2025-06-18"}""")).second).jsonObject
        assertEquals("2025-06-18", init["result"]!!.jsonObject["protocolVersion"]!!.jsonPrimitive.content)
        val tools = Json.parseToJsonElement(request(s, call("tools/list", "{}")).second).jsonObject["result"]!!.jsonObject["tools"]!!.jsonArray
        assertEquals(1, tools.size); assertEquals("ler_contexto_revisado", tools[0].jsonObject["name"]!!.jsonPrimitive.content)
        val data = Json.parseToJsonElement(request(s, call()).second).jsonObject["result"]!!.jsonObject
        assertEquals(context, data["structuredContent"]!!.jsonObject["contexto"])
        assertFalse(data["isError"]!!.jsonPrimitive.boolean)
        assertFalse(data.toString().contains(s.credencial()))
        assertEquals(202, request(s, """{"jsonrpc":"2.0","method":"notifications/initialized"}""").first)
    }

    @Test fun nenhuma_escrita_ou_argumento_extra_e_aceito(): Unit = ServidorLocal(context).use { s ->
        for (p in listOf("""{"name":"gravar_fato","arguments":{}}""", """{"name":"ler_contexto_revisado","arguments":{"raw":true}}""")) {
            assertEquals(-32602, Json.parseToJsonElement(request(s, call(params = p)).second).jsonObject["error"]!!.jsonObject["code"]!!.jsonPrimitive.int)
        }
        assertEquals(-32601, Json.parseToJsonElement(request(s, call("motor.executar")).second).jsonObject["error"]!!.jsonObject["code"]!!.jsonPrimitive.int)
    }

    @Test fun atualizacao_e_expiracao_nao_inventam_base() {
        var now = 0L
        ServidorLocal(context) { now }.use { s ->
            now = TimeUnit.HOURS.toNanos(1) + 1
            var r = Json.parseToJsonElement(request(s, call()).second).jsonObject["result"]!!.jsonObject
            assertTrue(r["isError"]!!.jsonPrimitive.boolean); assertFalse("structuredContent" in r)
            s.atualizar(context)
            r = Json.parseToJsonElement(request(s, call()).second).jsonObject["result"]!!.jsonObject
            assertFalse(r["isError"]!!.jsonPrimitive.boolean)
            s.invalidar(); assertFalse(s.estado()["contexto_disponivel"]!!.jsonPrimitive.boolean)
        }
    }

    @Test fun pii_e_recusada_na_entrada_inclusive_em_atualizacoes(): Unit = ServidorLocal(context).use { s ->
        val pii = Json.parseToJsonElement("""{"schema_version":1,"leitura":{"estados":["estimado"],"fontes":["usuario"],"titulo":"Livro inventado"}}""").jsonObject
        assertFails { s.atualizar(pii) }
        assertFails { ServidorLocal(pii) }
        assertEquals(context, Json.parseToJsonElement(request(s, call()).second).jsonObject["result"]!!.jsonObject["structuredContent"]!!.jsonObject["contexto"])
    }

    @Test fun encerrar_fecha_socket_e_proxima_sessao_tem_outro_token() {
        val s = ServidorLocal(context); val port = URI(s.endpoint).port; val old = s.credencial()
        s.close(); s.close()
        assertFalse(s.estado()["ativo"]!!.jsonPrimitive.boolean)
        assertFails { s.credencial() }; assertFails { Socket("127.0.0.1", port).close() }
        ServidorLocal(context).use { assertTrue(old != it.credencial()) }
    }

    @Test fun parser_recusa_smuggling_corpo_excessivo_e_json_invalido(): Unit = ServidorLocal(context).use { s ->
        assertEquals(400, request(s, call(), headers = "Content-Length: 1\r\n").first)
        assertEquals(400, request(s, call(), headers = "Transfer-Encoding: chunked\r\n").first)
        assertEquals(413, request(s, "x".repeat(17000)).first)
        assertEquals(405, request(s, "", verb = "GET").first)
        assertEquals(-32700, Json.parseToJsonElement(request(s, "{broken").second).jsonObject["error"]!!.jsonObject["code"]!!.jsonPrimitive.int)
        assertEquals(-32600, Json.parseToJsonElement(request(s, "[]").second).jsonObject["error"]!!.jsonObject["code"]!!.jsonPrimitive.int)
        assertEquals(-32602, Json.parseToJsonElement(request(s, call("initialize", "[]")).second).jsonObject["error"]!!.jsonObject["code"]!!.jsonPrimitive.int)
        val prefix = "POST /mcp HTTP/1.1\r\nHost: ${s.host}\r\nAuthorization: Bearer ${s.credencial()}\r\nContent-Type: application/json\r\nContent-Length: 1\r\n\r\n".toByteArray()
        assertEquals(-32700, Json.parseToJsonElement(raw(s, prefix + byteArrayOf(0xff.toByte())).second).jsonObject["error"]!!.jsonObject["code"]!!.jsonPrimitive.int)
    }
}
