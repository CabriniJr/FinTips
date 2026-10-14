"""Ouro de leitura, gerado a partir da referência Python com dados sintéticos."""
from fintips.reading import librera_positions, pacing


def ouro_leitura() -> dict:
    def p(day, bp):
        return {"dia": f"2026-10-{day:02}", "progresso_bp": bp}
    cases = [
        ("vazio", [], None, None),
        ("uma_posicao", [p(14, 3000)], None, 3),
        ("ritmo_regular", [p(1, 1000), p(7, 2200), p(14, 3600)], None, 4),
        ("preliminar", [p(7, 3000), p(14, 3500)], None, 3),
        ("prazo_e_sessoes", [p(7, 3000), p(14, 3500)], "2026-11-14", 3),
        ("prazo_hoje", [p(14, 3500)], "2026-10-14", 1),
        ("prazo_vencido", [p(14, 3500)], "2026-10-13", 3),
        ("sem_avanco", [p(1, 3500), p(14, 3500)], None, 3),
        ("recuo", [p(1, 3000), p(7, 5000), p(14, 1000)], None, 3),
        ("recuo_e_retomada", [p(1, 5000), p(7, 1000), p(10, 2000), p(14, 3000)], None, 3),
        ("arquivo_antigo", [p(1, 1000), p(6, 2000)], None, 3),
        ("limite_sete_dias", [p(1, 1000), p(7, 2000)], None, 3),
        ("no_fim", [p(1, 10000)], None, 3),
        ("ordem_invertida", [p(14, 3600), p(1, 1000), p(7, 2200)], None, 4),
        ("divisao_nao_exata", [p(1, 1000), p(14, 2001)], None, 3),
        ("avanco_minimo", [p(1, 9998), p(14, 9999)], None, 1),
        ("observacao_fora_da_janela", [{"dia": "2026-09-01", "progresso_bp": 0}, p(14, 2500)], None, 7),
        ("sem_plano_semanal", [p(1, 1000), p(14, 2001)], "2026-11-14", None),
    ]
    output = []
    for name, points, target, days in cases:
        inputs = {"points": points, "today": "2026-10-14", "deadline": target, "reading_days": days}
        output.append({"nome": name, "entrada": inputs, "resultado": pacing(**inputs)})
    parser = [
        {"nome": "campos_minimos", "entrada": {"Livro A.epub": {"p": 0.375, "t": 1791986400000, "pt": "trecho não exportado", "path": "arquivo-local"}}},
        {"nome": "extremos_e_arredondamento", "entrada": {"zero.epub": {"p": 0, "t": 1}, "fim.pdf": {"p": 1, "t": 2}, "empate.epub": {"p": 0.00005, "t": 3}}},
        {"nome": "legado_e_sem_data", "entrada": {"legado.pdf": {"p": 38, "t": 1}, "sem_data.epub": {"p": 0.5, "t": 0}, "texto.epub": {"p": "0.5", "t": 1}}},
        {"nome": "fora_da_escala", "entrada": {"negativo.pdf": {"p": -1, "t": 1}, "booleano.pdf": {"p": True, "t": 1}, "pasta/livro.pdf": {"p": 0.5, "t": 1}}},
    ]
    for c in parser:
        c["resultado"] = librera_positions(c["entrada"])
    return {"gerado_por": "fintips.reading", "casos": output, "parser": parser}
