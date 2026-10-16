#!/usr/bin/env python3
"""Instrumentação real: somente o pacote CI, com notificações inicialmente negadas.

Revogar runtime permission pode matar o UID. Fazer isso antes do runner evita
simular a negativa ou matar o próprio processo de teste.
"""
from pathlib import Path
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "kotlin/app/build/outputs/apk"
PACKAGE = "com.fintips.app.ci"
meta = json.loads((APP / "debug/output-metadata.json").read_text())
if meta["applicationId"] != PACKAGE:
    raise SystemExit("O teste de permissão só pode operar sobre o APK CI isolado")
sdk = Path(os.environ.get("ANDROID_HOME") or os.environ["ANDROID_SDK_ROOT"])
adb = str(sdk / "platform-tools/adb")
for apk in (APP / "debug/app-debug.apk", APP / "androidTest/debug/app-debug-androidTest.apk"):
    subprocess.run([adb, "install", "-r", str(apk)], check=True)
subprocess.run([adb, "shell", "pm", "revoke", PACKAGE, "android.permission.POST_NOTIFICATIONS"], check=True)
report = ROOT / "kotlin/app/build/reports/androidTests/mcp/resultado.txt"
report.parent.mkdir(parents=True, exist_ok=True)
result = subprocess.run([adb, "shell", "am", "instrument", "-w", "-e", "class",
                         "com.fintips.app.McpAndroidTest,com.fintips.app.PonteAndroidTest,com.fintips.app.TriagemAndroidTest", PACKAGE + ".test/androidx.test.runner.AndroidJUnitRunner"],
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
report.write_text(result.stdout)
print(result.stdout)
# am instrument pode retornar zero mesmo com falha JUnit. Exigir os 7 casos.
if result.returncode or not re.search(r"^OK \(7 tests\)$", result.stdout, re.M):
    raise SystemExit("Instrumentação Android não confirmou os 7 testes")
