package com.fintips.mcp

import kotlinx.serialization.json.*
import kotlin.test.*
import org.junit.jupiter.api.Test

class SessaoLocalTest {
    private val c = Json.parseToJsonElement("""{"schema_version":1,"leitura":{"estados":["estimado"],"fontes":["usuario"]}}""").jsonObject
    private fun id(s: JsonObject) = s["sessao"]!!.jsonPrimitive.content

    @Test fun so_revisao_explicita_pode_ampliar_escopos() = SessaoLocal().use { s ->
        val a = s.iniciar(c)
        val other = Json.parseToJsonElement("""{"schema_version":1,"leitura":{"estados":[],"fontes":[]},"planos":[]}""").jsonObject
        assertFails { s.atualizar(id(a), other) }
        assertTrue(s.estado()["contexto_disponivel"]!!.jsonPrimitive.boolean)
    }
    @Test fun pausar_impede_atualizacao_automatica_de_reativar_consulta() = SessaoLocal().use { s ->
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
    @Test fun atualizar_revisao_preserva_conexao_mas_encerra_geracao_anterior() = SessaoLocal().use { s ->
        val a = s.iniciar(c); val token = s.credencial()
        val b = s.iniciar(c)
        assertEquals(a["endpoint"], b["endpoint"]); assertTrue(token == s.credencial())
        assertTrue(id(a) != id(b)); assertFails { s.atualizar(id(a), null) }
    }
    @Test fun falha_de_dados_omite_contexto_e_uma_atualizacao_valida_recupera() = SessaoLocal().use { s ->
        val a = s.iniciar(c)
        s.atualizar(id(a), null)
        assertFalse(s.estado()["contexto_disponivel"]!!.jsonPrimitive.boolean)
        assertEquals(JsonArray(listOf(JsonPrimitive("leitura"))), s.estado()["escopos"]!!.jsonArray)
        s.atualizar(id(a), c); assertTrue(s.estado()["contexto_disponivel"]!!.jsonPrimitive.boolean)
    }
    @Test fun encerrar_revoga_e_fechar_nao_permite_reinicio_tardio() {
        val s = SessaoLocal(); val a = s.iniciar(c)
        s.encerrar(); assertFalse(s.ativo()); assertFails { s.atualizar(id(a), c) }; assertFails { s.credencial() }
        s.iniciar(c); s.close(); s.close(); assertFails { s.iniciar(c) }
    }
}
