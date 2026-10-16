#!/usr/bin/env python3
"""OAuth + SDK MCP real → relay HTTPS/WSS → cliente Kotlin → MCP Kotlin local.

Só fontes sintéticas e uma CA efêmera. Nenhum token aparece na saída.
"""
import asyncio
import hashlib
import base64
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import tempfile
from urllib.parse import urlencode, urlparse, parse_qs
import re
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = {"schema_version": 1, "leitura": {"estados": ["estimado"], "fontes": ["usuario"]}}

async def main():
    cp = ROOT / 'kotlin/conector/build/test-classpath.txt'
    if not cp.exists():
        raise SystemExit('Execute :conector:classpathDeTeste primeiro')
    with tempfile.TemporaryDirectory(prefix='fintips-ponte-') as tmp:
        cert, key = Path(tmp)/'certificate.pem', Path(tmp)/'key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost',
                        '-addext','subjectAltName=DNS:localhost,IP:127.0.0.1','-keyout',str(key),'-out',str(cert)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        relay = await asyncio.create_subprocess_exec('node',str(ROOT/'integracoes/ponte/fixture.mjs'),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE)
        phone = None
        try:
            relay.stdin.write((json.dumps({'key':str(key),'cert':str(cert)})+'\n').encode());await relay.stdin.drain()
            config=json.loads(await relay.stdout.readline())
            java=str(Path(os.environ['JAVA_HOME'])/'bin/java') if os.environ.get('JAVA_HOME') else 'java'
            phone=await asyncio.create_subprocess_exec(java,'-cp',cp.read_text(),'com.fintips.mcp.FixturePonteKt',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE)
            phone.stdin.write((json.dumps({'origin':config['origin'],'invite':config['invite'],'certificate':str(cert),'context':CONTEXT})+'\n').encode());await phone.stdin.drain()
            assert json.loads(await phone.stdout.readline()) == {'ready':True}
            async def command(data):
                phone.stdin.write((json.dumps(data)+'\n').encode());await phone.stdin.drain();return json.loads(await phone.stdout.readline())
            ssl_context=ssl.create_default_context(cafile=str(cert))
            async with httpx.AsyncClient(verify=ssl_context) as http:
                async def post(path,data):return await http.post(config['origin']+path,json=data)
                async def authorize(provider,callback):
                    client=(await post('/oauth/register',{'redirect_uris':[callback],'token_endpoint_auth_method':'none'})).json()['client_id']
                    verifier=secrets.token_urlsafe(32);challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
                    q=urlencode({'client_id':client,'redirect_uri':callback,'response_type':'code','scope':'context:read','resource':config['origin']+'/mcp','state':secrets.token_hex(16),'code_challenge':challenge,'code_challenge_method':'S256'})
                    page=(await http.get(config['origin']+'/oauth/authorize?'+q)).text
                    code=re.search(r'class="code">([A-Z2-7-]+)<',page)[1].replace('-','');poll=re.search(r'data-poll="([^"]+)"',page)[1]
                    result=await command({'op':'approve','code':code,'scopes':['leitura'],'provider':provider});assert not result.get('fixture_error')
                    redirect=(await post('/api/poll',{'poll':poll})).json()['redirect'];params=parse_qs(urlparse(redirect).query)
                    token=(await post('/oauth/token',{'grant_type':'authorization_code','client_id':client,'code':params['code'][0],'redirect_uri':callback,'resource':config['origin']+'/mcp','code_verifier':verifier})).json()
                    assert token.get('access_token');return token['access_token']
                credentials=[]
                for provider,callback in [('chatgpt','https://chatgpt.com/connector_platform_oauth_redirect'),('claude','https://claude.ai/api/mcp/auth_callback')]:
                    token=await authorize(provider,callback);credentials.append(token)
                    async with httpx.AsyncClient(verify=ssl_context,headers={'Authorization':'Bearer '+token}) as client:
                        async with streamable_http_client(config['origin']+'/mcp',http_client=client) as (read,write,_):
                            async with ClientSession(read,write) as session:
                                initialized=await session.initialize();assert initialized.serverInfo.name=='fintips-ponte-celular'
                                tools=await session.list_tools();assert [t.name for t in tools.tools]==['ler_contexto_revisado']
                                for state in ['estimado','sem_avanco']:
                                    context={'schema_version':1,'leitura':{'estados':[state],'fontes':['usuario']}}
                                    assert not (await command({'op':'update','context':context})).get('fixture_error')
                                    r=await session.call_tool('ler_contexto_revisado',{})
                                    assert not r.isError and r.structuredContent['contexto']==context
                                    assert r.structuredContent['sincronizacao']=='consulta_ao_celular'
                await command({'op':'pause'})
                async with httpx.AsyncClient(verify=ssl_context,headers={'Authorization':'Bearer '+credentials[0]}) as client:
                    async with streamable_http_client(config['origin']+'/mcp',http_client=client) as (read,write,_):
                        async with ClientSession(read,write) as session:
                            await session.initialize();r=await session.call_tool('ler_contexto_revisado',{})
                            assert r.isError and r.structuredContent is None
                await command({'op':'disconnect'})
            print('ok: Dois clientes OAuth PKCE + SDK MCP real → HTTPS/WSS relay → cliente Kotlin → socket MCP Kotlin; atualização e pausa sem snapshot')
        finally:
            for p in (phone,relay):
                if p is None:continue
                p.stdin.close()
                try:await asyncio.wait_for(p.wait(),8)
                except asyncio.TimeoutError:p.kill();await p.wait()

asyncio.run(main())
