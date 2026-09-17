"""Testes do motor. Rode: python -m pytest tests -q (ou python tests/test_engine.py)."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fintips.analysis import baseline, invisible_spending, recurrences  # noqa: E402
from fintips.categorize import Categorizer  # noqa: E402
from fintips.parsers.ofx import parse_amount, parse_datetime, parse_ofx  # noqa: E402
from fintips.purchases import PurchaseIntent, evaluate as eval_buy  # noqa: E402
from fintips.score import compute  # noqa: E402

FIXTURE = Path(__file__).parent / "fixture.ofx"


def test_parse_amount():
    assert parse_amount("-23.21") == Decimal("-23.21")
    assert parse_amount("R$ 1.234,56") == Decimal("1234.56")
    assert parse_amount("1.234,56") == Decimal("1234.56")
    assert parse_amount("1,234.56") == Decimal("1234.56")


def test_parse_datetime():
    dt = parse_datetime("20260504191415[-3:BRT]")
    assert (dt.year, dt.month, dt.day, dt.hour) == (2026, 5, 4, 19)
    assert parse_datetime("15/09/2026").day == 15


def _stmt():
    st = parse_ofx(FIXTURE)
    Categorizer(my_names=["Titular Da Conta Exemplo"], aliases={"Carlos Alberto Nogueira": "pai"}).apply_all(
        st.transactions
    )
    return st


def test_reversal_keeps_both_legs():
    """O PagBank repete o FITID no estorno — as duas pernas têm que sobreviver."""
    st = _stmt()
    ids = [t.id for t in st.transactions]
    assert len(ids) == len(set(ids)), "ids devem ser únicos"
    assert len(st.transactions) == 9


def test_reconciliation():
    st = _stmt()
    ok, diff = st.reconciles()
    assert ok, f"não concilia: {diff}"


def test_flows():
    st = _stmt()
    by_memo = {t.memo_raw[:20]: t for t in st.transactions}
    assert by_memo["Renda Fixa - Aplicaç"].flow == "savings_out"
    assert by_memo["Salário/Remuneração "].flow == "income"
    assert by_memo["Cobrança Seguro Cart"].category == "taxas"


def test_merchant_never_becomes_person():
    st = _stmt()
    centro = next(t for t in st.transactions if "CULTURA" in t.memo_raw)
    assert centro.counterparty_kind == "merchant"
    assert centro.counterparty == "CENTRO DE CULTURA"


def test_person_is_pseudonymized_and_alias_applied():
    st = _stmt()
    pai = next(t for t in st.transactions if "Carlos Alberto" in t.memo_raw)
    assert pai.counterparty == "pai" and pai.flow == "transfer"
    outro = next(t for t in st.transactions if "Marina Duarte" in t.memo_raw)
    assert outro.counterparty.startswith("PF:")
    assert "Marina" not in outro.counterparty


def test_self_transfer_is_neutral():
    st = _stmt()
    eu = next(t for t in st.transactions if "Titular Da Conta" in t.memo_raw)
    assert eu.flow == "transfer" and eu.counterparty_kind == "self"


def test_score_bounds_and_lever():
    st = _stmt()
    base = baseline(st)
    sc = compute(base, invisible_spending(st), [], patrimonio_liquido=Decimal("15000"))
    assert 0 <= sc["score"] <= 100
    assert sc["proximo_ponto"]


def test_purchase_advice_blocks_reserve_breach():
    st = _stmt()
    # baseline explícito: a fixture tem um mês só, e o teste é sobre a regra
    # de reserva, não sobre a média.
    base = {
        "renda_media_mes": 6000.00,
        "despesa_media_mes": 3200.00,
        "sobra_media_mes": 2800.00,
        "taxa_poupanca_media": 0.4667,
        "volatilidade_despesa": 0.26,
        "meses_no_vermelho": 0,
    }
    caro = PurchaseIntent(item="notebook", preco=Decimal("12000"), urgencia="alta")
    res = eval_buy(caro, st, base, [], saldo_conta=Decimal("990"), patrimonio=Decimal("15201"))
    assert res["reserva"]["compra_fura_reserva"] is True
    assert res["veredito"] in ("nao_agora", "juntar_antes", "espere_30_dias")
    barato = PurchaseIntent(item="fone", preco=Decimal("50"))
    ok = eval_buy(barato, st, base, [], saldo_conta=Decimal("990"), patrimonio=Decimal("15201"))
    assert ok["score_prudencia"] >= res["score_prudencia"]


def test_recurrence_detection():
    st = _stmt()
    recs = recurrences(st, min_months=1)
    assert any(r.counterparty for r in recs)


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    raise SystemExit(1 if fails else 0)
