"""Importação automática de leitura: referência portável, sem rede ou caminhos."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo
from .reading import librera_positions


def merge_reading(reading, raw, profile, now_ms, zone, excluded=()):
    if not isinstance(profile, str) or not profile.strip() or len(profile) > 100:
        raise ValueError("perfil inválido")
    profile = profile.strip()
    tz = ZoneInfo(zone)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    today = (epoch + timedelta(milliseconds=now_ms)).astimezone(tz).date().isoformat()
    parsed = librera_positions(raw)
    result = deepcopy(reading)
    added = updated = ignored = 0
    ignored += parsed['ignorados']
    for p in parsed['posicoes']:
        if p['tempo_ms'] > now_ms or [profile, p['chave']] in excluded:
            ignored += 1
            continue
        day = (epoch + timedelta(milliseconds=p['tempo_ms'])).astimezone(tz).date().isoformat()
        if day > today:
            ignored += 1
            continue
        book = next((b for b in result['livros'] if b['fonte'] == 'librera' and b['chave'] == p['chave'] and b['perfil'] == profile), None)
        if book is None:
            import re
            id = 'lib_' + sha256((str(len(profile.encode())) + ':' + profile + p['chave']).encode()).hexdigest()
            if any(b['id'] == id for b in result['livros']):
                raise ValueError('conflito de identidade')
            title = re.sub(r'\.[a-z0-9]+$', '', p['chave'], flags=re.I).strip() or p['chave']
            book = dict(id=id, titulo=title, fonte='librera', chave=p['chave'], perfil=profile, prazo='', dias_semana=None, observacoes=[])
            result['livros'].append(book)
            added += 1
        old = next((o for o in book['observacoes'] if o['dia'] == day), None)
        if old and (old['origem'] == 'usuario' or old['tempo_ms'] >= p['tempo_ms']):
            continue
        book['observacoes'] = sorted([o for o in book['observacoes'] if o['dia'] != day] + [dict(dia=day, progresso_bp=p['progresso_bp'], tempo_ms=p['tempo_ms'], origem='librera')], key=lambda o:o['dia'])
        updated += 1
    return dict(leitura=result, adicionados=added, atualizados=updated, ignorados=ignored)
