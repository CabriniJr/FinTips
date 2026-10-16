"""Verify the APK with its local MCP service; package files, never keys."""
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
preferred = sdk / "build-tools/34.0.0"
tools = preferred if (preferred / "apksigner").is_file() else tools[-1]
apk = root / "kotlin/app/build/outputs/apk/debug/app-debug.apk"
cert = subprocess.check_output([str(tools / "apksigner"), "verify", "--print-certs", str(apk)], text=True)
digests = {value.lower() for value in re.findall(
    r"certificate SHA-256 digest:\s*([0-9a-f]{64})", cert, re.I)}
if len(digests) != 1:
    raise SystemExit(f"Não foi possível identificar um certificado único no apksigner {tools.name}")
digest = digests.pop()
expected_cert = os.environ.get("FINTIPS_EXPECTED_CERT", "").lower()
if expected_cert and digest != expected_cert:
    raise SystemExit("Assinatura incompatível com o certificado esperado; publicação bloqueada")
badging = subprocess.check_output([str(tools / "aapt"), "dump", "badging", str(apk)], text=True)
package = re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", badging)
expected_package = os.environ.get("FINTIPS_EXPECTED_PACKAGE", "com.fintips.app.ui")
if package.group(1) != expected_package:
    raise SystemExit("Pacote inesperado")
permissoes = set(re.findall(r"uses-permission[^:\n]*:\s*name='([^']+)'", badging))
esperadas = {"android.permission.INTERNET", "android.permission.FOREGROUND_SERVICE",
             "android.permission.FOREGROUND_SERVICE_SPECIAL_USE", "android.permission.POST_NOTIFICATIONS",
             "android.permission.RECEIVE_BOOT_COMPLETED"}
internas = {f"{expected_package}.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION"}
if not esperadas <= permissoes or permissoes - esperadas - internas or badging.count("launchable-activity:") != 1:
    raise SystemExit("Permissões/launcher não respeitam o contrato do servidor local")
label = "FinTips CI" if expected_package == "com.fintips.app.ci" else "FinTips UI"
if f"application-label:'{label}'" not in badging or f"label='{label}'" not in badging:
    raise SystemExit("Nome do app/launcher não identifica a variante esperada")
manifest = subprocess.check_output([str(tools / "aapt"), "dump", "xmltree", str(apk), "AndroidManifest.xml"], text=True)
if not re.search(r"android:allowBackup[^\n]*=\s*\(type 0x12\)0x0\s*$", manifest, re.M):
    raise SystemExit("Backup automático não está desabilitado")
services = [m.group(0) for m in re.finditer(r"(?ms)^(\s*)E: service\b.*?(?=^\1E:|\Z)", manifest)]
service = next((s for s in services if "com.fintips.app.McpLocalService" in s), None)
if not service or "com.fintips.app.McpLocalService" not in service or not re.search(
        r"android:exported[^\n]*=\s*\(type 0x12\)0x0\s*$", service, re.M):
    raise SystemExit("Serviço MCP ausente ou exportado")
if "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE" not in service:
    raise SystemExit("Finalidade do foreground service não declarada")
job = next((s for s in services if "com.fintips.app.LibreraJobService" in s), None)
if not job or 'android.permission.BIND_JOB_SERVICE' not in job or not re.search(r'android:exported[^\n]*=\s*\(type 0x12\)0xffffffff\s*$', job, re.M):
    raise SystemExit("Job Librera não está protegido pela permissão do sistema")
with zipfile.ZipFile(apk) as archive:
    files = [p for p in (root / "fintips/web").rglob("*") if p.is_file()]
    expected_assets = {"assets/" + str(p.relative_to(root / "fintips/web")) for p in files}
    if {n for n in archive.namelist() if n.startswith("assets/") and not n.endswith("/")} != expected_assets:
        raise SystemExit("Conjunto de assets diverge do build web")
    for path in files:
        if archive.read("assets/" + str(path.relative_to(root / "fintips/web"))) != path.read_bytes():
            raise SystemExit("Asset embarcado diverge do build web")
if os.environ.get("FINTIPS_VERIFY_ONLY") == "true":
    print(f"APK local/serviço e assinatura verificados: {package.group(1)}, {len(files)} assets")
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
        "ui": "WebView com assets locais; MCP loopback e ponte HTTPS/WSS opcional",
        "testado_em_aparelho": False, "assets_verificados": len(files)}
(output / "build-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
(output / "SHA256SUMS.txt").write_text(f"{checksum}  {name}\n")
print(f"APK verificado: {package.group(1)}, {len(files)} assets, assinatura válida")
