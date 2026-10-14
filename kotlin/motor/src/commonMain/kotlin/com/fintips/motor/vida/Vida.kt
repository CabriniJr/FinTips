package com.fintips.motor.vida

import com.fintips.motor.Dinheiro
import com.fintips.motor.arredondar
import com.fintips.motor.norm
import kotlinx.datetime.DatePeriod
import kotlinx.datetime.LocalDate
import kotlinx.datetime.minus
import kotlinx.datetime.plus

/**
 * O domínio de vida: atributos, missões e registros.
 *
 * Este módulo expande o FinTips de app de finanças para app de vida. O motor
 * financeiro inteiro — score, causas, perfil, alavancas — passa a ser **uma**
 * das seis frentes, a do dinheiro. As outras cinco são novas.
 *
 * A disciplina do projeto atravessa inteira, e fica mais afiada: o app não
 * decide se alguém treinou. Mas aqui aparece algo que não existia no lado
 * financeiro — **evidência de máquina**. O celular sabe o tempo de tela, os
 * passos e o horário de dormir sem precisar perguntar. Isso é mais forte que
 * palpite e mais fraco que a palavra da pessoa, e por isso tem uma escada de
 * proveniência própria.
 *
 * ## Por que uma escada separada da financeira
 *
 * `Origem`, no lado do dinheiro, responde "quem classificou esta transação".
 * Aqui a pergunta é outra: "como sabemos que isso foi feito". São perguntas
 * diferentes com respostas diferentes, e fundi-las forçaria o porte a divergir
 * do motor Python — que não tem nem nunca terá o conceito de sensor.
 */

/**
 * As seis frentes.
 *
 * As siglas vêm do plano do usuário, onde cada item de rotina já aparece
 * etiquetado. Mantê-las é o que permite ler o plano e gerar missões sem um
 * passo de tradução no meio, onde erro se esconde.
 */
enum class Atributo(val sigla: String, val nome: String, val oQueTreina: String) {
    FOR("FOR", "Força", "musculação, carga, movimento de resistência"),
    AGI("AGI", "Agilidade", "cardio, pedal, trilha, caminhada"),
    VIT("VIT", "Vitalidade", "sono, alimentação, exames, saúde"),
    INT("INT", "Intelecto", "estudo, leitura, lab, carreira"),
    FOC("FOC", "Foco", "atenção, tempo de tela, revisão"),
    OURO("OURO", "Ouro", "dinheiro: aporte, orçamento, decisão de compra");

    companion object {
        fun de(sigla: String): Atributo? =
            entries.firstOrNull { it.sigla.equals(sigla.trim(), ignoreCase = true) }
    }
}

/**
 * O ritmo da missão.
 *
 * O plano organiza a rotina em quatro camadas, e a diária existe com um
 * propósito explícito: ser o mínimo que cabe até no dia ruim. Uma missão
 * diária que só se cumpre no dia bom não é missão, é aspiração.
 */
enum class Cadencia(val chave: String, val diasDaJanela: Int) {
    DIARIA("diaria", 1),
    SEMANAL("semanal", 7),
    MENSAL("mensal", 30),
    TRIMESTRAL("trimestral", 90),
    ANUAL("anual", 365);

    companion object {
        fun de(chave: String): Cadencia? =
            entries.firstOrNull { it.chave.equals(chave.trim(), ignoreCase = true) }
    }
}

/**
 * Como se soube que a missão foi cumprida, em ordem de autoridade crescente.
 *
 * `SENSOR` fica acima de `AGENTE` de propósito, e é a diferença mais
 * importante desta escada. "Você treinou?" é pergunta factual: se o celular
 * mediu, a medida vale mais que a conclusão de quem interpretou a conversa.
 * Mas a pessoa continua acima de tudo, porque o sensor erra de um jeito que
 * ela sabe explicar — o celular ficou em casa, o vídeo foi assistido no
 * computador, o treino foi na rua.
 */
enum class OrigemDoRegistro(val chave: String, val autoridade: Int) {
    /** O app supôs pela rotina. Nunca conta como cumprido. */
    PRESUMIDO("presumido", 0),

