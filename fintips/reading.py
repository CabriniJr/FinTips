"""Posição de leitura e pacing. Cálculo puro; dados identificáveis ficam no client."""
from __future__ import annotations

from datetime import date
from math import floor, isfinite


def librera_positions(data: dict) -> dict:
    """Projeta app-Progress.json em chave local, p normalizado e timestamp.

    Não copia pt (texto da página), bookmarks, caminhos ou configurações.
    p é fração 0..1 no Librera; valores legados fora dessa escala são omitidos.
    """
    if not isinstance(data, dict):
        raise ValueError("formato de progresso não suportado")
    positions = []
    ignored = 0
    for key, record in data.items():
        if not isinstance(key, str) or not key.strip() or "/" in key or "\\" in key or not isinstance(record, dict):
            ignored += 1
            continue
        p, t = record.get("p"), record.get("t")
        if (type(p) not in (int, float) or not isfinite(p) or not 0 <= p <= 1
                or type(t) is not int or not 0 < t <= 8_640_000_000_000_000):
            ignored += 1
            continue
        positions.append({"chave": key, "progresso_bp": floor(p * 10000 + 0.5), "tempo_ms": t})
    return {"posicoes": positions, "ignorados": ignored}


def pacing(points: list[dict], *, today: str, deadline: str | None = None,
           reading_days: int | None = None) -> dict:
    """Uma posição final por dia. 10000 bp = 100%; projeção usa razão exata.

    Janela de 28 dias, com reinício ao recuar e bloqueio de previsão quando a
    última posição tem mais de sete dias. Dias entre observações entram no
    denominador, sem afirmar que foram dias sem leitura.
    """
    now = date.fromisoformat(today)
    target = date.fromisoformat(deadline) if deadline else None
    if reading_days is not None and (type(reading_days) is not int or not 1 <= reading_days <= 7):
        raise ValueError("dias de leitura devem estar entre 1 e 7")
    seen = set()
    normalized = []
    for point in points:
        day = date.fromisoformat(point["dia"])
        bp = point["progresso_bp"]
        if day > now or day in seen or type(bp) is not int or not 0 <= bp <= 10000:
            raise ValueError("observação de leitura inválida")
        seen.add(day)
        normalized.append((day, bp))
    normalized.sort()
    recent = [p for p in normalized if (now - p[0]).days <= 28]
    reset = 0
    for i in range(1, len(recent)):
        if recent[i][1] < recent[i - 1][1]:
            reset = i
    recent = recent[reset:]
    current = normalized[-1][1] if normalized else None
    last = normalized[-1][0] if normalized else None
    span = (recent[-1][0] - recent[0][0]).days if len(recent) >= 2 else 0
    gain = recent[-1][1] - recent[0][1] if len(recent) >= 2 else 0
    missing = 10000 - current if current is not None else None
    days_to_target = (target - now).days if target else None
    projected = None
    if current is None:
        status = "sem_dados"
    elif current == 10000:
        status, projected = "no_fim", 0
    elif last and (now - last).days > 7:
        status = "desatualizado"
    elif len(recent) < 2:
        status = "calibrando"
    elif gain == 0:
        status = "sem_avanco"
    else:
        status = "estimado"
        projected = (missing * span + gain - 1) // gain
    needed = None
    goal_session = None
    if missing is not None and days_to_target is not None and days_to_target >= 0:
        available = max(1, days_to_target)
        needed = (missing + available - 1) // available
        if reading_days is not None:
            sessions = max(1, (available * reading_days + 6) // 7)
            goal_session = (missing + sessions - 1) // sessions
    elif days_to_target is None and reading_days is not None and status == "estimado":
        divisor = span * reading_days
        goal_session = (gain * 7 + divisor - 1) // divisor
    return {
        "estado": status, "progresso_bp": current, "amostras": len(recent),
        "intervalo_dias": span, "avanco_bp": gain, "previsao_dias": projected,
        "prazo_dias": days_to_target, "necessario_bp_dia": needed,
        "meta_bp_sessao": goal_session, "historico_reiniciado": reset > 0,
        "preliminar": status == "estimado" and len(recent) < 3,
    }
