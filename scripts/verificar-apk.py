"""Verify the offline APK and package only distributable files, never keys."""
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

root = Path(__file__).resolve().parents[1]
sdk = Path(os.environ.get("ANDROID_HOME") or os.environ["ANDROID_SDK_ROOT"])
tools = [Path(p).parent for p in glob.glob(str(sdk / "build-tools/*/apksigner"))]
tools.sort(key=lambda p: tuple(int(x) for x in re.findall(r"\d+", p.name)))
if not tools:
    raise SystemExit("Android build-tools/apksigner indisponíveis")
tools = tools[-1]
apk = root / "kotlin/app/build/outputs/apk/debug/app-debug.apk"
cert = subprocess.check_output([str(tools / "apksigner"), "verify", "--print-certs", str(apk)], text=True)
digest = re.search(r"Signer #1 certificate SHA-256 digest: ([0-9a-fA-F]{64})", cert).group(1).lower()
expected_cert = os.environ.get("FINTIPS_EXPECTED_CERT", "").lower()
if expected_cert and digest != expected_cert:
    raise SystemExit("Assinatura incompatível com o certificado esperado; publicação bloqueada")
badging = subprocess.check_output([str(tools / "aapt"), "dump", "badging", str(apk)], text=True)
package = re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", badging)
expected_package = os.environ.get("FINTIPS_EXPECTED_PACKAGE", "com.fintips.app.ui")
if package.group(1) != expected_package:
    raise SystemExit("Pacote inesperado")
if "android.permission.INTERNET" in badging or badging.count("launchable-activity:") != 1:
    raise SystemExit("Permissões/launcher não respeitam o contrato offline")
manifest = subprocess.check_output([str(tools / "aapt"), "dump", "xmltree", str(apk), "AndroidManifest.xml"], text=True)
if not re.search(r"android:allowBackup[^\n]*=\s*\(type 0x12\)0x0\s*$", manifest, re.M):
    raise SystemExit("Backup automático não está desabilitado")
with zipfile.ZipFile(apk) as archive:
    files = [p for p in (root / "fintips/web").rglob("*") if p.is_file()]
    expected_assets = {"assets/" + str(p.relative_to(root / "fintips/web")) for p in files}
    if {n for n in archive.namelist() if n.startswith("assets/") and not n.endswith("/")} != expected_assets:
        raise SystemExit("Conjunto de assets diverge do build web")
    for path in files:
        if archive.read("assets/" + str(path.relative_to(root / "fintips/web"))) != path.read_bytes():
            raise SystemExit("Asset embarcado diverge do build web")
if os.environ.get("FINTIPS_VERIFY_ONLY") == "true":
    print(f"APK offline e assinatura verificados: {package.group(1)}, {len(files)} assets")
    raise SystemExit(0)
output = root / "dist"
output.mkdir(exist_ok=True)
name = os.environ.get("FINTIPS_APK_NAME", "FinTips-Android-ci.apk")
if Path(name).name != name or not name.endswith(".apk"):
    raise SystemExit("Nome inválido para o APK")
destination = output / name
shutil.copyfile(apk, destination)
checksum = hashlib.sha256(destination.read_bytes()).hexdigest()
source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
info = {"commit": source, "variante": "debug", "application_id": package.group(1),
        "version_code": int(package.group(2)), "version_name": package.group(3),
        "apk_sha256": checksum, "certificado_sha256": digest,
        "ui": "WebView offline; alvo Compose compilado separadamente",
        "testado_em_aparelho": False, "assets_verificados": len(files)}
(output / "build-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
(output / "SHA256SUMS.txt").write_text(f"{checksum}  {name}\n")
print(f"APK verificado: {package.group(1)}, {len(files)} assets, assinatura válida")
