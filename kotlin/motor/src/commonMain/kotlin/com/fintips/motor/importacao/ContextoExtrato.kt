package com.fintips.motor.importacao

import com.fintips.motor.Dinheiro
import com.fintips.motor.ofx.lerOfx
import kotlinx.datetime.LocalDate
import kotlinx.serialization.json.*

private const val MAX_SAFE = 9007199254740991L
private fun safe(n: Long): Long { require(n in -MAX_SAFE..MAX_SAFE); return n }
private fun soma(values: Iterable<Long>) = values.fold(0L) { a,b -> safe(a+b) }

fun temSaldoDeclarado(raw: String)=Regex("<BALAMT>\\s*[^<\\s]",RegexOption.IGNORE_CASE).containsMatchIn(raw)

/** Projeção por lista fechada. Memo, conta, banco, FITID e nome do arquivo não saem. */
fun contextosExtratos(arquivos: JsonArray, sal: String): Pair<JsonObject, JsonObject> {
    val movimentos = mutableListOf<MovimentoImportado>()
    require(arquivos.size <= 20)
    val vistos=mutableSetOf<List<String>>(); val contas=mutableSetOf<List<String>>()
    val meses=mutableMapOf<String,MutableList<Long>>(); val inicios=mutableListOf<String>();val fins=mutableListOf<String>()
    var conferidos=0;var divergentes=0;var naoConferidos=0
    for(el in arquivos) {
        val e=el.jsonObject;val raw=e["ofx"]!!.jsonPrimitive.content
        require(raw.encodeToByteArray().size<=1024*1024 && Regex("<BANKTRANLIST>",RegexOption.IGNORE_CASE).findAll(raw).count()==1 && Regex("<ACCTID>\\s*[^<\\s]",RegexOption.IGNORE_CASE).containsMatchIn(raw))
        val blocks=Regex("<STMTTRN>(.*?)</STMTTRN>",setOf(RegexOption.IGNORE_CASE,RegexOption.DOT_MATCHES_ALL)).findAll(raw).toList()
        require(Regex("<STMTTRN>",RegexOption.IGNORE_CASE).findAll(raw).count()==blocks.size && raw.contains("</BANKTRANLIST>",ignoreCase=true))
        require(blocks.all { Regex("<FITID>\\s*[^<\\s]",RegexOption.IGNORE_CASE).containsMatchIn(it.groupValues[1]) })
        val temSaldo=temSaldoDeclarado(raw)
        val originais=mutableMapOf<String,String>();val extrato=lerOfx(raw,sal,originais)
        require(extrato.conta.moeda=="BRL" && extrato.transacoes.size<=10000)
        val conta=listOf(extrato.conta.idHash,extrato.conta.idBanco,extrato.conta.instituicao);contas.add(conta)
        inicios.add(extrato.periodoInicio.toString());fins.add(extrato.periodoFim.toString())
        safe(extrato.saldoDeclarado.centavos);soma(extrato.transacoes.map { safe(it.valor.centavos) })
        val abertura=e["saldo_inicial"]?.takeUnless { it==JsonNull }?.jsonPrimitive?.also { require(it.isString) }?.content
        if(abertura==null || !temSaldo) naoConferidos++ else {
            require(Regex("^-?\\d{1,12}([.,]\\d{1,2})?$").matches(abertura))
            if(extrato.concilia(Dinheiro.de(abertura)).bate) conferidos++ else divergentes++
        }
        for(tx in extrato.transacoes) {
            val valor=safe(tx.valor.centavos)
            val chave=conta+listOf(originais.getValue(tx.id),tx.momento.instante.toString(),valor.toString())
            if(vistos.add(chave)) {
                meses.getOrPut(tx.mes) { mutableListOf() }.add(valor)
                movimentos.add(MovimentoImportado(tx.mes, valor, grupoImportado(tx.memoBruto, valor)))
            }
        }
        require(vistos.size<=50000)
    }
    val linhas=meses.keys.sorted().map { mes -> val vs=meses.getValue(mes);buildJsonObject {
        val entradas=soma(vs.filter { it>0 });val saidas=soma(vs.filter { it<0 }.map { -it })
        put("mes",mes);put("transacoes",vs.size);put("entradas_centavos",entradas);put("saidas_centavos",saidas);put("liquido_centavos",safe(entradas-saidas))
    } }
    val context = buildJsonObject {
        put("schema_version",1);put("estado",if(arquivos.isEmpty()) "sem_extrato" else "importado")
        put("arquivos",arquivos.size);put("contas",contas.size);put("transacoes",vistos.size)
        put("inicio",inicios.minOrNull()?.let { JsonPrimitive(it) } ?: JsonNull);put("fim",fins.maxOrNull()?.let { JsonPrimitive(it) } ?: JsonNull)
        for(k in listOf("entradas_centavos","saidas_centavos","liquido_centavos")) put(k,soma(linhas.map { it[k]!!.jsonPrimitive.long }))
        put("meses",JsonArray(linhas));putJsonObject("conciliacao") { put("conferidos",conferidos);put("divergentes",divergentes);put("nao_conferidos",naoConferidos) }
        put("classificacao","pendente");put("saldo_disponivel_centavos",JsonNull)
    }
    return context to resumoFluxos(movimentos)
}

fun contextoExtratos(arquivos: JsonArray, sal: String) = contextosExtratos(arquivos, sal).first
fun fluxosExtratos(arquivos: JsonArray, sal: String) = contextosExtratos(arquivos, sal).second

/** Valida novamente o bloco antes do HTTP; não aceita texto arbitrário do WebView. */
fun validarContextoExtratos(c: JsonObject): JsonObject {
    require(c.keys==setOf("schema_version","estado","arquivos","contas","transacoes","inicio","fim","entradas_centavos","saidas_centavos","liquido_centavos","meses","conciliacao","classificacao","saldo_disponivel_centavos"))
    require(c["schema_version"]==JsonPrimitive(1) && c["estado"] in listOf(JsonPrimitive("importado"),JsonPrimitive("sem_extrato")) && c["classificacao"]==JsonPrimitive("pendente") && c["saldo_disponivel_centavos"]==JsonNull)
    for(k in listOf("arquivos","contas","transacoes","entradas_centavos","saidas_centavos","liquido_centavos")) require(!c[k]!!.jsonPrimitive.isString && safe(c[k]!!.jsonPrimitive.long).let { it>=0 || k=="liquido_centavos" })
    for(k in listOf("inicio","fim")) if(c[k]!=JsonNull) { require(c[k]!!.jsonPrimitive.isString);LocalDate.parse(c[k]!!.jsonPrimitive.content) }
    require(c["meses"]!!.jsonArray.size<=1200)
    c["meses"]!!.jsonArray.forEach { row -> val r=row.jsonObject
        require(r.keys==setOf("mes","transacoes","entradas_centavos","saidas_centavos","liquido_centavos"))
        require(r["mes"]!!.jsonPrimitive.isString && Regex("^\\d{4}-(0[1-9]|1[0-2])$").matches(r["mes"]!!.jsonPrimitive.content))
        for(k in listOf("transacoes","entradas_centavos","saidas_centavos","liquido_centavos")) require(!r[k]!!.jsonPrimitive.isString && safe(r[k]!!.jsonPrimitive.long).let { it>=0 || k=="liquido_centavos" })
    }
    val conciliacao=c["conciliacao"]!!.jsonObject;require(conciliacao.keys==setOf("conferidos","divergentes","nao_conferidos"))
    conciliacao.values.forEach { require(!it.jsonPrimitive.isString && it.jsonPrimitive.int in 0..20) }
    return c
}
