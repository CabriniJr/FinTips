#!/usr/bin/env python3
"""Gera os arquivos de ouro que o motor Kotlin tem que reproduzir.

A porta para Kotlin é módulo a módulo, e a única forma de saber que nada mudou
de comportamento no caminho é ter os dois motores respondendo a mesma pergunta
e comparar. Este script é o lado Python dessa conversa: ele roda o motor atual
e grava a resposta em JSON, num formato que o teste Kotlin lê.

O ouro é **gerado**, nunca escrito à mão. Ouro escrito à mão é a opinião de
quem escreveu sobre o que o motor deveria fazer; ouro gerado é o que ele faz.
A diferença aparece exatamente nos casos esquisitos, que são os que importam.

    python3 scripts/gerar-ouro.py

Regravar o ouro depois de mudar o motor Python é normal e esperado — o diff do
arquivo passa a mostrar, em números, o que a mudança causou.
"""

from __future__ import annotations

import json
import sys
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

DESTINO = RAIZ / "kotlin" / "motor" / "src" / "jvmTest" / "resources" / "ouro"

from fintips.parsers.ofx import parse_amount  # noqa: E402


def centavos(valor: Decimal) -> int:
    """A mesma conversão que o motor Kotlin faz ao guardar em Long."""
    return int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def ouro_dinheiro() -> dict:
    """Leitura de valor e arredondamento — a base de tudo que vem depois.

    Os textos incluem os formatos que aparecem em extrato brasileiro e os
    casos de fronteira do arredondamento: empate exato (1.005 e 1.015, que vão
    para lados diferentes porque meio-para-o-par olha a paridade) e o `"1.234"`
    ambíguo, que o motor lê como um real e vinte e três.
    """
    textos = [
        "-23.21", "R$ 1.234,56", "1,234.56", "1.234", "1.23", "1,234",
        "5", "5,5", "0", "", "12,30", "-1.234,56", "(45.60)",
        "1.2345", "1.235", "1.005", "1.015", "0.005", "0.015",
        "1234567.89", "-0.01", "  42,00  ",
    ]
    leituras = []
    for t in textos:
        v = parse_amount(t)
        leituras.append({"texto": t, "centavos": centavos(v), "decimal": str(v)})

    divisoes = []
    for c, d in [
        (5, 2), (7, 2), (3, 2), (1, 2), (10, 3), (11, 3), (100, 7),
        (-5, 2), (-7, 2), (-10, 3), (-1, 2), (6001, 3), (0, 5),
        (123456, 6), (99999, 7), (250, 4), (150, 4),
    ]:
        q = (Decimal(c) / Decimal(d)).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
        divisoes.append({"centavos": c, "divisor": d, "esperado": int(q)})

    return {
        "o_que_e": "leitura de valor e divisão com arredondamento meio-para-o-par",
        "gerado_por": "fintips.parsers.ofx.parse_amount + Decimal.quantize",
        "leituras": leituras,
        "divisoes": divisoes,
    }


# Sal fixo para o ouro. O sal real do usuário mora em `.fintips-salt` e nunca
# sai da máquina; aqui ele precisa ser conhecido dos dois lados, senão o hash
# da conta jamais bateria e o teste falharia por motivo errado.
SAL_DO_OURO = "ouro-do-harness"


