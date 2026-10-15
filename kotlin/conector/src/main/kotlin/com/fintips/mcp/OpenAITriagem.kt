package com.fintips.mcp

import com.fintips.motor.triagem.pedidoOpenAITriagem
import com.fintips.motor.triagem.validarSugestaoTriagem
import com.fintips.motor.triagem.pedidoAgente
import com.fintips.motor.triagem.resolverAgente
import kotlinx.serialization.json.*
import okhttp3.*
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Só a projeção tipada vai à API. Sem chat, nomes, URLs de origem ou mapas locais. */
class OpenAITriagem(
    client: OkHttpClient = OkHttpClient.Builder().connectTimeout(10,TimeUnit.SECONDS)
        .readTimeout(40,TimeUnit.SECONDS).writeTimeout(5,TimeUnit.SECONDS).callTimeout(45,TimeUnit.SECONDS)
        .retryOnConnectionFailure(false).build(),
    endpoint: String = "https://api.openai.com/v1/responses",
) {
    private val http=client.newBuilder().followRedirects(false).followSslRedirects(false).retryOnConnectionFailure(false).build()
    private val url=endpoint.toHttpUrl().also { require(it.isHttps && it.username.isEmpty() && it.password.isEmpty() && it.query==null && it.fragment==null) }
    private val current=AtomicReference<Call?>(null)
    fun cancelar() { current.getAndSet(null)?.cancel() }
    fun sugerir(bundle: JsonObject, drafts: JsonArray, key: String, autorizado: Boolean, hoje: String = java.time.LocalDate.now().toString(), agente: Boolean = false): JsonObject {
        if(!autorizado) throw FalhaTriagem("CONSENTIMENTO")
        if(!key.startsWith("sk-") || key.length !in 20..512 || key.any { it.isWhitespace() || it.code < 32 }) throw FalhaTriagem("CHAVE")
        val prepared=if(agente) pedidoAgente(bundle,drafts,hoje) else pedidoOpenAITriagem(bundle,drafts,hoje)
        val req=Request.Builder().url(url).header("Authorization","Bearer $key")
            .post((if(agente) prepared else prepared["pedido"]!!).toString().toRequestBody("application/json; charset=utf-8".toMediaType())).build()
        val call=http.newCall(req)
        if(!current.compareAndSet(null,call)) throw FalhaTriagem("OCUPADO")
        try {
            call.execute().use { response ->
                if(!response.isSuccessful) throw FalhaTriagem(if(response.code==401) "CHAVE" else if(response.code==429) "LIMITE" else "REDE")
                require(response.header("Content-Type")?.substringBefore(';')?.trim()=="application/json")
                val out=ByteArrayOutputStream()
                response.body!!.byteStream().use { input ->
                    val buf=ByteArray(2048)
                    while(true) { val n=input.read(buf);if(n<0) break;require(out.size()+n<=65536);out.write(buf,0,n) }
                }
                val result=Json.parseToJsonElement(out.toString("UTF-8")).jsonObject
                require(result["status"]==JsonPrimitive("completed"))
                val texts=result["output"]!!.jsonArray.filter { it.jsonObject["type"]==JsonPrimitive("message") }
                    .flatMap { it.jsonObject["content"]!!.jsonArray }.filter { it.jsonObject["type"]==JsonPrimitive("output_text") }
                require(texts.size==1)
                val choice=Json.parseToJsonElement(texts.single().jsonObject["text"]!!.jsonPrimitive.content).jsonObject
                return if(agente) resolverAgente(bundle,drafts,hoje,choice) else validarSugestaoTriagem(prepared["publico"]!!.jsonObject,choice)
            }
        } catch(e: FalhaTriagem) { throw e }
        catch(_: Exception) { throw FalhaTriagem(if(call.isCanceled()) "CANCELADO" else "RESPOSTA") }
        finally { current.compareAndSet(call,null) }
    }
}
class FalhaTriagem(val codigo: String): IllegalStateException(codigo)
