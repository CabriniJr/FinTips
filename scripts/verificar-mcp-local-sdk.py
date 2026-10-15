#!/usr/bin/env python3
"""SDK MCP real contra o mesmo servidor Kotlin usado no APK. Só fixture local."""
import asyncio
import json
import os
from pathlib import Path
import subprocess

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]


async def main():
    cp = ROOT / "kotlin/conector/build/test-classpath.txt"
    if not cp.is_file():
        raise SystemExit("Execute kotlin/gradlew -p kotlin :conector:classpathDeTeste primeiro")
    java = str(Path(os.environ["JAVA_HOME"]) / "bin/java") if os.environ.get("JAVA_HOME") else "java"
    process = subprocess.Popen([java, "-cp", cp.read_text(), "com.fintips.mcp.FixtureServerKt"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        context = {"schema_version": 1, "leitura": {"estados": ["estimado"], "fontes": ["usuario"]}}
        process.stdin.write(json.dumps(context) + "\n"); process.stdin.flush()
        config = json.loads(process.stdout.readline())  # Token só no pipe; nunca impresso.
        async with httpx.AsyncClient(headers={"Authorization": "Bearer " + config["token"]}) as http:
            async with streamable_http_client(config["endpoint"], http_client=http) as (read, write, _):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize()
                    assert initialized.serverInfo.name == "fintips-local"
                    tools = await session.list_tools()
                    assert [t.name for t in tools.tools] == ["ler_contexto_revisado"]
                    result = await session.call_tool("ler_contexto_revisado", {})
                    assert not result.isError
                    assert result.structuredContent["contexto"] == context
                    assert result.structuredContent["sincronizacao"] == "local_no_celular"
        async with httpx.AsyncClient() as http:
            denied = await http.post(config["endpoint"], json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            assert denied.status_code == 401
        print("ok: SDK MCP real → servidor Kotlin loopback; initialize/list/call e bearer obrigatório")
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()


if __name__ == "__main__":
    asyncio.run(main())
