package com.fintips.motor

/**
 * Pseudonimização local.
 *
 * O número da conta, o CPF e o nome de terceiros nunca entram no modelo
 * canônico. O que entra é um hash truncado, estável entre importações, salgado
 * com um segredo que mora só na máquina do usuário (`.fintips-salt`).
 *
 * O sal importa mais do que parece: sem ele, hash de conta bancária é
 * reversível por força bruta em segundos — o espaço de números de conta é
 * pequeno.
 *
 * SHA-256 entra por `expect`/`actual` em vez de uma implementação à mão aqui.
 * Escrever criptografia à mão é uma ideia ruim mesmo quando o algoritmo é
 * conhecido, e cada alvo já traz a sua: `MessageDigest` na JVM e no Android,
 * `CryptoKit` no iOS quando ele entrar.
 */

expect fun sha256Hex(texto: String): String

/** Digest truncado. O formato do Python: sha256(sal + "|" + valor)[:tamanho]. */
fun digest(valor: String, sal: String = "", tamanho: Int = 10): String =
    sha256Hex("$sal|$valor").take(tamanho)

fun hashConta(numeroConta: String, sal: String = ""): String = "acct:" + digest(numeroConta, sal)

/**
 * Apelido estável de pessoa física.
 *
 * O `norm` antes do hash não é enfeite: sem ele, "José" e "JOSE" gerariam
 * pseudônimos diferentes e a mesma pessoa apareceria duas vezes no extrato.
 * Foi por isso que esta função esperou o módulo de texto ficar pronto, em vez
 * de ser portada pela metade.
 */
fun pseudonimo(nome: String, sal: String = ""): String = "PF:" + digest(norm(nome), sal, 6)
