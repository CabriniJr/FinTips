package com.fintips.mcp

import com.fintips.motor.validarContextoIA
import kotlinx.serialization.json.*
import java.io.Closeable
import java.util.UUID

/** Consentimento e ciclo de vida testáveis sem Android. Nunca ampliam escopos
 * numa atualização automática; revisão explícita cria uma nova geração.
 */
class SessaoLocal(private val relogio: () -> Long = System::nanoTime) : Closeable {
    private data class Running(val server: ServidorLocal, val id: String, val scopes: Set<String>, val paused: Boolean = false)
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
            putJsonArray("escopos") { r.scopes.forEach { add(it) } }
        }
    }
    @Synchronized fun atualizar(session: String, c: JsonObject?): JsonObject {
        val r = running ?: error("servidor encerrado")
        require(r.id == session)
        if (c == null) r.server.invalidar() else {
            require(!r.paused && c.keys - "schema_version" == r.scopes)
            r.server.atualizar(c)
        }
        return estado()
    }
    @Synchronized fun pausar(session: String): JsonObject {
        val r = running ?: error("servidor encerrado")
        require(r.id == session)
        r.server.invalidar(); running = r.copy(paused = true)
        return estado()
    }
    @Synchronized fun credencial() = running?.server?.credencial() ?: error("servidor encerrado")
    @Synchronized fun encerrar(): JsonObject {
        running?.server?.close(); running = null
        return estado()
    }
    @Synchronized override fun close() { encerrar(); fechada = true }
}
