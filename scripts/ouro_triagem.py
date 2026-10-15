"""Fontes sintéticas para o contrato novo; nenhum texto do usuário."""
import copy
from fintips import triagem_universal as t

def fontes():
    drafts=[]
    for index,(name,c) in enumerate(t.TIPOS.items()):
        fields={}
        for k,s in c['campos'].items():
            if s['obrigatorio']:
                fields[k]={'texto':'LOCAL_ONLY_CANARY '+k,'opcao':s.get('opcoes',[''])[0], 'data':'2026-10-15','booleano':False,'inteiro':max(s.get('minimo',0),123)}[s['tipo']]
        if name in ['compromisso','patrimonio']:fields.update(origem_real='ORIGEM_ONLY_CANARY')
        if name=='compromisso':fields['destino_real']='DESTINO_ONLY_CANARY'
        if name=='livro':fields.update(progresso_bp=2500,dias_semana=3)
        if name=='objetivo':fields.update(atual=25,meta=100,unidade='UNIDADE_ONLY_CANARY')
        drafts.append({'id':f'asset-local-{index}','tipo':name,'campos':fields,'porque':'Evidência sintética confirmada localmente.','acao':'criar'})
    return drafts

def gerar():
    empty=t.vazio();ds=fontes();p=t.preparar(empty,ds,[],'lote-1')
    out=t.aplicar(empty,p,True,'2026-10-15',1792065600000)
    bundle=out['bundle']
    draft=copy.deepcopy(ds[0]);draft['id']='novo-plano';draft['campos']['titulo']=ds[0]['campos']['titulo']
    draft['campos'].pop('atributo')
    update=copy.deepcopy(ds[2]);update['acao']='atualizar';update['campos']['progresso_bp']=3000
    cases=[]
    def add(name,op,input):cases.append({'nome':name,'operacao':op,'entrada':input,'resultado':t.executar(op,input)})
    add('lote de todos os tipos sem escrita','triagem.preparar',{'bundle':empty,'rascunhos':ds,'relacoes':[],'id':'lote-1'})
    add('lote de todos os tipos aplicado atomicamente','triagem.aplicar',{'bundle':empty,'proposta':p,'confirmado':True,'hoje':'2026-10-15','tempo_ms':1792065600000})
    add('retry é idempotente','triagem.aplicar',{'bundle':bundle,'proposta':p,'confirmado':True,'hoje':'2026-10-16','tempo_ms':1792152000000})
    add('rótulos, cálculos e relações sem texto privado','triagem.contexto',{'bundle':bundle,'rascunhos':[draft],'hoje':'2026-10-15'})
    p2=t.preparar(bundle,[update],[],'lote-2')
    add('atualizar progresso preserva o histórico','triagem.aplicar',{'bundle':bundle,'proposta':p2,'confirmado':True,'hoje':'2026-10-16','tempo_ms':1792152000000})
    linked=copy.deepcopy(ds[0]);linked['id']='plano-novo';linked['campos']['titulo']='NOVO_ONLY_CANARY'
    rel={'de':{'tipo':'plano','id':'plano-novo'},'para':{'tipo':'livro','id':ds[2]['id']},'tipo':'apoia','porque':'Vínculo escolhido pela pessoa.'}
    p3=t.preparar(bundle,[linked],[rel],'lote-3')
    out3=t.aplicar(bundle,p3,True,'2026-10-16',1792152000000)
    add('vínculo explícito entre tipos diferentes','triagem.aplicar',{'bundle':bundle,'proposta':p3,'confirmado':True,'hoje':'2026-10-16','tempo_ms':1792152000000})
    future=t.aplicar(empty,t.preparar(empty,[ds[2]],[],'future'),True,'2026-10-16',1792152000000)['bundle']
    add('posição futura fica fora do contexto e do pacing','triagem.contexto',{'bundle':future,'rascunhos':[draft],'hoje':'2026-10-15'})
    window=copy.deepcopy(bundle)
    window['caderno']['aplicacoes']=[{'id':f'antigo-{i}','hash':'0'*64} for i in range(256)]
    pw=t.preparar(window,[update],[],'janela-recibos')
    add('janela de recibos não impede novas atualizações','triagem.aplicar',{'bundle':window,'proposta':pw,'confirmado':True,'hoje':'2026-10-16','tempo_ms':1792152000000})
    blanks=copy.deepcopy(ds[2]);blanks['id']='nullable-book';blanks['campos'].update(prazo='',dias_semana=None,progresso_bp=None)
    pb=t.preparar(empty,[blanks],[],'nullable')
    add('opcionais nulos não inventam observação','triagem.aplicar',{'bundle':empty,'proposta':pb,'confirmado':True,'hoje':'2026-10-15','tempo_ms':1792065600000})
    generic=copy.deepcopy(next(d for d in ds if d['tipo']=='compromisso'));generic['acao']='atualizar';generic['campos']={'titulo':'ALTERADO_ONLY_CANARY','valor_centavos':321}
    pg=t.preparar(bundle,[generic],[],'generic-patch')
    add('atualização parcial preserva origem e destino privados','triagem.aplicar',{'bundle':bundle,'proposta':pg,'confirmado':True,'hoje':'2026-10-15','tempo_ms':1792065600000})
    bad=copy.deepcopy(p);bad['operacoes'][0]['campos']['titulo']='Outro conteúdo'
    invalid=[{'nome':'não confirmado','operacao':'triagem.aplicar','entrada':{'bundle':empty,'proposta':p,'confirmado':False,'hoje':'2026-10-15','tempo_ms':1792065600000}},
       {'nome':'ID reaproveitado com conteúdo diferente','operacao':'triagem.aplicar','entrada':{'bundle':bundle,'proposta':bad,'confirmado':True,'hoje':'2026-10-15','tempo_ms':1792065600000}}]
    changed=copy.deepcopy(bundle);changed['vida']['planos'][0]['titulo']='MODIFICADO_ONLY_CANARY'
    invalid.append({'nome':'proposta obsoleta','operacao':'triagem.aplicar','entrada':{'bundle':changed,'proposta':p2,'confirmado':True,'hoje':'2026-10-16','tempo_ms':1792152000000}})
    for kind,field,value in [('plano','campo_desconhecido','PII_ONLY_CANARY'),('tarefa','repetir','true'),('compromisso','valor_centavos',1.5),('livro','progresso_bp',10001),('plano','prazo','2026-02-30')]:
        d=copy.deepcopy(next(d for d in ds if d['tipo']==kind));d['campos'][field]=value
        invalid.append({'nome':f'campo inválido {kind}/{field}','operacao':'triagem.preparar','entrada':{'bundle':empty,'rascunhos':[d],'relacoes':[],'id':'invalido'}})
    for c in invalid:
        try:t.executar(c['operacao'],c['entrada'])
        except Exception:pass
        else:raise AssertionError(c['nome'])
    return {'gerado_por':'fintips.triagem_universal (fontes sintéticas)','casos':cases,'recusados':invalid}
