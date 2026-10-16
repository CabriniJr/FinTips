package com.fintips.motor

/**
 * A fronteira de saída: o que atravessa a rede, campo por campo.
 *
 * O registro de depósitos diz onde os dados moram. Este diz o que sai do
 * aparelho quando o agente é um modelo que roda em outro lugar.
 *
 * O esclarecimento de 16/10/2026 desenhou a linha num lugar estreito, e ele é
 * mais permissivo do que "não mandar nada": **texto de planejamento sai, valor
 * sai, identidade financeira não sai.** O agente precisa ler "certificação de
 * observabilidade" para decompor um objetivo; ele não precisa saber para qual
 * estabelecimento o dinheiro foi.
 *
 * Isto não é a política de [pseudonimo] e de [hashConta], e as duas não devem
 * ser harmonizadas por quem passar aqui depois. Aquelas governam o que o app
 * escreve no disco **local** — e lá o nome do estabelecimento fica em claro,
 * porque é ele que dá sentido à análise de gastos na máquina da pessoa. Aqui a
 * pergunta é outra: o que atravessa a rede. Um campo pode ser legítimo no
 * disco e proibido na saída.
 *
 * Porte de `fintips/contracts.py`. O registro está escrito duas vezes, uma em
 * cada motor, e é por isso que `ouro/fronteira.json` carrega o registro inteiro
 * e não só as respostas: abrir um campo num motor e esquecer o outro é
 * exatamente o erro que um ouro de respostas não pegaria.
 */

/** O que a política permite. `FECHADO` é a ausência de declaração. */
enum class PoliticaDeSaida(val codigo: String) {
    TEXTO_PLANEJAMENTO("texto_planejamento"),
    VALOR_FINANCEIRO("valor_financeiro"),
    IDENTIDADE_FINANCEIRA_LOCAL("identidade_financeira_local"),
    ROTULO_TECNICO("rotulo_tecnico"),
    SEGREDO_LOCAL("segredo_local"),
    FECHADO("fechado"),
    ;

    companion object {
        fun de(codigo: String): PoliticaDeSaida =
            entries.firstOrNull { it.codigo == codigo } ?: FECHADO
    }
}

/** Um campo que atravessa a fronteira, e sob que condição. */
data class CampoAberto(
    val campo: String,
    val politica: PoliticaDeSaida,
    val unidade: String = "",
)

/**
 * Um tipo que o agente pode ler, com todos os campos classificados.
 *
 * `fecha` é o que nunca sai. `projetaAParte` é o que não sai *neste* campo
 * porque é um tipo da fronteira por si, projetado item por item pela política
 * dele — e a distinção importa porque as duas aparecem na aba de privacidade.
 * Dizer "a IA nunca recebe as etapas do objetivo" é mentira: ela recebe cada
 * etapa, com a política de `etapa`.
 */
data class TipoDaFronteira(
    val nome: String,
    val classe: String,
    val abre: List<CampoAberto>,
    val fecha: List<String> = emptyList(),
    val projetaAParte: List<String> = emptyList(),
) {
    val naoSaiNesteCampo: List<String> get() = fecha + projetaAParte
}

private fun aberto(campo: String, politica: PoliticaDeSaida, unidade: String = "") =
    CampoAberto(campo, politica, unidade)

private val TEXTO = PoliticaDeSaida.TEXTO_PLANEJAMENTO
private val VALOR = PoliticaDeSaida.VALOR_FINANCEIRO
private val IDENT = PoliticaDeSaida.IDENTIDADE_FINANCEIRA_LOCAL
private val ROTULO = PoliticaDeSaida.ROTULO_TECNICO

