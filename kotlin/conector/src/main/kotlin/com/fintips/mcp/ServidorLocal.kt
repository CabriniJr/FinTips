package com.fintips.mcp

import com.fintips.motor.validarContextoIA
import kotlinx.serialization.json.*
import java.io.ByteArrayOutputStream
import java.io.Closeable
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Transporte JVM/Android; o motor puro permanece separado. Sem cliente HTTP,
 * arquivos, logs, wildcard de interface ou operação remota de escrita.
 */
class ServidorLocal(contexto: JsonObject, private val relogio: () -> Long = System::nanoTime) : Closeable {
    private data class Snapshot(val json: JsonObject, val vence: Long)
    private val snapshot = AtomicReference<Snapshot?>()
    private val segredo = ByteArray(32).also { SecureRandom().nextBytes(it) }
    private val token = Base64.getUrlEncoder().withoutPadding().encodeToString(segredo)
    private val socket = ServerSocket()
    private val ativos = ConcurrentHashMap.newKeySet<Socket>()
    private val workers = ThreadPoolExecutor(2, 2, 0L, TimeUnit.SECONDS, ArrayBlockingQueue(8),
        { r -> Thread(r, "fintips-mcp-request").apply { isDaemon = true } })
    @Volatile private var encerrado = false
    val endpoint: String
    val host: String
    private val aceitador: Thread

