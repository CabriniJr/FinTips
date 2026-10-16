package com.fintips.mcp

import kotlinx.serialization.json.*
import kotlin.test.*
import org.junit.jupiter.api.Test

class SessaoLocalTest {
    private val c = Json.parseToJsonElement("""{"schema_version":1,"leitura":{"estados":["estimado"],"fontes":["usuario"]}}""").jsonObject
    private fun id(s: JsonObject) = s["sessao"]!!.jsonPrimitive.content

    @Test fun so_revisao_explicita_pode_ampliar_escopos(): Unit = SessaoLocal().use { s ->
        val a = s.iniciar(c)
        val other = Json.parseToJsonElement("""{"schema_version":1,"leitura":{"estados":[],"fontes":[]},"planos":[]}""").jsonObject
        assertFails { s.atualizar(id(a), other) }
        assertTrue(s.estado()["contexto_disponivel"]!!.jsonPrimitive.boolean)
    }
    @Test fun pausar_impede_atualizacao_automatica_de_reativar_consulta(): Unit = SessaoLocal().use { s ->
        val a = s.iniciar(c)
        s.pausar(id(a))
        assertTrue(s.estado()["pausado"]!!.jsonPrimitive.boolean)
        assertFalse(s.estado()["contexto_disponivel"]!!.jsonPrimitive.boolean)
        assertFails { s.atualizar(id(a), c) }
        val b = s.iniciar(c)
        assertTrue(id(a) != id(b))
        assertFails { s.atualizar(id(a), c) }
        assertFalse(b["pausado"]!!.jsonPrimitive.boolean)
    }
    @Test fun atualizar_revisao_preserva_conexao_mas_encerra_geracao_anterior(): Unit = SessaoLocal().use { s ->
        val a = s.iniciar(c); val token = s.credencial()
        val b = s.iniciar(c)
        assertEquals(a["endpoint"], b["endpoint"]); assertTrue(token == s.credencial())
        assertTrue(id(a) != id(b)); assertFails { s.atualizar(id(a), null) }
    }
    @Test fun falha_de_dados_omite_contexto_e_uma_atualizacao_valida_recupera(): Unit = SessaoLocal().use { s ->
        val a = s.iniciar(c)
        s.atualizar(id(a), null)
        assertFalse(s.estado()["contexto_disponivel"]!!.jsonPrimitive.boolean)
        assertEquals(JsonArray(listOf(JsonPrimitive("leitura"))), s.estado()["escopos"]!!.jsonArray)
        s.atualizar(id(a), c); assertTrue(s.estado()["contexto_disponivel"]!!.jsonPrimitive.boolean)
    }
    @Test fun teste_local_exige_resposta_mcp_e_contexto_disponivel(): Unit = SessaoLocal().use { s ->
        val a = s.iniciar(c); val session = id(a)
        assertEquals(JsonPrimitive("pendente"), a["teste_local"])
        assertEquals(JsonPrimitive("ok"), s.verificar(session)["teste_local"])
        s.atualizar(session, null)
        assertFails { s.verificar(session) }
        assertEquals(JsonPrimitive("pendente"), s.estado()["teste_local"])
        s.atualizar(session, c)
        s.verificar(session)
        s.pausar(session)
        assertFails { s.verificar(session) }
        assertEquals(JsonPrimitive("pendente"), s.estado()["teste_local"])
    }
    @Test fun teste_antigo_nao_verifica_uma_nova_autorizacao(): Unit = SessaoLocal().use { s ->
        val a = s.iniciar(c); s.iniciar(c)
        assertFails { s.verificar(id(a)) }
        assertEquals(JsonPrimitive("pendente"), s.estado()["teste_local"])
    }
    @Test fun encerrar_nao_espera_sonda_e_sonda_antiga_nao_confirma_nova_sessao() {
        val entrou = java.util.concurrent.CountDownLatch(1)
        val liberar = java.util.concurrent.CountDownLatch(1)
        SessaoLocal(sonda = { entrou.countDown(); check(liberar.await(5, java.util.concurrent.TimeUnit.SECONDS)) }).use { s ->
            val a = s.iniciar(c)
            val falhou = java.util.concurrent.atomic.AtomicBoolean(false)
            val t = kotlin.concurrent.thread { falhou.set(runCatching { s.verificar(id(a)) }.isFailure) }
            check(entrou.await(2, java.util.concurrent.TimeUnit.SECONDS))
            try { s.encerrar(); s.iniciar(c) } finally { liberar.countDown() }
            t.join(3000); assertFalse(t.isAlive); assertTrue(falhou.get())
            assertEquals(JsonPrimitive("pendente"), s.estado()["teste_local"])
        }
    }
    @Test fun encerrar_revoga_e_fechar_nao_permite_reinicio_tardio() {
        val s = SessaoLocal(); val a = s.iniciar(c)
        s.encerrar(); assertFalse(s.ativo()); assertFails { s.atualizar(id(a), c) }; assertFails { s.credencial() }
        s.iniciar(c); s.close(); s.close(); assertFails { s.iniciar(c) }
    }
}
