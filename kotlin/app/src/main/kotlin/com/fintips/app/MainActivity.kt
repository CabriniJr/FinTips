package com.fintips.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent

/**
 * A Activity, e ela não faz nada além de abrir a tela.
 *
 * Nenhuma regra aqui, de propósito: o que está neste módulo não roda em teste
 * nenhum do repositório, porque exige SDK e emulador. Tudo que decide algo
 * vive em `commonMain` e tem teste.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(estado: Bundle?) {
        super.onCreate(estado)
        val guarda = guardaDoAparelho(applicationContext)
        setContent { TelaDoDia(guarda) }
    }
}
