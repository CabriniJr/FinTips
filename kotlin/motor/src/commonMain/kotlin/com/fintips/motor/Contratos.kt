package com.fintips.motor

import kotlinx.datetime.LocalDate

/**
 * Os contratos — a fronteira entre o que o app garante e o que o agente decide.
 *
 * Aqui a porta faz a única coisa que ela se permite mudar: **representação**.
 * O Python valida origem e atitude como string em tempo de execução; o Kotlin
 * usa `enum`, e o compilador passa a recusar `origem = "usario"` antes de
 * qualquer teste rodar.
 *
 * Isso não é violar a regra de "porta replica, não corrige", porque não muda
 * comportamento nenhum: o texto que vai para o disco continua sendo
 * `"heuristica"`, `"aceitar"`, e o harness compara a serialização caractere
 * por caractere. Trocar como o dado é guardado na memória é livre; trocar o
 * que sai no arquivo, não.
 *
 * A regra que sustenta o resto continua a mesma: **nada é verdade sem
 * proveniência**.
 */

const val VERSAO_CONTRATOS = 2   // 2: entra o contrato Causa

/**
 * Quem decidiu, em ordem de autoridade crescente.
 *
 * A ordem importa mais que os nomes: é ela que impede uma heurística de
 * sobrescrever o que a pessoa afirmou, por mais "confiante" que a heurística
 * esteja.
 */
enum class Origem(val chave: String, val autoridade: Int) {
    /** Lista embutida no pacote. Ranqueia o que olhar primeiro, nunca conclui. */
    HEURISTICA("heuristica", 0),

    /** Derivado dos próprios dados: cadência, agrupamento, arquétipo casado. */
    IMPORTACAO("importacao", 1),

    /** O agente concluiu, normalmente depois de conversar. */
    AGENTE("agente", 2),

    /** A pessoa afirmou. Vence tudo. */
    USUARIO("usuario", 3);

    /** Só conta como fato estabelecido o que veio do agente ou do usuário. */
    val eVerdade: Boolean get() = autoridade >= AGENTE.autoridade

    companion object {
        fun de(chave: String): Origem =
            entries.firstOrNull { it.chave == chave } ?: HEURISTICA
    }
}

data class Proveniencia(
    val origem: Origem = Origem.HEURISTICA,
    val confianca: Double = 0.4,
    val porque: String = "",
    val evidencia: List<String> = emptyList(),
    val quando: String = "",
    val porQuem: String = "",
) {
    val autoridade: Int get() = origem.autoridade
    val eVerdade: Boolean get() = origem.eVerdade

    fun paraMapa(): Map<String, Any?> = linkedMapOf(
        "origem" to origem.chave,
        "confianca" to arredondar(confianca, 2),
        "porque" to porque,
        "evidencia" to evidencia,
        "quando" to quando,
        "por_quem" to porQuem,
    )
}

/**
 * Id estável derivado do conteúdo: `prefixo-` mais os 8 primeiros dígitos do
 * SHA-256 das partes unidas por `|`.
 *
 * Estável é o ponto: a mesma causa sobre a mesma categoria gera o mesmo id em
 * qualquer máquina e em qualquer momento, então regravar não duplica.
 */
fun novoId(prefixo: String, vararg partes: String): String =
    "$prefixo-" + sha256Hex(partes.joinToString("|")).take(8)

/** Uma categoria existe porque alguém a criou — não porque está no código. */
data class Categoria(
    val id: String,
    val nome: String,
    val descricao: String = "",
    val essencial: Boolean? = null,
    val pai: String? = null,
    val proveniencia: Proveniencia = Proveniencia(),
) {
    fun paraMapa(): Map<String, Any?> = linkedMapOf(
        "id" to id,
        "nome" to nome,
        "descricao" to descricao,
        "essencial" to essencial,
        "pai" to pai,
        "proveniencia" to proveniencia.paraMapa(),
    )
}

