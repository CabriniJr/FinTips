#!/usr/bin/env python3
"""Interoperabilidade real com o SDK MCP Python. Apenas servidor local e fixture.

Não acessa contas ChatGPT/Claude nem publica o endpoint. Tokens sintéticos
vivem só na memória deste teste e nunca são impressos.
"""
import asyncio
import hashlib
import base64
import json
from pathlib import Path
import re
import secrets
import subprocess
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://mcp.example.invalid"
CALLBACK = "https://client.example.invalid/callback"
SERVER = """
import {createCompanion} from './integracoes/mcp/server.mjs';
const server = createCompanion({baseUrl:'https://mcp.example.invalid',redirects:['https://client.example.invalid/callback']});
server.listen(0,'127.0.0.1',()=>process.stdout.write(JSON.stringify({port:server.address().port})+'\\n'));
"""


async def main():
    process = subprocess.Popen(["node", "--input-type=module", "-e", SERVER], cwd=ROOT,
                               stdout=subprocess.PIPE, text=True)
    try:
        port = json.loads(process.stdout.readline())["port"]
        local = f"http://127.0.0.1:{port}"
        async with httpx.AsyncClient(base_url=local, follow_redirects=False) as http:
            client = (await http.post("/oauth/register", json={"redirect_uris": [CALLBACK]})).json()["client_id"]
            verifier = secrets.token_urlsafe(32)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            query = urlencode(dict(client_id=client, redirect_uri=CALLBACK, response_type="code", scope="context:read",
                                   state="sdk-fixture", resource=BASE + "/mcp", code_challenge=challenge, code_challenge_method="S256"))
            html = (await http.get("/oauth/authorize?" + query)).text
            code = re.search(r'class="code">([^<]+)', html)[1].replace("-", "")
            poll = re.search(r'data-poll="([^"]+)', html)[1]
            context = {"schema_version": 1, "leitura": {"estados": ["estimado"], "fontes": ["librera"]}}
            approved = await http.post("/api/link", headers={"origin": BASE}, json=dict(code=code, context=context, revocation="a" * 64))
            approved.raise_for_status()
            callback = (await http.post("/api/poll", json={"poll": poll})).json()["redirect"]
            params = parse_qs(urlparse(callback).query)
            assert params["iss"] == [BASE] and params["state"] == ["sdk-fixture"]
            result = await http.post("/oauth/token", data=dict(grant_type="authorization_code", client_id=client,
                                     code=params["code"][0], redirect_uri=CALLBACK, code_verifier=verifier, resource=BASE + "/mcp"))
            result.raise_for_status()
            token = result.json()["access_token"]
        async with httpx.AsyncClient(headers={"Authorization": "Bearer " + token}) as client:
            async with streamable_http_client(local + "/mcp", http_client=client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize()
                    assert initialized.serverInfo.name == "fintips-contexto"
                    tools = await session.list_tools()
                    assert [t.name for t in tools.tools] == ["ler_contexto_revisado"]
                    data = await session.call_tool("ler_contexto_revisado", {})
                    assert not data.isError and data.structuredContent["contexto"] == context
                    assert json.loads(data.content[0].text)["sincronizacao"] == "snapshot_revisado"
        print("ok: SDK MCP — initialize, tools/list e tools/call com OAuth PKCE e snapshot mínimo")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    asyncio.run(main())
