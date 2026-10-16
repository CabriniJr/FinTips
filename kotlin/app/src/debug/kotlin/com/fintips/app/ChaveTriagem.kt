package com.fintips.app

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** A chave nunca passa pelo WebView. Só o ciphertext fica em preferências. */
internal class ChaveTriagem(context: Context, private val alias: String = "fintips.openai.triagem.v1") {
    private val prefs=context.getSharedPreferences(alias,Context.MODE_PRIVATE)
    private fun key(): SecretKey {
        val store=KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val existing=store.getKey(alias,null) as? SecretKey
        if(existing!=null) return existing
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true).build())
        }.generateKey()
    }
    @Synchronized fun salvar(value: String) {
        require(value.startsWith("sk-") && value.length in 20..512 && value.none { it.isWhitespace() || it.code<32 })
        val cipher=Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE,key()) }
        val encrypted=cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        check(prefs.edit().putString("encrypted",Base64.encodeToString(encrypted,Base64.NO_WRAP))
            .putString("iv",Base64.encodeToString(cipher.iv,Base64.NO_WRAP)).commit())
    }
    @Synchronized fun ler(): String? {
        val raw=prefs.getString("encrypted",null) ?: return null
        val iv=prefs.getString("iv",null) ?: error("chave indisponível")
        val cipher=Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,Base64.decode(iv,Base64.NO_WRAP))) }
        return cipher.doFinal(Base64.decode(raw,Base64.NO_WRAP)).toString(Charsets.UTF_8)
    }
    @Synchronized fun configurada(): Boolean = runCatching { ler()!=null }.getOrDefault(false)
    @Synchronized fun apagar() {
        check(prefs.edit().clear().commit())
        KeyStore.getInstance("AndroidKeyStore").apply { load(null); if(containsAlias(alias)) deleteEntry(alias) }
    }
}
