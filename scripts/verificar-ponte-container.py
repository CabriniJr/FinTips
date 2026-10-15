#!/usr/bin/env python3
"""Smoke do artefato de implantação; convite efêmero nunca vai à saída."""
import json
import os
import secrets
import subprocess
import time
import urllib.request

env = os.environ.copy()
env.update(PHONE_JOIN_SECRET=secrets.token_hex(32), PUBLIC_URL="https://relay.example",
           OAUTH_CALLBACKS=json.dumps([{"uri": "https://claude.ai/api/mcp/auth_callback", "provider": "claude"}]))
container = subprocess.check_output([
    "docker", "run", "-d", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
    "-e", "PHONE_JOIN_SECRET", "-e", "PUBLIC_URL", "-e", "OAUTH_CALLBACKS",
    "-p", "127.0.0.1::8787", "fintips-ponte:qa"], env=env, text=True).strip()
try:
    ports = json.loads(subprocess.check_output(["docker", "inspect", "--format", "{{json .NetworkSettings.Ports}}", container], text=True))
    origin = "http://127.0.0.1:" + ports["8787/tcp"][0]["HostPort"]
    for _ in range(50):
        try:
            with urllib.request.urlopen(origin + "/health", timeout=1) as response:
                assert json.load(response) == {"ok": True, "mode": "phone_relay"}
            break
        except OSError:
            time.sleep(.1)
    else:
        raise SystemExit("Container não iniciou o relay")
    with urllib.request.urlopen(origin + "/.well-known/oauth-authorization-server", timeout=2) as response:
        assert json.load(response)["issuer"] == "https://relay.example"
    assert subprocess.check_output(["docker", "exec", container, "id", "-u"], text=True).strip() == "1000"
    subprocess.run(["docker", "exec", container, "node", "--input-type=module", "-e",
                    "import fs from 'node:fs'; if(fs.existsSync('/app/data') || fs.existsSync('/app/integracoes/ponte/fixture.mjs')) process.exit(1)"], check=True)
    print("ok: container não-root/read-only, health e OAuth; sem dados ou fixtures na imagem")
finally:
    subprocess.run(["docker", "rm", "-f", container], check=True, stdout=subprocess.DEVNULL)
