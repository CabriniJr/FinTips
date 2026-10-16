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
import com.fintips.mcp.OpenAITriagem
import com.fintips.mcp.FalhaTriagem
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.JsonPrimitive
import android.app.AlertDialog
import android.widget.EditText
import android.text.InputType
import android.view.WindowManager
import android.view.inputmethod.EditorInfo
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
    private val triagemAI = OpenAITriagem()
    private val chaveTriagem by lazy { ChaveTriagem(this) }
    private val estadoCliente by lazy { EstadoCliente(this) }
    private val librera by lazy { LibreraFonte(this,estadoCliente) }
    private var libreraProfile="principal"
    private var libreraPicking=false
    private val libreraPicker=registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        libreraPicking=false
        if(uri!=null) io.execute {
            var granted=false
            try {
                val hadGrant=contentResolver.persistedUriPermissions.any { it.uri==uri && it.isReadPermission }
                contentResolver.takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);granted=!hadGrant
                librera.conectar(uri,libreraProfile)
            } catch(_:Exception) {
                if(granted && runCatching { estadoCliente.fonte()?.get("uri")?.jsonPrimitive?.content }.getOrNull()!=uri.toString()) runCatching { contentResolver.releasePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION) }
                runOnUiThread { if(!closed) view.evaluateJavascript("dispatchEvent(new CustomEvent('fintips:librera-error',{detail:'Não foi possível conectar. Escolha o app-Progress.json que o Librera atualiza, com acesso persistente; a fonte anterior foi preservada.'}))",null) }
            } finally { atualizarEstadoWeb() }
        } else atualizarEstadoWeb()
    }
    private val extratos by lazy { ExtratosLocais(this) }
    private var keyDialog: AlertDialog? = null
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
        view.addJavascriptInterface(EstadoWebBridge(estadoCliente), "FinTipsState")
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
                            op in setOf("triagem.chave_status", "triagem.configurar_chave", "triagem.apagar_chave", "triagem.sugerir", "triagem.organizar", "triagem.cancelar") -> triagemOperation(op, input)
                            op=="estado.contexto" -> { require(input.keys().asSequence().toSet()==setOf("scopes"));JSONObject(com.fintips.motor.projetarBundleIA(estadoCliente.bundle(),input.getJSONArray("scopes").let { a -> (0 until a.length()).map { a.getString(it) } },java.time.LocalDate.now().toString()).toString()) }
                            op=="estado.exportar" -> { require(input.length()==0);LocalBackup().saveStateCopy(estadoCliente.copia());JSONObject().put("status","copia_solicitada") }
                            op=="guarda.descritores" -> { require(input.length()==0);JSONObject(guardasAndroid.toString()) }
                            op.startsWith("librera.") -> libreraOperation(op,input)
                            op.startsWith("extrato.") && op != "extrato.conferir" -> extratoOperation(op,input)
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
                        val triageFailure = generateSequence<Throwable>(e) { it.cause }.filterIsInstance<FalhaTriagem>().firstOrNull()
                        val message = if (operation?.startsWith("triagem.") == true) mensagemTriagem(triageFailure?.codigo) else if (operation?.startsWith("ponte.") == true) mensagemPonte(bridgeFailure?.codigo) else failure?.codigo?.mensagem ?: if (operation?.startsWith("servidor.") == true)
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
        io.execute { runCatching { if(estadoCliente.existe()) librera.agendar() } }
        if (savedInstanceState == null || view.restoreState(savedInstanceState) == null) {
            view.loadUrl("https://$HOST/index.html" + if (intent.getBooleanExtra("abrir_ia", false)) "#ia" else "")
        }
    }

    /** Exportação para Downloads local; não oferece provedor remoto de destino. */
    inner class LocalBackup {
        @JavascriptInterface
        fun saveStateCopy(json: String) = savePrivateCopy(json,16*1024*1024)

        @JavascriptInterface
        fun saveCopy(json: String) = savePrivateCopy(json, 2 * 1024 * 1024)

        fun saveStatements(json: String) = savePrivateCopy(json, 24 * 1024 * 1024)

        private fun savePrivateCopy(json: String, maxBytes: Int) {
            if (json.length > maxBytes || Build.VERSION.SDK_INT < 29) {
                notice("Cópias em Downloads exigem Android 10 ou mais recente e espaço disponível no aparelho.")
                return
            }
            val bytes = json.toByteArray(Charsets.UTF_8)
            if (bytes.size > maxBytes) {
                notice("A cópia local excede o limite permitido.")
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

    private fun atualizarEstadoWeb() = runOnUiThread {
        if(!closed) view.evaluateJavascript("dispatchEvent(new Event('fintips:librera-updated'))",null)
    }
    private fun libreraOperation(op: String,i: JSONObject): JSONObject = when(op) {
        "librera.status" -> { require(i.length()==0);JSONObject(librera.status().toString()) }
        "librera.conectar" -> {
            require(i.keys().asSequence().toSet() in listOf(emptySet<String>(),setOf("perfil")))
            val p=i.optString("perfil","principal").trim();require(p.isNotBlank() && p.length<=100)
            runOnUiThread { if(!closed && !libreraPicking) { libreraPicking=true;libreraProfile=p
                try { libreraPicker.launch(arrayOf("application/json","text/plain","application/octet-stream")) }
                catch(_:Exception) { libreraPicking=false;notice("Não foi possível abrir o seletor de documentos.");atualizarEstadoWeb() }
            } }
            JSONObject().put("status","selecao_solicitada")
        }
        "librera.sincronizar" -> { require(i.length()==0);val result=librera.sincronizar();atualizarEstadoWeb();JSONObject(result.toString()) }
        "librera.desconectar" -> { require(i.length()==0);val result=librera.desconectar();atualizarEstadoWeb();JSONObject(result.toString()) }
        else -> error("operação indisponível")
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

    private fun extratoOperation(op: String, i: JSONObject): JSONObject = when(op) {
        "extrato.estado", "extrato.contexto" -> { require(i.length()==0);JSONObject((if(op=="extrato.estado") extratos.estado() else extratos.contexto()).toString()) }
        "extrato.fluxos" -> { require(i.length()==0);JSONObject(extratos.fluxos().toString()) }
        "extrato.importar" -> {
            require(i.keys().asSequence().toSet().all { it in setOf("ofx","saldo_inicial") })
            JSONObject(extratos.importar(i.getString("ofx"),if(i.isNull("saldo_inicial")) null else i.getString("saldo_inicial")).toString())
        }
        "extrato.remover" -> { require(i.keys().asSequence().toSet()==setOf("ref"));JSONObject(extratos.remover(i.getString("ref")).toString()) }
        "extrato.exportar" -> { require(i.length()==0);LocalBackup().saveStatements(extratos.copia());JSONObject().put("status","copia_solicitada") }
        else -> error("operação indisponível")
    }

    private fun triagemOperation(op: String, i: JSONObject): JSONObject = when(op) {
        "triagem.chave_status" -> JSONObject().put("configurada",chaveTriagem.configurada()).put("modelo","gpt-4.1-mini")
        "triagem.configurar_chave" -> { triagemAI.cancelar(); runOnUiThread { configurarChaveTriagem() }; JSONObject().put("status","dialogo_solicitado") }
        "triagem.apagar_chave" -> { triagemAI.cancelar(); chaveTriagem.apagar(); JSONObject().put("configurada",false) }
        "triagem.cancelar" -> { triagemAI.cancelar(); JSONObject().put("status","cancelado") }
        "triagem.sugerir", "triagem.organizar" -> {
            val body=Json.parseToJsonElement(i.toString()).jsonObject
            val (financeiro,fluxos) = extratos.contextos()
            val authoritativeBundle=estadoCliente.bundle()
            JSONObject(triagemAI.sugerir(authoritativeBundle,body["rascunhos"]!!.jsonArray,
                chaveTriagem.ler() ?: throw FalhaTriagem("CHAVE"),i.optBoolean("autorizado",false),i.getString("hoje"),agente=op=="triagem.organizar",financeiro=financeiro,fluxosFinanceiros=fluxos).toString())
        }
        else -> error("operação indisponível")
    }
    private fun configurarChaveTriagem() {
        if(closed || keyDialog?.isShowing==true) return
        val alreadySecure=window.attributes.flags and WindowManager.LayoutParams.FLAG_SECURE != 0
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        val input=EditText(this).apply {
            inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            importantForAutofill=android.view.View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS
            imeOptions=EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING
            hint="sk-…";setSingleLine();setPadding(32,24,32,24)
        }
        val dialog=AlertDialog.Builder(this,android.R.style.Theme_Material_Dialog_Alert)
            .setTitle("Chave OpenAI neste aparelho")
            .setMessage("A chave fica cifrada com Android Keystore e não entra no chat, cópias locais ou MCP. A API recebe só valores e rótulos abstratos após sua autorização. Modelo: gpt-4.1-mini.")
            .setView(input).setPositiveButton("Guardar",null).setNegativeButton("Cancelar",null).create()
        keyDialog=dialog
        dialog.setOnDismissListener {
            input.text?.clear();keyDialog=null
            if(!alreadySecure) window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
            if(!closed) view.evaluateJavascript("dispatchEvent(new Event('fintips:chave-triagem'))",null)
        }
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val raw=input.text.toString().trim()
                try { chaveTriagem.salvar(raw);dialog.dismiss() }
                catch(_:Exception) { input.error="Chave inválida ou armazenamento indisponível. Nada foi exibido ou enviado." }
            }
        }
        dialog.show();dialog.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
    }
    private fun mensagemTriagem(code: String?): String = when(code) {
        "CHAVE" -> "TRIAGEM-02: Configure ou substitua a chave OpenAI neste aparelho."
        "LIMITE" -> "TRIAGEM-03: A API atingiu um limite. Você pode continuar a triagem local."
        "CONSENTIMENTO" -> "TRIAGEM-04: Revise e autorize o contexto abstrato antes de usar a API."
        "CANCELADO" -> "TRIAGEM-05: Consulta cancelada. Seus registros foram preservados."
        "OCUPADO" -> "TRIAGEM-06: Aguarde a consulta atual ou cancele."
        "REDE", "RESPOSTA" -> "TRIAGEM-07: A API não retornou uma sugestão válida. Você pode continuar localmente."
        else -> "TRIAGEM-01: Contrato ou revisão recusados. Nenhum registro foi alterado; confira os campos e a versão da proposta."
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
        "servidor.atualizar_nativo" -> { require(i.keys().asSequence().toSet()==setOf("sessao"));McpLocalService.atualizarDaGuarda(this,i.getString("sessao")) }
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
        io.execute { runCatching { if(estadoCliente.existe() && estadoCliente.fonte()?.get("ativa")==JsonPrimitive(true)) { librera.agendar();librera.sincronizar();atualizarEstadoWeb() } } }
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
        triagemAI.cancelar(); keyDialog?.dismiss(); keyDialog=null
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