val TIPOS_DA_FRONTEIRA: List<TipoDaFronteira> = listOf(
    TipoDaFronteira(
        "transacao", "fintips.models:Transaction",
        abre = listOf(
            aberto("amount", VALOR, "centavos_brl"),
            aberto("ts", ROTULO),
            aberto("flow", ROTULO),
            aberto("category", ROTULO),
            aberto("channel", ROTULO),
            aberto("counterparty_kind", ROTULO),
            aberto("counterparty", IDENT),
            aberto("category_source", ROTULO),
        ),
        fecha = listOf(
            "id", "memo_raw", "city", "tags", "account_id",
            "category_confidence", "rule_id",
        ),
    ),
    TipoDaFronteira(
        "objetivo", "fintips.objetivos:Objetivo",
        abre = listOf(
            aberto("id", ROTULO),
            aberto("titulo", TEXTO),
            aberto("porque", TEXTO),
            aberto("comecou_em", ROTULO),
            aberto("data_alvo", ROTULO),
            aberto("origem", ROTULO),
            aberto("porque_da_origem", TEXTO),
            aberto("assinado_em", ROTULO),
            aberto("arquivado", ROTULO),
            aberto("plano_id", ROTULO),
            aberto("missoes", ROTULO),
        ),
        projetaAParte = listOf("etapas"),
    ),
    TipoDaFronteira(
        "etapa", "fintips.objetivos:Etapa",
        abre = listOf(
            aberto("id", ROTULO),
            aberto("titulo", TEXTO),
            aberto("tipo", ROTULO),
            aberto("prazo", ROTULO),
            aberto("prazo_original", ROTULO),
            aberto("adiamentos", ROTULO, "numero"),
            aberto("custo", VALOR, "centavos_brl"),
            aberto("depende_de", ROTULO),
            aberto("obrigatoria", ROTULO),
            aberto("porque", TEXTO),
        ),
    ),
    TipoDaFronteira(
        "check", "fintips.objetivos:Check",
        abre = listOf(
            aberto("objetivo_id", ROTULO),
            aberto("etapa_id", ROTULO),
            aberto("dia", ROTULO),
            aberto("origem", ROTULO),
            aberto("nota", TEXTO),
        ),
    ),
    TipoDaFronteira(
        "alternativa", "fintips.contracts:Alternativa",
        abre = listOf(
            aberto("nome", TEXTO),
            aberto("custo", VALOR, "centavos_brl"),
            aberto("custo_mensal", VALOR, "centavos_brl"),
            aberto("horizonte_meses", VALOR, "numero"),
            aberto("consequencia", TEXTO),
            aberto("risco", TEXTO),
            aberto("descartada_porque", TEXTO),
        ),
    ),
    TipoDaFronteira(
        "traco_de_perfil", "fintips.profile:TracoDePerfil",
        abre = listOf(
            aberto("eixo", ROTULO),
            aberto("arquetipo", ROTULO),
            aberto("nome", TEXTO),
            aberto("descricao", TEXTO),
            aberto("substituiu", ROTULO),
        ),
        projetaAParte = listOf("proveniencia"),
    ),
    TipoDaFronteira(
        "missao", "fintips.life:Missao",
        abre = listOf(
            aberto("id", ROTULO),
            aberto("titulo", TEXTO),
            aberto("atributo", ROTULO),
            aberto("cadencia", ROTULO),
            aberto("como_medir", TEXTO),
            aberto("sensor_possivel", ROTULO),
            aberto("porque", TEXTO),
            aberto("ativa", ROTULO),
            aberto("valor_mensal", VALOR, "centavos_brl"),
            aberto("colide_com", ROTULO),
        ),
    ),
    TipoDaFronteira(
        // A proveniência atravessa porque é ela que diz ao agente se algo foi
        // concluído ou só ranqueado — sem isso ele trata palpite como fato.
        "proveniencia", "fintips.contracts:Proveniencia",
        abre = listOf(
            aberto("origem", ROTULO),
            aberto("confianca", ROTULO),
            aberto("porque", TEXTO),
            aberto("quando", ROTULO),
            aberto("por_quem", ROTULO),
        ),
        fecha = listOf("evidencia"),
    ),
    TipoDaFronteira(
        "decisao", "fintips.contracts:Decisao",
        abre = listOf(
            aberto("id", ROTULO),
            aberto("titulo", TEXTO),
            aberto("situacao", TEXTO),
            aberto("pergunta", TEXTO),
            aberto("tipo", ROTULO),
            aberto("escolhida", TEXTO),
            aberto("porque", TEXTO),
            aberto("status", ROTULO),
            aberto("ligacoes", ROTULO),
            aberto("revisar_em", ROTULO),
            aberto("substitui", ROTULO),
            aberto("substituida_por", ROTULO),
            aberto("criado_em", ROTULO),
            aberto("decidido_em", ROTULO),
        ),
        fecha = listOf("instantaneo", "desfecho"),
        projetaAParte = listOf("alternativas", "proveniencia"),
    ),
    TipoDaFronteira(
        // Causa é o tipo mais fechado dos dez, de propósito: ela explica um
        // padrão do extrato, e a tabela do plano libera objetivo, curso, livro,
        // produto e intenção de compra — não isso. O `enunciado` é o lugar mais
        // provável de um nome de estabelecimento aparecer sem ninguém ter
        // decidido liberá-lo.
        "causa", "fintips.contracts:Causa",
        abre = listOf(
            aberto("id", ROTULO),
            aberto("efeito_tipo", ROTULO),
            aberto("natureza", ROTULO),
            aberto("atitude", ROTULO),
            aberto("revisar_em", ROTULO),
            aberto("criado_em", ROTULO),
        ),
        fecha = listOf("efeito_ref", "enunciado", "atitude_nota", "evidencia"),
        projetaAParte = listOf("proveniencia"),
    ),
)

