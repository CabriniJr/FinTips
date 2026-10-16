package com.fintips.app

import android.webkit.WebView
import android.app.NotificationManager
import android.os.Build
import android.os.ParcelFileDescriptor
import androidx.lifecycle.Lifecycle
import androidx.test.platform.app.InstrumentationRegistry
import android.view.ViewGroup
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.FixMethodOrder
import org.junit.runners.MethodSorters
import org.junit.runner.RunWith
import java.net.Socket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Exercita o bridge e o foreground service no Android, sem substituir wrappers. */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class McpAndroidTest {
    private fun eval(s: ActivityScenario<PreviewActivity>, script: String): String {
        val done = CountDownLatch(1); var result = "null"
        s.onActivity { a ->
            val web = (a.findViewById<ViewGroup>(android.R.id.content)).getChildAt(0) as WebView
            web.evaluateJavascript(script) { result = it; done.countDown() }
        }
        check(done.await(60, TimeUnit.SECONDS)) { "WebView não respondeu" }
        return result
    }
    private fun awaitEval(s: ActivityScenario<PreviewActivity>, script: String): String {
        val until = System.nanoTime() + TimeUnit.SECONDS.toNanos(120)
        while (System.nanoTime() < until) {
            val r = eval(s, script)
            if (r != "null" && r != "false") return r
            Thread.sleep(100)
        }
        error("Resposta Android indisponível")
    }
    private fun request(s: ActivityScenario<PreviewActivity>, op: String, input: JSONObject = JSONObject()): JSONObject {
        val request = JSONObject().put("id", "teste-nativo").put("operation", op).put("input", input)
        eval(s, """(() => {
          window.__mcpResposta = null;
          const anterior = FinTipsMotor.onmessage;
          FinTipsMotor.onmessage = e => {
            const r = JSON.parse(e.data);
            if (r.id === 'teste-nativo') { window.__mcpResposta = r; FinTipsMotor.onmessage = anterior; }
            else if (anterior) anterior(e);
          };
          FinTipsMotor.postMessage(${JSONObject.quote(request.toString())});
        })()""")
        val r = JSONObject(awaitEval(s, "window.__mcpResposta || null"))
        return r
    }
    private fun command(s: ActivityScenario<PreviewActivity>, op: String, input: JSONObject = JSONObject()): JSONObject {
        val r = request(s, op, input)
        assertFalse("Bridge recusou $op: ${r.optString("error")}", r.has("error"))
        return r.getJSONObject("result")
    }
    private fun ready(s: ActivityScenario<PreviewActivity>) {
        awaitEval(s, "typeof FinTipsMotor !== 'undefined' && typeof FinTipsMotor.onmessage === 'function' && document.readyState === 'complete'")
    }
    private fun notifications(grant: Boolean) {
        if (Build.VERSION.SDK_INT < 33) return
        val i = InstrumentationRegistry.getInstrumentation()
        val c = i.targetContext
        c.getSharedPreferences("mcp-local", 0).edit().putBoolean("notificacoes_solicitadas", true).commit()
        // O CI revoga antes de iniciar a instrumentação; fazê-lo aqui
        // encerraria o próprio processo que executa os testes.
        if (grant) ParcelFileDescriptor.AutoCloseInputStream(i.uiAutomation.executeShellCommand("pm grant ${c.packageName} android.permission.POST_NOTIFICATIONS")).use { it.readBytes() }
        assertEquals(grant, c.getSystemService(NotificationManager::class.java).areNotificationsEnabled())
    }
    @Test fun b_servidor_responde_pelo_socket_e_encerra_pelo_bridge_real() {
        ActivityScenario.launch(PreviewActivity::class.java).use { s ->
            ready(s)
            assertFalse(command(s, "servidor.status").getBoolean("ativo"))
            val context = JSONObject("""{"schema_version":1,"leitura":{"estados":[],"fontes":[]}}""")
            val state = command(s, "servidor.iniciar", JSONObject().put("context", context))
            try {
                assertTrue(state.getBoolean("ativo"))
                assertEquals("ok", state.getString("teste_local"))
                assertEquals("ok", command(s, "servidor.verificar", JSONObject().put("sessao", state.getString("sessao"))).getString("teste_local"))
                assertTrue(state.getBoolean("contexto_disponivel"))
                val endpoint = java.net.URI(state.getString("endpoint"))
                val token = McpLocalService.credencial()
                val body = """{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ler_contexto_revisado","arguments":{}}}"""
                Socket("127.0.0.1", endpoint.port).use { socket ->
                    socket.soTimeout = 5000
                    val request = "POST /mcp HTTP/1.1\r\nHost: ${endpoint.rawAuthority}\r\nAuthorization: Bearer $token\r\nContent-Type: application/json\r\nContent-Length: ${body.toByteArray().size}\r\n\r\n$body"
                    socket.getOutputStream().write(request.toByteArray())
                    val response = socket.getInputStream().bufferedReader().readText()
                    assertTrue(response.startsWith("HTTP/1.1 200"))
                    assertFalse(JSONObject(response.substringAfter("\r\n\r\n")).getJSONObject("result").getBoolean("isError"))
                }
            } finally { command(s, "servidor.encerrar") }
            assertFalse(command(s, "servidor.status").getBoolean("ativo"))
        }
    }
    @Test fun a_notificacoes_bloqueadas_nao_impedem_servidor_e_erro_nao_vaza_contexto() {
        notifications(false)
        ActivityScenario.launch(PreviewActivity::class.java).use { s ->
            ready(s)
            val invalid = request(s, "servidor.iniciar", JSONObject().put("context",
                JSONObject("""{"schema_version":1,"leitura":{"estados":[],"fontes":[]},"titulo":"CANARY_PRIVADO"}""")))
            assertTrue(invalid.getString("error").startsWith("MCP-02:"))
            assertFalse(invalid.toString().contains("CANARY_PRIVADO"))
            assertFalse(command(s, "servidor.status").getBoolean("ativo"))
            val c = JSONObject("""{"schema_version":1,"leitura":{"estados":[],"fontes":[]}}""")
            val state = command(s, "servidor.iniciar", JSONObject().put("context", c))
            try { assertEquals("ok", state.getString("teste_local")) }
            finally { command(s, "servidor.encerrar") }
        }
    }
    @Test fun c_trocar_de_app_mantem_mcp_e_acao_da_notificacao_revoga_sessao() {
        notifications(true)
        val c = InstrumentationRegistry.getInstrumentation().targetContext
        ActivityScenario.launch(PreviewActivity::class.java).use { s ->
            ready(s)
            val input = JSONObject().put("context", JSONObject("""{"schema_version":1,"leitura":{"estados":[],"fontes":[]}}"""))
            val a = command(s, "servidor.iniciar", input)
            val token = McpLocalService.credencial()
            try {
                s.moveToState(Lifecycle.State.CREATED)
                assertEquals("ok", McpLocalService.verificar(a.getString("sessao")).getString("teste_local"))
                val notification = c.getSystemService(NotificationManager::class.java).activeNotifications.single { it.id == 6501 }
                notification.notification.actions.single { it.title.toString() == "Encerrar" }.actionIntent.send()
                val until = System.nanoTime() + TimeUnit.SECONDS.toNanos(10)
                while (McpLocalService.status().getBoolean("ativo") && System.nanoTime() < until) Thread.sleep(50)
                assertFalse(McpLocalService.status().getBoolean("ativo"))
                s.moveToState(Lifecycle.State.RESUMED)
                val b = command(s, "servidor.iniciar", input)
                assertEquals("ok", b.getString("teste_local"))
                assertFalse("O token anterior deve estar revogado", token == McpLocalService.credencial())
            } finally {
                s.moveToState(Lifecycle.State.RESUMED)
                command(s, "servidor.encerrar")
            }
        }
    }

}
