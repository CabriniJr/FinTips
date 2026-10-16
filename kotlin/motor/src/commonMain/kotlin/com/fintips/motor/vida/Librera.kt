package com.fintips.motor.vida

import com.fintips.motor.sha256Hex
import kotlinx.datetime.*
import kotlinx.serialization.json.*
import kotlin.math.floor

/** Mesmo recorte de reading.librera_positions: pt, caminhos e metadados não entram. */
fun posicoesLibrera(data: JsonElement): JsonObject {
    val root = data as? JsonObject ?: error("formato inválido")
    var ignored=0
    val positions=buildJsonArray {
        for ((key,value) in root) {
            val row=value as? JsonObject
            val p=row?.get("p") as? JsonPrimitive; val t=row?.get("t") as? JsonPrimitive
            val progress=p?.takeUnless { it.isString }?.doubleOrNull
            val time=t?.takeUnless { it.isString }?.longOrNull
            if (key.isBlank() || '/' in key || '\\' in key || progress==null || !progress.isFinite() || progress !in 0.0..1.0 || time==null || time !in 1L..8640000000000000L) { ignored++;continue }
            addJsonObject { put("chave",key);put("progresso_bp",floor(progress*10000+.5).toInt());put("tempo_ms",time) }
        }
    }
    return buildJsonObject { put("posicoes",positions);put("ignorados",ignored) }
}

/** Altera a mesma leitura canônica; uma correção do usuário vence no dia. */
fun importarLibrera(reading: JsonObject, raw: JsonElement, profileRaw: String, nowMs: Long, zone: String, excluded: JsonArray=JsonArray(emptyList())): JsonObject {
    require(profileRaw.isNotBlank() && profileRaw.length<=100)
    val profile=profileRaw.trim();val tz=TimeZone.of(zone)
    val today=Instant.fromEpochMilliseconds(nowMs).toLocalDateTime(tz).date
    val parsed=posicoesLibrera(raw);var ignored=parsed["ignorados"]!!.jsonPrimitive.int
    var added=0;var updated=0
    val books=reading["livros"]!!.jsonArray.toMutableList()
    for (el in parsed["posicoes"]!!.jsonArray) {
        val p=el.jsonObject;val key=p["chave"]!!.jsonPrimitive.content;val time=p["tempo_ms"]!!.jsonPrimitive.long
        val pair=buildJsonArray { add(profile);add(key) }
        if(time>nowMs || pair in excluded) { ignored++;continue }
        val day=Instant.fromEpochMilliseconds(time).toLocalDateTime(tz).date
        if(day>today) { ignored++;continue }
        var index=books.indexOfFirst { val b=it.jsonObject;b["fonte"]==JsonPrimitive("librera") && b["chave"]==JsonPrimitive(key) && b["perfil"]==JsonPrimitive(profile) }
        if(index<0) {
            val id="lib_"+sha256Hex(profile.encodeToByteArray().size.toString()+":"+profile+key)
            require(books.none { it.jsonObject["id"]==JsonPrimitive(id) })
            val title=Regex("\\.[a-z0-9]+$",RegexOption.IGNORE_CASE).replace(key,"").trim().ifEmpty { key }
            books.add(buildJsonObject { put("id",id);put("titulo",title);put("fonte","librera");put("chave",key);put("perfil",profile);put("prazo","");put("dias_semana",JsonNull);put("observacoes",JsonArray(emptyList())) })
            index=books.lastIndex;added++
        }
        val book=books[index].jsonObject
        val obs=book["observacoes"]!!.jsonArray
        val old=obs.firstOrNull { it.jsonObject["dia"]==JsonPrimitive(day.toString()) }?.jsonObject
        if(old!=null && (old["origem"]==JsonPrimitive("usuario") || old["tempo_ms"]!!.jsonPrimitive.long>=time)) continue
        val point=buildJsonObject { put("dia",day.toString());put("progresso_bp",p["progresso_bp"]!!);put("tempo_ms",time);put("origem","librera") }
        val next=(obs.filterNot { it.jsonObject["dia"]==point["dia"] }+point).sortedBy { it.jsonObject["dia"]!!.jsonPrimitive.content }
        books[index]=JsonObject(book+("observacoes" to JsonArray(next)));updated++
    }
    return buildJsonObject { put("leitura",JsonObject(reading+("livros" to JsonArray(books))));put("adicionados",added);put("atualizados",updated);put("ignorados",ignored) }
}
