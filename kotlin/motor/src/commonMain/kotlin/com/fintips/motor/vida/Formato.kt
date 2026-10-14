package com.fintips.motor.vida

import com.fintips.motor.Dinheiro
import kotlinx.datetime.LocalDate
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

/**
 * O catálogo e os registros, em JSON, para o aparelho.
 *
 * ## Por que JSON aqui e YAML lá
 *
 * O workspace guarda `missoes.yaml` porque é arquivo que a pessoa edita à mão,
 * e YAML existe para isso. O aparelho não edita nada à mão e, mais importante,
 * **o celular é outra máquina**: ele não lê `~/Documents/FinTips/data/`, nem vai
 * ler. Qualquer coisa que chegue ao aparelho chega por transporte — e o formato
 * de transporte não precisa ser o formato de edição.
 *
 * Isso tem uma consequência boa que não era óbvia: **a leitura de YAML em
 * Kotlin não bloqueia o app**. O que o aparelho precisa é de um formato que ele
 * leia e escreva sozinho, e o Python exporta com `fintips exportar-missoes`.
 *
 * ## Por que uma dependência nova no commonMain
 *
 * O motor tinha uma só (`kotlinx-datetime`), e o leitor OFX foi escrito à mão
 * de propósito. Aqui a escolha é diferente, pelo mesmo motivo que SHA-256 entrou
 * por `expect`/`actual`: **ler** JSON à mão é onde o erro se esconde — escape,
 * unicode, aninhamento. Emitir à mão é fácil e o motor já faz; interpretar, não.
 *
 * O registro vai em **JSONL**, uma linha por marcação, porque registro é
 * histórico: `append` só sabe crescer, enquanto reescrever o arquivo inteiro a
 * cada marcação permite perder o passado num erro de escrita.
 */

@Serializable
private class MissaoJson(
    val id: String,
    val titulo: String = "",
    val atributo: String,
    val cadencia: String,
    @SerialName("como_medir") val comoMedir: String = "",
    @SerialName("sensor_possivel") val sensorPossivel: Boolean = false,
    val porque: String = "",
    val ativa: Boolean = true,
    @SerialName("valor_mensal") val valorMensal: String? = null,
    @SerialName("colide_com") val colideCom: List<String> = emptyList(),
)

@Serializable
private class RegraJson(
    val id: String,
    val tipo: String,
    @SerialName("acima_de") val acimaDe: String,
    val dias: Int,
    val porque: String,
)

@Serializable
private class CatalogoJson(
    @SerialName("schema_version") val schemaVersion: Int = 1,
    val missoes: List<MissaoJson> = emptyList(),
    val regras: List<RegraJson> = emptyList(),
)

@Serializable
private class RegistroJson(
    @SerialName("missao_id") val missaoId: String,
    val dia: String,
    val origem: String,
    val medida: String = "",
    val nota: String = "",
)

object FormatoDeVida {

