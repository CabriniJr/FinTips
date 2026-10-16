package com.fintips.app

import android.content.ContentProvider
import android.content.ContentValues
import android.content.Intent
import android.database.Cursor
import android.net.Uri
import android.os.Bundle
import android.os.ParcelFileDescriptor
import java.io.File

/** Somente no APK de instrumentação: URI e conteúdo sintéticos com grant persistente. */
class LibreraTestProvider : ContentProvider() {
    private val file get()=File(context!!.filesDir,"librera-source-test.json")
    override fun onCreate()=true
    override fun getType(uri: Uri)="application/json"
    override fun query(uri: Uri,projection: Array<out String>?,selection: String?,selectionArgs: Array<out String>?,sortOrder: String?): Cursor?=null
    override fun insert(uri: Uri,values: ContentValues?): Uri?=null
    override fun delete(uri: Uri,selection: String?,selectionArgs: Array<out String>?)=0
    override fun update(uri: Uri,values: ContentValues?,selection: String?,selectionArgs: Array<out String>?)=0
    override fun openFile(uri: Uri,mode: String): ParcelFileDescriptor=ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY)
    override fun call(method: String,arg: String?,extras: Bundle?): Bundle {
        when(method) {
            "set" -> file.writeText(arg!!)
            "grant" -> context!!.grantUriPermission("com.fintips.app.ci",URI,Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
            else -> error("operação de teste inválida")
        }
        return Bundle()
    }
    companion object { val URI: Uri=Uri.parse("content://com.fintips.app.ci.test.librera/progress") }
}
