package com.fintips.mcp

import com.fintips.motor.validarContextoIA
import kotlinx.serialization.json.*
import java.io.Closeable
import java.util.UUID

/** Consentimento e ciclo de vida testáveis sem Android. Nunca ampliam escopos
 * numa atualização automática; revisão explícita cria uma nova geração.
 */
class SessaoLocal(
    private val relogio: () -> Long = System::nanoTime,
    private val sonda: (ServidorLocal) -> Unit = { it.verificar() },
) : Closeable {
    private data class Running(val server: ServidorLocal, val id: String, val scopes: Set<String>, val paused: Boolean = false, val testado: Boolean = false)
    private var running: Running? = null
    private var fechada = false

    @Synchronized fun iniciar(c: JsonObject): JsonObject {
        check(!fechada)
        val valid = validarContextoIA(Json.parseToJsonElement(c.toString()).jsonObject)
        val server = running?.server ?: ServidorLocal(valid, relogio)
        server.atualizar(valid)
        running = Running(server, UUID.randomUUID().toString(), valid.keys - "schema_version")
        return estado()
    }
    @Synchronized fun ativo() = running != null
    @Synchronized fun estado(): JsonObject {
        val r = running ?: return buildJsonObject { put("ativo", false); put("contexto_disponivel", false) }
        return buildJsonObject {
            r.server.estado().forEach { (k, v) -> put(k, v) }
            put("sessao", r.id); put("pausado", r.paused)
            put("teste_local", if (r.testado) "ok" else "pendente")
            putJsonArray("escopos") { r.scopes.forEach { add(it) } }
        }
    }
    @Synchronized fun atualizar(session: String, c: JsonObject?): JsonObject {
        val r = running ?: error("servidor encerrado")
        require(r.id == session)
        if (c == null) { r.server.invalidar(); running = r.copy(testado = false) } else {
            require(!r.paused && c.keys - "schema_version" == r.scopes)
            r.server.atualizar(c)
        }
        return estado()
    }
    @Synchronized fun pausar(session: String): JsonObject {
        val r = running ?: error("servidor encerrado")
        require(r.id == session)
        r.server.invalidar(); running = r.copy(paused = true, testado = false)
        return estado()
    }
    fun verificar(session: String): JsonObject {
        val r = synchronized(this) {
            val atual = running ?: error("servidor encerrado")
            require(atual.id == session && !atual.paused)
            running = atual.copy(testado = false)
            atual
        }
        // A parada e a revogação não esperam o timeout de uma sonda de rede.
        sonda(r.server)
        return synchronized(this) {
            val atual = running ?: error("servidor encerrado")
            require(atual.id == session && !atual.paused)
            running = atual.copy(testado = true)
            estado()
        }
    }
    @Synchronized fun credencial() = running?.server?.credencial() ?: error("servidor encerrado")
    @Synchronized fun encerrar(): JsonObject {
        running?.server?.close(); running = null
        return estado()
    }
    @Synchronized override fun close() { encerrar(); fechada = true }
}
