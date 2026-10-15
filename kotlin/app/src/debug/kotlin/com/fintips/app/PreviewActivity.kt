package com.fintips.app

import android.content.ContentValues
import android.content.ClipData
import android.content.ClipDescription
import android.content.ClipboardManager
import android.content.pm.PackageManager
import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.ResultReceiver
import android.provider.MediaStore
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.webkit.WebViewAssetLoader
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import androidx.webkit.WebMessageCompat
import org.json.JSONObject
import com.fintips.mcp.FalhaPonte
import java.io.ByteArrayInputStream
import java.util.concurrent.Executors
import java.util.concurrent.CompletableFuture
import java.util.concurrent.TimeUnit

/** Apenas debug: assets locais e conexão MCP externa opcional e autorizada. */
class PreviewActivity : ComponentActivity() {
    private lateinit var view: WebView
    private var files: ValueCallback<Array<Uri>>? = null
    private val io = Executors.newFixedThreadPool(3)
    private val motor = MotorBridge()
    private var closed = false
    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) {
        McpLocalService.refreshNotification()
    }
    private val picker = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        files?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result.resultCode, result.data))
        files = null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val loader = WebViewAssetLoader.Builder()
            .addPathHandler("/", WebViewAssetLoader.AssetsPathHandler(this)).build()
        view = WebView(this)
        view.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = true // Arquivo escolhido pela pessoa, via seletor Android.
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
            setSupportMultipleWindows(false)
        }
        view.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(v: WebView, request: WebResourceRequest): WebResourceResponse =
                if (request.url.scheme == "https" && request.url.host == HOST) {
                    loader.shouldInterceptRequest(request.url) ?: blocked()
                } else blocked()

            override fun shouldOverrideUrlLoading(v: WebView, request: WebResourceRequest): Boolean =
                request.url.scheme != "https" || request.url.host != HOST
        }
        view.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(v: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
                files?.onReceiveValue(null)
                files = callback
                return try { picker.launch(params.createIntent()); true }
                catch (_: Exception) { files?.onReceiveValue(null); files = null; false }
            }
        }
        view.addJavascriptInterface(LocalBackup(), "FinTipsLocal")
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(view, "FinTipsMotor", setOf("https://$HOST")) { _, message, origin, mainFrame, reply ->
                if (!mainFrame || origin.scheme != "https" || origin.host != HOST || origin.port !in listOf(-1, 443) || message.type != WebMessageCompat.TYPE_STRING) return@addWebMessageListener
                val raw = message.data ?: return@addWebMessageListener
                if (raw.toByteArray(Charsets.UTF_8).size > 1536 * 1024) return@addWebMessageListener
                io.execute {
                    var id: String? = null
                    var operation: String? = null
                    val response = try {
                        val request = JSONObject(raw)
                        id = request.getString("id").also { require(it.length <= 100) }
                        val op = request.getString("operation").also { operation = it }
                        val input = request.getJSONObject("input")
                        val result = when {
                            op == "ponte.copiar_endpoint" -> copyLocal(McpLocalService.ponteOperation("ponte.status", JSONObject()).getString("origem") + "/mcp", false)
                            op == "ponte.abrir_cliente" -> openAIClient(input.getString("provedor"))
                            op.startsWith("ponte.") -> McpLocalService.ponteOperation(op, input)
                            op.startsWith("servidor.") -> localServer(op, input)
                                .put("versao_app", packageManager.getPackageInfo(packageName, 0).versionName)
                                .put("android_sdk", Build.VERSION.SDK_INT)
                            op == "ia.abrir" -> openConnector(input)
                            else -> motor.execute(op, input)
                        }
                        JSONObject().put("id", id).put("result", result)
                    } catch (e: Exception) {
                        val failure = generateSequence<Throwable>(e) { it.cause }.filterIsInstance<FalhaMcp>().firstOrNull()
                        val bridgeFailure = generateSequence<Throwable>(e) { it.cause }.filterIsInstance<FalhaPonte>().firstOrNull()
                        val message = if (operation?.startsWith("ponte.") == true) mensagemPonte(bridgeFailure?.codigo) else failure?.codigo?.mensagem ?: if (operation?.startsWith("servidor.") == true)
                            CodigoMcp.DESCONHECIDO.mensagem else "O motor não aceitou este pedido. Confira os dados e tente novamente."
                        JSONObject().put("id", id ?: JSONObject.NULL).put("error", message)
                    }
                    runOnUiThread { if (!closed) reply.postMessage(response.toString()) }
                }
            }
        }
        view.setDownloadListener { url, _, _, _, _ ->
            if (url.startsWith("blob:https://$HOST/")) {
                val quoted = JSONObject.quote(url)
                view.evaluateJavascript("fetch($quoted).then(r=>r.text()).then(t=>FinTipsLocal.saveCopy(t))", null)
            }
        }
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                view.evaluateJavascript("Boolean(document.querySelector('dialog[open]'))") { open ->
                    if (open == "true") {
                        view.evaluateJavascript("document.querySelector('dialog[open]').dispatchEvent(new Event('cancel',{cancelable:true}))", null)
                    } else if (view.canGoBack()) view.goBack() else finish()
                }
            }
        })
        setContentView(view)
        if (savedInstanceState == null || view.restoreState(savedInstanceState) == null) {
            view.loadUrl("https://$HOST/index.html" + if (intent.getBooleanExtra("abrir_ia", false)) "#ia" else "")
        }
    }

    /** Exportação para Downloads local; não oferece provedor remoto de destino. */
    inner class LocalBackup {
        @JavascriptInterface
        fun saveCopy(json: String) {
            if (json.length > 2 * 1024 * 1024 || Build.VERSION.SDK_INT < 29) {
                notice("Cópias em Downloads exigem Android 10 ou mais recente e arquivo de até 2 MB.")
                return
            }
            val bytes = json.toByteArray(Charsets.UTF_8)
            if (bytes.size > 2 * 1024 * 1024) {
                notice("A cópia local excede o limite de 2 MB.")
                return
            }
            io.execute {
                var uri: Uri? = null
                try {
                    // Preserva inclusive backup de armazenamento corrompido.
                    // Não registrar conteúdo, nem exigir JSON válido para recuperá-lo.
                    val values = ContentValues().apply {
                        put(MediaStore.MediaColumns.DISPLAY_NAME, "fintips-local-${System.currentTimeMillis()}.json")
                        put(MediaStore.MediaColumns.MIME_TYPE, "application/json")
                        put(MediaStore.MediaColumns.RELATIVE_PATH, "Download/FinTips")
                        put(MediaStore.MediaColumns.IS_PENDING, 1)
                    }
                    uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                        ?: error("destino indisponível")
                    contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
                        ?: error("destino indisponível")
                    values.clear(); values.put(MediaStore.MediaColumns.IS_PENDING, 0)
                    contentResolver.update(uri, values, null, null)
                    notice("Cópia salva em Downloads/FinTips. O arquivo contém seus dados pessoais.")
                } catch (_: Exception) {
                    uri?.let { runCatching { contentResolver.delete(it, null, null) } }
                    notice("Não foi possível salvar a cópia local.")
                }
            }
        }
    }

    private fun notice(message: String) = runOnUiThread { Toast.makeText(this, message, Toast.LENGTH_LONG).show() }

    private fun openAIClient(provider: String): JSONObject {
        val url = when (provider) { "chatgpt" -> "https://chatgpt.com/"; "claude" -> "https://claude.ai/"; else -> error("provedor inválido") }
        runOnUiThread {
            if (!closed) try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addCategory(Intent.CATEGORY_BROWSABLE)) }
            catch (_: Exception) { notice("Abra o site da IA para configurar o conector MCP.") }
        }
        return JSONObject().put("status", "abertura_solicitada")
    }

    private fun mensagemPonte(code: String?): String = when (code) {
        "CODIGO_EXPIRADO" -> "PONTE-02: Código expirado ou já usado. Inicie uma nova autorização na IA."
        "AUTORIZACAO_RECUSADA" -> "PONTE-03: A ponte recusou a autorização. Confira o convite ou o código informado."
        "SESSAO_ENCERRADA" -> "PONTE-04: Inicie o servidor local antes de conectar a ponte."
        else -> "PONTE-01: Não foi possível concluir a conexão. Confira o endereço HTTPS, a rede e o estado da ponte."
    }

    private fun localServer(operation: String, i: JSONObject): JSONObject = when (operation) {
        "servidor.status" -> McpLocalService.status()
        "servidor.verificar" -> McpLocalService.verificar(i.getString("sessao"))
        "servidor.atualizar" -> McpLocalService.atualizar(i.getString("sessao"), i.getJSONObject("context").toString())
        "servidor.invalidar" -> McpLocalService.atualizar(i.getString("sessao"), null)
        "servidor.pausar" -> McpLocalService.pausar(i.getString("sessao"))
        "servidor.copiar_token" -> copyLocal(McpLocalService.credencial(), true)
        "servidor.copiar_endereco" -> copyLocal(McpLocalService.status().getString("endpoint"), false)
        "servidor.notificacoes" -> {
            runOnUiThread { requestNotifications(true) }
            JSONObject().put("status", "solicitado")
        }
        "servidor.iniciar", "servidor.encerrar" -> {
            if (operation == "servidor.encerrar" && !McpLocalService.status().optBoolean("ativo")) McpLocalService.status()
            else {
                val context = if (operation == "servidor.iniciar") {
                    try { MotorBridge.validateContext(i.getJSONObject("context").toString()) }
                    catch (_: Exception) { throw FalhaMcp(CodigoMcp.CONTEXTO) }
                } else null
                val future = CompletableFuture<JSONObject>()
                val receiver = object : ResultReceiver(Handler(Looper.getMainLooper())) {
                    override fun onReceiveResult(code: Int, data: Bundle?) {
                        if (code == 0) runCatching { JSONObject(data?.getString("json") ?: error("resposta ausente")) }
                            .onSuccess { future.complete(it) }.onFailure { future.completeExceptionally(it) }
                        else future.completeExceptionally(FalhaMcp(CodigoMcp.de(data?.getString("erro"))))
                    }
                }
                runOnUiThread {
                    try {
                        check(!closed)
                        val command = Intent(this, McpLocalService::class.java).putExtra("reply", receiver)
                        if (context != null) {
                            requestNotifications(false)
                            command.action = McpLocalService.START; command.putExtra("context", context)
                            startForegroundService(command)
                        } else { command.action = McpLocalService.STOP; startService(command) }
                    } catch (_: Exception) { future.completeExceptionally(FalhaMcp(CodigoMcp.ANDROID)) }
                }
                try { future.get(10, TimeUnit.SECONDS) }
                catch (_: java.util.concurrent.TimeoutException) { throw FalhaMcp(CodigoMcp.TEMPO) }
            }
        }
        else -> error("operação indisponível")
    }

    private fun copyLocal(value: String, secret: Boolean): JSONObject {
        val future = CompletableFuture<JSONObject>()
        runOnUiThread {
            try {
                check(!closed)
                val clip = ClipData.newPlainText(if (secret) "Token MCP local" else "Endereço MCP local", value)
                if (secret && Build.VERSION.SDK_INT >= 33) clip.description.extras = android.os.PersistableBundle().apply {
                    putBoolean(ClipDescription.EXTRA_IS_SENSITIVE, true)
                }
                getSystemService(ClipboardManager::class.java).setPrimaryClip(clip)
                future.complete(JSONObject().put("status", "copiado"))
            } catch (e: Exception) { future.completeExceptionally(e) }
        }
        return future.get(2, TimeUnit.SECONDS)
    }

    private fun requestNotifications(explicit: Boolean) {
        if (closed) return
        val prefs = getSharedPreferences("mcp-local", MODE_PRIVATE)
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            val asked = prefs.getBoolean("notificacoes_solicitadas", false)
            if (!explicit && asked) return
            if (explicit && asked && !shouldShowRequestPermissionRationale(Manifest.permission.POST_NOTIFICATIONS)) {
                startActivity(Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(android.provider.Settings.EXTRA_APP_PACKAGE, packageName))
            } else {
                prefs.edit().putBoolean("notificacoes_solicitadas", true).apply()
                notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        } else if (explicit) startActivity(Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(android.provider.Settings.EXTRA_APP_PACKAGE, packageName))
    }

    override fun onResume() {
        super.onResume()
        if (::view.isInitialized) { view.onResume(); view.evaluateJavascript("dispatchEvent(new Event('fintips:resume'))", null) }
    }

    override fun onPause() {
        if (::view.isInitialized) view.onPause()
        super.onPause()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent); setIntent(intent)
        if (intent.getBooleanExtra("abrir_ia", false)) view.evaluateJavascript("location.hash='ia'", null)
    }

    /** Somente a projeção validada sai, por gesto explícito, no navegador externo.
     * O fragmento não é enviado no pedido HTTP; a página de pareamento o consome.
     * O WebView segue offline e nunca recebe conteúdo remoto.
     */
    private fun openConnector(i: JSONObject): JSONObject {
        val base = Uri.parse(i.getString("endpoint"))
        require(base.scheme == "https" && !base.host.isNullOrBlank() && base.userInfo == null)
        require(base.encodedPath in listOf("", "/") && base.query == null && base.fragment == null)
        val revocation = i.getString("revocation")
        require(Regex("[a-f0-9]{64}").matches(revocation))
        val payload = JSONObject().put("revocation", revocation)
        if (i.optBoolean("revoke", false)) payload.put("revoke", true) else {
            val code = i.getString("code").replace("-", "").uppercase()
            require(Regex("[A-Z2-7]{12}").matches(code))
            payload.put("code", code).put("context", JSONObject(MotorBridge.validateContext(i.getJSONObject("context").toString())))
        }
        val url = base.buildUpon().path("/link").fragment(payload.toString()).build()
        runOnUiThread {
            if (!closed) try { startActivity(Intent(Intent.ACTION_VIEW, url).addCategory(Intent.CATEGORY_BROWSABLE)) }
            catch (_: Exception) { notice("Nenhum navegador disponível para abrir o conector.") }
        }
        return JSONObject().put("status", "navegador_solicitado")
    }

    override fun onSaveInstanceState(outState: Bundle) {
        view.saveState(outState)
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        closed = true
        files?.onReceiveValue(null); files = null
        view.removeJavascriptInterface("FinTipsLocal")
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) WebViewCompat.removeWebMessageListener(view, "FinTipsMotor")
        view.destroy()
        io.shutdown()
        super.onDestroy()
    }

    private fun blocked() = WebResourceResponse("text/plain", "UTF-8", 403, "Offline", emptyMap(), ByteArrayInputStream(ByteArray(0)))

    companion object { private const val HOST = "appassets.androidplatform.net" }
}