/**
 * O `quando` de uma regra. Campo vazio não restringe.
 *
 * Tudo aqui é comparável de forma determinística — nada depende do humor do
 * modelo no dia. O agente escolhe a condição; o app só aplica.
 */
data class Condicao(
    val contraparteId: String = "",
    val contraparteContem: String = "",
    val memoCasa: String = "",          // expressão regular
    val canal: String = "",
    val fluxo: String = "",
    val categoriaAtual: String = "",
    val valorMin: Double? = null,
    val valorMax: Double? = null,
    val diasSemana: List<Int> = emptyList(),   // 0 = segunda
    val horaMin: Int? = null,
    val horaMax: Int? = null,
) {
    fun vazia(): Boolean = listOf(
        contraparteId.isNotEmpty(), contraparteContem.isNotEmpty(), memoCasa.isNotEmpty(),
        canal.isNotEmpty(), fluxo.isNotEmpty(), categoriaAtual.isNotEmpty(),
        valorMin != null, valorMax != null, diasSemana.isNotEmpty(),
        horaMin != null, horaMax != null,
    ).none { it }

    /**
     * Regra mais específica vence a mais genérica.
     *
     * Os pesos são os do motor Python, inclusive na assimetria: contraparte
     * identificada vale 5 e fluxo vale 1, porque "é a Uber" diz muito mais
     * sobre uma transação do que "é uma saída".
     */
    fun especificidade(): Int {
        var total = 0
        if (contraparteId.isNotEmpty()) total += 5
        if (memoCasa.isNotEmpty()) total += 4
        if (contraparteContem.isNotEmpty()) total += 3
        if (canal.isNotEmpty()) total += 2
        if (fluxo.isNotEmpty()) total += 1
        if (categoriaAtual.isNotEmpty()) total += 1
        if (valorMin != null || valorMax != null) total += 2
        if (diasSemana.isNotEmpty()) total += 2
        if (horaMin != null || horaMax != null) total += 2
        return total
    }

    /** Campo vazio não vai para o arquivo, como no Python. */
    fun paraMapa(): Map<String, Any?> {
        val m = linkedMapOf<String, Any?>(
            "contraparte_id" to contraparteId,
            "contraparte_contem" to contraparteContem,
            "memo_casa" to memoCasa,
            "canal" to canal,
            "fluxo" to fluxo,
            "categoria_atual" to categoriaAtual,
            "valor_min" to valorMin,
            "valor_max" to valorMax,
            "dias_semana" to diasSemana,
            "hora_min" to horaMin,
            "hora_max" to horaMax,
        )
        return m.filterValues { v ->
            v != null && v != "" && !(v is List<*> && v.isEmpty())
        }
    }
}

/** O `então` de uma regra. */
data class Efeito(
    val categoria: String = "",
    val fluxo: String = "",
    val marcar: List<String> = emptyList(),
    val rotulo: String = "",
) {
    fun paraMapa(): Map<String, Any?> = linkedMapOf<String, Any?>(
        "categoria" to categoria,
        "fluxo" to fluxo,
        "marcar" to marcar,
        "rotulo" to rotulo,
    ).filterValues { v -> v != null && v != "" && !(v is List<*> && v.isEmpty()) }
}

data class Regra(
    val id: String,
    val quando: Condicao,
    val entao: Efeito,
    val proveniencia: Proveniencia = Proveniencia(),
    val ativa: Boolean = true,
    val nota: String = "",
) {
    /**
     * Autoridade primeiro, depois especificidade, depois confiança.
     *
     * A ordem é a decisão de produto: uma regra genérica que a pessoa afirmou
     * vence uma regra específica que a heurística chutou. O contrário deixaria
     * o palpite mandar sempre que fosse mais detalhado.
     */
    fun prioridade(): Triple<Int, Int, Double> =
        Triple(proveniencia.autoridade, quando.especificidade(), proveniencia.confianca)

    fun paraMapa(): Map<String, Any?> = linkedMapOf(
        "id" to id,
        "quando" to quando.paraMapa(),
        "entao" to entao.paraMapa(),
        "proveniencia" to proveniencia.paraMapa(),
        "ativa" to ativa,
        "nota" to nota,
    )
}

