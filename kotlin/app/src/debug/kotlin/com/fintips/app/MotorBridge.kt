package com.fintips.app

import com.fintips.motor.executarMotorLocal
import com.fintips.motor.validarContextoIA
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.json.JSONObject

/** Só traduz o transporte Android para o contrato testado no motor. */
internal class MotorBridge {
    fun execute(operation: String, input: JSONObject): JSONObject =
        JSONObject(executarMotorLocal(operation, Json.parseToJsonElement(input.toString()).jsonObject).toString())

    companion object {
        fun validateContext(s: String): String = validarContextoIA(Json.parseToJsonElement(s).jsonObject).toString()
    }
}
