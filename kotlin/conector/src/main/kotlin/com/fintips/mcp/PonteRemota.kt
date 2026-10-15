package com.fintips.mcp

import com.fintips.motor.validarContextoIA
import kotlinx.serialization.json.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.HttpUrl.Companion.toHttpUrl
import java.io.ByteArrayOutputStream
import java.io.Closeable
import java.net.URI
import java.util.concurrent.*
import java.util.concurrent.atomic.AtomicBoolean

/** Transporte, sem registros, arquivos, logs ou chave do MCP local no relay.
 * Consentimentos e credenciais vivem em memória; fechar revoga o lado local
 * imediatamente e solicita revogação remota sem bloquear a UI Android.
 */
class PonteRemota private constructor(
    val origem: String,
    private val token: String,
    private val http: OkHttpClient,
    private val lerContexto: (Set<String>) -> JsonObject,
    private val podeEnviar: (String, Set<String>) -> Boolean,
) : Closeable {
    private class Grant(val id: String, val provider: String, val scopes: Set<String>, var phase: String = "aguardando_ia")
    private val lock = Any()
    private val closed = AtomicBoolean(false)
    private val grants = linkedMapOf<String, Grant>()
    private val activated = linkedSetOf<String>()
    private var state = "conectando"
    private var serial = 0L
    private var retry = 1L
    private var ws: WebSocket? = null
    private val scheduler = Executors.newSingleThreadScheduledExecutor { r -> Thread(r, "fintips-ponte-reconnect").apply { isDaemon = true } }
    private val work = ThreadPoolExecutor(2, 2, 0L, TimeUnit.SECONDS, ArrayBlockingQueue(8),
        { r -> Thread(r, "fintips-ponte-consulta").apply { isDaemon = true } })

    fun estado(): JsonObject = synchronized(lock) { buildJsonObject {
        put("ativo", !closed.get()); put("origem", origem); put("estado", state)
        putJsonArray("autorizacoes") { grants.values.forEach { g -> addJsonObject {
            put("id", g.id); put("provedor", g.provider); put("estado", g.phase)
            putJsonArray("escopos") { areas.filter { it in g.scopes }.forEach { add(it) } }
        } } }
    } }
    private fun request(path: String, data: JsonObject): JsonObject {
        check(!closed.get())
        return post(http, origem, path, data, token)
    }
    fun consultarCodigo(code: String): JsonObject {
        require(codeRegex.matches(code))
        synchronized(lock) { check(state == "online" && !closed.get()) }
        val r = request("/phone/authorization", buildJsonObject { put("code", code) })
        require(r.keys == setOf("provider", "callback_host", "expires_in") && r["provider"]?.jsonPrimitive?.content in providers)
        val host = r["callback_host"]!!.jsonPrimitive.content
        val allowed = if (r["provider"] == JsonPrimitive("chatgpt")) setOf("chatgpt.com") else setOf("claude.ai", "claude.com")
        require(host in allowed)
        return r
    }
    fun autorizar(code: String, escopos: Set<String>, provider: String): JsonObject {
        require(escopos.isNotEmpty() && areas.containsAll(escopos) && provider in providers)
        synchronized(lock) { check(grants.size < 20 && state == "online") }
        val info = consultarCodigo(code)
        require(info["provider"]!!.jsonPrimitive.content == provider)
        val r = request("/phone/approve", buildJsonObject {
            put("code", code); putJsonArray("scopes") { areas.filter { it in escopos }.forEach { add(it) } }
        })
        val id = r["grant"]!!.jsonPrimitive.content
        require(r.keys == setOf("grant", "provider", "scopes", "status") && idRegex.matches(id) &&
            r["provider"] == JsonPrimitive(provider) && r["status"] == JsonPrimitive("approved") &&
            r["scopes"] == JsonArray(areas.filter { it in escopos }.map { JsonPrimitive(it) }))
        synchronized(lock) {
            check(!closed.get())
            val g = Grant(id, provider, escopos.toSet())
            if (activated.remove(id)) g.phase = "autorizado"
            grants[id] = g
        }
        return estado()
    }
    fun negar(code: String): JsonObject {
        require(codeRegex.matches(code))
        request("/phone/deny", buildJsonObject { put("code", code) })
        return estado()
    }
    fun revogar(id: String): JsonObject {
        require(idRegex.matches(id))
        synchronized(lock) { grants.remove(id); activated.remove(id) }
        request("/phone/revoke", buildJsonObject { put("grant", id) })
        return estado()
    }
    private fun connect() {
        val generation = synchronized(lock) {
            if (closed.get()) return
            state = if (serial == 0L) "conectando" else "reconectando"
            ++serial
        }
        val request = Request.Builder().url(origem.replaceFirst("https://", "wss://") + "/phone/channel")
            .header("Authorization", "Bearer $token").header("Sec-WebSocket-Protocol", "fintips-phone-v1").build()
        val opened = http.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                synchronized(lock) { if (closed.get() || serial != generation) webSocket.cancel() else ws = webSocket }
            }
            override fun onMessage(webSocket: WebSocket, text: String) {
                if (closed.get()) return
                try {
                    require(text.toByteArray(Charsets.UTF_8).size <= 16384)
                    val b = Json.parseToJsonElement(text).jsonObject
                    synchronized(lock) { check(serial == generation && !closed.get()) }
                    when (b["type"]?.jsonPrimitive?.content) {
                        "ready" -> synchronized(lock) {
                            require(b.keys == setOf("type", "protocol", "activated") && b["protocol"] == JsonPrimitive(1))
                            val ids = b["activated"]!!.jsonArray
                            require(ids.size <= 20 && ids.all { idRegex.matches(it.jsonPrimitive.content) })
                            activated.clear()
                            ids.forEach { id ->
                                val value = id.jsonPrimitive.content
                                val grant = grants[value]
                                if (grant != null) grant.phase = "autorizado" else activated.add(value)
                            }
                            state = "online"; retry = 1
                        }
                        "grant_activated", "grant_revoked" -> synchronized(lock) {
                            require(b.keys == setOf("type", "id"))
                            val id = b["id"]!!.jsonPrimitive.content; require(idRegex.matches(id))
                            if (b["type"] == JsonPrimitive("grant_revoked")) { grants.remove(id); activated.remove(id) }
                            else if (grants[id] != null) grants[id]!!.phase = "autorizado"
                            else { require(activated.size < 20); activated.add(id) }
                        }
                        "request" -> {
                            require(b.keys == setOf("type", "id", "nonce", "grant", "scopes"))
                            require(listOf("id", "nonce", "grant").all { idRegex.matches(b[it]!!.jsonPrimitive.content) })
                            val requested = b["scopes"]!!.jsonArray.map { it.jsonPrimitive.content }
                            require(requested.isNotEmpty() && requested == areas.filter { it in requested })
                            try { work.execute { answer(webSocket, generation, b, requested.toSet()) } }
                            catch (_: RejectedExecutionException) { error(webSocket, b, "contexto_indisponivel") }
                        }
                        else -> throw IllegalArgumentException()
                    }
                } catch (_: Exception) {
                    synchronized(lock) { if (serial == generation) state = "erro_de_protocolo" }
                    webSocket.close(1008, "invalid relay message")
                }
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { failed(generation, code == 1008) }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) { failed(generation, response?.code == 401) }
        })
        synchronized(lock) { if (!closed.get() && serial == generation) ws = opened else opened.cancel() }
    }
    private fun failed(generation: Long, permanent: Boolean) {
        val wait = synchronized(lock) {
            if (closed.get() || serial != generation) return
            ws = null
            if (permanent || state == "erro_de_protocolo") { state = "credencial_ou_protocolo_recusado"; return }
            state = "reconectando"
            val delay = retry; retry = minOf(30L, retry * 2); delay
        }
        runCatching { scheduler.schedule({ connect() }, wait, TimeUnit.SECONDS) }
    }
    private fun error(socket: WebSocket, b: JsonObject, code: String) {
        if (closed.get()) return
        socket.send(buildJsonObject { put("type", "result"); put("id", b["id"]!!); put("nonce", b["nonce"]!!); put("error", code) }.toString())
    }
    private fun answer(socket: WebSocket, generation: Long, b: JsonObject, scopes: Set<String>) {
        val id = b["grant"]!!.jsonPrimitive.content
        val grant = synchronized(lock) { grants[id]?.takeIf { !closed.get() && serial == generation && state == "online" && it.scopes == scopes } }
        if (grant == null) { error(socket, b, "autorizacao_indisponivel"); return }
        try {
            val data = lerContexto(scopes)
            val context = validarContextoIA(data["contexto"]!!.jsonObject)
            require(context.keys - "schema_version" == scopes)
            val ttl = data["validade_restante_segundos"]!!.jsonPrimitive.long
            require(ttl in 1..3600)
            val session = data["sessao_local"]!!.jsonPrimitive.content
            val allowed = synchronized(lock) { !closed.get() && serial == generation && grants[id] === grant }
            if (!allowed || !podeEnviar(session, scopes)) { error(socket, b, "autorizacao_indisponivel"); return }
            val payload = buildJsonObject {
                put("type", "result"); put("id", b["id"]!!); put("nonce", b["nonce"]!!)
                put("contexto", context); put("validade_restante_segundos", ttl)
            }.toString()
            synchronized(lock) {
                if (!closed.get() && serial == generation && grants[id] === grant && socket.send(payload)) grant.phase = "consulta_recebida"
            }
        } catch (_: Exception) { error(socket, b, "contexto_indisponivel") }
    }
    override fun close() {
        if (!closed.compareAndSet(false, true)) return
        val socket = synchronized(lock) { state = "encerrado"; grants.clear(); activated.clear(); ws.also { ws = null } }
        socket?.cancel(); scheduler.shutdownNow(); work.shutdownNow()
        // Sem espera de rede no encerramento do foreground service.
        Thread({ runCatching { post(http.newBuilder().callTimeout(3, TimeUnit.SECONDS).build(), origem,
            "/phone/disconnect", buildJsonObject {}, token) } }, "fintips-ponte-revogar").apply { isDaemon = true; start() }
    }
    companion object {
        private val areas = listOf("rotina", "planos", "leitura")
        private val providers = setOf("chatgpt", "claude")
        private val idRegex = Regex("[A-Za-z0-9_-]{43}")
        private val joinRegex = Regex("[A-Za-z0-9_-]{43}|[A-Za-z0-9_-]{64}")
        private val codeRegex = Regex("[A-Z2-7]{12}")
        private val media = "application/json; charset=utf-8".toMediaType()
        fun normalizarOrigem(origin: String): String {
            val u = URI(origin)
            require(u.scheme == "https" && !u.host.isNullOrBlank() && u.rawUserInfo == null && u.rawQuery == null && u.rawFragment == null && u.rawPath in listOf("", "/"))
            require(u.port == -1 || u.port in 1..65535)
            return origin.toHttpUrl().toString().removeSuffix("/")
        }
        fun criar(origin: String, invite: String, lerContexto: (Set<String>) -> JsonObject,
                  podeEnviar: (String, Set<String>) -> Boolean,
                  client: OkHttpClient = OkHttpClient.Builder().connectTimeout(5, TimeUnit.SECONDS).readTimeout(10, TimeUnit.SECONDS)
                      .writeTimeout(5, TimeUnit.SECONDS).callTimeout(15, TimeUnit.SECONDS).pingInterval(60, TimeUnit.SECONDS)
                      .followRedirects(false).followSslRedirects(false).retryOnConnectionFailure(false).build()): PonteRemota {
            val base = normalizarOrigem(origin); require(joinRegex.matches(invite))
            val safe = client.newBuilder().followRedirects(false).followSslRedirects(false).build()
            val r = post(safe, base, "/phone/enroll", buildJsonObject { put("protocol", 1); put("invite", invite) }, null)
            require(r.keys == setOf("device", "token", "protocol", "expires_in") && r["protocol"] == JsonPrimitive(1) &&
                idRegex.matches(r["device"]!!.jsonPrimitive.content) && idRegex.matches(r["token"]!!.jsonPrimitive.content))
            return PonteRemota(base, r["token"]!!.jsonPrimitive.content, safe, lerContexto, podeEnviar).also { it.connect() }
        }
        private fun post(client: OkHttpClient, origin: String, path: String, data: JsonObject, token: String?): JsonObject {
            val builder = Request.Builder().url(origin + path).post(data.toString().toRequestBody(media))
            if (token != null) builder.header("Authorization", "Bearer $token")
            client.newCall(builder.build()).execute().use { response ->
                if (!response.isSuccessful) throw FalhaPonte(if (response.code == 410) "CODIGO_EXPIRADO" else if (response.code == 401 || response.code == 400) "AUTORIZACAO_RECUSADA" else "PONTE_INDISPONIVEL")
                require(response.header("Content-Type")?.substringBefore(';')?.trim() == "application/json")
                val out = ByteArrayOutputStream()
                response.body!!.byteStream().use { input ->
                    val b = ByteArray(1024)
                    while (true) { val n = input.read(b); if (n < 0) break; require(out.size() + n <= 16384); out.write(b, 0, n) }
                }
                return Json.parseToJsonElement(out.toString("UTF-8")).jsonObject
            }
        }
    }
}
class FalhaPonte(val codigo: String) : IllegalStateException(codigo)
