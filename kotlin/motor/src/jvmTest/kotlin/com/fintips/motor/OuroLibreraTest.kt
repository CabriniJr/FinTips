package com.fintips.motor

import com.fintips.motor.vida.importarLibrera
import com.fintips.motor.vida.posicoesLibrera
import kotlinx.serialization.json.*
import kotlin.test.*

class OuroLibreraTest {
    @Test fun importacao_auto_replica_referencia_com_correcao_recuo_perfis_e_exclusao() {
        val ouro=Json.parseToJsonElement(javaClass.getResourceAsStream("/ouro/librera-auto.json")!!.reader().readText()).jsonObject
        for(el in ouro["casos"]!!.jsonArray) {
            val c=el.jsonObject;val i=c["entrada"]!!.jsonObject
            assertEquals(c["contexto_ia"],projetarBundleIA(c["bundle"]!!.jsonObject,listOf("rotina","planos","leitura"),"2026-10-16"))
            assertEquals(c["resultado"],importarLibrera(i["reading"]!!.jsonObject,i["raw"]!!,i["profile"]!!.jsonPrimitive.content,i["now_ms"]!!.jsonPrimitive.long,i["zone"]!!.jsonPrimitive.content,i["excluded"]!!.jsonArray),c["nome"].toString())
        }
        val parser=Json.parseToJsonElement(javaClass.getResourceAsStream("/ouro/leitura.json")!!.reader().readText()).jsonObject
        for(el in parser["parser"]!!.jsonArray) { val c=el.jsonObject;assertEquals(c["resultado"],posicoesLibrera(c["entrada"]!!)) }
    }
}
