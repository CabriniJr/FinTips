package com.fintips.app;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileNotFoundException;
import java.nio.charset.StandardCharsets;

/** Somente no APK de testes; usa APIs Android/Java também no processo do provedor. */
public class LibreraTestProvider extends ContentProvider {
    public static final Uri URI=Uri.parse("content://com.fintips.app.ci.test.librera/progress");
    private File file() { return new File(getContext().getFilesDir(),"librera-source-test.json"); }
    @Override public boolean onCreate() { return true; }
    @Override public String getType(Uri uri) { return "application/json"; }
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] selectionArgs,String sortOrder) { return null; }
    @Override public Uri insert(Uri uri,ContentValues values) { return null; }
    @Override public int delete(Uri uri,String selection,String[] args) { return 0; }
    @Override public int update(Uri uri,ContentValues values,String selection,String[] args) { return 0; }
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode) throws FileNotFoundException { return ParcelFileDescriptor.open(file(),ParcelFileDescriptor.MODE_READ_ONLY); }
    @Override public Bundle call(String method,String arg,Bundle extras) {
        long token=Binder.clearCallingIdentity();
        try {
            if ("set".equals(method)) {
                try(FileOutputStream output=new FileOutputStream(file())) { output.write(arg.getBytes(StandardCharsets.UTF_8)); }
                catch(java.io.IOException error) { throw new IllegalStateException(error); }
            } else if ("grant".equals(method)) {
                getContext().grantUriPermission("com.fintips.app.ci",URI,Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
            } else throw new IllegalArgumentException("Operação de teste inválida");
            return new Bundle();
        } finally { Binder.restoreCallingIdentity(token); }
    }
}
