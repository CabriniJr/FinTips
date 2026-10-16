package com.fintips.motor

import kotlinx.serialization.json.*

data class FrenteParaIA(val area: String, val total: Int, val feitas: Int)
data class PlanoParaIA(val area: String, val concluido: Boolean)
data class LeituraParaIA(val estado: String, val fonte: String)

private val areasIA = listOf("FOR", "AGI", "VIT", "INT", "FOC", "OURO")
private val estadosLeituraIA = listOf("sem_dados", "desatualizado", "calibrando", "sem_avanco", "estimado", "no_fim")

/** Replica ai_context.project_context. Não aceita texto livre, datas ou nomes. */
fun projetarContextoIA(frentes: List<FrenteParaIA>, planos: List<PlanoParaIA>,
    leituras: List<LeituraParaIA>, escopos: List<String>): JsonObject {
    require(escopos.distinct().size == escopos.size && escopos.all { it in listOf("rotina", "planos", "leitura") })
    require(frentes.size == areasIA.size && frentes.map { it.area }.toSet() == areasIA.toSet())
    require(frentes.all { it.total in 0..10000 && it.feitas in 0..it.total })
    require(planos.all { it.area in areasIA })
    require(leituras.all { it.estado in estadosLeituraIA && it.fonte in listOf("usuario", "librera") })
    return buildJsonObject {
        put("schema_version", 1)
        if ("rotina" in escopos) putJsonArray("rotina") {
            areasIA.forEach { area ->
                val f = frentes.single { it.area == area }
                addJsonObject {
                    put("area", area)
                    put("evidencia", when {
                        f.total == 0 -> "sem_metas"
                        f.feitas == 0 -> "sem_registro"
                        f.feitas == f.total -> "completa"
                        else -> "parcial"
                    })
                    put("origem", "usuario")
                }
            }
        }
        if ("planos" in escopos) putJsonArray("planos") {
            areasIA.forEach { area ->
                val ps = planos.filter { it.area == area }
                addJsonObject {
                    put("area", area)
                    put("estado", when {
                        ps.isEmpty() -> "sem_planos"
                        ps.all { it.concluido } -> "concluidos"
                        ps.none { it.concluido } -> "em_andamento"
                        else -> "misto"
                    })
                }
            }
        }
        if ("leitura" in escopos) putJsonObject("leitura") {
            putJsonArray("estados") { estadosLeituraIA.filter { s -> leituras.any { it.estado == s } }.forEach { add(it) } }
            putJsonArray("fontes") { listOf("usuario", "librera").filter { s -> leituras.any { it.fonte == s } }.forEach { add(it) } }
        }
    }
}

/** Fronteira de saída: recusa chaves extras em qualquer nível, inclusive PII. */
fun validarContextoIA(c: JsonObject): JsonObject {
    require(c.keys.all { it in listOf("schema_version", "rotina", "planos", "leitura") })
    require(c["schema_version"] == JsonPrimitive(1) && c.size > 1)
    for ((key, field, values) in listOf(
        Triple("rotina", "evidencia", listOf("sem_metas", "sem_registro", "completa", "parcial")),
        Triple("planos", "estado", listOf("sem_planos", "concluidos", "em_andamento", "misto")))) {
        c[key]?.let { array ->
            require(array.jsonArray.size == areasIA.size)
            array.jsonArray.forEachIndexed { n, item ->
                val o = item.jsonObject
                require(o.keys == if (key == "rotina") setOf("area", field, "origem") else setOf("area", field))
                require(o["area"] == JsonPrimitive(areasIA[n]))
                require(values.any { o[field] == JsonPrimitive(it) })
                if (key == "rotina") require(o["origem"] == JsonPrimitive("usuario"))
            }
        }
    }
    c["leitura"]?.jsonObject?.let { r ->
        require(r.keys == setOf("estados", "fontes"))
        for ((key, vocabulary) in listOf("estados" to estadosLeituraIA, "fontes" to listOf("usuario", "librera"))) {
            val items = r[key]!!.jsonArray
            require(items == JsonArray(vocabulary.filter { JsonPrimitive(it) in items }.map { JsonPrimitive(it) }))
        }
        require(r["estados"]!!.jsonArray.isEmpty() == r["fontes"]!!.jsonArray.isEmpty())
    }
    return c
}

/** Mesmo contrato reduzido v1; a seleção de áreas continua sendo da sessão. */
fun projetarBundleIA(bundle: JsonObject, scopes: List<String>, today: String): JsonObject {
    com.fintips.motor.triagem.validarBundle(bundle)
    val date=kotlinx.datetime.LocalDate.parse(today)
    val life=bundle["vida"]!!.jsonObject
    val tasks=life["tarefas"]!!.jsonArray.map { it.jsonObject }.filter { t -> t["inicio"]!!.jsonPrimitive.content<=today && (t["repetir"]==JsonPrimitive(true) || t["inicio"]==JsonPrimitive(today)) }
    val done=life["registros"]!!.jsonArray.map { it.jsonObject }.filter { it["dia"]==JsonPrimitive(today) }.map { it["tarefaId"] }.toSet()
    val fronts=areasIA.map { a -> val ts=tasks.filter { it["atributo"]==JsonPrimitive(a) };FrenteParaIA(a,ts.size,ts.count { it["id"] in done }) }
    val plans=life["planos"]!!.jsonArray.map { val p=it.jsonObject;PlanoParaIA(p["atributo"]!!.jsonPrimitive.content,p["concluido"]!!.jsonPrimitive.boolean) }
    val reading=if("leitura" !in scopes) emptyList() else bundle["leitura"]!!.jsonObject["livros"]!!.jsonArray.map {
        val b=it.jsonObject;val obs=b["observacoes"]!!.jsonArray.map { it.jsonObject }
        val pace=com.fintips.motor.vida.ritmoDeLeitura(obs.map { p -> com.fintips.motor.vida.PosicaoDeLeitura(kotlinx.datetime.LocalDate.parse(p["dia"]!!.jsonPrimitive.content),p["progresso_bp"]!!.jsonPrimitive.int) },date,
            b["prazo"]?.jsonPrimitive?.content?.takeIf { it.isNotEmpty() }?.let { kotlinx.datetime.LocalDate.parse(it) },b["dias_semana"]?.takeUnless { it==JsonNull }?.jsonPrimitive?.int)
        val source=obs.maxByOrNull { p -> p["dia"]!!.jsonPrimitive.content }?.get("origem") ?: b["fonte"]!!
        LeituraParaIA(pace.estado,source.jsonPrimitive.content)
    }
    return projetarContextoIA(fronts,plans,reading,scopes)
}
