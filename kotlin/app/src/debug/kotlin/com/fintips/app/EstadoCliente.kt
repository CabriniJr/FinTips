package com.fintips.app

import android.content.Context
import android.util.AtomicFile
import com.fintips.motor.triagem.validarBundle
import com.fintips.motor.vida.importarLibrera
import kotlinx.serialization.json.*
import java.io.File
import java.util.UUID

internal val guardasAndroid by lazy { Json.parseToJsonElement(GUARDAS_ANDROID).jsonObject["guardas"]!!.jsonObject }
internal fun guardaAndroid(key: String) = guardasAndroid[key]!!.jsonObject

/** Autoridade única Android de vida/leitura/caderno/chat. UI e job transacionam aqui.
 * O legado WebView não é apagado nem atualizado após a migração. */
internal class EstadoCliente(context: Context, nome: String = guardaAndroid("estado")["arquivo"]!!.jsonPrimitive.content) {
    private val file = AtomicFile(File(context.noBackupFilesDir,nome))
    fun existe() = synchronized(LOCK) { file.baseFile.exists() || File(file.baseFile.path+".bak").exists() }
    private fun ler(): JsonObject {
        require(existe()) { "estado não migrado" }
        val bytes=file.openRead().use { input ->
            val out=java.io.ByteArrayOutputStream();val buffer=ByteArray(8192)
            while(true) { val n=input.read(buffer);if(n<0) break;require(out.size()+n<=MAX_BYTES);out.write(buffer,0,n) };out.toByteArray()
        }
        return Json.parseToJsonElement(bytes.decodeToString()).jsonObject.also(::validar)
    }
    private fun validar(b: JsonObject) {
        require(b.keys==setOf("schema_version","revisao","revisao_bundle","revisao_chat","revisao_fonte","bundle","chat","fonte_librera","excluidos_librera"))
        require(b["schema_version"]==JsonPrimitive(1))
        for(k in listOf("revisao","revisao_bundle","revisao_chat","revisao_fonte")) require(!b[k]!!.jsonPrimitive.isString && b[k]!!.jsonPrimitive.long in 1L..9007199254740991L)
        validarBundle(b["bundle"]!!.jsonObject)
        validarChat(b["chat"]!!)
        require(b["excluidos_librera"]!!.jsonArray.size<=3000)
        b["excluidos_librera"]!!.jsonArray.forEach { require(it.jsonArray.size==2 && it.jsonArray.all { v -> v.jsonPrimitive.isString }) }
        b["fonte_librera"]?.takeUnless { it==JsonNull }?.jsonObject?.let { s ->
            require(s.keys==setOf("uri","perfil","geracao","ativa","tentativa_ms","sucesso_ms","estado","adicionados","atualizados","ignorados"))
            require(s["uri"]!!.jsonPrimitive.isString && s["uri"]!!.jsonPrimitive.content.startsWith("content://"))
            require(s["perfil"]!!.jsonPrimitive.content.isNotBlank() && s["perfil"]!!.jsonPrimitive.content.length<=100)
            require(s["geracao"]!!.jsonPrimitive.content.length in 20..100)
            require(s["ativa"] in listOf(JsonPrimitive(true),JsonPrimitive(false)))
            for(k in listOf("tentativa_ms","sucesso_ms","adicionados","atualizados","ignorados")) require(!s[k]!!.jsonPrimitive.isString && s[k]!!.jsonPrimitive.long in 0L..9007199254740991L)
            require(s["estado"]!!.jsonPrimitive.content in setOf("atualizada","desconectada","arquivo_invalido","arquivo_indisponivel","permissao_revogada","limite_atingido"))
        }
    }
    private fun validarChat(c: JsonElement) {
        if(c==JsonNull) return
        val obj=c.jsonObject
        require(obj["schema_version"]==JsonPrimitive(1) && obj["messages"]!!.jsonArray.size<=80 && obj["drafts"]!!.jsonArray.size<=20 && obj["links"]!!.jsonArray.size<=30)
        require(obj["cloudConsent"] in listOf(JsonPrimitive(true),JsonPrimitive(false)))
        require(obj["requests"]!!.jsonPrimitive.int in 0..1000000 && !obj["requests"]!!.jsonPrimitive.isString)
        require(obj["separate"]!!.jsonArray.all { it.jsonPrimitive.isString })
        obj["drafts"]!!.jsonArray.forEach { val d=it.jsonObject
            require(d["id"]!!.jsonPrimitive.isString && d["tipo"]!!.jsonPrimitive.isString && d["campos"] is JsonObject && d["porque"]!!.jsonPrimitive.isString && d["acao"] in listOf(JsonPrimitive("criar"),JsonPrimitive("atualizar")))
        }
        obj["handledTurn"]?.let { require(it.jsonPrimitive.isString && it.jsonPrimitive.content.length<=5000) }
        obj["agentQuestion"]?.takeUnless { it==JsonNull }?.jsonObject?.let { q ->
            require(q["index"]!!.jsonPrimitive.int in 0 until obj["drafts"]!!.jsonArray.size && q["field"]!!.jsonPrimitive.isString)
            q["text"]?.let { require(it.jsonPrimitive.isString && it.jsonPrimitive.content.length<=5000) }
        }
        obj["messages"]!!.jsonArray.forEach { val m=it.jsonObject
            require(m["role"] in listOf(JsonPrimitive("usuario"),JsonPrimitive("assistente")) && m["text"]!!.jsonPrimitive.isString && m["text"]!!.jsonPrimitive.content.length<=5000)
        }
    }
    private fun gravar(b: JsonObject) {
        validar(b);val bytes=b.toString().encodeToByteArray();require(bytes.size<=MAX_BYTES)
        val stream=file.startWrite()
        try { stream.write(bytes);file.finishWrite(stream) } catch(e:Exception) { file.failWrite(stream);throw e }
    }
    private fun inc(b: JsonObject,k: String) = (b[k]!!.jsonPrimitive.long+1).also { require(it<=9007199254740991L) }
    private fun publico(b: JsonObject) = buildJsonObject {
        for(k in listOf("revisao","revisao_bundle","revisao_chat","bundle","chat")) put(k,b[k]!!)
        put("deposito",guardaAndroid("estado"));put("librera",statusFonte(b))
    }
    fun snapshot(): JsonObject = synchronized(LOCK) { publico(ler()) }
    fun bundle(): JsonObject = synchronized(LOCK) { ler()["bundle"]!!.jsonObject }
    fun inicializar(bundle: JsonObject, chat: JsonElement): JsonObject = synchronized(LOCK) {
        if(existe()) return@synchronized publico(ler())
        val b=buildJsonObject { put("schema_version",1);put("revisao",1);put("revisao_bundle",1);put("revisao_chat",1);put("revisao_fonte",1);put("bundle",bundle);put("chat",chat);put("fonte_librera",JsonNull);put("excluidos_librera",JsonArray(emptyList())) }
        gravar(b);publico(b)
    }
    fun escrever(revisao: Long, key: String, value: JsonElement): JsonObject = synchronized(LOCK) {
        require(key in listOf("bundle","chat"));val b=ler();val rk="revisao_$key"
        check(b[rk]!!.jsonPrimitive.long==revisao) { "revisão mudou" }
        if(value==b[key]) return@synchronized publico(b)
        val next=b.toMutableMap();next[key]=value;next[rk]=JsonPrimitive(inc(b,rk));next["revisao"]=JsonPrimitive(inc(b,"revisao"))
        if(key=="bundle") {
            fun refs(v: JsonElement) = v.jsonObject["leitura"]!!.jsonObject["livros"]!!.jsonArray.map { it.jsonObject }.filter { it["fonte"]==JsonPrimitive("librera") && (it["chave"] as? JsonPrimitive)?.isString==true }.map { buildJsonArray { add(it["perfil"]!!);add(it["chave"]!!) } }.toSet()
            val before=refs(b["bundle"]!!);val after=refs(value)
            val excluded=(b["excluidos_librera"]!!.jsonArray.toSet()+(before-after))-after
            next["excluidos_librera"]=JsonArray(excluded.toList())
        }
        val updated=JsonObject(next);gravar(updated);publico(updated)
    }
    fun tokenFonte(): Long = synchronized(LOCK) { ler()["revisao_fonte"]!!.jsonPrimitive.long }
    fun fonte(): JsonObject? = synchronized(LOCK) { if(!existe()) null else ler()["fonte_librera"]?.takeUnless { it==JsonNull }?.jsonObject }
    private fun statusFonte(b: JsonObject): JsonObject = buildJsonObject {
        val s=b["fonte_librera"]?.takeUnless { it==JsonNull }?.jsonObject
        put("conectada",s?.get("ativa")==JsonPrimitive(true))
        for(k in listOf("perfil","tentativa_ms","sucesso_ms","estado","adicionados","atualizados","ignorados")) put(k,s?.get(k) ?: JsonNull)
    }
    fun statusLibrera(): JsonObject = synchronized(LOCK) { statusFonte(ler()) }
    fun conectar(uri: String, perfil: String, raw: JsonElement, now: Long, zone: String, expectedToken: Long = tokenFonte()): JsonObject = synchronized(LOCK) {
        require(uri.startsWith("content://") && perfil.isNotBlank() && perfil.length<=100)
        val b=ler();check(b["revisao_fonte"]!!.jsonPrimitive.long==expectedToken) { "fonte mudou" };val source=buildJsonObject {
            put("uri",uri);put("perfil",perfil.trim());put("geracao",UUID.randomUUID().toString());put("ativa",true)
            put("tentativa_ms",now);put("sucesso_ms",now);put("estado","atualizada");put("adicionados",0);put("atualizados",0);put("ignorados",0)
        }
        // Um arquivo sem posições utilizáveis não substitui uma fonte válida.
        val count=com.fintips.motor.vida.posicoesLibrera(raw)["posicoes"]!!.jsonArray.count { it.jsonObject["tempo_ms"]!!.jsonPrimitive.long<=now }
        require(count>0)
        atualizar(JsonObject(b+("revisao_fonte" to JsonPrimitive(inc(b,"revisao_fonte")))),source,raw,now,zone)
        statusLibrera()
    }
    private fun atualizar(b: JsonObject, source: JsonObject, raw: JsonElement, now: Long, zone: String) {
        val old=b["bundle"]!!.jsonObject
        val result=importarLibrera(old["leitura"]!!.jsonObject,raw,source["perfil"]!!.jsonPrimitive.content,now,zone,b["excluidos_librera"]!!.jsonArray)
        val bundle=JsonObject(old+("leitura" to result["leitura"]!!))
        val state=JsonObject(b+mapOf("bundle" to bundle,"revisao" to JsonPrimitive(inc(b,"revisao")),"revisao_bundle" to (if(bundle==old) b["revisao_bundle"]!! else JsonPrimitive(inc(b,"revisao_bundle"))),"fonte_librera" to JsonObject(source+mapOf("tentativa_ms" to JsonPrimitive(now),"sucesso_ms" to JsonPrimitive(now),"estado" to JsonPrimitive("atualizada"),"adicionados" to result["adicionados"]!!,"atualizados" to result["atualizados"]!!,"ignorados" to result["ignorados"]!!))))
        gravar(state)
    }
    fun atualizarFonte(geracao: String, raw: JsonElement, now: Long, zone: String, cancelado: ()->Boolean = { false }): Boolean = synchronized(LOCK) {
        val b=ler();val s=b["fonte_librera"]?.takeUnless { it==JsonNull }?.jsonObject ?: return@synchronized false
        if(cancelado() || s["ativa"]!=JsonPrimitive(true) || s["geracao"]!=JsonPrimitive(geracao)) return@synchronized false
        atualizar(b,s,raw,now,zone);true
    }
    fun falhaFonte(geracao: String, code: String, now: Long) = synchronized(LOCK) {
        require(code in setOf("permissao_revogada","arquivo_indisponivel","arquivo_invalido","limite_atingido"))
        val b=ler();val s=b["fonte_librera"]?.takeUnless { it==JsonNull }?.jsonObject ?: return@synchronized
        if(s["ativa"]!=JsonPrimitive(true) || s["geracao"]!=JsonPrimitive(geracao)) return@synchronized
        gravar(JsonObject(b+mapOf("revisao" to JsonPrimitive(inc(b,"revisao")),"fonte_librera" to JsonObject(s+mapOf("tentativa_ms" to JsonPrimitive(now),"estado" to JsonPrimitive(code))))))
    }
    fun desconectar(): String? = synchronized(LOCK) {
        val b=ler();val s=b["fonte_librera"]?.takeUnless { it==JsonNull }?.jsonObject
        val source=s?.let { JsonObject(it+mapOf("ativa" to JsonPrimitive(false),"geracao" to JsonPrimitive(UUID.randomUUID().toString()),"estado" to JsonPrimitive("desconectada"))) } ?: JsonNull
        gravar(JsonObject(b+mapOf("revisao" to JsonPrimitive(inc(b,"revisao")),"revisao_fonte" to JsonPrimitive(inc(b,"revisao_fonte")),"fonte_librera" to source)))
        s?.get("uri")?.jsonPrimitive?.content
    }
    fun copia(): String = synchronized(LOCK) {
        runCatching { ler().toString() }.getOrElse {
            val bytes=file.openRead().use { input -> val out=java.io.ByteArrayOutputStream();val b=ByteArray(8192);while(true) { val n=input.read(b);if(n<0) break;require(out.size()+n<=MAX_BYTES);out.write(b,0,n) };out.toByteArray() }
            buildJsonObject { put("tipo","fintips_estado_recuperacao");put("schema_version",1);put("bytes_base64",android.util.Base64.encodeToString(bytes,android.util.Base64.NO_WRAP)) }.toString()
        }
    }
    companion object { private val LOCK=Any();private const val MAX_BYTES=8*1024*1024 }
}
