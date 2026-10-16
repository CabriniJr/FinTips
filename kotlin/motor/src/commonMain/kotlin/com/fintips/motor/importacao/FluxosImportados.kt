package com.fintips.motor.importacao

import com.fintips.motor.norm
import kotlinx.serialization.json.*

/** Leitura do canal canônico, sem inferir a identidade ou a intenção de um Pix.
 * É uma separação inicial, não o classificador financeiro completo/score. */
internal val GRUPOS_IMPORTADOS = listOf("income", "expense", "savings_out", "savings_in", "refund", "pendente")
private val SINAIS = mapOf("income" to 1, "expense" to -1, "savings_out" to -1, "savings_in" to 1, "refund" to 1)
private val canais by lazy { Json.parseToJsonElement(CANAIS_IMPORTACAO).jsonArray.map { norm(it.jsonObject["match"]!!.jsonPrimitive.content) to it.jsonObject } }
internal data class MovimentoImportado(val mes: String, val centavos: Long, val grupo: String)

internal fun grupoImportado(memo: String, centavos: Long): String {
    val target = norm(memo)
    val rule = canais.firstOrNull { target.startsWith(it.first) }?.second
        ?: return "pendente"
    if (rule["canal"]?.jsonPrimitive?.content?.startsWith("pix") == true) return "pendente"
    val flow = rule["fluxo"]?.jsonPrimitive?.content ?: return "pendente"
    if (centavos == 0L || SINAIS[flow] != if (centavos > 0) 1 else -1) return "pendente"
    return flow
}
private fun safe(n: Long): Long { require(n in -9007199254740991L..9007199254740991L); return n }
private fun soma(values: List<Long>) = values.fold(0L) { a, b -> safe(a + b) }
private fun grupos(rows: List<MovimentoImportado>) = buildJsonArray {
    for (g in GRUPOS_IMPORTADOS) {
        val values = rows.filter { it.grupo == g }.map { it.centavos }
        if (values.isEmpty()) continue
        addJsonObject {
            put("fluxo", g); put("transacoes", values.size)
            put("entradas_centavos", soma(values.filter { it > 0 }))
            put("saidas_centavos", soma(values.filter { it < 0 }.map { -it }))
        }
    }
}
internal fun resumoFluxos(rows: List<MovimentoImportado>): JsonObject = buildJsonObject {
    put("schema_version", 1); put("origem", "heuristica"); put("revisao_regras", REVISAO_CANAIS)
    put("transacoes", rows.size); put("grupos", grupos(rows))
    putJsonArray("meses") {
        for (month in rows.map { it.mes }.distinct().sorted()) addJsonObject {
            put("mes", month); put("grupos", grupos(rows.filter { it.mes == month }))
        }
    }
}

/** Allowlist de transporte: nunca inclui memo, nomes, conta, FITID ou caminho. */
fun validarFluxosImportados(data: JsonObject): JsonObject {
    require(data.keys == setOf("schema_version", "origem", "revisao_regras", "transacoes", "grupos", "meses"))
    require(data["schema_version"] == JsonPrimitive(1) && data["origem"] == JsonPrimitive("heuristica"))
    require(data["revisao_regras"]!!.jsonPrimitive.isString && Regex("^[0-9a-f]{64}$").matches(data["revisao_regras"]!!.jsonPrimitive.content))
    fun numero(v: JsonElement): Long { require(!v.jsonPrimitive.isString); return safe(v.jsonPrimitive.long).also { require(it >= 0) } }
    fun readGroups(items: JsonArray): Map<String, List<Long>> {
        require(items.size <= GRUPOS_IMPORTADOS.size)
        val result = mutableMapOf<String, List<Long>>()
        for (e in items) {
            val r = e.jsonObject
            require(r.keys == setOf("fluxo", "transacoes", "entradas_centavos", "saidas_centavos"))
            require(r["fluxo"]!!.jsonPrimitive.isString)
            val flow = r["fluxo"]!!.jsonPrimitive.content
            require(flow in GRUPOS_IMPORTADOS && flow !in result)
            val ns = listOf("transacoes", "entradas_centavos", "saidas_centavos").map { numero(r[it]!!) }
            require(ns[0] in 1L..50000L)
            require((SINAIS[flow] != 1 || ns[2] == 0L) && (SINAIS[flow] != -1 || ns[1] == 0L))
            result[flow] = ns
        }
        return GRUPOS_IMPORTADOS.associateWith { result[it] ?: listOf(0L, 0L, 0L) }
    }
    val totals = readGroups(data["grupos"]!!.jsonArray)
    val count = numero(data["transacoes"]!!)
    require(count <= 50000 && count == soma(totals.values.map { it[0] }))
    val months = data["meses"]!!.jsonArray; require(months.size <= 1200)
    val acc = GRUPOS_IMPORTADOS.associateWith { mutableListOf(0L, 0L, 0L) }
    var previous = ""
    for (m in months) {
        val month = m.jsonObject; require(month.keys == setOf("mes", "grupos"))
        require(month["mes"]!!.jsonPrimitive.isString)
        val key = month["mes"]!!.jsonPrimitive.content
        require(Regex("^\\d{4}-(0[1-9]|1[0-2])$").matches(key) && key > previous); previous = key
        for ((g, ns) in readGroups(month["grupos"]!!.jsonArray)) {
            for (i in 0..2) acc.getValue(g)[i] = safe(acc.getValue(g)[i] + ns[i])
        }
    }
    require(GRUPOS_IMPORTADOS.all { acc.getValue(it) == totals.getValue(it) })
    return data
}