    /** O agente concluiu a partir de uma conversa. */
    AGENTE("agente", 1),

    /** O aparelho mediu: tempo de tela, passos, horário. */
    SENSOR("sensor", 2),

    /** A pessoa marcou. Vence tudo. */
    USUARIO("usuario", 3);

    val contaComoCumprido: Boolean get() = autoridade >= AGENTE.autoridade

    companion object {
        fun de(chave: String): OrigemDoRegistro? =
            entries.firstOrNull { it.chave == chave }
    }
}

/**
 * Uma missão do plano.
 *
 * `comoMedir` descreve o que torna a missão verificável — é texto do plano,
 * não do app. `sensorPossivel` diz se existe aparelho capaz de responder: ele
 * não promete que o sensor está ligado, só que a pergunta é mensurável. Uma
 * missão sem sensor possível fica na palavra da pessoa, e o app diz isso na
 * tela em vez de fingir rigor que não tem.
 */
data class Missao(
    val id: String,
    val titulo: String,
    val atributo: Atributo,
    val cadencia: Cadencia,
    val comoMedir: String = "",
    val sensorPossivel: Boolean = false,
    /** De onde a missão veio. O plano da pessoa é dela: origem `usuario`. */
    val porque: String = "",
    val ativa: Boolean = true,
    /**
     * Quanto a missão move por mês, quando é de dinheiro. É o que traduz preço
     * em meses de aporte: "este item custa 0,58 do seu aporte" diz mais que o
     * valor em reais.
     */
    val valorMensal: Dinheiro? = null,
    /**
     * O que esta missão considera conflito. **Declarado pela pessoa**, nunca
     * inferido: é a única porta pela qual uma compra toca uma frente que não é
     * dinheiro.
     */
    val colideCom: List<String> = emptyList(),
)

/** Um cumprimento, com a data e como se soube. */
data class RegistroDeMissao(
    val missaoId: String,
    val dia: LocalDate,
    val origem: OrigemDoRegistro,
    /** O que o sensor mediu, quando houve sensor. Texto livre: "0 min de tela". */
    val medida: String = "",
    val nota: String = "",
) {
    val contaComoCumprido: Boolean get() = origem.contaComoCumprido
}

/**
 * O estado de uma missão numa data.
 *
 * `sequencia` conta dias (ou janelas) consecutivos cumpridos até `ate`.
 * `recorde` guarda a maior sequência já alcançada — ele existe porque o plano
 * é explícito sobre recaída: *"nunca dois dias seguidos; caiu hoje, amanhã é
 * dia limpo"*. Zerar o recorde junto com a sequência transformaria um
 * tropeço em perda de tudo, que é exatamente o pensamento que o plano manda
 * evitar.
 */
data class EstadoDaMissao(
    val missao: Missao,
    val cumpridaNaJanela: Boolean,
    val sequencia: Int,
    val recorde: Int,
    val ultimoRegistro: RegistroDeMissao?,
)

/**
 * Calcula sequência e recorde de uma missão diária.
 *
 * Só dias com registro que **conta** entram; um registro `presumido` é
 * ignorado, porque o app supor que você treinou não é você ter treinado.
 */
fun estadoDiario(
    missao: Missao,
    registros: List<RegistroDeMissao>,
    hoje: LocalDate,
): EstadoDaMissao {
    val cumpridos = registros
        .filter { it.missaoId == missao.id && it.contaComoCumprido }
        .map { it.dia }
        .toSet()

    var sequencia = 0
    var dia = hoje
    // Hoje ainda não cumprido não quebra a sequência — o dia não acabou.
    if (dia !in cumpridos) dia = dia.minus(DatePeriod(days = 1))
    while (dia in cumpridos) {
        sequencia += 1
        dia = dia.minus(DatePeriod(days = 1))
    }

    var recorde = 0
    var corrente = 0
    var anterior: LocalDate? = null
    for (d in cumpridos.sorted()) {
        corrente = if (anterior != null && anterior.plus(DatePeriod(days = 1)) == d) corrente + 1 else 1
        if (corrente > recorde) recorde = corrente
        anterior = d
    }

    return EstadoDaMissao(
        missao = missao,
        cumpridaNaJanela = hoje in cumpridos,
        sequencia = sequencia,
        recorde = recorde,
        ultimoRegistro = registros
            .filter { it.missaoId == missao.id && it.contaComoCumprido }
            .maxByOrNull { it.dia },
    )
}

