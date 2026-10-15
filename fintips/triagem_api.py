"""API de contratos locais, sem novo endpoint público de escrita no MCP."""
import json
import os
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request
from . import triagem_universal as t
from . import triagem_openai

router=APIRouter(prefix='/api/triagem',tags=['Triagem universal'])


def fronteira(request):
    if request.client is None or request.client.host not in ["127.0.0.1", "::1", "::ffff:127.0.0.1"]:
        raise HTTPException(403,"A triagem exige o próprio dispositivo")
    if request.url.hostname not in ['127.0.0.1','localhost','::1']:
        raise HTTPException(403,'A triagem exige a API no próprio dispositivo')
    origin=request.headers.get('origin')
    if origin:
        u=urlsplit(origin)
        if u.scheme!='http' or u.hostname not in ['127.0.0.1','localhost','::1'] or u.port not in [5173,request.url.port or 80]:
            raise HTTPException(403,'Origem recusada')
    if request.headers.get('sec-fetch-site')=='cross-site':raise HTTPException(403,'Origem recusada')


@router.get('/catalogo')
def catalogo(request:Request):
    fronteira(request);return t.CATALOGO


@router.post('/{operacao}')
async def executar(operacao:str,request:Request):
    fronteira(request)
    if operacao not in ['contexto','preparar','aplicar','validar','sugerir']:raise HTTPException(404,'Operação indisponível')
    if request.headers.get('content-type','').split(';')[0]!='application/json':raise HTTPException(415,'Use JSON')
    raw=bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw)>1536*1024:raise HTTPException(413,'Contrato excede o limite local')
    try:
        body=json.loads(raw)
        if operacao=='sugerir':
            t.exigir(t.exato(body,['bundle','rascunhos','confirmado_envio','hoje']))
            # A chave só é lida pelo processo local. Não é aceita no corpo HTTP.
            import asyncio
            return await asyncio.to_thread(triagem_openai.sugerir,body['bundle'],body['rascunhos'],os.environ.get('FINTIPS_OPENAI_API_KEY',''),body['confirmado_envio'],body['hoje'])
        return t.executar('triagem.'+operacao,body)
    except Exception:
        raise HTTPException(400,'Contrato ou sugestão recusados; nenhum registro foi persistido') from None