/**
 * Compromisso mensal **definido**, não detectado.
 *
 * A detecção continua existindo, mas só produz candidato. Custo fixo de
 * verdade é o que alguém afirmou ser compromisso.
 */
data class CustoFixo(
    val id: String,
    val rotulo: String,
    val baseTipo: String,               // categoria | contraparte | regra | valor
    val baseRef: String,
    val valorMensal: Double,
    val metodo: String = "declarado",   // declarado | mediana_meses_completos | media
    val natureza: String = "rotina",    // o agente nomeia; não há lista fixa
    val ativo: Boolean = true,
    val proveniencia: Proveniencia = Proveniencia(),
) {
    fun paraMapa(): Map<String, Any?> = linkedMapOf(
        "id" to id,
        "rotulo" to rotulo,
        "base" to linkedMapOf("tipo" to baseTipo, "ref" to baseRef),
        "valor_mensal" to arredondar(valorMensal, 2),
        "valor_anual" to arredondar(valorMensal * 12, 2),
        "metodo" to metodo,
        "natureza" to natureza,
        "ativo" to ativo,
        "proveniencia" to proveniencia.paraMapa(),
    )
}

/** Um pedaço de contexto sobre o usuário, com o que o sustenta. */
data class Fato(
    val chave: String,
    val valor: Any?,
    val tipo: String = "texto",
    val proveniencia: Proveniencia = Proveniencia(),
    val expiraEm: String? = null,
    val substituiu: String? = null,
) {
    fun vencido(hoje: LocalDate): Boolean {
        val prazo = expiraEm ?: return false
        return try {
            LocalDate.parse(prazo) < hoje
        } catch (e: IllegalArgumentException) {
            false
        }
    }

    fun paraMapa(hoje: LocalDate): Map<String, Any?> = linkedMapOf(
        "chave" to chave,
        "valor" to valor,
        "tipo" to tipo,
        "expira_em" to expiraEm,
        "substituiu" to substituiu,
        "vencido" to vencido(hoje),
        "proveniencia" to proveniencia.paraMapa(),
    )
}

/** Atitude sobre uma causa. Vocabulário fechado: o dossiê calcula em cima. */
enum class Atitude(val chave: String) {
    NENHUMA("nenhuma"),
    /** Fica como está — e agora isso é escolha, não descuido. */
    ACEITAR("aceitar"),
    REDUZIR("reduzir"),
    ELIMINAR("eliminar"),
    SUBSTITUIR("substituir"),
    /** Vira automático e sai da decisão diária. */
    AUTOMATIZAR("automatizar"),
    /** Sem decisão ainda; olhar de novo em tal data. */
    OBSERVAR("observar");

    companion object {
        fun de(chave: String): Atitude? = entries.firstOrNull { it.chave == chave }
    }
}

/**
 * Naturezas sugeridas para uma causa. Lista **aberta** de propósito — o app
 * valida a forma, não o conteúdo, e a vida de alguém pode pedir uma palavra
 * que não está aqui.
 */
val NATUREZAS_SUGERIDAS = listOf(
    "gatilho", "necessidade", "obrigacao", "habito", "compensacao", "evento", "estrutural",
)

/**
 * Por que um padrão de gasto existe — e o que se decidiu sobre ele.
 *
 * A única camada do motor que fala de motivo, e por isso a mais perigosa. Um
 * número o app calcula; um motivo ele não tem como saber. Não existe detecção
 * de causa neste código, e não deve existir.
 */