data class ForcaDoAtributo(
    val atributo: Atributo,
    val missoes: Int,
    val cumpridas: Int,
    val pct: Double,
    /** Missões cujo cumprimento foi medido por aparelho, e não só afirmado. */
    val comEvidenciaDeMaquina: Int,
)

/**
 * Quanto de cada frente foi cumprido na janela.
 *
 * Deliberadamente **não** existe XP nem nível aqui. Nível é um número que sobe
 * para sempre e, por construção, não consegue dizer "esta semana foi pior que
 * a passada" — que é a única informação que muda comportamento. A barra
 * mostra a janela atual; a sequência mostra constância; o recorde mostra do
 * que a pessoa já foi capaz.
 */
fun forcaDosAtributos(
    missoes: List<Missao>,
    registros: List<RegistroDeMissao>,
    hoje: LocalDate,
    cadencia: Cadencia = Cadencia.DIARIA,
): List<ForcaDoAtributo> {
    val doPeriodo = missoes.filter { it.ativa && it.cadencia == cadencia }
    val inicio = hoje.minus(DatePeriod(days = cadencia.diasDaJanela - 1))

    val cumpridosPorMissao = registros
        .filter { it.contaComoCumprido && it.dia >= inicio && it.dia <= hoje }
        .groupBy { it.missaoId }

    return Atributo.entries.map { atributo ->
        val dele = doPeriodo.filter { it.atributo == atributo }
        val cumpridas = dele.count { cumpridosPorMissao.containsKey(it.id) }
        val porMaquina = dele.count { m ->
            cumpridosPorMissao[m.id]?.any { it.origem == OrigemDoRegistro.SENSOR } == true
        }
        ForcaDoAtributo(
            atributo = atributo,
            missoes = dele.size,
            cumpridas = cumpridas,
            // Arredondado em uma casa porque o motor Python arredonda — uma
            // missão de três dá 33.3 lá e 33.33333333333333 aqui se a divisão
            // for crua. As duas "parecem certas", e a diferença só apareceria
            // quando alguém comparasse a barra do app com o número do painel.
            pct = if (dele.isEmpty()) 0.0 else arredondar(cumpridas.toDouble() / dele.size * 100, 1),
            comEvidenciaDeMaquina = porMaquina,
        )
    }
}

/**
 * Quanto do que o app afirma está apoiado em medida, e não só em memória.
 *
 * É o espelho de `cobertura_da_classificacao` do lado financeiro, e existe
 * pelo mesmo motivo: deixar visível o quanto ainda é palavra. O plano diz que
 * força de vontade sozinha já falhou antes — e memória de uso de celular é
 * justamente o que distorce a favor de quem lembra.
 */
fun coberturaDeEvidencia(
    missoes: List<Missao>,
    registros: List<RegistroDeMissao>,
): Map<String, Any> {
    val ativas = missoes.filter { it.ativa }
    val mensuraveis = ativas.count { it.sensorPossivel }
    val comRegistroDeSensor = ativas.count { m ->
        registros.any { it.missaoId == m.id && it.origem == OrigemDoRegistro.SENSOR }
    }
    return linkedMapOf(
        "missoes_ativas" to ativas.size,
        "mensuraveis_por_aparelho" to mensuraveis,
        "com_medida_registrada" to comRegistroDeSensor,
        "pct_medido" to if (ativas.isEmpty()) 0.0
                        else arredondar(comRegistroDeSensor.toDouble() / ativas.size * 100, 1),
        "explicacao" to (
            "quanto do que o app afirma veio de medida. O resto é memória, e " +
            "memória de tempo de tela distorce a favor de quem lembra"
        ),
    )
}