    /** Tolerante a chave desconhecida: catálogo novo não quebra app velho. */
    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        prettyPrint = false
    }

    const val SCHEMA = 1

    /**
     * Lê o catálogo exportado.
     *
     * As recusas são as mesmas do `fintips/life.py`, e existem pelo mesmo
     * motivo: atributo ou cadência fora do vocabulário não vira valor padrão
     * silencioso — vira erro com o nome do que está errado. Catálogo torto que
     * carrega é pior que catálogo que recusa, porque o app mostra barra de uma
     * frente que a pessoa não pediu.
     */
    fun lerCatalogo(texto: String): Vida {
        if (texto.isBlank()) return Vida()
        val c = json.decodeFromString<CatalogoJson>(texto)

        val vistos = mutableSetOf<String>()
        val missoes = c.missoes.map { m ->
            require(vistos.add(m.id)) { "missão '${m.id}' aparece duas vezes no catálogo" }
            Missao(
                id = m.id,
                titulo = m.titulo.ifBlank { m.id },
                atributo = Atributo.de(m.atributo)
                    ?: error(
                        "missão '${m.id}': atributo '${m.atributo}' não existe. " +
                            "Os seis são ${Atributo.entries.joinToString(", ") { it.sigla }}",
                    ),
                cadencia = Cadencia.de(m.cadencia)
                    ?: error(
                        "missão '${m.id}': cadência '${m.cadencia}' não existe. " +
                            "As cinco são ${Cadencia.entries.joinToString(", ") { it.chave }}",
                    ),
                comoMedir = m.comoMedir,
                sensorPossivel = m.sensorPossivel,
                porque = m.porque,
                ativa = m.ativa,
                valorMensal = m.valorMensal?.let { Dinheiro.de(it) },
                colideCom = m.colideCom,
            )
        }
        val regras = c.regras.map { r ->
            RegraDeclarada(
                id = r.id,
                tipo = r.tipo,
                acimaDe = Dinheiro.de(r.acimaDe),
                dias = r.dias,
                porque = r.porque,
            )
        }
        return Vida(missoes = missoes, regras = regras)
    }

    /** Emite o catálogo. Usado em teste de ida-e-volta e para reexportar. */
    fun escreverCatalogo(vida: Vida): String = json.encodeToString(
        CatalogoJson(
            schemaVersion = SCHEMA,
            missoes = vida.missoes.map { m ->
                MissaoJson(
                    id = m.id,
                    titulo = m.titulo,
                    atributo = m.atributo.sigla,
                    cadencia = m.cadencia.chave,
                    comoMedir = m.comoMedir,
                    sensorPossivel = m.sensorPossivel,
                    porque = m.porque,
                    ativa = m.ativa,
                    valorMensal = m.valorMensal?.let { formatarReais(it) },
                    colideCom = m.colideCom,
                )
            },
            regras = vida.regras.map { r ->
                RegraJson(
                    id = r.id, tipo = r.tipo, acimaDe = formatarReais(r.acimaDe),
                    dias = r.dias, porque = r.porque,
                )
            },
        ),
    )

    /** Uma linha de JSONL. Sem `\n`: quem grava decide o fim de linha. */
    fun escreverRegistro(r: RegistroDeMissao): String = json.encodeToString(
        RegistroJson(
            missaoId = r.missaoId,
            dia = r.dia.toString(),
            origem = r.origem.chave,
            medida = r.medida,
            nota = r.nota,
        ),
    )

    /**
     * Lê o histórico.
     *
     * `missoesConhecidas` vazio pula a conferência, para quem lê registro sem
     * catálogo na mão. Com catálogo, registro órfão é erro: ele representa uma
     * missão que a pessoa não tem, e contá-lo encheria barra de frente nenhuma.
     */
    fun lerRegistros(
        texto: String,
        missoesConhecidas: Set<String> = emptySet(),
    ): List<RegistroDeMissao> = texto.lineSequence()
        .map { it.trim() }
        .filter { it.isNotEmpty() }
        .mapIndexed { i, linha ->
            val r = json.decodeFromString<RegistroJson>(linha)
            val origem = OrigemDoRegistro.de(r.origem)
                ?: error(
                    "linha ${i + 1}: origem '${r.origem}' não existe. As quatro são " +
                        OrigemDoRegistro.entries.joinToString(", ") { it.chave },
                )
            require(missoesConhecidas.isEmpty() || r.missaoId in missoesConhecidas) {
                "linha ${i + 1}: registro da missão '${r.missaoId}', que não está no catálogo"
            }
            RegistroDeMissao(
                missaoId = r.missaoId,
                dia = LocalDate.parse(r.dia),
                origem = origem,
                medida = r.medida,
                nota = r.nota,
            )
        }
        .toList()

    /** Reais com duas casas e ponto decimal, como o Python grava. */
    private fun formatarReais(d: Dinheiro): String {
        val neg = d.centavos < 0
        val abs = if (neg) -d.centavos else d.centavos
        val centavos = (abs % 100).toString().padStart(2, '0')
        return (if (neg) "-" else "") + "${abs / 100}.$centavos"
    }
}
