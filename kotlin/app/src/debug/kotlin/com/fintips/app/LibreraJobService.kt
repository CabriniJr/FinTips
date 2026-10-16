package com.fintips.app

import android.app.job.JobParameters
import android.app.job.JobService
import android.os.CancellationSignal
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/** Job persistente, sem WebView, API de IA ou serviço contínuo. */
class LibreraJobService : JobService() {
    private val executor=Executors.newSingleThreadExecutor()
    private var signal: CancellationSignal?=null
    private var stopped=AtomicBoolean(false)
    override fun onStartJob(params: JobParameters): Boolean {
        val cancel=CancellationSignal();val stop=AtomicBoolean(false);signal=cancel;stopped=stop
        executor.execute {
            try { LibreraFonte(applicationContext).sincronizar(cancel) { stop.get() } }
            catch(_:Exception) { /* Guarda ilegível não é reiniciada. A UI oferece recuperação. */ }
            finally { if(!stop.get()) jobFinished(params,false) }
        }
        return true
    }
    override fun onStopJob(params: JobParameters): Boolean { stopped.set(true);signal?.cancel();return true }
    override fun onDestroy() { stopped.set(true);signal?.cancel();executor.shutdownNow();super.onDestroy() }
}