// ---------------------------------------------- a ponte com o dinheiro

/**
 * Uma regra que a pessoa escreveu para si. O motor aplica; não opina.
 *
 * É o único tipo deste pacote com direito de mexer num veredito de compra, e
 * só porque o veredito já é dela: ela decidiu esperar, e pediu ao app para
 * aplicar. Daí `porque` ser obrigatório na construção — regra que muda
 * veredito sem dizer de onde veio é opinião do app disfarçada.
 */
data class RegraDeclarada(
    val id: String,
    val tipo: String,
    val acimaDe: Dinheiro,
    val dias: Int,
    val porque: String,
) {
    init {
        require(porque.isNotBlank()) {
            "regra '$id' sem porque — regra que mexe em veredito precisa dizer " +
                "de onde veio, ou vira opinião do app"
        }
        require(tipo in TIPOS_DE_REGRA) {
            "regra '$id': tipo '$tipo' não é suportado. Suportados: $TIPOS_DE_REGRA"
        }
    }

    companion object {
        val TIPOS_DE_REGRA = listOf("espera_antes_de_comprar")
    }
}

/** O catálogo da pessoa e os registros dela. */
data class Vida(
    val missoes: List<Missao> = emptyList(),
    val registros: List<RegistroDeMissao> = emptyList(),
    val regras: List<RegraDeclarada> = emptyList(),
) {
    val vazia: Boolean get() = missoes.isEmpty()
}

data class RegraAplicada(
    val id: String,
    val acimaDe: Dinheiro,
    val dias: Int,
    val porqueElaEscreveu: String,
    val aplica: Boolean,
    val liberadaEm: LocalDate?,
)

data class MissaoEmJogo(
    val missao: String,
    val titulo: String,
    val atributo: Atributo,
    val cadencia: Cadencia,
    val porQueEntraAqui: String,
    val colisaoDeclarada: String?,
    val porqueDaMissao: String,
    val sequenciaEmRisco: Int?,
    val recorde: Int?,
)

data class CustoEmAportes(
    val missao: String,
    val aporteMensal: Dinheiro,
    val mesesDeAporte: Double,
)

data class ContextoDeCompra(
    val regraDeclarada: RegraAplicada?,
    val missoesEmJogo: List<MissaoEmJogo>,
    val custoEmAportes: CustoEmAportes?,
    val frentesNoMomento: List<ForcaDoAtributo>,
    val semMissoesCadastradas: Boolean,
)

/**
 * O que as seis frentes dizem sobre uma compra.
 *
 * O módulo **não infere nada**. A colisão entre uma compra e uma missão existe
 * só porque a pessoa escreveu a palavra em `colideCom`: o motor não decide que
 * tablet é vício. É a mesma regra das causas, que não têm nem terão detecção —
 * e diagnóstico errado sobre vício é pior que silêncio.
 *
 * Missão de dinheiro entra sempre, sem precisar de palavra declarada, porque
 * qualquer compra disputa com ela por definição.
 */
