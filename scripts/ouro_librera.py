"""Cenários inventados de fonte automática; sem arquivos ou títulos pessoais."""
from copy import deepcopy
from datetime import datetime,timezone
from fintips.librera import merge_reading
from fintips.ai_context import project_bundle

NOW=1792152000000
EMPTY={'schema_version':1,'livros':[]}
RAW={'Livro Sintético.epub':{'p':.25,'t':1791986400000,'pt':'PAGE_CONTENT_CANARY','path':'PRIVATE_PATH_CANARY'}}

def gerar():
    first=merge_reading(EMPTY,RAW,'principal',NOW,'America/Sao_Paulo')['leitura']
    manual=deepcopy(first);manual['livros'][0]['observacoes'][0]['origem']='usuario';manual['livros'][0]['observacoes'][0]['progresso_bp']=3600
    cases=[
        ('primeira_importacao',EMPTY,RAW,'principal',NOW,[]),
        ('repeticao',first,RAW,'principal',NOW,[]),
        ('atualizacao_mesmo_dia',first,{'Livro Sintético.epub':{'p':.32,'t':1791986401000}},'principal',NOW,[]),
        ('arquivo_atrasado',first,{'Livro Sintético.epub':{'p':.15,'t':1791986399000}},'principal',NOW,[]),
        ('correcao_usuario_vence',manual,{'Livro Sintético.epub':{'p':.50,'t':1791986402000}},'principal',NOW,[]),
        ('novo_dia',first,{'Livro Sintético.epub':{'p':.40,'t':1792072800000}},'principal',NOW,[]),
        ('recuo_nao_e_conclusao',first,{'Livro Sintético.epub':{'p':.10,'t':1792072800000}},'principal',NOW,[]),
        ('outro_perfil',first,RAW,'trabalho',NOW,[]),
        ('futuro',EMPTY,{'Livro.epub':{'p':.8,'t':NOW+86400000}},'principal',NOW,[]),
        ('removido_nao_reaparece',EMPTY,RAW,'principal',NOW,[['principal','Livro Sintético.epub']]),
        ('extensao_apenas',EMPTY,{'.epub':{'p':.1,'t':NOW}},'principal',NOW,[]),
        ('formas_invalidas',EMPTY,{'path/livro':{'p':.2,'t':NOW},'float.epub':{'p':.4,'t':1.0},'bad':{'p':True,'t':NOW}},'principal',NOW,[]),
    ]
    output = {'casos':[dict(nome=n,entrada=dict(reading=r,raw=raw,profile=p,now_ms=ms,zone='America/Sao_Paulo',excluded=ex),resultado=merge_reading(r,raw,p,ms,'America/Sao_Paulo',ex)) for n,r,raw,p,ms,ex in cases]}
    for case in output['casos']:
        bundle=dict(schema_version=1,vida=dict(schema_version=1,tarefas=[],registros=[],planos=[],medidas=[]),leitura=case['resultado']['leitura'],caderno=dict(schema_version=1,assets=[],relacoes=[],aplicacoes=[]))
        case['bundle']=bundle
        case['contexto_ia']=project_bundle(bundle,['rotina','planos','leitura'],'2026-10-16')
    return output

