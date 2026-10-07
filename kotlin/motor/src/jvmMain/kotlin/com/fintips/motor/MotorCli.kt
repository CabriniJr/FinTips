package com.fintips.motor

import com.fintips.motor.ofx.lerOfx
import java.io.File

/**
 * Entrada de linha de comando do motor Kotlin.
 *
 * Existe para uma coisa só: deixar os dois motores produzirem a mesma resposta
 * para olho humano, sobre o mesmo extrato, no mesmo momento. O harness de ouro
 * já prova paridade, mas ele prova em arquivo de teste — e um teste verde não
 * convence ninguém do mesmo jeito que duas colunas de números iguais na tela.
 *
 *     gradle :motor:rodar --args="/caminho/extrato.ofx sal-opcional"
 *
 * Imprime JSON porque quem lê isto é o `scripts/comparar-motores.py`. O humano
 * lê a tabela que o comparador monta.
 *
 * **Só o que foi portado aparece aqui.** A heurística de classificação ainda
 * não existe no Kotlin, então nenhum dos dois lados classifica nada: toda
 * transação fica no fluxo padrão. Isso deixa a comparação honesta — os dois
 * motores respondem exatamente à mesma pergunta — e deixa visível o que ainda
 * falta portar.
 */
fun main(args: Array<String>) {
    if (args.isEmpty()) {
        System.err.println("uso: rodar <extrato.ofx> [sal]")
        kotlin.system.exitProcess(2)
    }
    val arquivo = File(args[0])
    if (!arquivo.exists()) {
        System.err.println("arquivo não encontrado: ${arquivo.absolutePath}")
        kotlin.system.exitProcess(2)
    }
    val sal = args.getOrElse(1) { "" }

    val extrato = lerOfx(arquivo.readText(Charsets.UTF_8), sal)
    val conciliacao = extrato.concilia()
    val base = baseline(extrato)

    // O score recebe o baseline recém-calculado, invisível zerado e nenhum
    // plano. Invisível depende das etiquetas da heurística, que não foi
    // portada; zerar nos dois lados é mais honesto do que inventar um valor.
    val sc = calcularScore(
        taxaPoupanca = base.taxaPoupancaMedia,
        volatilidadeDespesa = base.volatilidadeDespesa,
        mesesNoVermelho = base.mesesNoVermelho,
        rendaMediaMes = base.rendaMediaMes,
        despesaMediaMes = base.despesaMediaMes,
        taxasEsegurosMes = Dinheiro.ZERO,
        microGastosMes = Dinheiro.ZERO,
        planos = emptyList(),
        patrimonioLiquido = extrato.saldoDeclarado,
    )

    val j = Json()
    j.objeto {
        campo("motor", "kotlin")
        chave("conta"); objeto {
            campo("id_hash", extrato.conta.idHash)
            campo("instituicao", extrato.conta.instituicao)
            campo("id_banco", extrato.conta.idBanco)
            campo("tipo", extrato.conta.tipo)
            campo("moeda", extrato.conta.moeda)
        }
        campo("origem", extrato.origem)
        chave("periodo"); objeto {
            campo("inicio", extrato.periodoInicio.toString())
            campo("fim", extrato.periodoFim.toString())
        }
        chave("saldo"); objeto {
            campo("centavos", extrato.saldoDeclarado.centavos)
            campo("em", extrato.saldoEm.toString())
        }
        chave("conciliacao"); objeto {
            campo("bate", conciliacao.bate)
            campo("diferenca_centavos", conciliacao.diferenca.centavos)
        }
        chave("transacoes"); lista {
            for (t in extrato.transacoes) {
                objeto {
                    campo("id", t.id)
                    campo("data", t.momento.dataIso())
                    campo("hora", t.momento.horaMinuto())
                    campo("mes", t.mes)
                    campo("centavos", t.valor.centavos)
                    campo("memo", t.memoBruto)
                }
            }
        }
        chave("baseline"); objeto {
            chave("meses_considerados"); lista { for (m in base.mesesConsiderados) texto(m) }
            campo("renda_media_centavos", base.rendaMediaMes.centavos)
            campo("despesa_media_centavos", base.despesaMediaMes.centavos)
            campo("sobra_media_centavos", base.sobraMediaMes.centavos)
            campo("taxa_poupanca_media", base.taxaPoupancaMedia)
            campo("volatilidade_despesa", base.volatilidadeDespesa)
            campo("meses_no_vermelho", base.mesesNoVermelho.toLong())
        }
        chave("score"); objeto {
            campo("score", sc.score)
            campo("faixa", sc.faixa)
            chave("dimensoes"); lista {
                for (d in sc.dimensoes) {
                    objeto {
                        campo("nome", d.nome)
                        campo("pontos", d.pontos)
                        campo("maximo", d.maximo.toLong())
                    }
                }
            }
            campo("proximo_ponto", sc.proximoPonto)
        }
    }
    println(j)
}

/**
 * Emissor de JSON mínimo.
 *
 * Escrito à mão em vez de trazer `kotlinx-serialization` para o `jvmMain`: o
 * motor não tem dependência de runtime, e não vai ganhar uma por causa de uma
 * ferramenta de desenvolvimento. São três tipos de valor e um escape.
 */
private class Json {
    private val sb = StringBuilder()
    private var precisaVirgula = false

    fun objeto(bloco: Json.() -> Unit) {
        abrir('{'); bloco(); fechar('}')
    }

    fun lista(bloco: Json.() -> Unit) {
        abrir('['); bloco(); fechar(']')
    }

    fun chave(nome: String) {
        separar()
        sb.append(aspas(nome)).append(':')
        precisaVirgula = false
    }

    fun campo(nome: String, valor: String) { chave(nome); texto(valor) }
    fun campo(nome: String, valor: Long) { chave(nome); sb.append(valor); precisaVirgula = true }
    fun campo(nome: String, valor: Double) { chave(nome); sb.append(valor); precisaVirgula = true }
    fun campo(nome: String, valor: Boolean) { chave(nome); sb.append(valor); precisaVirgula = true }

    fun texto(valor: String) {
        separar(); sb.append(aspas(valor)); precisaVirgula = true
    }

    private fun abrir(c: Char) { separar(); sb.append(c); precisaVirgula = false }
    private fun fechar(c: Char) { sb.append(c); precisaVirgula = true }
    private fun separar() { if (precisaVirgula) sb.append(','); }

    private fun aspas(s: String): String {
        val out = StringBuilder("\"")
        for (c in s) {
            when (c) {
                '"' -> out.append("\\\"")
                '\\' -> out.append("\\\\")
                '\n' -> out.append("\\n")
                '\r' -> out.append("\\r")
                '\t' -> out.append("\\t")
                else -> if (c < ' ') out.append("\\u%04x".format(c.code)) else out.append(c)
            }
        }
        return out.append('"').toString()
    }

    override fun toString() = sb.toString()
}
