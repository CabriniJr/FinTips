#!/usr/bin/env python3
"""Registro Android → constante nativa, sem caminhos pessoais. Conferido no CI."""
import json
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
registry=json.loads((root/'fintips/rules/guardas-android.json').read_text())
if any(g['schema_version']!=1 for g in registry['guardas'].values()):
    raise SystemExit('Nova versão de guarda Android exige implementar/conferir migrador antes de gerar')
raw=json.dumps(registry,ensure_ascii=False,separators=(',',':'))
assert '$' not in raw and '\"\"\"' not in raw
text='// Gerado por scripts/gerar-guardas-android.py; não editar.\npackage com.fintips.app\n\ninternal const val GUARDAS_ANDROID = \"\"\"'+raw+'\"\"\"\n'
p=root/'kotlin/app/src/debug/kotlin/com/fintips/app/GuardasGeradas.kt'
if '--conferir' in sys.argv:
    if not p.exists() or p.read_text()!=text: raise SystemExit('Registro Android desatualizado')
else: p.write_text(text)
print('ok: guardas Android derivadas do registro único')
