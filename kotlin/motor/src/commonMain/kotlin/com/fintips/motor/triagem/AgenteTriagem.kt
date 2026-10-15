package com.fintips.motor.triagem

import com.fintips.motor.semAcento
import kotlinx.serialization.json.*

private val politica = Json.parseToJsonElement(AGENTE_POLICY_JSON).jsonObject
private fun normalAgente(s: String) = semAcento(s.lowercase())
private fun fechado(o: JsonObject, vararg names: String) = o.keys == names.toSet()

/** A tabela de valores reais só é usada para restaurar referências no aparelho. */
fun contextoAgente(bundle: JsonObject, drafts: JsonArray, hoje: String): JsonObject {
    val base=contexto(bundle,drafts,hoje)
    val values=mutableListOf<JsonElement>();val local=linkedMapOf<String,JsonElement>();val opaque=linkedMapOf<String,String>()
    fun add(owner: String, field: String, value: JsonElement, kind: String, papel: String="campo") {
        if(values.size>=512) return
        val ref="valor_${values.size}"
        values+=buildJsonObject {
            put("ref",ref);put("dono",owner);put("campo",field);put("tipo",kind);put("papel",papel)
            if(kind in listOf("inteiro","booleano","opcao")) put("valor",value)
            if(kind=="texto") {
                val text=normalAgente(value.jsonPrimitive.content);val words=Regex("[a-z]+").findAll(text).map { it.value }.toSet()
                putJsonArray("estrutura") { Regex("[a-z0-9]+").findAll(text).take(200).forEach { m->
                    add(politica.obj("lexico")[m.value]?.jsonPrimitive?.content ?: opaque.getOrPut(m.value) { "opaco_${opaque.size}" })
                } }
                putJsonArray("conceitos") {
                    politica.obj("conceitos").forEach { (k,v)->if(v.jsonArray.any { it.jsonPrimitive.content in words }) add(k) }
                    if("todo dia" in text || "todos os dias" in text) add("recorrente")
                }
            }
        }
        local[ref]=buildJsonObject { put("valor",value);put("campo",field);put("tipo",kind);put("dono",owner) }
    }
    drafts.forEachIndexed { index,el -> val d=el.jsonObject;val owner="rascunho_$index"
        fields(d.str("tipo")).forEach { (field,sp)->val s=sp.jsonObject;val v=d.obj("campos")[field]
            if(s["presenca_publica"]!=JsonPrimitive(true) || v==null || v==JsonNull || v==JsonPrimitive("")) return@forEach
            add(owner,field,v,s.str("tipo"))
            if(s.str("tipo")=="texto" && field in listOf("titulo","descricao")) {
                val original=v.jsonPrimitive.content;val text=normalAgente(original)
                Regex("""(?<![\w.,])([0-7])\s*(?:dias?|vezes|x)\s*(?:por\s*|na\s*|/\s*)(?:semana)(?!\w)""").findAll(text).forEach { m->
                    val n=m.groupValues[1].toInt();if(n>0) add(owner,"dias_semana",JsonPrimitive(n),"inteiro","extraido")
                }
                Regex("""(?:ja\s+li|estou\s+em|progresso\s*(?:de|:)?)\s*([0-9]{1,3})(?:[,.]([0-9]{1,2}))?\s*%(?!\w)""").findAll(text).forEach { m->
                    val n=m.groupValues[1].toInt()*100+m.groupValues[2].padEnd(2,'0').toInt();if(n<=10000) add(owner,"progresso_bp",JsonPrimitive(n),"inteiro","extraido")
                }
                Regex("""(?<![\w.,])([0-9]{1,4})\s*(?:minutos?|min)(?!\w)""").findAll(text).forEach { m->
                    val n=m.groupValues[1].toInt();if(n<=1440 && Regex("""\b(fiquei|usei|registrar|registro|uso)\b""").containsMatchIn(text)) add(owner,"minutos",JsonPrimitive(n),"inteiro","extraido")
                }
                Regex("""r\$\s*([0-9.,]+)""").findAll(text).forEach { m->
                    if(Regex("""[0-9]+(?:[.,][0-9]{1,2})?""").matches(m.groupValues[1])) {
                        val pieces=m.groupValues[1].split('.',',');val whole=pieces[0].toLongOrNull()
                        if(whole!=null && whole<=90_000_000_000L) {
                            val amount=whole*100+(pieces.getOrNull(1)?.padEnd(2,'0')?.toLong() ?: 0L)
                            if(amount<=9_000_000_000_000L) add(owner,"valor_centavos",JsonPrimitive(amount),"inteiro","extraido")
                        }
                    }
                }
                var short=Regex("""[“"]([^”"]{1,300})[”"]""").find(original)?.groupValues?.get(1)
                if(short==null) {
                    val reading=Regex("""^(?:(?:quero|pretendo|planejo)\s+)?(?:(?:comecar a|estou)\s+)?(?:ler|lendo)\s+(.+)$""").find(text)
                    val match=Regex("""^(?:(?:quero|pretendo|planejo)\s+)?(?:(?:começar a|estou)\s+)?(?:ler|lendo)\s+(.+)$""",RegexOption.IGNORE_CASE).find(original)
                    val candidate=if(reading!=null && match!=null) match.groupValues[1] else if(d.str("tipo")=="livro") original else null
                    if(candidate!=null) {
                        val clean=Regex("""\s+(?=\d+\s*(?:dias?|vezes|x|minutos?|min)\b|(?:e\s+)?(?:terminar|acabar)\b|porque\b|at[eé]\b|todos os dias\b)""",RegexOption.IGNORE_CASE).split(candidate,2).first().trim()
                        if(clean.isNotEmpty() && !Regex("""^(mais|menos|um|uma|todo|todos|melhor)\b""").containsMatchIn(normalAgente(clean)) && clean!=original) short=clean
                    }
                }
                if(short!=null) { add(owner,"titulo",JsonPrimitive(short),"texto","titulo_curto");if(d.str("tipo")=="livro" || Regex("[a-z]+").findAll(text).any { m->JsonPrimitive(m.value) in politica.obj("conceitos").arr("leitura") }) add(owner,"titulo",JsonPrimitive("Ler "+short),"texto","acao_leitura") }
            }
        }
    }
    add("catalogo","inicio",JsonPrimitive(hoje),"data","padrao_hoje")
    add("catalogo","repetir",JsonPrimitive(false),"booleano","padrao")
    add("catalogo","repetir",JsonPrimitive(true),"booleano","recorrente")
    tipos.forEach { (_,c)->c.jsonObject.obj("campos").forEach { (field,sp)->val s=sp.jsonObject
        if(s.str("tipo")=="opcao") s.arr("opcoes").forEach { v->
            if(values.none { it.jsonObject["dono"]==JsonPrimitive("catalogo") && it.jsonObject["campo"]==JsonPrimitive(field) && it.jsonObject["valor"]==v }) add("catalogo",field,v,"opcao")
        }
    } }
    val public=JsonObject(base.obj("publico")+mapOf("limitado" to JsonPrimitive(base.obj("publico")["limitado"]==JsonPrimitive(true) || values.size>=512),"valores_disponiveis" to JsonArray(values),"contratos" to buildJsonObject {
        tipos.forEach { (kind,c)->putJsonObject(kind) { c.jsonObject.obj("campos").forEach { (f,sp)->val s=sp.jsonObject
            if(s["presenca_publica"]==JsonPrimitive(true)) put(f,JsonObject(s.filterKeys { it in listOf("tipo","obrigatorio","minimo","maximo","opcoes") }))
        } } }
    }))
    return buildJsonObject { put("publico",public);put("valores_locais",JsonObject(local));put("mapa_local",base["mapa_local"]!!) }
}

