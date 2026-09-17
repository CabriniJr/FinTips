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


GERADORES = {
    "dinheiro.json": ouro_dinheiro,
    # Os próximos entram aqui, na ordem da porta:
    #   "modelo.json"   — Transaction/Account/Statement do fixture
    #   "ofx.json"      — o canônico inteiro, transação a transação
    #   "analise.json"  — baseline, meses, recorrências
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
