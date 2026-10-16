package com.fintips.app

import android.content.Context
import android.content.Intent
import android.app.job.JobScheduler
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class LibreraAndroidTest {
    private val context get()=InstrumentationRegistry.getInstrumentation().targetContext.also { check(it.packageName=="com.fintips.app.ci") }
    private fun emptyBundle()=Json.parseToJsonElement("""{"schema_version":1,"vida":{"schema_version":1,"tarefas":[],"registros":[],"planos":[],"medidas":[]},"leitura":{"schema_version":1,"livros":[]},"caderno":{"schema_version":1,"assets":[],"relacoes":[],"aplicacoes":[]}}""").jsonObject
    private fun raw(p: Double,t: Long)=buildJsonObject { putJsonObject("Livro Sintético.epub") { put("p",p);put("t",t);put("pt","PAGE_CONTENT_CANARY");put("path","PATH_CANARY") } }
    private fun books(b: JsonObject)=b["bundle"]!!.jsonObject["leitura"]!!.jsonObject["livros"]!!.jsonArray
    private fun clean(f: File) { f.delete();File(f.path+".bak").delete();File(f.path+".new").delete() }

    @Test fun guarda_atomica_rejeita_concorrencia_preserva_remocao_e_nao_reinicia_corrupcao() {
        val name="estado-test-${UUID.randomUUID()}.json";val file=File(context.noBackupFilesDir,name)
        try {
            val repo=EstadoCliente(context,name);val before=repo.inicializar(emptyBundle(),JsonNull)
            assertEquals(before,EstadoCliente(context,name).snapshot())
            val now=System.currentTimeMillis();repo.conectar("content://synthetic/progress","principal",raw(.25,now-1000),now,"UTC")
            val updated=repo.snapshot();assertEquals(1,books(updated).size)
            val bytes=file.readBytes()
            try { repo.escrever(before["revisao_bundle"]!!.jsonPrimitive.long,"bundle",emptyBundle());fail("edição obsoleta aceita") } catch(_:IllegalStateException) {}
            assertArrayEquals(bytes,file.readBytes())
            val removed=repo.escrever(updated["revisao_bundle"]!!.jsonPrimitive.long,"bundle",emptyBundle())
            val gen=repo.fonte()!!["geracao"]!!.jsonPrimitive.content
            repo.atualizarFonte(gen,raw(.5,now),now,"UTC")
            assertTrue(books(repo.snapshot()).isEmpty()) // remoção não vira livro ressuscitado.
            val b=file.readBytes();assertFalse(repo.atualizarFonte(gen,raw(.8,now),now,"UTC") { true });assertArrayEquals(b,file.readBytes())
            val pendingToken=repo.tokenFonte()
            repo.desconectar();assertFalse(repo.atualizarFonte(gen,raw(.9,now),now,"UTC"))
            try { repo.conectar("content://synthetic/progress","principal",raw(.9,now),now,"UTC",pendingToken);fail("reativou seleção cancelada") } catch(_:IllegalStateException) {}
            assertEquals(JsonPrimitive(false),repo.statusLibrera()["conectada"])
            assertFalse(repo.snapshot().toString().contains("PAGE_CONTENT_CANARY"))
            file.writeText("corrompido")
            try { repo.inicializar(emptyBundle(),JsonNull);fail("reiniciou guarda ilegível") } catch(_:Exception) {}
            assertEquals("corrompido",file.readText());assertTrue(repo.copia().contains("fintips_estado_recuperacao"))
        } finally { clean(file) }
    }

    @Test fun uri_persistente_e_job_real_atualizam_registro_sem_webview_e_revogacao_preserva_historico() {
        val c=context;val file=File(c.noBackupFilesDir,guardaAndroid("estado")["arquivo"]!!.jsonPrimitive.content)
        val original=if(file.exists()) file.readBytes() else null
        val scheduler=c.getSystemService(Context.JOB_SCHEDULER_SERVICE) as JobScheduler
        val uri=LibreraTestProvider.URI;val now=System.currentTimeMillis()
        try {
            clean(file)
            val repo=EstadoCliente(c);repo.inicializar(emptyBundle(),JsonNull)
            c.contentResolver.call(uri,"set",raw(.2,now-2000).toString(),null)
            c.contentResolver.call(uri,"grant",null,null)
            c.contentResolver.takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION)
            val source=LibreraFonte(c,repo);val status=source.conectar(uri,"principal")
            assertEquals(JsonPrimitive(true),status["agendada"])
            val job=scheduler.getPendingJob(LibreraFonte.JOB_ID)!!
            assertTrue(job.isPersisted);assertEquals(15*60*1000L,job.intervalMillis)
            assertEquals(1,books(EstadoCliente(c).snapshot()).size)
            c.contentResolver.call(uri,"set",raw(.45,now-1000).toString(),null)
            android.os.ParcelFileDescriptor.AutoCloseInputStream(InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommand("cmd jobscheduler run -f com.fintips.app.ci ${LibreraFonte.JOB_ID}")).use { it.readBytes() }
            val until=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(30)
            var advanced=false
            while(System.nanoTime()<until) {
                val last=books(repo.snapshot()).single().jsonObject["observacoes"]!!.jsonArray.last().jsonObject
                if(last["progresso_bp"]==JsonPrimitive(4500)) { advanced=true;break }
                Thread.sleep(100)
            }
            assertTrue("Job não atualizou a guarda canônica",advanced)
            val canonical=repo.bundle()
            c.contentResolver.call(uri,"set","invalid-json",null);source.sincronizar()
            assertEquals(canonical,repo.bundle());assertEquals(JsonPrimitive("arquivo_invalido"),source.status()["estado"])
            c.contentResolver.releasePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);source.sincronizar()
            assertEquals(canonical,repo.bundle());assertEquals(JsonPrimitive("permissao_revogada"),source.status()["estado"])
            val staleSelection=repo.tokenFonte()
            source.desconectar();assertNull(scheduler.getPendingJob(LibreraFonte.JOB_ID));assertEquals(canonical,repo.bundle())
            c.contentResolver.call(uri,"set",raw(.6,now).toString(),null)
            c.contentResolver.call(uri,"grant",null,null)
            c.contentResolver.takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION)
            try { source.conectar(uri,"outro_perfil",expectedToken=staleSelection);fail("reativou seleção obsoleta") } catch(_:IllegalStateException) {}
            assertEquals(JsonPrimitive(false),source.status()["conectada"]);assertEquals(canonical,repo.bundle())
        } finally {
            scheduler.cancel(LibreraFonte.JOB_ID)
            runCatching { EstadoCliente(c).desconectar() }
            runCatching { c.contentResolver.releasePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION) }
            clean(file);if(original!=null) file.writeBytes(original)
        }
    }
    private fun eval(s: androidx.test.core.app.ActivityScenario<PreviewActivity>, js: String): String {
        val done=java.util.concurrent.CountDownLatch(1);var result="null"
        s.onActivity { a ->
            val web=a.findViewById<android.view.ViewGroup>(android.R.id.content).getChildAt(0) as android.webkit.WebView
            web.evaluateJavascript(js) { result=it;done.countDown() }
        }
        check(done.await(30,java.util.concurrent.TimeUnit.SECONDS));return result
    }
    private fun waitJs(s: androidx.test.core.app.ActivityScenario<PreviewActivity>, js: String) {
        val end=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(30)
        while(System.nanoTime()<end) { if(eval(s,js)=="true") return;Thread.sleep(100) }
        error("A UI não confirmou a migração/atualização")
    }
    @Test fun webview_migra_legado_sem_apagar_e_le_atualizacao_nativa_do_livro() {
        val c=context;val file=File(c.noBackupFilesDir,guardaAndroid("estado")["arquivo"]!!.jsonPrimitive.content)
        val original=if(file.exists()) file.readBytes() else null
        var scene: androidx.test.core.app.ActivityScenario<PreviewActivity>?=null
        var legacy: String?=null;var legacyRead=false
        try {
            clean(file)
            scene=androidx.test.core.app.ActivityScenario.launch(PreviewActivity::class.java)
            waitJs(scene,"document.readyState==='complete' && typeof FinTipsState!=='undefined' && document.querySelector('.bottom-nav')!==null")
            val old=Json.parseToJsonElement(eval(scene,"localStorage.getItem('fintips.client.v1')"));legacy=if(old==JsonNull) null else old.jsonPrimitive.content;legacyRead=true
            val bundle=emptyBundle();val life=bundle["vida"]!!.jsonObject
            val plan=Json.parseToJsonElement("""{"id":"plan_synthetic","titulo":"Plano sintético","atributo":"INT","porque":"Escolha sintética","proximoPasso":"Próximo passo sintético","prazo":"","concluido":false}""")
            val seed=JsonObject(bundle+("vida" to JsonObject(life+("planos" to JsonArray(listOf(plan))))))
            eval(scene,"localStorage.setItem('fintips.client.v1',${org.json.JSONObject.quote(seed.toString())})")
            scene.close();scene=null;clean(file)
            scene=androidx.test.core.app.ActivityScenario.launch(PreviewActivity::class.java)
            waitJs(scene,"document.readyState==='complete' && document.querySelector('.bottom-nav')!==null")
            assertEquals(seed,EstadoCliente(c).bundle())
            val now=System.currentTimeMillis()
            EstadoCliente(c).conectar("content://synthetic/progress","principal",raw(.25,now-1000),now,"UTC")
            eval(scene,"dispatchEvent(new Event('fintips:librera-updated'));location.hash='vida/INT'")
            waitJs(scene,"document.body.innerText.includes('Livro Sintético') && document.body.innerText.includes('25%')")
            assertEquals(JsonPrimitive(seed.toString()),Json.parseToJsonElement(eval(scene,"localStorage.getItem('fintips.client.v1')")))
        } finally {
            if(scene!=null && legacyRead) runCatching { eval(scene,if(legacy==null) "localStorage.removeItem('fintips.client.v1')" else "localStorage.setItem('fintips.client.v1',${org.json.JSONObject.quote(legacy)})") }
            scene?.close();(c.getSystemService(Context.JOB_SCHEDULER_SERVICE) as JobScheduler).cancel(LibreraFonte.JOB_ID)
            clean(file);if(original!=null) file.writeBytes(original)
        }
    }

}
