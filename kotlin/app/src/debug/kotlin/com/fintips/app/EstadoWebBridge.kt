package com.fintips.app

import android.webkit.JavascriptInterface
import kotlinx.serialization.json.*

/** Interface síncrona de guarda para os assets locais. Não faz rede nem chama IA.
 * O WebView bloqueia navegação/subrecursos fora da origem de assets do APK. */
internal class EstadoWebBridge(private val estado: EstadoCliente) {
    private fun resposta(action: ()->JsonElement): String = try {
        buildJsonObject { put("result",action()) }.toString()
    } catch(_: Exception) { buildJsonObject { put("error","Os dados nativos não puderam ser lidos ou mudaram durante a edição. Reabra a tela; os registros anteriores foram preservados.") }.toString() }
    @JavascriptInterface fun status(): String = resposta { buildJsonObject { put("existe",estado.existe());if(estado.existe()) { val s=estado.snapshot();put("revisao",s["revisao"]!!);put("revisao_bundle",s["revisao_bundle"]!!);put("librera",s["librera"]!!);put("deposito",s["deposito"]!!) } } }
    @JavascriptInterface fun snapshot(): String = resposta { estado.snapshot() }
    @JavascriptInterface fun inicializar(raw: String): String = resposta {
        require(raw.encodeToByteArray().size<=8*1024*1024)
        val i=Json.parseToJsonElement(raw).jsonObject
        require(i.keys==setOf("bundle","chat"));estado.inicializar(i["bundle"]!!.jsonObject,i["chat"]!!)
    }
    @JavascriptInterface fun salvar(raw: String): String = resposta {
        require(raw.encodeToByteArray().size<=8*1024*1024)
        val i=Json.parseToJsonElement(raw).jsonObject
        require(i.keys==setOf("revisao","chave","valor"));estado.escrever(i["revisao"]!!.jsonPrimitive.long,i["chave"]!!.jsonPrimitive.content,i["valor"]!!)
    }
    @JavascriptInterface fun copia(): String = resposta { JsonPrimitive(estado.copia()) }
}
