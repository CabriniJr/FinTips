"""Testes das entidades e da projeção (núcleo v0.2, mantido na v0.3)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fintips import discovery, projection  # noqa: E402
from fintips.categorize import Categorizer  # noqa: E402
from fintips.entities import build_counterparties, canonical_name, slug  # noqa: E402
from fintips.parsers.ofx import parse_ofx  # noqa: E402

FIXTURE = Path(__file__).parent / "fixture.ofx"


def _stmt():
    st = parse_ofx(FIXTURE)
    Categorizer(my_names=["Titular Da Conta Exemplo"]).apply_all(st.transactions)
    return st


def test_canonical_name_agrupa_variacoes():
    assert canonical_name("Gelato Roma-LJ0046") == canonical_name("Gelato Roma-LJ0084")
    assert canonical_name("EMV CMT*144318981") == "EMV CMT"
    assert canonical_name("TOP SP TARFA*121206903") == "TOP SP TARFA"
    assert canonical_name("PF:ab12cd") == "PF:ab12cd"     # pseudônimo passa intacto
    assert slug("Gelato Roma") == "gelato-roma"


def test_counterparties_tem_cadencia_e_fluxos():
    st = _stmt()
    cps = build_counterparties(st.transactions, total_months=1)
    assert cps, "deveria gerar contrapartes"
    salario = next(c for c in cps if "salary" in c.channels)
    assert "income" in salario.flows
    assert all(c.id and c.display for c in cps)


def test_confirmacao_muda_categoria():
    tmp = Path("/tmp/fintips-test")
    tmp.mkdir(parents=True, exist_ok=True)
    arq = tmp / "contrapartes.yaml"
    if arq.exists():
        arq.unlink()
    st = _stmt()
    cps = build_counterparties(st.transactions, total_months=1)
    alvo = next(c for c in cps if c.kind == "merchant")
    discovery.confirm(arq, alvo.id, category="lazer", fixed=True)

    cps2 = build_counterparties(st.transactions, total_months=1)
    discovery.apply_confirmations(cps2, discovery.load_confirmations(arq))
    conf = next(c for c in cps2 if c.id == alvo.id)
    assert conf.category == "lazer" and conf.source == "confirmado" and conf.fixed


def test_deteccao_de_custo_fixo_produz_candidatos():
    """A detecção continua existindo — mas como hipótese, não como verdade."""
    st = _stmt()
    cps = build_counterparties(st.transactions, total_months=1)
    meses = sorted({t.month for t in st.transactions})
    candidatos = discovery.detect_fixed_costs(st, cps, months=meses)
    assert isinstance(candidatos, list)
    for c in candidatos:
        assert c.kind in ("contratual", "rotina", "declarado")
        assert c.confidence <= 1.0


def test_projecao_conclui_plano_e_reserva():
    out = projection.project(
        baseline={"renda_media_mes": 6000, "despesa_media_mes": 3000, "reserva_alvo_meses": 6},
        fixed_monthly=1000,
        saldo_conta=1000,
        patrimonio=16000,
        planos=[{
            "id": "p1", "nome": "Trekking", "falta": 6000,
            "prioridade": "alta", "aporte_planejado_mes": 1000, "status": "apertado",
        }],
        meses=12,
    )
    assert len(out["linhas"]) == 12
    assert out["planos"][0]["conclui_em"], "plano com aporte suficiente tem que fechar"
    assert out["premissas"]["sobra_mensal"] == 3000.0
    conservador = projection.project(
        baseline={"renda_media_mes": 6000, "despesa_media_mes": 3000},
        fixed_monthly=1000, saldo_conta=1000, patrimonio=16000, planos=[],
        meses=6, cenario="conservador",
    )
    assert conservador["premissas"]["sobra_mensal"] < out["premissas"]["sobra_mensal"]


def test_invisivel_respeita_decisao():
    from fintips.analysis import invisible_spending

    st = _stmt()
    cheio = invisible_spending(st)
    filtrado = invisible_spending(st, ignorar_categorias={"transporte"})
    assert filtrado["micro_gastos"]["total"] <= cheio["micro_gastos"]["total"]
    assert "transporte" in filtrado["excluido_por_declaracao"]


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
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"ERRO {name}: {type(e).__name__}: {e}")
    raise SystemExit(1 if fails else 0)
