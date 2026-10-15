package com.fintips.motor

import com.fintips.motor.ofx.lerOfx
import com.fintips.motor.vida.*
import kotlinx.datetime.LocalDate
import kotlinx.serialization.json.*

/** Contrato embarcado, puro e sem I/O. Nenhuma operação grava arquivos ou usa rede. */
fun executarMotorLocal(operacao: String, i: JsonObject): JsonObject = when (operacao) {
    "status" -> buildJsonObject { put("motor", "kotlin"); put("schema_version", 1) }
    "leitura.ritmo" -> {
        val ps = i.array("points"); require(ps.size <= 10000)
        val r = ritmoDeLeitura(ps.map { it.jsonObject.let { p -> PosicaoDeLeitura(LocalDate.parse(p.text("dia")), p.integer("progresso_bp")) } },
            LocalDate.parse(i.text("today")), i.optionalText("deadline")?.let { LocalDate.parse(it) },
            if (i["reading_days"] == null || i["reading_days"] == JsonNull) null else i.integer("reading_days"))
        buildJsonObject {
            put("estado", r.estado); put("progresso_bp", r.progressoBp?.let { JsonPrimitive(it) } ?: JsonNull)
            put("amostras", r.amostras); put("intervalo_dias", r.intervaloDias); put("avanco_bp", r.avancoBp)
            put("previsao_dias", r.previsaoDias?.let { JsonPrimitive(it) } ?: JsonNull)
            put("prazo_dias", r.prazoDias?.let { JsonPrimitive(it) } ?: JsonNull)
            put("necessario_bp_dia", r.necessarioBpDia?.let { JsonPrimitive(it) } ?: JsonNull)
            put("meta_bp_sessao", r.metaBpSessao?.let { JsonPrimitive(it) } ?: JsonNull)
            put("historico_reiniciado", r.historicoReiniciado); put("preliminar", r.preliminar)
        }
    }
    "vida.frentes" -> {
        val tasks = i.array("tasks"); require(tasks.size <= 10000)
        val ids = mutableSetOf<String>(); val missions = mutableListOf<Missao>(); val records = mutableListOf<RegistroDeMissao>()
        val today = LocalDate.parse(i.text("today"))
        tasks.forEach { el ->
            val t = el.jsonObject; val id = t.text("id")
            require(id.length in 1..128 && ids.add(id))
            val area = t.text("area"); require(area in Atributo.entries.map { it.sigla })
            missions.add(Missao(id, "", Atributo.de(area)!!, Cadencia.DIARIA))
            if (t.boolean("done")) records.add(RegistroDeMissao(id, today, OrigemDoRegistro.USUARIO))
        }
        val state = montarTela(Vida(missions, records), today)
        buildJsonObject {
            put("done", state.feitasHoje); put("total", state.totalDeHoje)
            putJsonArray("fronts") { state.frentes.forEach { f -> addJsonObject {
                put("area", f.atributo.sigla); put("total", f.missoes); put("done", f.cumpridas); put("pct", f.pct)
            } } }
        }
    }
    "ia.contexto" -> {
        val fs = i.array("fronts"); val ps = i.array("plans"); val rs = i.array("reading")
        require(fs.size == 6 && ps.size <= 10000 && rs.size <= 10000)
        projetarContextoIA(
            fs.map { it.jsonObject.let { f -> FrenteParaIA(f.text("area"), f.integer("total"), f.integer("done")) } },
            ps.map { it.jsonObject.let { p -> PlanoParaIA(p.text("area"), p.boolean("done")) } },
            rs.map { it.jsonObject.let { r -> LeituraParaIA(r.text("state"), r.text("source")) } },
            i.array("scopes").map { it.jsonPrimitive.also { p -> require(p.isString) }.content })
    }
    "extrato.conferir" -> {
        val raw = i.text("ofx"); require(raw.encodeToByteArray().size <= 1024 * 1024)
        val opening = i.text("saldo_inicial")
        require(Regex("^-?\\d{1,12}([.,]\\d{1,2})?$").matches(opening))
        // Conferência de saldo, nunca classificação baseada no fluxo default do parser.
        val e = lerOfx(raw, sal = "conferencia-local-nao-exportavel")
        require(e.transacoes.size <= 10000 && e.conta.moeda == "BRL")
        val c = e.concilia(Dinheiro.de(opening))
        buildJsonObject {
            put("inicio", e.periodoInicio.toString()); put("fim", e.periodoFim.toString())
            put("saldo_centavos", e.saldoDeclarado.centavos); put("transacoes", e.transacoes.size)
            put("conciliado", c.bate); put("diferenca_centavos", c.diferenca.centavos)
        }
    }
    else -> error("operação indisponível")
}

private fun JsonObject.array(k: String) = this[k]!!.jsonArray
private fun JsonObject.text(k: String) = this[k]!!.jsonPrimitive.also { require(it.isString) }.content
private fun JsonObject.optionalText(k: String) = if (this[k] == null || this[k] == JsonNull) null else text(k).takeIf { it.isNotEmpty() }
private fun JsonObject.integer(k: String) = this[k]!!.jsonPrimitive.also { require(!it.isString) }.int
private fun JsonObject.boolean(k: String) = this[k]!!.jsonPrimitive.also { require(!it.isString) }.boolean