def ouro_ofx() -> dict:
    """O canônico inteiro do fixture, transação a transação.

    Este é o ouro que pega de verdade: ele cobre leitura de tag SGML, data com
    fuso, valor em pt-BR, deduplicação por (FITID, valor, data), desambiguação
    de FITID repetido, ordenação e conciliação. Se o leitor Kotlin errar em
    qualquer um desses, o teste aponta a transação.
    """
    from fintips.parsers.ofx import parse_ofx

    stmt = parse_ofx(RAIZ / "tests" / "fixture.ofx", salt=SAL_DO_OURO)
    bate, diff = stmt.reconciles()
    return {
        "o_que_e": "canônico completo do tests/fixture.ofx",
        "gerado_por": "fintips.parsers.ofx.parse_ofx",
        "sal": SAL_DO_OURO,
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
        "saldo": {
            "centavos": centavos(stmt.ledger_balance),
            "em": stmt.balance_as_of.isoformat(),
        },
        "conciliacao": {"bate": bate, "diferenca_centavos": centavos(diff)},
        "transacoes": [
            {
                "id": t.id,
                "data": t.ts.strftime("%Y-%m-%d"),
                "hora": t.ts.strftime("%H:%M"),
                "mes": t.month,
                "centavos": centavos(t.amount),
                "memo": t.memo_raw,
                "conta_id": t.account_id,
            }
            for t in stmt.transactions
        ],
    }


def ouro_datas() -> dict:
    """Leitura de data OFX, isolada do fixture.

    Este ouro nasceu de uma lacuna encontrada na prática: todo `DTPOSTED` do
    fixture traz `[-3:BRT]` explícito, então o fuso padrão nunca era
    exercitado. Trocar o padrão de -3 para -2 no leitor Kotlin não quebrava
    teste nenhum — não porque o harness fosse cego, mas porque o fixture não
    fazia a pergunta.

    Harness é tão bom quanto o dado que ele compara. Estes casos fazem a
    pergunta: data sem fuso, só com dia, com fuso fracionário, em dd/mm/aaaa.
    """
    from fintips.parsers.ofx import parse_datetime

    brutos = [
        "20260601100000[-3:BRT]",
        "20260601100000",             # sem fuso: cai no padrão
        "20260601",                   # só a data
        "20260601235959[-3:BRT]",
        "20260601000000[+0:GMT]",
        "20260601120000[-3.5:XXX]",   # fuso fracionário
        "30/06/2026",
        "1/1/2027",
    ]
    casos = []
    for b in brutos:
        dt = parse_datetime(b)
        casos.append({
            "bruto": b,
            "data": dt.strftime("%Y-%m-%d"),
            "hora": dt.strftime("%H:%M"),
            "mes": dt.strftime("%Y-%m"),
            "deslocamento_segundos": int(dt.utcoffset().total_seconds()),
        })
    return {
        "o_que_e": "leitura de data OFX, incluindo os casos que o fixture não cobre",
        "gerado_por": "fintips.parsers.ofx.parse_datetime",
        "casos": casos,
    }


def ouro_privacidade() -> dict:
    """Hash de conta e pseudônimo — precisam bater dígito por dígito.

    Se divergirem, o workspace de quem já usa o motor Python vira lixo na
    primeira importação pelo Kotlin: a mesma conta apareceria como duas.
    """
    from fintips.privacy import digest, hash_account, pseudonym

    entradas = ["12345678", "0001-9", "", "Conta Corrente 42", "ÁÉÍÕÇ", "acentuação"]
    return {
        "o_que_e": "hash truncado de conta e pseudônimo de pessoa física",
        "gerado_por": "fintips.privacy.digest / hash_account / pseudonym",
        "sal": SAL_DO_OURO,
        "casos": [
            {
                "valor": v,
                "digest": digest(v, SAL_DO_OURO),
                "hash_conta": hash_account(v, SAL_DO_OURO),
                "pseudonimo": pseudonym(v, SAL_DO_OURO),
            }
            for v in entradas
        ],
    }


GERADORES = {
    "dinheiro.json": ouro_dinheiro,
    "datas.json": ouro_datas,
    "privacidade.json": ouro_privacidade,
    "ofx.json": ouro_ofx,
    # Os próximos entram aqui, na ordem da porta:
    #   "classificacao.json" — regras determinísticas e cobertura
    #   "analise.json"       — baseline, meses, recorrências
}


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nome, gerar in GERADORES.items():
        dados = gerar()
        caminho = DESTINO / nome
        caminho.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        n = sum(len(v) for v in dados.values() if isinstance(v, list))
        print(f"{caminho.relative_to(RAIZ)}  ({n} casos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
