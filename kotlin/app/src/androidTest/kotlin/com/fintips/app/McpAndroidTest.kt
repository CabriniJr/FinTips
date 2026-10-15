package com.fintips.app

import android.webkit.WebView
import android.view.ViewGroup
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.net.Socket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Exercita o bridge e o foreground service no Android, sem substituir wrappers. */
@RunWith(AndroidJUnit4::class)
class McpAndroidTest {
    private fun eval(s: ActivityScenario<PreviewActivity>, script: String): String {
        val done = CountDownLatch(1); var result = "null"
        s.onActivity { a ->
            val web = (a.findViewById<ViewGroup>(android.R.id.content)).getChildAt(0) as WebView
            web.evaluateJavascript(script) { result = it; done.countDown() }
        }
        check(done.await(10, TimeUnit.SECONDS)) { "WebView não respondeu" }
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
    private fun command(s: ActivityScenario<PreviewActivity>, op: String, input: JSONObject = JSONObject()): JSONObject {
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
        assertFalse("Bridge recusou $op: ${r.optString("error")}", r.has("error"))
        return r.getJSONObject("result")
    }
    @Test fun servidor_responde_pelo_socket_e_encerra_pelo_bridge_real() {
        ActivityScenario.launch(PreviewActivity::class.java).use { s ->
            awaitEval(s, "typeof FinTipsMotor !== 'undefined' && typeof FinTipsMotor.onmessage === 'function' && document.readyState === 'complete'")
            assertFalse(command(s, "servidor.status").getBoolean("ativo"))
            val context = JSONObject("""{"schema_version":1,"leitura":{"estados":[],"fontes":[]}}""")
            val state = command(s, "servidor.iniciar", JSONObject().put("context", context))
            try {
                assertTrue(state.getBoolean("ativo"))
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
}