    init {
        try {
            atualizar(contexto)
            socket.bind(InetSocketAddress(InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1)), 0), 8)
            check(socket.inetAddress.isLoopbackAddress && socket.inetAddress.hostAddress == "127.0.0.1")
            host = "127.0.0.1:${socket.localPort}"
            endpoint = "http://$host/mcp"
            aceitador = Thread({ aceitar() }, "fintips-mcp-loopback").apply { isDaemon = true; start() }
        } catch (e: Exception) { socket.close(); workers.shutdownNow(); throw e }
    }

    /** Só o invólucro local pode obter o token; ele não entra em respostas MCP. */
    fun credencial(): String { check(!encerrado); return token }
    fun atualizar(c: JsonObject) {
        check(!encerrado)
        val copia = Json.parseToJsonElement(validarContextoIA(c).toString()).jsonObject
        snapshot.set(Snapshot(copia, relogio() + TimeUnit.HOURS.toNanos(1)))
    }
    fun invalidar() { snapshot.set(null) }
    fun estado(): JsonObject = buildJsonObject {
        put("ativo", !encerrado)
        put("endpoint", endpoint)
        val s = atual()
        put("contexto_disponivel", s != null)
        putJsonArray("escopos") { s?.json?.keys?.filter { it != "schema_version" }?.forEach { add(it) } }
        put("validade_restante_segundos", s?.let { maxOf(0L, (it.vence - relogio()) / 1_000_000_000) } ?: 0)
    }
    /** Prova de funcionamento pelo socket real, nunca só pelo estado da thread.
     * Nenhum contexto ou credencial é devolvido por este diagnóstico local.
     */
    fun verificar() {
        check(!encerrado)
        fun pedir(method: String, params: JsonObject = buildJsonObject {}): JsonObject {
            val request = buildJsonObject {
                put("jsonrpc", "2.0"); put("id", "saude-local"); put("method", method); put("params", params)
            }.toString().toByteArray(Charsets.UTF_8)
            val response = Socket().use { s ->
                s.connect(InetSocketAddress(InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1)), socket.localPort), 1500)
                s.soTimeout = 2000
                s.getOutputStream().apply {
                    write(("POST /mcp HTTP/1.1\r\nHost: $host\r\nAuthorization: Bearer $token\r\n" +
                        "Content-Type: application/json\r\nContent-Length: ${request.size}\r\n\r\n").toByteArray(Charsets.US_ASCII))
                    write(request); flush()
                }
                val bytes = ByteArrayOutputStream()
                val input = s.getInputStream(); val buffer = ByteArray(1024)
                while (true) {
                    val n = input.read(buffer); if (n < 0) break
                    check(bytes.size() + n <= 16384); bytes.write(buffer, 0, n)
                }
                bytes.toString("UTF-8")
            }
            check(response.startsWith("HTTP/1.1 200 "))
            val r = Json.parseToJsonElement(response.substringAfter("\r\n\r\n")).jsonObject
            check(r["id"] == JsonPrimitive("saude-local") && r["error"] == null)
            return r["result"]!!.jsonObject
        }
        val initialized = pedir("initialize", buildJsonObject { put("protocolVersion", "2025-06-18") })
        check(initialized["serverInfo"]!!.jsonObject["name"] == JsonPrimitive("fintips-local"))
        val tools = pedir("tools/list")["tools"]!!.jsonArray
        check(tools.size == 1 && tools[0].jsonObject["name"] == JsonPrimitive("ler_contexto_revisado"))
        val result = pedir("tools/call", buildJsonObject {
            put("name", "ler_contexto_revisado"); putJsonObject("arguments") {}
        })
        check(result["isError"] == JsonPrimitive(false))
        validarContextoIA(result["structuredContent"]!!.jsonObject["contexto"]!!.jsonObject)
    }

    private fun atual(): Snapshot? {
        val s = snapshot.get() ?: return null
        if (s.vence <= relogio()) { snapshot.compareAndSet(s, null); return null }
        return s
    }
    private fun aceitar() {
        while (!encerrado) {
            val client = try { socket.accept() } catch (_: Exception) { break }
            ativos.add(client)
            try { workers.execute { client.use { runCatching { atender(it) } }; ativos.remove(client) } }
            catch (_: Exception) { ativos.remove(client); runCatching { client.close() } }
        }
    }
    private fun atender(s: Socket) {
        s.soTimeout = 2000
        val input = s.getInputStream()
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(3)
        var total = 0
        fun linha(): String {
            val bytes = ByteArrayOutputStream()
            while (true) {
                val c = input.read()
                require(System.nanoTime() < deadline)
                require(c >= 0 && c <= 127 && ++total <= 8192)
                if (c == 13) { require(input.read() == 10 && ++total <= 8192); break }
                require(c != 10 && (c >= 32 || c == 9))
                bytes.write(c)
            }
            return bytes.toString("US-ASCII")
        }
        val first: String
        val headers = mutableMapOf<String, String>()
        try {
            first = linha()
            while (true) {
                val l = linha(); if (l.isEmpty()) break
                require(!l.startsWith(" ") && !l.startsWith("\t"))
                val colon = l.indexOf(':'); require(colon > 0)
                val key = l.substring(0, colon).lowercase()
                require(Regex("[a-z0-9-]+").matches(key) && key !in headers)
                headers[key] = l.substring(colon + 1).trim()
            }
        } catch (_: Exception) { responder(s, 400); return }
        val parts = first.split(' ')
        if (parts.size != 3 || parts[2] != "HTTP/1.1") { responder(s, 400); return }
        if (headers["host"] != host || (headers["origin"] != null && headers["origin"] != "http://$host")) { responder(s, 403); return }
        if (parts[1] != "/mcp") { responder(s, 404); return }
        if (parts[0] != "POST") { responder(s, 405); return }
        val auth = headers["authorization"]
        if (auth == null || !MessageDigest.isEqual(auth.toByteArray(Charsets.UTF_8), "Bearer $token".toByteArray(Charsets.UTF_8))) { responder(s, 401); return }
        if (headers["transfer-encoding"] != null || headers["content-type"]?.substringBefore(';')?.trim()?.lowercase() != "application/json") { responder(s, 400); return }
        val length = headers["content-length"]?.takeIf { Regex("[0-9]{1,6}").matches(it) }?.toIntOrNull()
        if (length == null || length !in 1..16384) { responder(s, 413); return }
        val bytes = ByteArray(length)
        try {
            var read = 0
            while (read < bytes.size) { val n = input.read(bytes, read, bytes.size - read); require(n > 0 && System.nanoTime() < deadline); read += n }
        } catch (_: Exception) { responder(s, 400); return }
        val message = try {
            val text = Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString()
            Json.parseToJsonElement(text)
        } catch (_: Exception) { responder(s, 200, erro(JsonNull, -32700, "Parse error")); return }
        val m = message as? JsonObject
        val id = m?.get("id") ?: JsonNull
        if (m == null || m["jsonrpc"] != JsonPrimitive("2.0") || m["method"] !is JsonPrimitive || m["method"]!!.jsonPrimitive.isString.not() ||
            (id != JsonNull && (id !is JsonPrimitive || (!id.isString && id.doubleOrNull == null)))) {
            responder(s, 200, erro(JsonNull, -32600, "Invalid Request")); return
        }
        if (headers["mcp-protocol-version"] != null && headers["mcp-protocol-version"] !in versoes) { responder(s, 400); return }
        if ("id" !in m) { responder(s, 202); return }
        val params = m["params"] as? JsonObject
        if (m["params"] != null && params == null) { responder(s, 200, erro(id, -32602, "Invalid params")); return }
        val requestedVersion = params?.get("protocolVersion")
        if (m["method"] == JsonPrimitive("initialize") && requestedVersion != null && (requestedVersion !is JsonPrimitive || !requestedVersion.isString)) {
            responder(s, 200, erro(id, -32602, "Invalid params")); return
        }
        val result = when (m["method"]!!.jsonPrimitive.content) {
            "initialize" -> buildJsonObject {
                val version = params?.get("protocolVersion")?.jsonPrimitive?.content
                put("protocolVersion", if (version in versoes) version else "2025-06-18")
                putJsonObject("capabilities") { putJsonObject("tools") {} }
                putJsonObject("serverInfo") { put("name", "fintips-local"); put("version", "0.1.0") }
                put("instructions", "Contexto mínimo calculado no celular. sem_registro não prova falha. Somente leitura; não há acesso aos registros completos. Contexto indisponível ou vencido exige retorno ao FinTips.")
            }
            "ping" -> buildJsonObject {}
            "tools/list" -> buildJsonObject { putJsonArray("tools") { addJsonObject {
                put("name", "ler_contexto_revisado"); put("description", "Consulta indicadores reduzidos autorizados no celular. Ausência de registro não significa meta descumprida.")
                putJsonObject("inputSchema") { put("type", "object"); putJsonObject("properties") {}; put("additionalProperties", false) }
                putJsonObject("annotations") { put("readOnlyHint", true); put("destructiveHint", false); put("idempotentHint", true); put("openWorldHint", false) }
            } } }
            "tools/call" -> {
                val args = params?.get("arguments")
                if (params?.get("name") != JsonPrimitive("ler_contexto_revisado") || (args != null && (args !is JsonObject || args.isNotEmpty()))) {
                    responder(s, 200, erro(id, -32602, "Invalid params")); return
                }
                val current = atual()
                val data = current?.let { buildJsonObject {
                    put("contexto", it.json); put("sincronizacao", "local_no_celular")
                    put("validade_restante_segundos", maxOf(0L, (it.vence - relogio()) / 1_000_000_000))
                } }
                buildJsonObject {
                    put("isError", current == null)
                    if (data != null) put("structuredContent", data)
                    putJsonArray("content") { addJsonObject { put("type", "text"); put("text", data?.toString() ?: "Contexto local indisponível. Abra o FinTips para atualizar as áreas autorizadas.") } }
                }
            }
            else -> { responder(s, 200, erro(id, -32601, "Method not found")); return }
        }
        responder(s, 200, buildJsonObject { put("jsonrpc", "2.0"); put("id", id); put("result", result) })
    }
    private fun responder(s: Socket, status: Int, data: JsonObject? = null) {
        val body = data?.toString()?.toByteArray(Charsets.UTF_8) ?: ByteArray(0)
        val label = when (status) { 200 -> "OK"; 202 -> "Accepted"; 400 -> "Bad Request"; 401 -> "Unauthorized"; 403 -> "Forbidden"; 404 -> "Not Found"; 405 -> "Method Not Allowed"; else -> "Payload Too Large" }
        val auth = if (status == 401) "WWW-Authenticate: Bearer realm=\"FinTips local\"\r\n" else ""
        val allow = if (status == 405) "Allow: POST\r\n" else ""
        val header = "HTTP/1.1 $status $label\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: ${body.size}\r\nConnection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n$auth$allow\r\n"
        s.getOutputStream().apply { write(header.toByteArray(Charsets.US_ASCII)); write(body); flush() }
    }
    override fun close() {
        encerrado = true; snapshot.set(null)
        runCatching { socket.close() }; ativos.forEach { runCatching { it.close() } }
        workers.shutdownNow()
    }
    private fun erro(id: JsonElement, code: Int, message: String) = buildJsonObject {
        put("jsonrpc", "2.0"); put("id", id); putJsonObject("error") { put("code", code); put("message", message) }
    }
    companion object { private val versoes = setOf("2024-11-05", "2025-03-26", "2025-06-18") }
}
