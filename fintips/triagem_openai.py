"""OpenAI recebe exclusivamente a projeção fechada validada. Nunca o chat."""
import json
import urllib.request
from urllib.error import HTTPError, URLError
from .triagem_universal import contexto, validar_publico, schema_sugestao, validar_sugestao

INSTRUCOES = (
    'Organize a triagem FinTips usando apenas os contratos abstratos fornecidos. '
    'Escolha uma opcao existente. Priorize campos obrigatorios; quando completos, '
    'prefira revisao em lote para reduzir toil. Pode sugerir valor inteiro em '
    'sugerir_valor quando sustentado pelos numeros. Valores monetarios sao centavos; '
    'progresso_bp vai de 0 a 10000. Nunca trate ausencia como zero, deduza motivos, '
    'identifique pessoas ou invente ligacoes. Correlacoes sao sugestoes que exigem '
    'confirmacao local. Nao ha nomes, origem/destino reais ou texto da conversa.'
)


def pedido(publico):
    validar_publico(publico)
    return {'model':'gpt-4.1-mini','store':False,'max_output_tokens':256,
            'instructions':INSTRUCOES,'input':json.dumps(publico,ensure_ascii=False,separators=(',',':')),
            'text':{'format':{'type':'json_schema','name':'fintips_triagem_v1','strict':True,'schema':schema_sugestao(publico)}}}


def sugerir(bundle,rascunhos,key,confirmado_envio,hoje):
    if confirmado_envio is not True:raise ValueError('Autorize o envio do contexto abstrato')
    if not isinstance(key,str) or not key.startswith('sk-') or not 20<=len(key)<=512:raise ValueError('Configure a chave OpenAI neste dispositivo')
    public=contexto(bundle,rascunhos,hoje)['publico']
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(pedido(public)).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    class SemRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    try:
        with urllib.request.build_opener(SemRedirect()).open(req,timeout=40) as response:
            raw=response.read(65537)
        if len(raw)>65536:raise ValueError('Resposta OpenAI recusada')
        result=json.loads(raw)
        if result.get('status')!='completed':raise ValueError('A API não concluiu a sugestão')
        text=[c['text'] for o in result.get('output',[]) if o.get('type')=='message' for c in o.get('content',[]) if c.get('type')=='output_text']
        if len(text)!=1:raise ValueError('Resposta OpenAI recusada')
        return validar_sugestao(public,json.loads(text[0]))
    except HTTPError as e:
        raise ValueError('Chave OpenAI recusada' if e.code==401 else 'Limite ou indisponibilidade da API OpenAI') from None
    except (URLError,TimeoutError,json.JSONDecodeError,KeyError,TypeError):
        raise ValueError('A API OpenAI não respondeu com uma sugestão válida') from None