fun contextoDeCompra(
    vida: Vida,
    item: String,
    preco: Dinheiro,
    categoria: String = "",
    tags: List<String> = emptyList(),
    hoje: LocalDate,
): ContextoDeCompra {
    val texto = norm("$item $categoria ${tags.joinToString(" ")}")

    val regra = vida.regras.firstOrNull { it.tipo == "espera_antes_de_comprar" }?.let { r ->
        val aplica = preco.centavos > r.acimaDe.centavos
        RegraAplicada(
            id = r.id,
            acimaDe = r.acimaDe,
            dias = r.dias,
            porqueElaEscreveu = r.porque,
            aplica = aplica,
            liberadaEm = if (aplica) hoje.plus(DatePeriod(days = r.dias)) else null,
        )
    }

    val emJogo = vida.missoes.filter { it.ativa }.mapNotNull { m ->
        val termo = m.colideCom.firstOrNull { it.isNotBlank() && norm(it) in texto }
        if (termo == null && m.atributo != Atributo.OURO) return@mapNotNull null
        val estado = if (m.cadencia == Cadencia.DIARIA) estadoDiario(m, vida.registros, hoje) else null
        MissaoEmJogo(
            missao = m.id,
            titulo = m.titulo,
            atributo = m.atributo,
            cadencia = m.cadencia,
            porQueEntraAqui = if (termo != null)
                "a pessoa declarou que '$termo' colide com esta missão"
            else "missão de dinheiro — toda compra disputa com ela",
            colisaoDeclarada = termo,
            porqueDaMissao = m.porque,
            sequenciaEmRisco = estado?.sequencia,
            recorde = estado?.recorde,
        )
    }

    val aporte = vida.missoes.firstOrNull {
        it.ativa && it.atributo == Atributo.OURO && (it.valorMensal?.centavos ?: 0L) > 0L
    }
    val custo = aporte?.let { m ->
        val mensal = m.valorMensal!!
        CustoEmAportes(
            missao = m.id,
            aporteMensal = mensal,
            mesesDeAporte = mesesDeAporte(preco, mensal),
        )
    }

    return ContextoDeCompra(
        regraDeclarada = regra,
        missoesEmJogo = emJogo,
        custoEmAportes = custo,
        frentesNoMomento = forcaDosAtributos(vida.missoes, vida.registros, hoje),
        semMissoesCadastradas = vida.vazia,
    )
}

/**
 * Preço em meses de aporte, com duas casas.
 *
 * **Em aritmética inteira, e não em `Double`, por um motivo que custou um
 * harness para aparecer.** O Python divide em `Decimal` exato e arredonda
 * meio-para-o-par; o empate de meio centésimo (`0.005`) acontece de verdade lá.
 * Em `Double` esse empate nunca existe — `0.005` não é representável, o valor
 * cai um fio acima ou abaixo, e o meio-para-o-par nunca se aplica. O resultado
 * é divergência em metade dos casos de empate, nos dois sentidos:
 *
 * ```
 * preco=3 cent, aporte=200 cent  → python 0.02, kotlin 0.01
 * preco=5 cent, aporte=200 cent  → python 0.02, kotlin 0.03
 * ```
 *
 * `Dinheiro.dividir(Long)` já faz essa divisão com o empate exato. Multiplicar
 * por 100 antes põe os centésimos na casa das unidades, e aí a conta inteira é
 * a mesma que o `Decimal` faz.
 */
internal fun mesesDeAporte(preco: Dinheiro, aporteMensal: Dinheiro): Double =
    Dinheiro(preco.centavos * 100).dividir(aporteMensal.centavos).centavos / 100.0

data class ContextoDePlanos(
    val missaoDeAporte: Missao?,
    val aporteMensal: Dinheiro,
    val exigidoPelosPlanosMes: Dinheiro,
    val folgaMensal: Dinheiro,
    val planosCabemNoAporte: Boolean,
)

/**
 * O aporte que ela assinou contra o que os planos exigem por mês.
 *
 * Compromisso declarado de um lado, necessidade dos planos do outro. Quando não
 * fecham, o motor mostra a diferença e para: subir o aporte, esticar o prazo ou
 * cortar plano é escolha dela.
 */
fun contextoDePlanos(vida: Vida, exigidoPelosPlanos: Dinheiro): ContextoDePlanos {
    val aporte = vida.missoes.firstOrNull {
        it.ativa && it.atributo == Atributo.OURO && (it.valorMensal?.centavos ?: 0L) > 0L
    }
    val mensal = aporte?.valorMensal ?: Dinheiro(0)
    return ContextoDePlanos(
        missaoDeAporte = aporte,
        aporteMensal = mensal,
        exigidoPelosPlanosMes = exigidoPelosPlanos,
        folgaMensal = Dinheiro(mensal.centavos - exigidoPelosPlanos.centavos),
        planosCabemNoAporte = mensal.centavos >= exigidoPelosPlanos.centavos,
    )
}