data class Causa(
    val id: String,
    val efeitoTipo: String,
    val efeitoRef: String,
    val natureza: String,
    val enunciado: String,
    val atitude: Atitude = Atitude.NENHUMA,
    val atitudeNota: String = "",
    val evidencia: List<String> = emptyList(),
    val proveniencia: Proveniencia = Proveniencia(),
    val revisarEm: String? = null,
    val criadoEm: String = "",
) {
    /** Chave de correlação: é por aqui que o dossiê liga causa a dinheiro. */
    val alvo: String get() = "$efeitoTipo:$efeitoRef"

    fun vencida(hoje: LocalDate): Boolean {
        val prazo = revisarEm ?: return false
        return try {
            LocalDate.parse(prazo) < hoje
        } catch (e: IllegalArgumentException) {
            false
        }
    }

    fun paraMapa(hoje: LocalDate): Map<String, Any?> = linkedMapOf(
        "id" to id,
        "efeito" to linkedMapOf("tipo" to efeitoTipo, "ref" to efeitoRef),
        "alvo" to alvo,
        "natureza" to natureza,
        "enunciado" to enunciado,
        "atitude" to atitude.chave,
        "atitude_nota" to atitudeNota,
        "evidencia" to evidencia,
        "revisar_em" to revisarEm,
        "vencida" to vencida(hoje),
        "criado_em" to criadoEm,
        "proveniencia" to proveniencia.paraMapa(),
    )
}

/** Algo em aberto, com o custo mensal de não decidir. */
data class ItemDeTriagem(
    val id: String,
    val tipo: String,
    val titulo: String,
    val impactoMensal: Double,
    val porqueImporta: String,
    val evidencia: Map<String, Any?> = emptyMap(),
    val sugestao: Map<String, Any?>? = null,
    val estado: String = "aberto",
    val resolucao: Map<String, Any?>? = null,
    val criadoEm: String = "",
) {
    /**
     * O que ordena a fila: dinheiro por mês, ponderado pelo tipo.
     *
     * O peso existe porque nem todo real custa igual. Um fato ausente trava
     * vários cálculos ao mesmo tempo; uma classificação fraca só atrapalha um
     * relatório. Tipo desconhecido vale 1.0 — não some da fila por ser novo.
     */
    val prioridade: Double
        get() {
            val peso = PESOS_POR_TIPO[tipo] ?: 1.0
            val abs = if (impactoMensal < 0) -impactoMensal else impactoMensal
            return arredondar(abs * peso, 2)
        }

    companion object {
        val PESOS_POR_TIPO = mapOf(
            "fato_ausente" to 1.3,
            "custo_fixo_derivou" to 1.2,
            "contraparte_nova" to 1.0,
            "candidato_custo_fixo" to 1.0,
            "classificacao_fraca" to 0.9,
            "evento_sem_explicacao" to 0.8,
            "fato_vencido" to 0.8,
            "causa_ausente" to 1.1,
            "causa_a_revisar" to 1.0,
            "causa_sem_atitude" to 0.9,
        )
    }
}

/**
 * Arredondamento meio-para-o-par sobre Double, como o `round()` do Python.
 *
 * O `Math.round` da JVM arredonda meio-para-cima e divergiria: o Python 3 usa
 * meio-para-o-par em `round()`, e o valor aparece no arquivo gravado.
 */
internal fun arredondar(valor: Double, casas: Int): Double {
    if (valor.isNaN() || valor.isInfinite()) return valor
    var fator = 1.0
    repeat(casas) { fator *= 10 }
    val escalado = valor * fator
    val inteiro = kotlin.math.floor(escalado)
    val resto = escalado - inteiro
    val arredondado = when {
        resto > 0.5 -> inteiro + 1
        resto < 0.5 -> inteiro
        // empate exato: vai para o par
        inteiro.toLong() % 2L == 0L -> inteiro
        else -> inteiro + 1
    }
    return arredondado / fator
}
