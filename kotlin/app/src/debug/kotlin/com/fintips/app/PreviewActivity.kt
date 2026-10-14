package com.fintips.app

import android.content.ContentValues
import android.net.Uri
import android.os.Build
import android.os.Bundle
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
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.util.concurrent.Executors

/** Apenas debug: APK offline para avaliar os cinco destinos do protótipo. */
class PreviewActivity : ComponentActivity() {
    private lateinit var view: WebView
    private var files: ValueCallback<Array<Uri>>? = null
    private val io = Executors.newSingleThreadExecutor()
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
            view.loadUrl("https://$HOST/index.html")
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

    override fun onSaveInstanceState(outState: Bundle) {
        view.saveState(outState)
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        files?.onReceiveValue(null); files = null
        view.removeJavascriptInterface("FinTipsLocal")
        view.destroy()
        io.shutdown()
        super.onDestroy()
    }

    private fun blocked() = WebResourceResponse("text/plain", "UTF-8", 403, "Offline", emptyMap(), ByteArrayInputStream(ByteArray(0)))

    companion object { private const val HOST = "appassets.androidplatform.net" }
}
