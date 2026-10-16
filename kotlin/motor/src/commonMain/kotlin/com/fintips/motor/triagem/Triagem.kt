package com.fintips.motor.triagem

import com.fintips.motor.sha256Hex
import kotlinx.datetime.LocalDate
import kotlinx.serialization.json.*

internal val catalogo = Json.parseToJsonElement(CATALOGO_JSON).jsonObject
internal val tipos = catalogo["tipos"]!!.jsonObject
internal fun JsonObject.obj(k: String) = this[k]!!.jsonObject
internal fun JsonObject.arr(k: String) = this[k]!!.jsonArray
internal fun JsonObject.str(k: String) = this[k]!!.jsonPrimitive.also { require(it.isString) }.content
private fun texto(v: JsonElement?, limit: Int = 4000) = v is JsonPrimitive && v.isString && v.content.trim().isNotEmpty() && v.content.length <= limit
private fun inteiro(v: JsonElement?, lo: Long = 0, hi: Long = 9_000_000_000_000L): Boolean = v is JsonPrimitive && !v.isString && v.longOrNull?.let { it in lo..hi } == true
private fun dia(v: JsonElement?) = v is JsonPrimitive && v.isString && runCatching { LocalDate.parse(v.content).toString() == v.content }.getOrDefault(false)
private fun exact(v: JsonObject, vararg keys: String) = v.keys == keys.toSet()
private fun absent(v: JsonElement?) = v == null || v == JsonNull || v == JsonPrimitive("")
private fun canonico(v: JsonElement): String = when(v) {
    is JsonObject -> v.keys.sorted().joinToString(",", "{", "}") { JsonPrimitive(it).toString()+":"+canonico(v[it]!!) }
    is JsonArray -> v.joinToString(",", "[", "]") { canonico(it) }
    else -> v.toString()
}
internal fun digest(v: JsonElement) = sha256Hex(canonico(v))
internal fun fields(tipo: String) = tipos[tipo]!!.jsonObject.obj("campos")
internal fun validarCampos(tipo: String, campos: JsonObject, completo: Boolean = true) {
    require(tipo in tipos)
    val specs = fields(tipo); require(specs.keys.containsAll(campos.keys))
    specs.forEach { (k,e) ->
        val s = e.jsonObject; val v = campos[k]
        if (absent(v)) { require(!completo || s["obrigatorio"] == JsonPrimitive(false)); return@forEach }
        require(when(s.str("tipo")) {
            "texto" -> texto(v)
            "data" -> dia(v)
            "inteiro" -> inteiro(v,s["minimo"]!!.jsonPrimitive.long,s["maximo"]!!.jsonPrimitive.long)
            "booleano" -> v == JsonPrimitive(true) || v == JsonPrimitive(false)
            "opcao" -> v in s.arr("opcoes")
            else -> false
        })
    }
}
private fun ref(a: JsonObject) = a.str("tipo") to a.str("id")
internal fun assets(b: JsonObject): List<JsonObject> = buildList {
    listOf("tarefa" to "tarefas", "plano" to "planos", "medida" to "medidas").forEach { (type,col) ->
        b.obj("vida").arr(col).forEach { el -> val a=el.jsonObject
            val f=buildJsonObject { a.filterKeys { it in fields(type) }.forEach { (k,v)->put(k,v) }; if(type=="medida") put("rotulo",a["app"]!!) }
            add(buildJsonObject { put("id",a["id"]!!);put("tipo",type);put("campos",f) })
        }
    }
    b.obj("leitura").arr("livros").forEach { el -> val a=el.jsonObject
        val f=buildJsonObject {
            a.filter { (k,v) -> k in fields("livro") && v != JsonNull }.forEach { (k,v)->put(k,v) }
            a.arr("observacoes").map { it.jsonObject }.maxByOrNull { it.str("dia") }?.let { put("progresso_bp",it["progresso_bp"]!!) }
        }
        add(buildJsonObject { put("id",a["id"]!!);put("tipo","livro");put("campos",f) })
    }
    addAll(b.obj("caderno").arr("assets").map { it.jsonObject })
}
internal fun validarRelacao(r: JsonObject, refs: Set<Pair<String,String>>) {
    require(exact(r,"de","para","tipo","porque") && r["tipo"] in catalogo.arr("relacoes") && texto(r["porque"]))
    for(k in listOf("de","para")) require(exact(r.obj(k),"tipo","id") && ref(r.obj(k)) in refs)
    require(r["de"] != r["para"])
}
fun validarBundle(b: JsonObject): JsonObject {
    require(exact(b,"schema_version","vida","leitura","caderno") && b["schema_version"] == JsonPrimitive(1))
    val v=b.obj("vida"); val l=b.obj("leitura"); val c=b.obj("caderno")
    require(v["schema_version"] == JsonPrimitive(1) && listOf("tarefas","planos","registros","medidas").all { v[it] is JsonArray })
    require(l["schema_version"] == JsonPrimitive(1) && l["livros"] is JsonArray)
    require(exact(c,"schema_version","assets","relacoes","aplicacoes") && c["schema_version"] == JsonPrimitive(1) && listOf("assets","relacoes","aplicacoes").all { c[it] is JsonArray })
    val all=assets(b); val refs=all.map(::ref).toSet()
    require(all.size <= 3000 && c.arr("relacoes").size <= 3000 && c.arr("aplicacoes").size <= 256 && refs.size == all.size)
    all.forEach { require(texto(it["id"],128)); validarCampos(it.str("tipo"),it.obj("campos")) }
    val tasks=v.arr("tarefas").map { it.jsonObject.str("id") }.toSet()
    val records=v.arr("registros").map { it.jsonObject }
    require(records.map { it.str("tarefaId") to it.str("dia") }.toSet().size == records.size)
    records.forEach { require(it.str("tarefaId") in tasks && dia(it["dia"]) && it["origem"] == JsonPrimitive("usuario")) }
    v.arr("planos").forEach { require(it.jsonObject["concluido"] in listOf(JsonPrimitive(true),JsonPrimitive(false)) && it.jsonObject["porque"]!!.jsonPrimitive.isString && it.jsonObject["proximoPasso"]!!.jsonPrimitive.isString) }
    v.arr("medidas").forEach { require(it.jsonObject["origem"] == JsonPrimitive("usuario")) }
    c.arr("assets").forEach { el -> val a=el.jsonObject;val p=a.obj("proveniencia")
        require(tipos[a.str("tipo")]!!.jsonObject["destino"]==JsonPrimitive("caderno") && exact(a,"id","tipo","campos","proveniencia"))
        require(exact(p,"origem","porque","quando","por_quem","proposta") && p["origem"]==JsonPrimitive("usuario") && texto(p["porque"]) && dia(p["quando"]) && texto(p["por_quem"],128) && texto(p["proposta"],128))
    }
    l.arr("livros").forEach { el -> val a=el.jsonObject
        require(a["dias_semana"]==JsonNull || inteiro(a["dias_semana"],1,7))
        require(a["fonte"] in listOf(JsonPrimitive("usuario"),JsonPrimitive("librera")) && a["perfil"]!!.jsonPrimitive.isString && (a["chave"] == JsonNull || a["chave"]!!.jsonPrimitive.isString))
        val obs=a.arr("observacoes").map { it.jsonObject }; require(obs.map { it.str("dia") }.toSet().size == obs.size)
        obs.forEach { p -> require(dia(p["dia"]) && inteiro(p["progresso_bp"],0,10000) && inteiro(p["tempo_ms"],1,8_640_000_000_000_000) && p["origem"] in listOf(JsonPrimitive("usuario"),JsonPrimitive("librera"))) }
    }
    c.arr("relacoes").forEach { validarRelacao(it.jsonObject,refs) }
    val receipts=c.arr("aplicacoes").map { it.jsonObject }
    receipts.forEach { require(exact(it,"id","hash") && texto(it["id"],128) && Regex("[a-f0-9]{64}").matches(it.str("hash"))) }
    require(receipts.map { it.str("id") }.toSet().size == receipts.size)
    return b
}
private fun preparar(b: JsonObject, drafts: JsonArray, rels: JsonArray, id: String): JsonObject {
    validarBundle(b); require(id.trim().isNotEmpty() && id.length <= 128 && drafts.size in 1..20 && rels.size <= 30)
    val refs=assets(b).map(::ref).toMutableSet(); val used=mutableSetOf<Pair<String,String>>()
    drafts.forEach { el -> val d=el.jsonObject
        require(exact(d,"id","tipo","campos","porque","acao") && d.str("acao") in listOf("criar","atualizar") && texto(d["id"],128) && texto(d["porque"]))
        validarCampos(d.str("tipo"),d.obj("campos"))
        val key=ref(d); require(used.add(key) && ((d.str("acao")=="criar" && key !in refs) || (d.str("acao")=="atualizar" && key in refs))); refs.add(key)
    }
    rels.forEach { validarRelacao(it.jsonObject,refs) }
    return buildJsonObject { put("schema_version",1);put("id",id);put("base_hash",digest(b));put("operacoes",drafts);put("relacoes",rels) }
}
private fun aplicar(b: JsonObject, p: JsonObject, confirmed: JsonElement?, today: JsonElement?, ms: JsonElement?): JsonObject {
    validarBundle(b); require(confirmed==JsonPrimitive(true) && dia(today) && inteiro(ms,1,8_640_000_000_000_000))
    require(exact(p,"schema_version","id","base_hash","operacoes","relacoes") && p["schema_version"]==JsonPrimitive(1))
    val receipt=b.obj("caderno").arr("aplicacoes").firstOrNull { it.jsonObject["id"] == p["id"] }
    if(receipt!=null) {
        require(receipt.jsonObject["hash"]==JsonPrimitive(digest(p)))
        return buildJsonObject { put("bundle",b);put("repetido",true);put("id",p["id"]!!) }
    }
    require(p["base_hash"]==JsonPrimitive(digest(b)))
    require(preparar(b,p.arr("operacoes"),p.arr("relacoes"),p.str("id"))==p)
    val collections=linkedMapOf<String,MutableList<JsonElement>>()
    listOf("vida.tarefas","vida.planos","vida.medidas","leitura.livros","caderno.assets").forEach { path ->
        val (a,z)=path.split('.'); collections[path]=b.obj(a).arr(z).toMutableList()
    }
    p.arr("operacoes").forEach { el -> val op=el.jsonObject;val type=op.str("tipo");val id=op.str("id");val dest=tipos[type]!!.jsonObject.str("destino")
        val col=collections[if(dest=="caderno") "caderno.assets" else dest]!!
        val idx=col.indexOfFirst { it.jsonObject["id"]==op["id"] && (dest!="caderno" || it.jsonObject["tipo"]==op["tipo"]) }
        val old=if(idx<0) buildJsonObject {} else col[idx].jsonObject
        val prov=buildJsonObject { put("origem","usuario");put("porque",op["porque"]!!);put("quando",today!!);put("por_quem","triagem_confirmada");put("proposta",p["id"]!!) }
        val record=buildJsonObject {
            if(dest=="caderno") { put("id",id);put("tipo",type);putJsonObject("campos") { old["campos"]?.jsonObject?.forEach { (k,v)->put(k,v) };op.obj("campos").forEach { (k,v)->put(k,v) } };put("proveniencia",prov) }
            else {
                if(type=="plano") { put("porque","");put("proximoPasso","");put("prazo","");put("concluido",false) }
                if(type=="livro") { put("fonte","usuario");put("chave",JsonNull);put("perfil","");put("prazo","");put("dias_semana",JsonNull);putJsonArray("observacoes") {} }
                old.forEach { (k,v)->put(k,v) };put("id",id)
                op.obj("campos").forEach { (k,v) -> if(k!="progresso_bp" && !(type=="medida" && k=="rotulo")) {
                    val normalized=if(type=="plano" && k in listOf("porque","proximoPasso","prazo") && v==JsonNull) JsonPrimitive("")
                        else if(type=="livro" && k=="dias_semana" && v==JsonPrimitive("")) JsonNull
                        else if(type=="livro" && k=="prazo" && v==JsonNull) JsonPrimitive("") else v
                    put(k,normalized)
                } }
                put("proveniencia",prov)
                if(type=="medida") { put("app",op.obj("campos")["rotulo"]!!);put("origem","usuario") }
                if(type=="livro" && !absent(op.obj("campos")["progresso_bp"])) {
                    val obs=(old["observacoes"] as? JsonArray ?: JsonArray(emptyList())).filter { it.jsonObject["dia"]!=today } +
                        buildJsonObject { put("dia",today!!);put("progresso_bp",op.obj("campos")["progresso_bp"]!!);put("tempo_ms",ms!!);put("origem","usuario") }
                    put("observacoes",JsonArray(obs.sortedBy { it.jsonObject.str("dia") }))
                }
            }
        }
        if(idx<0) col.add(record) else col[idx]=record
    }
    val next=buildJsonObject {
        b.forEach { (section, value) ->
            if(section in listOf("vida","leitura","caderno")) put(section,buildJsonObject {
                value.jsonObject.forEach { (k,v) -> put(k,collections["$section.$k"]?.let(::JsonArray) ?: v) }
                if(section=="caderno") {
                    put("relacoes",JsonArray((b.obj("caderno").arr("relacoes")+p.arr("relacoes")).distinct()))
                    put("aplicacoes",JsonArray((b.obj("caderno").arr("aplicacoes")+buildJsonObject { put("id",p["id"]!!);put("hash",digest(p)) }).takeLast(256)))
                }
            }) else put(section,value)
        }
    }
    validarBundle(next)
    return buildJsonObject { put("bundle",next);put("repetido",false);put("id",p["id"]!!) }
}
internal fun contexto(b: JsonObject, drafts: JsonArray, today: String): JsonObject {
    validarBundle(b);require(dia(JsonPrimitive(today)) && drafts.size in 1..20)
    val all=assets(b);val local=all.take(100).map { a ->
        if(a.str("tipo")!="livro") a else buildJsonObject {
            a.forEach { (k,v)->put(k,v) }
            putJsonObject("campos") {
                a.obj("campos").filterKeys { it!="progresso_bp" }.forEach { (k,v)->put(k,v) }
                b.obj("leitura").arr("livros").first { it.jsonObject["id"]==a["id"] }.jsonObject.arr("observacoes")
                    .map { it.jsonObject }.filter { it.str("dia")<=today }.maxByOrNull { it.str("dia") }?.let { put("progresso_bp",it["progresso_bp"]!!) }
            }
        }
    };val map=linkedMapOf<String,JsonElement>();val options=mutableListOf<JsonElement>()
    fun item(a: JsonObject, ref: String): JsonObject {
        val type=a.str("tipo");val fs=a.obj("campos");validarCampos(type,fs,false);val specs=fields(type)
        val missing=specs.filter { (k,v) -> v.jsonObject["obrigatorio"]==JsonPrimitive(true) && absent(fs[k]) }.keys
        val values=buildJsonObject { fs.filter { (k,v)->specs[k]!!.jsonObject["publicavel"]==JsonPrimitive(true) && !absent(v) }.forEach { (k,v)->put(k,v) } }
        map[ref]=buildJsonObject { put("tipo",type);put("id",a["id"]!!);put("titulo",fs["titulo"] ?: fs["rotulo"] ?: JsonPrimitive("Registro")) }
        val calc=buildJsonArray {
            if(type=="objetivo" && inteiro(values["meta"]) && values["meta"]!!.jsonPrimitive.long>0 && inteiro(values["atual"])) {
                val n=values["atual"]!!.jsonPrimitive.long;val d=values["meta"]!!.jsonPrimitive.long
                addJsonObject { put("metodo","razao_bp");put("numerador",n);put("denominador",d);put("resultado",minOf(10000,n*10000/d)) }
            }
        }
        return buildJsonObject { put("ref",ref);put("tipo",type);put("preenchidos",JsonArray(specs.keys.filter { specs[it]!!.jsonObject["presenca_publica"]==JsonPrimitive(true) && !absent(fs[it]) }.map(::JsonPrimitive)));put("faltantes",JsonArray(missing.map(::JsonPrimitive)));put("valores",values);put("calculos",calc) }
    }
    val items=local.mapIndexed { i,a->item(a,"item_$i") }
    fun option(action: String, draft: String, field: String?=null, target: String?=null) { options.add(buildJsonObject {
        put("acao",action);put("rascunho",draft);put("campo",field?.let(::JsonPrimitive) ?: JsonNull);put("alvo",target?.let(::JsonPrimitive) ?: JsonNull)
    }) }
    val ds=drafts.mapIndexed { i,el -> val d=el.jsonObject
        require(exact(d,"id","tipo","campos","porque","acao") && d.str("acao") in listOf("criar","atualizar") && texto(d["id"],128) && texto(d["porque"]))
        val ref="rascunho_$i";val public=item(d,ref)
        public.arr("faltantes").forEach { option("perguntar",ref,it.jsonPrimitive.content) }
        if(public.arr("faltantes").isEmpty()) {
            option("revisar",ref)
            fields(d.str("tipo")).forEach { (k,v) -> if(v.jsonObject["tipo"]==JsonPrimitive("inteiro") && JsonPrimitive(k) !in public.arr("preenchidos")) option("sugerir_valor",ref,k) }
        }
        val title=(d.obj("campos")["titulo"]?.jsonPrimitive?.content ?: "").lowercase().trim()
        local.forEachIndexed { j,a ->
            val other=(a.obj("campos")["titulo"]?.jsonPrimitive?.content ?: "").lowercase().trim()
            // Python \w inclui Unicode; ambos mantêm letras/números/underscore.
            val words=Regex("[\\p{L}\\p{N}_]{4,}").findAll(title).map { it.value }.toSet()
            val overlap=words.intersect(Regex("[\\p{L}\\p{N}_]{4,}").findAll(other).map { it.value }.toSet())
            if(d["id"]!=a["id"] && ((title.isNotEmpty() && title==other)||overlap.size>=2)) option("correlacionar",ref,target="item_$j")
        }
        public
    }
    options.sortBy { if(it.jsonObject["acao"]==JsonPrimitive("perguntar")) 0 else 1 }
    val opts=options.take(100).mapIndexed { i,o -> buildJsonObject { o.jsonObject.forEach { (k,v)->put(k,v) };put("id","opcao_$i") } }
    val reverse=map.entries.associate { ref(it.value.jsonObject) to it.key }
    val rels=b.obj("caderno").arr("relacoes").mapNotNull { el -> val r=el.jsonObject;val a=reverse[ref(r.obj("de"))];val z=reverse[ref(r.obj("para"))]
        if(a==null||z==null) null else buildJsonObject { put("de",a);put("para",z);put("tipo",r["tipo"]!!) }
    }
    val fronts=JsonArray(listOf("FOR","AGI","VIT","INT","FOC","OURO").map { area ->
        val active=b.obj("vida").arr("tarefas").map { it.jsonObject }.filter {
            it["atributo"]==JsonPrimitive(area) && if(it["repetir"]==JsonPrimitive(true)) it.str("inicio")<=today else it.str("inicio")==today
        }
        val done=active.count { a -> b.obj("vida").arr("registros").any { it.jsonObject["tarefaId"]==a["id"] && it.jsonObject["dia"]==JsonPrimitive(today) } }
        buildJsonObject { put("area",area);put("total",active.size);put("done",done) }
    })
    val states=com.fintips.motor.executarMotorLocal("ia.contexto",buildJsonObject {
        put("fronts",fronts);putJsonArray("plans") {};putJsonArray("reading") {};putJsonArray("scopes") { add("rotina") }
    }).arr("rotina")
    val metrics=buildJsonArray {
        fronts.forEachIndexed { index,el -> val f=el.jsonObject;val ref="grupo_$index"
            map[ref]=buildJsonObject { put("tipo","area");put("id",f["area"]!!);put("titulo",f["area"]!!) }
            addJsonObject { put("ref",ref);put("tipo","tarefas");put("previstas",f["total"]!!);put("conclusoes_registradas",f["done"]!!);put("evidencia",states[index].jsonObject["evidencia"]!!) }
        }
        local.forEachIndexed { index,a -> if(a.str("tipo")=="livro") {
            val book=b.obj("leitura").arr("livros").first { it.jsonObject["id"]==a["id"] }.jsonObject
            val points=JsonArray(book.arr("observacoes").filter { it.jsonObject.str("dia")<=today }.map { o -> buildJsonObject {
                put("dia",o.jsonObject["dia"]!!);put("progresso_bp",o.jsonObject["progresso_bp"]!!)
            } })
            val calc=com.fintips.motor.executarMotorLocal("leitura.ritmo",buildJsonObject {
                put("points",points);put("today",today);put("deadline",book["prazo"] ?: JsonNull);put("reading_days",book["dias_semana"] ?: JsonNull)
            })
            addJsonObject { put("ref","item_$index");put("tipo","leitura");put("calculo",calc) }
        } }
    }
    return buildJsonObject {
        putJsonObject("publico") { put("schema_version",1);put("itens",JsonArray(items));put("rascunhos",JsonArray(ds));put("opcoes",JsonArray(opts));put("relacoes",JsonArray(rels));put("metricas",metrics);put("limitado",all.size>100||options.size>100) }
        put("mapa_local",JsonObject(map))
    }
}
fun executarTriagem(operacao: String, i: JsonObject): JsonObject = when(operacao) {
    "triagem.agente_contexto" -> contextoAgente(i.obj("bundle"),i.arr("rascunhos"),i.str("hoje"))
    "triagem.agente_aplicar" -> resolverAgente(i.obj("bundle"),i.arr("rascunhos"),i.str("hoje"),i.obj("resposta"))
    "triagem.agente_pedido" -> pedidoAgente(i.obj("bundle"),i.arr("rascunhos"),i.str("hoje"))
    "triagem.catalogo" -> catalogo
    "triagem.contexto" -> contexto(i.obj("bundle"),i.arr("rascunhos"),i.str("hoje"))
    "triagem.preparar" -> preparar(i.obj("bundle"),i.arr("rascunhos"),i.arr("relacoes"),i.str("id"))
    "triagem.aplicar" -> aplicar(i.obj("bundle"),i.obj("proposta"),i["confirmado"],i["hoje"],i["tempo_ms"])
    "triagem.validar" -> buildJsonObject { put("valido",true);put("base_hash",digest(validarBundle(i.obj("bundle")))) }
    else -> error("operação de triagem indisponível")
}

