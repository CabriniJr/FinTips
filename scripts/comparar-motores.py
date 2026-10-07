#!/usr/bin/env python3
"""Roda os dois motores no mesmo extrato e mostra o resultado lado a lado.

O harness de ouro já prova paridade, mas prova em arquivo de teste e fala por
`assert`. Isto aqui é para olho humano: duas colunas de números sobre o **seu**
extrato, com um sinal por linha dizendo se bateram.

    python3 scripts/comparar-motores.py extrato.ofx

A comparação cobre **só o que foi portado**: leitura do OFX, baseline e score.
E cobre de um jeito deliberadamente cru — nenhum dos dois lados roda a
heurística de classificação, porque ela ainda não existe no Kotlin. Por isso
toda transação fica no fluxo padrão, a renda aparece como zero e o score sai
baixo. Não é erro: é a pergunta exata que os dois motores conseguem responder
hoje, feita igual para os dois.

Sai com código 1 se algo divergir, para poder entrar em CI sem adaptação.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

SAL = "comparacao"

VERDE = "\033[32m"
VERMELHO = "\033[31m"
CINZA = "\033[90m"
NEGRITO = "\033[1m"
FIM = "\033[0m"


def cor(texto: str, c: str) -> str:
    """Sem cor quando a saída não é um terminal — senão o log de CI vira sopa."""
    return f"{c}{texto}{FIM}" if sys.stdout.isatty() else texto


def centavos(valor: Decimal) -> int:
    return int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


# --------------------------------------------------------------------------
# os dois motores
# --------------------------------------------------------------------------
def motor_python(caminho: Path) -> dict:
    from fintips.analysis import baseline
    from fintips.parsers.ofx import parse_ofx
    from fintips.score import compute

    stmt = parse_ofx(caminho, salt=SAL)
    bate, diff = stmt.reconciles()
    base = baseline(stmt)

    # mesmas entradas que o lado Kotlin usa: invisível zerado (depende da
    # heurística, que não foi portada) e nenhum plano cadastrado
    sc = compute(
        base,
        {"taxas_e_seguros": {"por_mes": 0}, "micro_gastos": {"por_mes": 0}},
        [],
        patrimonio_liquido=stmt.ledger_balance,
    )

    return {
        "motor": "python",
        "conta": {
            "id_hash": stmt.account.id_hash,
            "instituicao": stmt.account.institution,
            "id_banco": stmt.account.bank_id,
            "tipo": stmt.account.type,
            "moeda": stmt.account.currency,
        },
        "origem": stmt.source,
        "periodo": {
            "inicio": stmt.period_start.isoformat(),
            "fim": stmt.period_end.isoformat(),
        },
        "saldo": {"centavos": centavos(stmt.ledger_balance),
                  "em": stmt.balance_as_of.isoformat()},
        "conciliacao": {"bate": bate, "diferenca_centavos": centavos(diff)},
        "transacoes": [
            {
                "id": t.id,
                "data": t.ts.strftime("%Y-%m-%d"),
                "hora": t.ts.strftime("%H:%M"),
                "mes": t.month,
                "centavos": centavos(t.amount),
                "memo": t.memo_raw,
            }
            for t in stmt.transactions
        ],
        "baseline": {
            "meses_considerados": base["meses_considerados"],
            "renda_media_centavos": centavos(Decimal(str(base["renda_media_mes"]))),
            "despesa_media_centavos": centavos(Decimal(str(base["despesa_media_mes"]))),
            "sobra_media_centavos": centavos(Decimal(str(base["sobra_media_mes"]))),
            "taxa_poupanca_media": base["taxa_poupanca_media"],
            "volatilidade_despesa": base["volatilidade_despesa"],
            "meses_no_vermelho": base["meses_no_vermelho"],
        },
        "score": {
            "score": sc["score"],
            "faixa": sc["faixa"],
            "dimensoes": [
                {"nome": d["nome"], "pontos": d["pontos"], "maximo": d["maximo"]}
                for d in sc["dimensoes"]
            ],
            "proximo_ponto": sc["proximo_ponto"],
        },
    }


def motor_kotlin(caminho: Path) -> dict:
    """Chama o Gradle. Demora na primeira vez; depois o build fica em cache."""
    gradle = os.environ.get("GRADLE", "gradle")
    cmd = [
        gradle, "-p", str(RAIZ / "kotlin"), ":motor:rodar",
        f"--args={caminho} {SAL}", "--console=plain", "-q",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(cor("o motor Kotlin não rodou:", VERMELHO), file=sys.stderr)
        print(r.stderr[-3000:], file=sys.stderr)
        sys.exit(2)

    # O Gradle pode cuspir avisos antes do JSON (JAVA_TOOL_OPTIONS, por
    # exemplo). A última linha que começa com '{' é a nossa.
    linhas = [l for l in r.stdout.splitlines() if l.startswith("{")]
    if not linhas:
        print(cor("o motor Kotlin não imprimiu JSON:", VERMELHO), file=sys.stderr)
        print(r.stdout[-3000:], file=sys.stderr)
        sys.exit(2)
    return json.loads(linhas[-1])


# --------------------------------------------------------------------------
# comparação
# --------------------------------------------------------------------------
def real(centavos_: int) -> str:
    return f"{centavos_ / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def linhas_para_comparar(p: dict, k: dict) -> list[tuple[str, str, object, object]]:
    """(seção, rótulo, valor_python, valor_kotlin) — na ordem de leitura."""
    L: list[tuple[str, str, object, object]] = []

    def par(secao, rotulo, caminho):
        a, b = p, k
        for chave in caminho:
            a, b = a[chave], b[chave]
        L.append((secao, rotulo, a, b))

    par("leitura", "hash da conta", ("conta", "id_hash"))
    par("leitura", "instituição", ("conta", "instituicao"))
    par("leitura", "origem", ("origem",))
    par("leitura", "período início", ("periodo", "inicio"))
    par("leitura", "período fim", ("periodo", "fim"))
    par("leitura", "saldo declarado", ("saldo", "centavos"))
    par("leitura", "saldo em", ("saldo", "em"))
    par("leitura", "concilia", ("conciliacao", "bate"))
    par("leitura", "diferença", ("conciliacao", "diferenca_centavos"))
    L.append(("leitura", "nº de transações", len(p["transacoes"]), len(k["transacoes"])))

    par("baseline", "meses considerados", ("baseline", "meses_considerados"))
    par("baseline", "renda média/mês", ("baseline", "renda_media_centavos"))
    par("baseline", "despesa média/mês", ("baseline", "despesa_media_centavos"))
    par("baseline", "sobra média/mês", ("baseline", "sobra_media_centavos"))
    par("baseline", "taxa de poupança", ("baseline", "taxa_poupanca_media"))
    par("baseline", "volatilidade", ("baseline", "volatilidade_despesa"))
    par("baseline", "meses no vermelho", ("baseline", "meses_no_vermelho"))

    par("score", "score", ("score", "score"))
    par("score", "faixa", ("score", "faixa"))
    for i, d in enumerate(p["score"]["dimensoes"]):
        kd = k["score"]["dimensoes"][i]
        L.append(("score", f"  {d['nome']}", d["pontos"], kd["pontos"]))
    par("score", "maior ganho", ("score", "proximo_ponto"))
    return L


def formatar(rotulo: str, valor) -> str:
    monetario = any(t in rotulo for t in ("saldo", "renda", "despesa", "sobra", "diferença"))
    if monetario and isinstance(valor, int):
        return real(valor)
    if isinstance(valor, list):
        return ", ".join(str(v) for v in valor) or "—"
    if isinstance(valor, bool):
        return "sim" if valor else "não"
    return str(valor)


def comparar_transacoes(p: dict, k: dict) -> list[str]:
    problemas = []
    if len(p["transacoes"]) != len(k["transacoes"]):
        return [f"número de transações: python {len(p['transacoes'])}, kotlin {len(k['transacoes'])}"]
    for i, (a, b) in enumerate(zip(p["transacoes"], k["transacoes"])):
        for campo in ("id", "data", "hora", "mes", "centavos", "memo"):
            if a[campo] != b[campo]:
                problemas.append(f"transação {i} ({a['id']}) {campo}: python {a[campo]!r}, kotlin {b[campo]!r}")
    return problemas


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        print("uso: python3 scripts/comparar-motores.py <extrato.ofx>")
        return 2
    caminho = Path(sys.argv[1]).expanduser().resolve()
    if not caminho.exists():
        print(cor(f"arquivo não encontrado: {caminho}", VERMELHO))
        return 2

    print(cor(f"extrato: {caminho.name}", CINZA))
    print(cor("rodando o motor Python…", CINZA))
    p = motor_python(caminho)
    print(cor("rodando o motor Kotlin (Gradle; a primeira vez demora)…", CINZA))
    k = motor_kotlin(caminho)
    print()

    largura_rotulo = 22
    largura_valor = 26
    cabecalho = (
        f"{'':<{largura_rotulo}} {'PYTHON':<{largura_valor}} {'KOTLIN':<{largura_valor}}"
    )
    print(cor(NEGRITO + cabecalho + FIM, NEGRITO) if sys.stdout.isatty() else cabecalho)
    print(cor("─" * (largura_rotulo + largura_valor * 2 + 4), CINZA))

    secao_atual = None
    divergencias = 0
    for secao, rotulo, vp, vk in linhas_para_comparar(p, k):
        if secao != secao_atual:
            secao_atual = secao
            print(cor(f"\n{secao.upper()}", CINZA))
        igual = vp == vk
        if not igual:
            divergencias += 1
        marca = cor("✓", VERDE) if igual else cor("✗", VERMELHO)
        tp, tk = formatar(rotulo, vp), formatar(rotulo, vk)
        if len(tp) > largura_valor - 1 or len(tk) > largura_valor - 1:
            # texto longo (a dica do maior ganho, por exemplo) em duas linhas
            print(f"{marca} {rotulo:<{largura_rotulo - 2}}")
            print(f"    python: {tp}")
            print(f"    kotlin: {tk}")
        else:
            linha = f"{marca} {rotulo:<{largura_rotulo - 2}} {tp:<{largura_valor}} {tk:<{largura_valor}}"
            print(linha if igual else cor(linha, VERMELHO))

    problemas = comparar_transacoes(p, k)
    print(cor("\nTRANSAÇÕES", CINZA))
    if problemas:
        divergencias += len(problemas)
        for x in problemas:
            print(cor(f"✗ {x}", VERMELHO))
    else:
        n = len(p["transacoes"])
        print(f"{cor('✓', VERDE)} as {n} transações batem em id, data, hora, valor e memo")

    print()
    if divergencias:
        print(cor(f"{divergencias} divergência(s) entre os motores.", VERMELHO))
        return 1
    print(cor("os dois motores deram exatamente o mesmo resultado.", VERDE))
    print(cor(
        "cobre o que já foi portado: leitura do OFX, baseline e score. "
        "A heurística de classificação ainda não existe no Kotlin, então "
        "nenhum dos dois lados classifica — por isso a renda aparece zerada.",
        CINZA,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
