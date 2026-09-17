package com.fintips.motor

/**
 * Normalização de texto — a base de toda comparação do motor.
 *
 * Tudo que compara nome de estabelecimento passa por aqui: regra que casa por
 * contraparte, agrupamento de variações da mesma loja, pseudônimo de pessoa
 * física. Se `norm` divergir do Python nem que seja num acento, a mesma padaria
 * vira duas contrapartes e o custo mensal dela se parte ao meio.
 *
 * `decompoeUnicode` entra por `expect`/`actual` porque decomposição Unicode
 * (NFKD) não existe no stdlib comum do Kotlin — é `unicodedata` no Python,
 * `java.text.Normalizer` na JVM e no Android, e `precomposedStringWithCanonicalMapping`
 * no iOS quando ele entrar. Era a última das três lacunas de biblioteca padrão
 * que a porta encontrou.
 */

/** Decompõe em NFKD e remove as marcas combinantes (os acentos soltos). */
expect fun semAcento(texto: String): String

private val ESPACOS = Regex("\\s+")
private val NAO_ALFANUMERICO = Regex("[^A-Za-z0-9]+")

/**
 * Forma de comparação: sem acento, espaços colapsados, caixa alta.
 *
 * Caixa alta e não baixa porque é o que o Python faz, e o resultado aparece em
 * chave de agrupamento gravada em disco.
 */
fun norm(texto: String): String =
    ESPACOS.replace(semAcento(texto), " ").trim().uppercase()

/** Identificador estável de contraparte: sem acento, só alfanumérico, minúsculo. */
fun slug(texto: String): String {
    val limpo = NAO_ALFANUMERICO.replace(semAcento(texto), "-").trim('-').lowercase()
    return limpo.ifEmpty { "sem-nome" }
}

private val SUFIXO_DE_LOJA = Regex(
    "(?:[-\\s]*(?:LJ|LOJA|FIL|UN)\\s*\\d+|\\*\\d{3,}|\\s+\\d{3,}|\\s+[IVX]{1,4})$",
    RegexOption.IGNORE_CASE,
)
private val CODIGO_DE_ADQUIRENTE = Regex("^([A-Z0-9 ]+?)\\s*\\*\\s*(.+)$")
private val SO_NUMEROS_E_PONTUACAO = Regex("[\\d\\s.-]+")
private val ESPACO_DUPLO = Regex("\\s{2,}")

/**
 * Junta variações do mesmo estabelecimento.
 *
 * "Gelato Roma-LJ0046" e "Gelato Roma-LJ0084" viram um só; "EMV CMT*144318981"
 * vira "EMV CMT". Pseudônimo de pessoa física (`PF:`) passa intacto, porque
 * ali o sufixo numérico é o identificador, não ruído de maquininha.
 *
 * O laço existe porque um nome pode carregar mais de um sufixo empilhado, e
 * uma passada só deixaria o segundo para trás.
 */
fun nomeCanonico(bruto: String): String {
    var nome = bruto.trim()
    if (nome.startsWith("PF:") || nome.isEmpty()) return nome

    CODIGO_DE_ADQUIRENTE.matchEntire(nome.uppercase())?.let { m ->
        if (SO_NUMEROS_E_PONTUACAO.matchEntire(m.groupValues[2]) != null) {
            nome = m.groupValues[1]
        }
    }

    var anterior: String? = null
    while (anterior != nome) {
        anterior = nome
        nome = SUFIXO_DE_LOJA.replace(nome, "").trim(' ', '-', '.', '*')
    }
    val final = ESPACO_DUPLO.replace(nome, " ")
    return final.ifEmpty { bruto.trim() }
}
