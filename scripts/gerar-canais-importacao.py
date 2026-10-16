#!/usr/bin/env python3
"""Canais canônicos do Python → Kotlin; o portão acusa regras desatualizadas."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fintips.import_flows import channel_rules, rules_revision
raw = json.dumps(channel_rules(), ensure_ascii=False, separators=(",", ":"))
assert '$' not in raw and '\"\"\"' not in raw
text = '// Gerado por scripts/gerar-canais-importacao.py; não editar.\npackage com.fintips.motor.importacao\n\ninternal const val CANAIS_IMPORTACAO = \"\"\"' + raw + '\"\"\"\ninternal const val REVISAO_CANAIS = \"' + rules_revision() + '\"\n'
path = ROOT / 'kotlin/motor/src/commonMain/kotlin/com/fintips/motor/importacao/CanaisGerados.kt'
if '--conferir' in sys.argv:
    if not path.exists() or path.read_text() != text: raise SystemExit('Canais de importação Kotlin desatualizados')
else: path.write_text(text)
print('ok: canais Kotlin derivados do registro Python')