private fun objeto(properties: JsonObject)=buildJsonObject {
    put("type","object");put("additionalProperties",false);put("required",JsonArray(properties.keys.map(::JsonPrimitive)));put("properties",properties)
}
private fun enumAgente(values: List<String>)=buildJsonObject { put("type","string");put("enum",JsonArray(values.map(::JsonPrimitive))) }
private fun arrayAgente(item: JsonObject)=buildJsonObject { put("type","array");put("items",item) }
fun schemaAgente(public: JsonObject): JsonObject {
    val refs=public.arr("rascunhos").map { it.jsonObject.str("ref") }+(0..5).map { "novo_$it" }
    val fs=public.obj("contratos").values.flatMap { it.jsonObject.keys }.toSet().sorted()
    val binding=objeto(buildJsonObject { put("campo",enumAgente(fs));put("valor",enumAgente(public.arr("valores_disponiveis").map { it.jsonObject.str("ref") })) })
    val record=objeto(buildJsonObject { put("ref",enumAgente(refs));put("tipo",enumAgente(tipos.keys.toList()));put("campos",arrayAgente(binding)) })
    val all=refs+public.arr("itens").map { it.jsonObject.str("ref") }
    val edge=objeto(buildJsonObject { put("de",enumAgente(all));put("para",enumAgente(all));put("tipo",enumAgente(catalogo.arr("relacoes").map { it.jsonPrimitive.content })) })
    val q=objeto(buildJsonObject { put("ref",enumAgente(refs));put("campo",enumAgente(fs));putJsonObject("texto") { put("type","string") } })
    return objeto(buildJsonObject { put("registros",arrayAgente(record));put("relacoes",arrayAgente(edge));putJsonObject("pergunta") { putJsonArray("anyOf") { add(q);addJsonObject { put("type","null") } } } })
}
fun pedidoAgente(bundle: JsonObject, drafts: JsonArray, hoje: String): JsonObject {
    val public=contextoAgente(bundle,drafts,hoje).obj("publico")
    return buildJsonObject {
        put("model","gpt-4.1-mini");put("store",false);put("max_output_tokens",3000);put("instructions",politica["instrucoes"]!!);put("input",public.toString())
        putJsonObject("text") { putJsonObject("format") { put("type","json_schema");put("name","fintips_agente_v2");put("strict",true);put("schema",schemaAgente(public)) } }
    }
}

