package com.fintips.app

import android.app.job.JobInfo
import android.app.job.JobScheduler
import android.content.ComponentName
import android.content.Context
import android.net.Uri
import android.os.CancellationSignal
import kotlinx.serialization.json.*
import java.time.ZoneId

/** SAF: lê apenas o documento explicitamente escolhido; nenhum upload ou crawl. */
internal class LibreraFonte(private val context: Context, private val estado: EstadoCliente = EstadoCliente(context)) {
    private val scheduler get()=context.getSystemService(Context.JOB_SCHEDULER_SERVICE) as JobScheduler
    fun agendar(): Boolean {
        if(estado.fonte()?.get("ativa")!=JsonPrimitive(true)) return false
        val job=JobInfo.Builder(JOB_ID,ComponentName(context,LibreraJobService::class.java))
            .setPeriodic(15*60*1000L).setPersisted(true).build()
        return scheduler.schedule(job)==JobScheduler.RESULT_SUCCESS
    }
    fun status(): JsonObject = JsonObject(estado.statusLibrera()+mapOf("agendada" to JsonPrimitive(scheduler.getPendingJob(JOB_ID)!=null),"intervalo_minutos" to JsonPrimitive(15)))
    fun ler(uri: Uri, signal: CancellationSignal = CancellationSignal()): JsonElement {
        require(uri.scheme=="content")
        if(!context.contentResolver.persistedUriPermissions.any { it.uri==uri && it.isReadPermission }) throw SecurityException("permissão persistente indisponível")
        val bytes=context.contentResolver.openAssetFileDescriptor(uri,"r",signal)?.use { asset ->
            asset.createInputStream().use { input ->
                val out=java.io.ByteArrayOutputStream();val buffer=ByteArray(8192)
                while(true) { signal.throwIfCanceled();val n=input.read(buffer);if(n<0) break;require(out.size()+n<=MAX_BYTES);out.write(buffer,0,n) };out.toByteArray()
            }
        } ?: error("documento indisponível")
        return Json.parseToJsonElement(bytes.decodeToString())
    }
    fun conectar(uri: Uri, profile: String, signal: CancellationSignal = CancellationSignal()): JsonObject {
        val expectedToken=estado.tokenFonte()
        val previous=estado.fonte()?.get("uri")?.jsonPrimitive?.content
        val raw=ler(uri,signal)
        signal.throwIfCanceled()
        estado.conectar(uri.toString(),profile,raw,System.currentTimeMillis(),ZoneId.systemDefault().id,expectedToken)
        runCatching { McpLocalService.atualizarDaGuarda(context) }
        val scheduled=agendar()
        if(previous!=null && previous!=uri.toString()) liberar(Uri.parse(previous))
        return JsonObject(status()+mapOf("agendada" to JsonPrimitive(scheduled)))
    }
    fun sincronizar(signal: CancellationSignal=CancellationSignal(), cancelled: ()->Boolean = {false}): JsonObject {
        val s=estado.fonte() ?: return status()
        if(s["ativa"]!=JsonPrimitive(true)) return status()
        val gen=s["geracao"]!!.jsonPrimitive.content
        try {
            val raw=ler(Uri.parse(s["uri"]!!.jsonPrimitive.content),signal)
            signal.throwIfCanceled()
            estado.atualizarFonte(gen,raw,System.currentTimeMillis(),ZoneId.systemDefault().id,cancelled)
        } catch(e: Exception) {
            if(!cancelled() && !signal.isCanceled) {
                val code=when(e) { is SecurityException -> "permissao_revogada";is java.io.IOException -> "arquivo_indisponivel";else -> "arquivo_invalido" }
                estado.falhaFonte(gen,code,System.currentTimeMillis())
            }
        }
        runCatching { McpLocalService.atualizarDaGuarda(context) }
        return status()
    }
    fun desconectar(): JsonObject {
        val uri=estado.desconectar();scheduler.cancel(JOB_ID)
        uri?.let { liberar(Uri.parse(it)) }
        return status()
    }
    private fun liberar(uri: Uri) { runCatching { context.contentResolver.releasePersistableUriPermission(uri,android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION) } }
    companion object { const val JOB_ID=0x46544c;private const val MAX_BYTES=2*1024*1024 }
}
