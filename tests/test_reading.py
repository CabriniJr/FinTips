from datetime import date

import pytest

from fintips.reading import librera_positions, pacing


def point(day, bp):
    return {"dia": day, "progresso_bp": bp}


def test_progress_file_is_a_minimal_projection_without_page_content():
    result = librera_positions({"Livro de exemplo.epub": {"p": .375, "t": 1791986400000,
        "pt": "conteúdo privado", "path": "caminho privado", "x": 12}})
    assert result == {"posicoes": [{"chave": "Livro de exemplo.epub", "progresso_bp": 3750, "tempo_ms": 1791986400000}], "ignorados": 0}


@pytest.mark.parametrize("entry", [{"p": True, "t": 1}, {"p": "0.5", "t": 1},
    {"p": -1, "t": 1}, {"p": 50, "t": 1}, {"p": float("nan"), "t": 1},
    {"p": .5, "t": 0}, {"p": .5, "t": True}])
def test_unknown_or_legacy_position_does_not_become_zero(entry):
    assert librera_positions({"livro.epub": entry}) == {"posicoes": [], "ignorados": 1}


def test_calendar_pacing_counts_elapsed_days_and_does_not_round_before_forecasting():
    r = pacing([point("2026-10-01", 1000), point("2026-10-14", 2001)], today="2026-10-14", reading_days=3)
    assert r["previsao_dias"] == 104
    assert r["meta_bp_sessao"] == 180
    assert r["preliminar"]


def test_a_single_position_never_invents_a_reading_rate():
    assert pacing([point("2026-10-14", 3000)], today="2026-10-14")["previsao_dias"] is None


def test_going_back_resets_the_pacing_baseline_instead_of_counting_rereading_as_progress():
    r = pacing([point("2026-10-01", 5000), point("2026-10-07", 1000), point("2026-10-14", 3000)], today="2026-10-14")
    assert r["historico_reiniciado"]
    assert r["avanco_bp"] == 2000
    assert r["intervalo_dias"] == 7


def test_stale_position_keeps_progress_but_suppresses_forecast():
    r = pacing([point("2026-10-01", 1000), point("2026-10-06", 3000)], today="2026-10-14")
    assert r["estado"] == "desatualizado"
    assert r["progresso_bp"] == 3000
    assert r["previsao_dias"] is None


def test_deadline_today_and_expired_deadline_do_not_divide_by_zero():
    points = [point("2026-10-14", 3500)]
    assert pacing(points, today="2026-10-14", deadline="2026-10-14", reading_days=1)["meta_bp_sessao"] == 6500
    assert pacing(points, today="2026-10-14", deadline="2026-10-13", reading_days=1)["meta_bp_sessao"] is None


@pytest.mark.parametrize("points", [[point("2026-10-15", 1000)], [point("2026-10-14", 1000)] * 2,
    [point("2026-10-14", True)], [point("2026-10-14", 10001)]])
def test_invalid_observations_are_rejected(points):
    with pytest.raises(ValueError):
        pacing(points, today="2026-10-14")