fun resolverAgente(bundle: JsonObject, drafts: JsonArray, hoje: String, response: JsonObject): JsonObject {
    val ctx=contextoAgente(bundle,drafts,hoje);val local=ctx.obj("valores_locais")
    require(fechado(response,"registros","relacoes","pergunta") && response.arr("registros").size<=20 && response.arr("relacoes").size<=30)
    val out=drafts.map { it.jsonObject }.toMutableList();val refs=linkedMapOf<String,Int>();out.indices.forEach { refs["rascunho_$it"]=it }
    val seen=mutableSetOf<String>()
    response.arr("registros").forEach { el->val r=el.jsonObject
        require(fechado(r,"ref","tipo","campos") && r.str("tipo") in tipos && seen.add(r.str("ref")))
        val ref=r.str("ref");val kind=r.str("tipo")
        val index=if(Regex("novo_[0-5]").matches(ref)) {
            require(out.size<20);val idx=out.size
            out.add(buildJsonObject { put("id","agente-"+digest(buildJsonArray { add(JsonArray(drafts.map { it.jsonObject["id"]!! }));add(ref) }).take(24));put("tipo",kind);putJsonObject("campos") {};put("acao","criar");put("porque","Organizado pelo agente a partir de referências da conversa; revisão da pessoa.") });refs[ref]=idx;idx
        } else refs[ref] ?: error("referência desconhecida")
        val d=out[index];require(d.str("acao")=="criar" || d.str("tipo")==kind)
        val f=d.obj("campos").filterKeys { it in fields(kind) }.toMutableMap()
        require(r.arr("campos").size<=30);val used=mutableSetOf<String>()
        r.arr("campos").forEach { e->val b=e.jsonObject;require(fechado(b,"campo","valor") && used.add(b.str("campo")))
            val field=b.str("campo");val source=local[b.str("valor")]!!.jsonObject;val spec=fields(kind)[field]!!.jsonObject
            require(spec["presenca_publica"]==JsonPrimitive(true) && spec["tipo"]==source["tipo"])
            if(field in listOf("progresso_bp","minutos","atual")) {
                val owner=if(ref.startsWith("rascunho_")) JsonPrimitive(ref) else r.arr("campos").firstOrNull { it.jsonObject["campo"] in listOf(JsonPrimitive("titulo"),JsonPrimitive("rotulo")) }?.jsonObject?.str("valor")?.let { local[it]?.jsonObject?.get("dono") }
                require(source["dono"]==owner)
            }
            if(spec.str("tipo")!="texto" || field=="porque") require(source["campo"]==JsonPrimitive(field) || field.endsWith("_centavos") && source.str("campo").endsWith("_centavos"))
            val old=f[field]
            if(spec.str("tipo")!="texto" && old!=null && old!=JsonNull && old!=JsonPrimitive("")) require(old==source["valor"])
            f[field]=source["valor"]!!
        }
        validarCampos(kind,JsonObject(f),false)
        out[index]=JsonObject(d+mapOf("tipo" to JsonPrimitive(kind),"campos" to JsonObject(f)))
    }
    val autofilled=mutableSetOf<Pair<Int,String>>()
    for(index in out.indices) {
        val d=out[index];val title=(d.obj("campos")["titulo"] ?: d.obj("campos")["rotulo"])?.jsonPrimitive?.content ?: ""
        val matches=assets(bundle).filter { x->x["tipo"]==d["tipo"] && (d.str("tipo")!="medida" || x.obj("campos")["dia"]==d.obj("campos")["dia"]) && normalAgente((x.obj("campos")["titulo"] ?: x.obj("campos")["rotulo"] ?: JsonPrimitive("")).jsonPrimitive.content).trim()==normalAgente(title).trim() }
        if(d.str("acao")=="criar" && d.str("porque")!="Registro separado por escolha explícita da pessoa na conversa." && title.isNotEmpty() && matches.size==1) {
            val old=matches.single();require(out.indices.none { it!=index && out[it]["id"]==old["id"] && out[it]["tipo"]==old["tipo"] })
            val f=d.obj("campos").toMutableMap()
            fields(d.str("tipo")).forEach { (field,sp)->if(sp.jsonObject["obrigatorio"]==JsonPrimitive(true) && f[field] in listOf(null,JsonNull,JsonPrimitive("")) && field in old.obj("campos")) { f[field]=old.obj("campos")[field]!!;autofilled+=index to field } }
            out[index]=JsonObject(d+mapOf("id" to old["id"]!!,"acao" to JsonPrimitive("atualizar"),"campos" to JsonObject(f)))
        }
    }
    val mapping=linkedMapOf<String,JsonObject>()
    ctx.obj("mapa_local").filterKeys { it.startsWith("item_") }.forEach { (k,v)->mapping[k]=JsonObject(v.jsonObject.filterKeys { it in listOf("tipo","id") }) }
    refs.forEach { (k,i)->mapping[k]=JsonObject(out[i].filterKeys { it in listOf("tipo","id") }) }
    val rels=mutableListOf<JsonElement>()
    response.arr("relacoes").forEach { el->val r=el.jsonObject;require(fechado(r,"de","para","tipo"))
        val edge=buildJsonObject { put("de",mapping[r.str("de")]!!);put("para",mapping[r.str("para")]!!);put("tipo",r["tipo"]!!);put("porque","Relação proposta pelo agente a partir do contexto abstrato; revisão da pessoa.") }
        if(r["de"]!=r["para"] && edge["de"]==edge["para"]) return@forEach
        validarRelacao(edge,mapping.values.map { it.str("tipo") to it.str("id") }.toSet());require(edge !in rels);rels+=edge
    }
    var question: JsonObject?=null
    if(response["pergunta"]!=JsonNull) {
        val q=response.obj("pergunta");require(fechado(q,"ref","campo","texto"));val index=refs[q.str("ref")] ?: error("referência desconhecida");val d=out[index];val spec=fields(d.str("tipo"))[q.str("campo")]!!.jsonObject
        val questionText=q.str("texto");require(questionText.isNotBlank() && questionText.length<=500)
        val rendered=Regex("""\{\{([^{}]+)\}\}""").replace(questionText) { m->
            val source=out[refs[m.groupValues[1]] ?: error("menção desconhecida")].obj("campos")
            (source["titulo"] ?: source["rotulo"] ?: JsonPrimitive("este registro")).jsonPrimitive.content
        }
        require(rendered.isNotBlank() && rendered.length<=5000)
        require(spec["presenca_publica"]==JsonPrimitive(true))
        if((index to q.str("campo")) !in autofilled) {
            require(d.obj("campos")[q.str("campo")] in listOf(null,JsonNull,JsonPrimitive("")))
            question=buildJsonObject { put("index",index);put("field",q["campo"]!!);put("text",rendered) }
        }
    }
    if(question==null) for((index,d) in out.withIndex()) {
        val missing=fields(d.str("tipo")).entries.firstOrNull { (f,s)->s.jsonObject["obrigatorio"]==JsonPrimitive(true) && d.obj("campos")[f] in listOf(null,JsonNull,JsonPrimitive("")) }
        if(missing!=null) { question=buildJsonObject { put("index",index);put("field",missing.key) };break }
    }
    contexto(bundle,JsonArray(out),hoje)
    return buildJsonObject { put("rascunhos",JsonArray(out));put("relacoes",JsonArray(rels));put("pergunta",question ?: JsonNull);put("origem","openai") }
}