private val PORTIPO: Map<String, TipoDaFronteira> = TIPOS_DA_FRONTEIRA.associateBy { it.nome }

/** Que política vale para este campo. Campo não declarado é `FECHADO`. */
fun politicaDoCampo(tipo: String, campo: String): PoliticaDeSaida =
    PORTIPO[tipo]?.abre?.firstOrNull { it.campo == campo }?.politica
        ?: PoliticaDeSaida.FECHADO

/**
 * O alias que substitui uma identidade financeira na saída.
 *
 * Primeiro o mapa local, que dá um rótulo legível escolhido no aparelho. Sem
 * entrada no mapa, o próprio aparelho emite um pseudônimo com o sal — que
 * também é local, e é o que torna o alias estável entre chamadas sem nunca
 * mandar o nome.
 *
 * O `norm` dos dois lados não é enfeite: quem escreve o mapa à mão escreve
 * "loja do zé", e o extrato traz "LOJA DO ZE LTDA". Comparar as formas cruas
 * erra sempre, e errar aqui significa emitir pseudônimo onde havia rótulo.
 */
fun aliasFinanceiro(
    valor: String,
    identidades: Map<String, String> = emptyMap(),
    sal: String = "",
): String {
    // Nome vazio não tem identidade para proteger, e emitir pseudônimo de ""
    // criaria um alias estável para "ninguém" — que depois junta transações
    // sem contraparte como se fossem o mesmo destino.
    if (valor.isBlank()) return ""
    val procurado = norm(valor)
    for ((bruto, alias) in identidades) {
        if (norm(bruto) == procurado) return alias
    }
    if (sal.isEmpty()) return ""
    return pseudonimo(valor, sal)
}

/** O texto, e se alguma identidade conhecida foi trocada por alias. */
data class TextoProjetado(val texto: String, val trocou: Boolean)

/**
 * Troca por alias as identidades **conhecidas** que aparecem no texto.
 *
 * E o limite é esse mesmo, dito aqui para não ser prometido mais tarde: isto
 * substitui o que está no mapa local. Não detecta o nome de um estabelecimento
 * que ninguém cadastrou, e nenhuma expressão regular detecta. Por isso a
 * fronteira é por campo e fecha por omissão: a proteção vem de o campo não
 * sair, não de uma varredura no texto.
 */
fun textoSemIdentidades(texto: String, identidades: Map<String, String>): TextoProjetado {
    var saida = texto
    var trocou = false
    // Do mais longo para o mais curto: "loja do zé ltda" antes de "loja do zé",
    // senão o prefixo come o sufixo e sobra "estab-7 ltda".
    for ((bruto, alias) in identidades.entries.sortedByDescending { it.key.length }) {
        if (bruto.isEmpty()) continue
        for (forma in listOf(bruto, norm(bruto)).distinct()) {
            val novo = saida.replace(forma, alias, ignoreCase = true)
            if (novo != saida) {
                saida = novo
                trocou = true
            }
        }
    }
    return TextoProjetado(saida, trocou)
}
