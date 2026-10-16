package com.fintips.app

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.*
import com.fintips.mcp.SessaoLocal
import com.fintips.mcp.PonteRemota
import com.fintips.mcp.FalhaPonte
import kotlinx.serialization.json.*
import org.json.JSONObject
import java.util.concurrent.Executors

/** Sessão iniciada pela pessoa. Nenhum boot receiver, arquivo ou restart sticky. */
class McpLocalService : Service() {
    private val host = SessaoLocal(SystemClock::elapsedRealtimeNanos)
    private val io = Executors.newSingleThreadExecutor()
    @Volatile private var destroyed = false
    private var ponte: PonteRemota? = null
    private var ponteGeneration = 0L

    override fun onCreate() {
        super.onCreate()
        current = this
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL, "Servidor MCP local", NotificationManager.IMPORTANCE_LOW))
    }

    @Suppress("DEPRECATION")
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val reply = intent?.getParcelableExtra<ResultReceiver>("reply")
        if (intent?.action == STOP) {
            stopServer()
            reply?.send(0, Bundle().apply { putString("json", stopped().toString()) })
            return START_NOT_STICKY
        }
        if (intent?.action != START) { stopServer(); return START_NOT_STICKY }
        try {
            val n = notification("Preparando servidor local…")
            if (Build.VERSION.SDK_INT >= 34) startForeground(NOTIFICATION, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
            else startForeground(NOTIFICATION, n)
            val raw = intent.getStringExtra("context") ?: error("contexto ausente")
            require(raw.toByteArray(Charsets.UTF_8).size <= 4096)
            io.execute {
                var etapa = CodigoMcp.CONTEXTO
                try {
                    val c = Json.parseToJsonElement(MotorBridge.validateContext(raw)).jsonObject
                    check(!destroyed)
                    etapa = CodigoMcp.SOCKET
                    val started = host.iniciar(c)
                    etapa = CodigoMcp.TESTE
                    host.verificar(started["sessao"]!!.jsonPrimitive.content)
                    notifyRunning()
                    reply?.send(0, Bundle().apply { putString("json", state().toString()) })
                } catch (_: Exception) {
                    reply?.send(1, Bundle().apply { putString("erro", etapa.name) })
                    if (etapa == CodigoMcp.TESTE || !host.ativo()) stopServer()
                    else notifyRunning()
                }
            }
        } catch (_: Exception) {
            reply?.send(1, Bundle().apply { putString("erro", CodigoMcp.ANDROID.name) })
            if (!host.ativo()) stopServer()
        }
        return START_NOT_STICKY
    }

    private fun state() = JSONObject(host.estado().toString())

    @Synchronized private fun stopServer() {
        // Fecha a geração imediatamente: um início já enfileirado não pode
        // reabrir o socket entre stopSelf() e onDestroy().
        host.close()
        closePonte()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    @Synchronized private fun notifyRunning() {
        val manager = getSystemService(NotificationManager::class.java)
        if (!destroyed && host.ativo() && manager.areNotificationsEnabled())
            manager.notify(NOTIFICATION, notification(if (ponte != null) "Servidor local · ponte IA ativada" else "MCP ativo somente neste aparelho"))
    }

    private fun notification(text: String): Notification {
        val open = PendingIntent.getActivity(this, 0,
            Intent(this, PreviewActivity::class.java).putExtra("abrir_ia", true).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1, Intent(this, McpLocalService::class.java).setAction(STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, CHANNEL).setSmallIcon(R.drawable.ic_mcp_local)
            .setContentTitle("FinTips · servidor local").setContentText(text).setOngoing(true)
            .setContentIntent(open).addAction(Notification.Action.Builder(null, "Encerrar", stop).build()).build()
    }

    override fun onBind(intent: Intent?): IBinder? = null
    @Synchronized override fun onDestroy() {
        destroyed = true
        host.close()
        closePonte()
        if (current === this) current = null
        io.shutdownNow()
        super.onDestroy()
    }

    @Synchronized private fun closePonte() {
        ponteGeneration++
        ponte?.close(); ponte = null
    }
    @Synchronized private fun ponteState(): JSONObject = JSONObject(ponte?.estado()?.toString() ?: "{\"ativo\":false,\"estado\":\"encerrado\",\"autorizacoes\":[]}")
    private fun startPonte(origin: String, invite: String): JSONObject {
        val generation = synchronized(this) {
            check(!destroyed && host.ativo() && ponte == null)
            ++ponteGeneration
        }
        val client = PonteRemota.criar(origin, invite, host::contextoPara, host::podeEnviar)
        synchronized(this) {
            if (destroyed || current !== this || !host.ativo() || generation != ponteGeneration) {
                client.close(); throw FalhaPonte("SESSAO_ENCERRADA")
            }
            ponte = client
        }
        notifyRunning()
        return ponteState()
    }
    private fun bridge(): PonteRemota = synchronized(this) { ponte ?: throw FalhaPonte("PONTE_INDISPONIVEL") }
    private fun bridgeOperation(op: String, input: JSONObject): JSONObject = when (op) {
        "ponte.status" -> ponteState()
        "ponte.iniciar" -> startPonte(input.getString("origem"), input.getString("convite"))
        "ponte.encerrar" -> { closePonte(); notifyRunning(); ponteState() }
        "ponte.consultar" -> JSONObject(bridge().consultarCodigo(input.getString("codigo")).toString())
        "ponte.autorizar" -> {
            val context = Json.parseToJsonElement(MotorBridge.validateContext(input.getJSONObject("context").toString())).jsonObject
            val scopes = context.keys - "schema_version"
            // Exige fonte e consentimento locais válidos; não envia o JSON revisado.
            host.contextoPara(scopes)
            JSONObject(bridge().autorizar(input.getString("codigo"), scopes, input.getString("provedor")).toString())
        }
        "ponte.negar" -> JSONObject(bridge().negar(input.getString("codigo")).toString())
        "ponte.revogar" -> JSONObject(bridge().revogar(input.getString("id")).toString())
        else -> throw FalhaPonte("ACAO_INVALIDA")
    }

    companion object {
        const val START = "com.fintips.app.MCP_START"
        const val STOP = "com.fintips.app.MCP_STOP"
        private const val CHANNEL = "fintips-mcp-local"
        private const val NOTIFICATION = 6501
        @Volatile private var current: McpLocalService? = null
        private fun stopped() = JSONObject().put("ativo", false).put("contexto_disponivel", false)
        fun status(): JSONObject = current?.state() ?: stopped()
        fun ponteOperation(op: String, input: JSONObject): JSONObject {
            val service = current
            if (service == null && op == "ponte.status") return JSONObject("{\"ativo\":false,\"estado\":\"encerrado\",\"autorizacoes\":[]}")
            return (service ?: throw FalhaPonte("SESSAO_ENCERRADA")).bridgeOperation(op, input)
        }
        fun atualizarDaGuarda(context: android.content.Context, expectedSession: String? = null): JSONObject {
            val service=current ?: return stopped()
            val state=service.host.estado();val session=state["sessao"]?.jsonPrimitive?.content ?: return stopped()
            if(expectedSession!=null) require(expectedSession==session)
            if(state["pausado"]==JsonPrimitive(true)) return JSONObject(state.toString())
            try {
                val scopes=state["escopos"]!!.jsonArray.map { it.jsonPrimitive.content }
                val projection=com.fintips.motor.projetarBundleIA(EstadoCliente(context).bundle(),scopes,java.time.LocalDate.now().toString())
                return JSONObject(service.host.atualizar(session,projection).toString())
            } catch(e:Exception) { runCatching { service.host.atualizar(session,null) };throw e }
        }
        fun refreshNotification() { current?.notifyRunning() }
        fun pausar(session: String): JSONObject = JSONObject((current?.host?.pausar(session) ?: error("servidor encerrado")).toString())
        fun atualizar(session: String, raw: String?): JSONObject = JSONObject((current?.host?.atualizar(session,
            raw?.let { Json.parseToJsonElement(MotorBridge.validateContext(it)).jsonObject }) ?: error("servidor encerrado")).toString())
        fun verificar(session: String): JSONObject {
            val service = current ?: throw FalhaMcp(CodigoMcp.INDISPONIVEL)
            return try { JSONObject(service.host.verificar(session).toString()) }
            catch (_: Exception) { throw FalhaMcp(CodigoMcp.TESTE) }
        }
        fun credencial(): String = current?.host?.credencial() ?: error("servidor encerrado")
    }
}
