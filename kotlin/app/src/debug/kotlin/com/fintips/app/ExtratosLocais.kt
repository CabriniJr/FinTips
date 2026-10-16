package com.fintips.app

import android.content.Context
import android.util.AtomicFile
import com.fintips.motor.Dinheiro
import com.fintips.motor.ofx.lerOfx
import com.fintips.motor.importacao.contextoExtratos
import com.fintips.motor.importacao.contextosExtratos
import com.fintips.motor.importacao.temSaldoDeclarado
import kotlinx.serialization.json.*
import java.io.File
import java.security.MessageDigest
import java.util.UUID

/** Autoridade financeira desta preview: arquivo privado nativo, sem cópia no WebView.
 * Schema inicial 1. Sem migração de histórico: o conferidor anterior não gravava fontes.
 * Backup Android é desabilitado e noBackupFilesDir também exclui esta fonte da nuvem.
 */
internal class ExtratosLocais(context: Context, nome: String = NOME_ARQUIVO) {
    private val file = AtomicFile(File(context.noBackupFilesDir, nome))
    private fun ler(): JsonObject {
        if(!file.baseFile.exists() && !File(file.baseFile.path+".bak").exists()) return buildJsonObject {
            put("schema_version",1);put("sal",UUID.randomUUID().toString());put("arquivos",JsonArray(emptyList()))
        }
        val bytes=file.openRead().use { it.readBytesLimited() }
        return Json.parseToJsonElement(bytes.decodeToString()).jsonObject.also {
            require(it.keys==setOf("schema_version","sal","arquivos") && it["schema_version"]==JsonPrimitive(1))
            require(it["sal"]!!.jsonPrimitive.isString && it["sal"]!!.jsonPrimitive.content.length in 20..100)
            require(it["arquivos"]!!.jsonArray.size<=20)
        }
    }
    private fun java.io.InputStream.readBytesLimited(): ByteArray {
        val output=java.io.ByteArrayOutputStream();val buffer=ByteArray(8192)
        while(true) { val n=read(buffer);if(n<0) break;require(output.size()+n<=MAX_BYTES);output.write(buffer,0,n) }
        return output.toByteArray()
    }
    private fun resumo(b: JsonObject)=contextoExtratos(b["arquivos"]!!.jsonArray,b["sal"]!!.jsonPrimitive.content)
    private fun gravar(b: JsonObject) {
        resumo(b) // valida tudo antes de iniciar a única mutação, inclusive limites/somas.
        val bytes=b.toString().toByteArray(Charsets.UTF_8);require(bytes.size<=MAX_BYTES)
        val stream=file.startWrite()
        try { stream.write(bytes);file.finishWrite(stream) } catch(e:Exception) { file.failWrite(stream);throw e }
    }
    private fun estado(b: JsonObject): JsonObject = buildJsonObject {
        val (contexto, fluxos) = contextosExtratos(b["arquivos"]!!.jsonArray,b["sal"]!!.jsonPrimitive.content)
        put("fluxos", fluxos)
        putJsonObject("deposito") { put("arquivo",file.baseFile.name);put("schema_version",1);put("sensivel",true);put("guarda","privada_nativa_sem_backup_nuvem") };put("contexto",contexto);putJsonArray("fontes") { b["arquivos"]!!.jsonArray.forEach { entry ->
            val f=entry.jsonObject;val e=lerOfx(f["ofx"]!!.jsonPrimitive.content,b["sal"]!!.jsonPrimitive.content)
            val abertura=f["saldo_inicial"]?.takeUnless { it==JsonNull }?.jsonPrimitive?.content
            val temSaldo=temSaldoDeclarado(f["ofx"]!!.jsonPrimitive.content)
            val c=abertura?.takeIf { temSaldo }?.let { e.concilia(Dinheiro.de(it)) }
            addJsonObject {
                put("ref",f["ref"]!!);put("importado_em",f["importado_em"]!!)
                put("inicio",e.periodoInicio.toString());put("fim",e.periodoFim.toString());put("transacoes",e.transacoes.size)
                put("saldo_centavos",if(temSaldo) JsonPrimitive(e.saldoDeclarado.centavos) else JsonNull)
                put("conciliacao",if(c==null) "nao_conferido" else if(c.bate) "conferido" else "divergente")
                put("diferenca_centavos",c?.diferenca?.centavos?.let { JsonPrimitive(it) } ?: JsonNull)
            }
        } }
    }
    fun estado(): JsonObject = synchronized(LOCK) { estado(ler()) }
    fun contextos(): Pair<JsonObject,JsonObject> = synchronized(LOCK) { val b=ler();contextosExtratos(b["arquivos"]!!.jsonArray,b["sal"]!!.jsonPrimitive.content) }
    fun fluxos(): JsonObject = contextos().second
    fun contexto(): JsonObject = synchronized(LOCK) { resumo(ler()) }
    fun importar(raw: String, abertura: String?): JsonObject = synchronized(LOCK) {
        require(raw.encodeToByteArray().size<=1024*1024)
        val b=ler();val anteriores=b["arquivos"]!!.jsonArray
        val hash=MessageDigest.getInstance("SHA-256").digest((b["sal"]!!.jsonPrimitive.content+raw).toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
        val ref="fonte_$hash";val index=anteriores.indexOfFirst { it.jsonObject["ref"]==JsonPrimitive(ref) }
        val antes=resumo(b)["transacoes"]!!.jsonPrimitive.int
        val entry=buildJsonObject {
            put("ref",ref);put("ofx",raw)
            put("importado_em",if(index<0) JsonPrimitive(System.currentTimeMillis()) else anteriores[index].jsonObject["importado_em"]!!)
            put("saldo_inicial",abertura?.let { JsonPrimitive(it) } ?: if(index<0) JsonNull else anteriores[index].jsonObject["saldo_inicial"]!!)
        }
        val next=JsonObject(b+ ("arquivos" to JsonArray(if(index<0) anteriores+entry else anteriores.mapIndexed { n,e -> if(n==index) entry else e })))
        gravar(next)
        JsonObject(estado(next)+mapOf("duplicado" to JsonPrimitive(index>=0),"novas_transacoes" to JsonPrimitive(resumo(next)["transacoes"]!!.jsonPrimitive.int-antes)))
    }
    fun remover(ref: String): JsonObject = synchronized(LOCK) {
        require(Regex("^fonte_[0-9a-f]{64}$").matches(ref))
        val b=ler();val items=b["arquivos"]!!.jsonArray;require(items.any { it.jsonObject["ref"]==JsonPrimitive(ref) })
        val next=JsonObject(b+("arquivos" to JsonArray(items.filterNot { it.jsonObject["ref"]==JsonPrimitive(ref) })))
        gravar(next);estado(next)
    }
    fun copia(): String = synchronized(LOCK) {
        runCatching {
            val b=ler();resumo(b)
            buildJsonObject { put("tipo","fintips_extratos_locais");put("schema_version",1);put("arquivo",b) }.toString()
        }.getOrElse {
            // Leitura ilegível nunca vira arquivo vazio: exporta bytes para recuperação.
            val bytes=file.openRead().use { it.readBytesLimited() }
            buildJsonObject { put("tipo","fintips_extratos_recuperacao");put("schema_version",1);put("arquivo_base64",android.util.Base64.encodeToString(bytes,android.util.Base64.NO_WRAP)) }.toString()
        }
    }
    companion object { const val NOME_ARQUIVO="extratos-v1.json";private val LOCK=Any();private const val MAX_BYTES=16*1024*1024 }
}
