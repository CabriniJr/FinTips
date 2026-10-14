package com.fintips.motor.vida

import kotlinx.datetime.LocalDate

/**
 * Onde o aparelho guarda o catálogo e o histórico.
 *
 * ## Por que lambdas e não `expect`/`actual`
 *
 * A tentação era um `expect class GuardaDeArquivo` com um `actual` por alvo.
 * O problema é que isso põe **lógica** dentro da parte específica de
 * plataforma — e o que está no `androidMain` não roda em teste nenhum desta
 * máquina, porque o alvo Android exige SDK.
 *
 * Com a leitura e a escrita entrando como duas funções, tudo que é decisão
 * fica aqui, em `commonMain`, testado: quando recusar, o que fazer com
 * arquivo ausente, como o histórico cresce, qual origem conta. O Android
 * entrega duas linhas sobre `filesDir` e não tem onde esconder erro.
 *
 * É a mesma ideia do `expect`/`actual` do SHA-256, levada mais longe: a
 * fronteira de plataforma deve ser a menor possível, e nunca o lugar onde
 * mora a regra.
 */
class Guarda(
    /** Devolve o conteúdo, ou `null` se o arquivo não existe. */
    private val lerTexto: (nome: String) -> String?,
    /** Acrescenta ao fim. Cria o arquivo se não existir. */
    private val acrescentarTexto: (nome: String, conteudo: String) -> Unit,
) {
    companion object {
        const val CATALOGO = "missoes.json"
        const val HISTORICO = "registros.jsonl"
    }

    /**
     * O catálogo. Ausência não é erro.
     *
     * Aparelho sem catálogo é o estado inicial de todo mundo, e o app precisa
     * abrir e dizer o que fazer — não estourar.
     */
    fun catalogo(): Vida =
        lerTexto(CATALOGO)?.let { FormatoDeVida.lerCatalogo(it) } ?: Vida()

    /** O histórico, conferido contra o catálogo. */
    fun registros(vida: Vida): List<RegistroDeMissao> =
        lerTexto(HISTORICO)?.let {
            FormatoDeVida.lerRegistros(it, vida.missoes.map { m -> m.id }.toSet())
        } ?: emptyList()

    /** Catálogo e histórico juntos, que é como a tela sempre quer. */
    fun carregar(): Vida {
        val v = catalogo()
        return v.copy(registros = registros(v))
    }

    /**
     * Marca uma missão.
     *
     * Recusa missão fora do catálogo em vez de gravar órfão: registro de missão
     * que não existe não enche barra nenhuma e some do relatório — erro que não
     * aparece é o pior tipo.
     *
     * **Não recusa marcação repetida no mesmo dia**, e isso é deliberado. O
     * histórico é append: duas marcações do mesmo dia são dois fatos, e a
     * segunda pode trazer medida melhor (a pessoa marcou pela manhã, o sensor
     * confirmou à noite). O cálculo de sequência já trabalha com conjunto de
     * dias, então repetir não distorce número nenhum.
     */
    fun marcar(
        vida: Vida,
        missaoId: String,
        dia: LocalDate,
        origem: OrigemDoRegistro = OrigemDoRegistro.USUARIO,
        medida: String = "",
        nota: String = "",
    ): RegistroDeMissao {
        require(vida.missoes.any { it.id == missaoId }) {
            "missão '$missaoId' não está no catálogo deste aparelho"
        }
        val r = RegistroDeMissao(missaoId, dia, origem, medida, nota)
        acrescentarTexto(HISTORICO, FormatoDeVida.escreverRegistro(r) + "\n")
        return r
    }
}