private val motivos=listOf("preencher_necessario","revisar_em_lote","evitar_duplicata","ritmo_realista","contexto_relacionado")
/** Constrói corpo HTTPS a partir da fonte local; não aceita projeção do JS. */
fun pedidoOpenAITriagem(bundle: JsonObject, rascunhos: JsonArray, hoje: String): JsonObject {
    val public=contexto(bundle,rascunhos,hoje).obj("publico")
    val schema=buildJsonObject {
        put("type","object");put("additionalProperties",false)
        put("required",JsonArray(listOf("escolha","valor","motivo").map(::JsonPrimitive)))
        putJsonObject("properties") {
            putJsonObject("escolha") { put("type","string");put("enum",JsonArray(public.arr("opcoes").map { it.jsonObject["id"]!! })) }
            putJsonObject("valor") { put("type",JsonArray(listOf(JsonPrimitive("integer"),JsonPrimitive("null")))) }
            putJsonObject("motivo") { put("type","string");put("enum",JsonArray(motivos.map(::JsonPrimitive))) }
        }
    }
    return buildJsonObject {
        putJsonObject("pedido") {
            put("model","gpt-4.1-mini");put("store",false);put("max_output_tokens",256)
            put("instructions","Organize a triagem FinTips usando apenas os contratos abstratos fornecidos. Escolha uma opcao existente. Priorize campos obrigatorios; quando completos, prefira revisao em lote para reduzir toil. Pode sugerir valor inteiro em sugerir_valor quando sustentado pelos numeros. Valores monetarios sao centavos; progresso_bp vai de 0 a 10000. Nunca trate ausencia como zero, deduza motivos, identifique pessoas ou invente ligacoes. Correlacoes sao sugestoes que exigem confirmacao local. Nao ha nomes, origem/destino reais ou texto da conversa.")
            put("input",public.toString())
            putJsonObject("text") { putJsonObject("format") { put("type","json_schema");put("name","fintips_triagem_v1");put("strict",true);put("schema",schema) } }
        }
        put("publico",public)
    }
}
fun validarSugestaoTriagem(public: JsonObject, s: JsonObject): JsonObject {
    require(exact(s,"escolha","valor","motivo") && s.str("motivo") in motivos)
    val option=public.arr("opcoes").firstOrNull { it.jsonObject["id"]==s["escolha"] }?.jsonObject ?: error("opção desconhecida")
    if(option.str("acao")=="sugerir_valor") {
        val draft=public.arr("rascunhos").first { it.jsonObject["ref"]==option["rascunho"] }.jsonObject
        val spec=fields(draft.str("tipo"))[option.str("campo")]!!.jsonObject
        require(inteiro(s["valor"],spec["minimo"]!!.jsonPrimitive.long,spec["maximo"]!!.jsonPrimitive.long))
    } else require(s["valor"]==JsonNull)
    return buildJsonObject { put("opcao",option);put("valor",s["valor"]!!);put("motivo",s["motivo"]!!);put("origem","openai") }
}
