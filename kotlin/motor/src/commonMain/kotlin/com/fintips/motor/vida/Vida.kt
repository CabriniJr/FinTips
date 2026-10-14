package com.fintips.motor.vida

import com.fintips.motor.arredondar
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
