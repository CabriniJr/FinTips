"""Contrato local de triagem: proposta → revisão → aplicação atômica.

Texto/IDs reais nunca fazem parte de ``publico``. O mesmo contrato puro roda
no Android e na API local; persistir o resultado é responsabilidade do cliente.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
from datetime import date
from pathlib import Path

CATALOGO = json.loads((Path(__file__).parent/'rules/triagem-catalogo.json').read_text())
TIPOS = CATALOGO['tipos']
AREAS = ['FOR', 'AGI', 'VIT', 'INT', 'FOC', 'OURO']


def exigir(ok):
    if not ok:
        raise ValueError('Contrato de triagem inválido; nada foi alterado')


def inteiro(v, a=0, b=9_000_000_000_000):
    return type(v) is int and a <= v <= b


def texto(v, limite=4000):
    return isinstance(v, str) and 0 < len(v.strip()) <= limite


def dia(v):
    try:
        return isinstance(v, str) and date.fromisoformat(v).isoformat() == v
    except ValueError:
        return False


def exato(v, keys):
    return isinstance(v, dict) and set(v) == set(keys)


def canonico(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def resumo(v):
    return hashlib.sha256(canonico(v).encode()).hexdigest()


def vazio():
    return {'schema_version': 1, 'vida': {'schema_version': 1, 'tarefas': [], 'registros': [], 'planos': [], 'medidas': []},
            'leitura': {'schema_version': 1, 'livros': []},
            'caderno': {'schema_version': 1, 'assets': [], 'relacoes': [], 'aplicacoes': []}}


def validar_campos(tipo, campos, completo=True):
    exigir(tipo in TIPOS and isinstance(campos, dict))
    specs = TIPOS[tipo]['campos']
    exigir(set(campos) <= set(specs))
    for k, spec in specs.items():
        v = campos.get(k)
        if v is None or v == '':
            exigir(not completo or not spec['obrigatorio'])
            continue
        t = spec['tipo']
        exigir((t == 'texto' and texto(v)) or (t == 'data' and dia(v)) or
               (t == 'inteiro' and inteiro(v, spec['minimo'], spec['maximo'])) or
               (t == 'booleano' and type(v) is bool) or (t == 'opcao' and v in spec['opcoes']))
    return campos


def assets(bundle):
    result = []
    for tipo, collection in [('tarefa','tarefas'),('plano','planos'),('medida','medidas')]:
        for a in bundle['vida'][collection]:
            fields = {k:v for k,v in a.items() if k in TIPOS[tipo]['campos']}
            if tipo == 'medida': fields['rotulo'] = a['app']
            result.append({'id':a['id'], 'tipo':tipo, 'campos':fields})
    for a in bundle['leitura']['livros']:
        fields = {k:v for k,v in a.items() if k in TIPOS['livro']['campos'] and v is not None}
        if a['observacoes']:
            fields['progresso_bp'] = sorted(a['observacoes'], key=lambda o:o['dia'])[-1]['progresso_bp']
        result.append({'id':a['id'], 'tipo':'livro', 'campos':fields})
    return result + bundle['caderno']['assets']


def validar_bundle(b):
    exigir(exato(b, ['schema_version','vida','leitura','caderno']) and inteiro(b['schema_version'],1,1))
    v, l, c = b['vida'], b['leitura'], b['caderno']
    exigir(isinstance(v,dict) and inteiro(v.get('schema_version'),1,1) and all(isinstance(v.get(k),list) for k in ['tarefas','planos','registros','medidas']))
    exigir(isinstance(l,dict) and inteiro(l.get('schema_version'),1,1) and isinstance(l.get('livros'),list))
    exigir(exato(c, ['schema_version','assets','relacoes','aplicacoes']) and inteiro(c['schema_version'],1,1))
    exigir(all(isinstance(c[k],list) for k in ['assets','relacoes','aplicacoes']))
    all_assets = assets(b)
    exigir(len(all_assets) <= 3000 and len(c['relacoes']) <= 3000 and len(c['aplicacoes']) <= 256)
    refs = {(a['tipo'],a['id']) for a in all_assets}
    exigir(len(refs) == len(all_assets))
    for a in all_assets:
        exigir(texto(a['id'],128)); validar_campos(a['tipo'],a['campos'])
    tasks = {a['id'] for a in v['tarefas']}
    exigir(len({(r['tarefaId'],r['dia']) for r in v['registros']}) == len(v['registros']))
    for r in v['registros']:
        exigir(r['tarefaId'] in tasks and dia(r['dia']) and r['origem'] == 'usuario')
    for a in v['planos']: exigir(type(a['concluido']) is bool and isinstance(a['porque'],str) and isinstance(a['proximoPasso'],str))
    for a in v['medidas']: exigir(a['origem'] == 'usuario')
    for a in c['assets']:
        exigir(TIPOS[a['tipo']]['destino']=='caderno' and exato(a,['id','tipo','campos','proveniencia']))
        p=a['proveniencia'];exigir(exato(p,['origem','porque','quando','por_quem','proposta']) and p['origem']=='usuario' and texto(p['porque']) and dia(p['quando']) and texto(p['por_quem'],128) and texto(p['proposta'],128))
    for a in l['livros']:
        exigir(a['dias_semana'] is None or inteiro(a['dias_semana'],1,7))
        exigir(a['fonte'] in ['usuario','librera'] and isinstance(a['perfil'],str) and (a['chave'] is None or isinstance(a['chave'],str)))
        exigir(len({p['dia'] for p in a['observacoes']}) == len(a['observacoes']))
        for p in a['observacoes']: exigir(dia(p['dia']) and inteiro(p['progresso_bp'],0,10000) and inteiro(p['tempo_ms'],1,8_640_000_000_000_000) and p['origem'] in ['usuario','librera'])
    for rel in c['relacoes']: validar_relacao(rel, refs)
    for receipt in c['aplicacoes']:
        exigir(exato(receipt,['id','hash']) and texto(receipt['id'],128) and bool(re.fullmatch('[a-f0-9]{64}',receipt['hash'])))
    exigir(len({r['id'] for r in c['aplicacoes']}) == len(c['aplicacoes']))
    return b


def validar_relacao(r, refs):
    exigir(exato(r,['de','para','tipo','porque']) and r['tipo'] in CATALOGO['relacoes'] and texto(r['porque']))
    for k in ['de','para']:
        exigir(exato(r[k],['tipo','id']) and (r[k]['tipo'],r[k]['id']) in refs)
    exigir(r['de'] != r['para'])


def preparar(bundle, rascunhos, relacoes, proposal_id):
    validar_bundle(bundle)
    exigir(texto(proposal_id,128) and isinstance(rascunhos,list) and 1 <= len(rascunhos) <= 20)
    ops = []
    for d in rascunhos:
        exigir(exato(d,['id','tipo','campos','porque','acao']) and d['acao'] in ['criar','atualizar'] and texto(d['id'],128) and texto(d['porque']))
        validar_campos(d['tipo'],d['campos'])
        ops.append(copy.deepcopy(d))
    refs = {(a['tipo'],a['id']) for a in assets(bundle)}
    for d in ops:
        ref = (d['tipo'],d['id'])
        exigir((d['acao'] == 'criar' and ref not in refs) or (d['acao'] == 'atualizar' and ref in refs))
        refs.add(ref)
    exigir(len({(o['tipo'],o['id']) for o in ops}) == len(ops) and isinstance(relacoes,list) and len(relacoes) <= 30)
    for r in relacoes: validar_relacao(r,refs)
    return {'schema_version':1,'id':proposal_id,'base_hash':resumo(bundle),'operacoes':ops,'relacoes':copy.deepcopy(relacoes)}


def aplicar(bundle, proposta, confirmado, hoje, tempo_ms):
    validar_bundle(bundle)
    exigir(confirmado is True and dia(hoje) and inteiro(tempo_ms,1,8_640_000_000_000_000))
    exigir(exato(proposta,['schema_version','id','base_hash','operacoes','relacoes']) and inteiro(proposta['schema_version'],1,1))
    receipt = next((a for a in bundle['caderno']['aplicacoes'] if a['id'] == proposta['id']),None)
    digest = resumo(proposta)
    if receipt:
        exigir(receipt['hash'] == digest)
        return {'bundle':bundle,'repetido':True,'id':proposta['id']}
    exigir(proposta['base_hash'] == resumo(bundle))
    expected = preparar(bundle,proposta['operacoes'],proposta['relacoes'],proposta['id'])
    exigir(expected == proposta)
    result = copy.deepcopy(bundle)
    for op in proposta['operacoes']:
        t, f, aid = op['tipo'], op['campos'], op['id']
        prov = {'origem':'usuario','porque':op['porque'],'quando':hoje,'por_quem':'triagem_confirmada','proposta':proposta['id']}
        destino = TIPOS[t]['destino']
        if destino == 'caderno':
            collection = result['caderno']['assets']
            old = next((a for a in collection if a['id']==aid and a['tipo']==t),{})
            record = {'id':aid,'tipo':t,'campos':{**copy.deepcopy(old.get('campos',{})),**copy.deepcopy(f)},'proveniencia':prov}
        else:
            left,right = destino.split('.'); collection = result[left][right]
            old = next((a for a in collection if a['id'] == aid),{})
            record = {**old, 'id':aid, **copy.deepcopy(f), 'proveniencia':prov}
            if t == 'plano':
                record = {'porque':'','proximoPasso':'','prazo':'','concluido':False,**record}
                for key in ['porque','proximoPasso','prazo']:
                    if record[key] is None:record[key]=''
            if t == 'medida':
                record['app'] = record.pop('rotulo'); record['origem'] = 'usuario'
            if t == 'livro':
                record = {'fonte':'usuario','chave':None,'perfil':'','prazo':'','dias_semana':None,'observacoes':[],**record}
                if record['dias_semana']=='':record['dias_semana']=None
                if record['prazo'] is None:record['prazo']=''
                progress = record.pop('progresso_bp',None)
                if progress is not None and progress!='':
                    record['observacoes'] = sorted([p for p in record['observacoes'] if p['dia'] != hoje] +
                        [{'dia':hoje,'progresso_bp':progress,'tempo_ms':tempo_ms,'origem':'usuario'}],key=lambda p:p['dia'])
        index = next((i for i,a in enumerate(collection) if a['id'] == aid and (destino != 'caderno' or a['tipo'] == t)),None)
        if index is None: collection.append(record)
        else: collection[index] = record
    for r in proposta['relacoes']:
        if r not in result['caderno']['relacoes']: result['caderno']['relacoes'].append(copy.deepcopy(r))
    result['caderno']['aplicacoes'] = (result['caderno']['aplicacoes'] + [{'id':proposta['id'],'hash':digest}])[-256:]
    validar_bundle(result)
    return {'bundle':result,'repetido':False,'id':proposta['id']}


def contexto(bundle, rascunhos, hoje):
    validar_bundle(bundle)
    exigir(dia(hoje))
    exigir(isinstance(rascunhos,list) and 1 <= len(rascunhos) <= 20)
    existentes = assets(bundle)
    # Limite determinístico, explicitado no protocolo. Nenhum título é enviado.
    locais = copy.deepcopy(existentes[:100])
    for a in locais:
        if a['tipo']=='livro':
            book=next(b for b in bundle['leitura']['livros'] if b['id']==a['id'])
            obs=sorted([o for o in book['observacoes'] if o['dia']<=hoje],key=lambda o:o['dia'])
            a['campos'].pop('progresso_bp',None)
            if obs:a['campos']['progresso_bp']=obs[-1]['progresso_bp']
    mapa = {}; itens = []; options = []
    def item(a, ref, draft=False):
        exigir(a['tipo'] in TIPOS); validar_campos(a['tipo'],a['campos'],False)
        specs = TIPOS[a['tipo']]['campos']; fields = a['campos']
        missing = [k for k,s in specs.items() if s['obrigatorio'] and (k not in fields or fields[k] is None or fields[k] == '')]
        values = {k:v for k,v in fields.items() if k in specs and specs[k]['publicavel'] and v is not None and v != ''}
        mapa[ref] = {'tipo':a['tipo'],'id':a['id'],'titulo':fields.get('titulo',fields.get('rotulo','Registro'))}
        calc = []
        if a['tipo'] == 'objetivo' and inteiro(values.get('meta')) and values['meta'] > 0 and inteiro(values.get('atual')):
            calc.append({'metodo':'razao_bp','numerador':values['atual'],'denominador':values['meta'],'resultado':min(10000,values['atual']*10000//values['meta'])})
        return {'ref':ref,'tipo':a['tipo'],'preenchidos':[k for k in specs if specs[k]['presenca_publica'] and k in fields and fields[k] is not None and fields[k] != ''], 'faltantes':missing,'valores':values,'calculos':calc}
    for i,a in enumerate(locais): itens.append(item(a,f'item_{i}'))
    drafts = []
    for i,d in enumerate(rascunhos):
        exigir(exato(d,['id','tipo','campos','porque','acao']) and d['acao'] in ['criar','atualizar'] and texto(d['id'],128) and texto(d['porque']))
        ref = f'rascunho_{i}'; public = item(d,ref,True); drafts.append(public)
        for field in public['faltantes']:
            options.append({'acao':'perguntar','rascunho':ref,'campo':field,'alvo':None})
        if not public['faltantes']:
            options.append({'acao':'revisar','rascunho':ref,'campo':None,'alvo':None})
            for k,s in TIPOS[d['tipo']]['campos'].items():
                if s['tipo'] == 'inteiro' and k not in public['preenchidos']:
                    options.append({'acao':'sugerir_valor','rascunho':ref,'campo':k,'alvo':None})
        # Correlação textual acontece exclusivamente localmente. É sugestão, não causa.
        title = str(d['campos'].get('titulo','')).lower().strip()
        for j,a in enumerate(locais):
            other = str(a['campos'].get('titulo','')).lower().strip()
            tokens = set(re.findall(r'\w{4,}',title)); overlap = tokens & set(re.findall(r'\w{4,}',other))
            if d['id'] != a['id'] and (title and title == other or len(overlap) >= 2):
                options.append({'acao':'correlacionar','rascunho':ref,'campo':None,'alvo':f'item_{j}'})
    options.sort(key=lambda o:o['acao']!='perguntar')
    for i,o in enumerate(options): o['id'] = f'opcao_{i}'
    public = {'schema_version':1,'itens':itens,'rascunhos':drafts,'opcoes':options[:100],
              'relacoes':[], 'metricas':[], 'limitado':len(existentes) > 100 or len(options) > 100}
    reverse = {(v['tipo'],v['id']):k for k,v in mapa.items()}
    for r in bundle['caderno']['relacoes']:
        a,b = reverse.get((r['de']['tipo'],r['de']['id'])),reverse.get((r['para']['tipo'],r['para']['id']))
        if a and b: public['relacoes'].append({'de':a,'para':b,'tipo':r['tipo']})
    from .ai_context import project_context
    from .reading import pacing
    fronts=[]
    for area in AREAS:
        active=[a for a in bundle['vida']['tarefas'] if a['atributo']==area and (a['inicio']<=hoje if a['repetir'] else a['inicio']==hoje)]
        done=sum(any(r['tarefaId']==a['id'] and r['dia']==hoje for r in bundle['vida']['registros']) for a in active)
        fronts.append({'area':area,'total':len(active),'done':done})
    states=project_context(fronts=fronts,plans=[],reading=[],scopes=['rotina'])['rotina']
    for index,(f,state) in enumerate(zip(fronts,states)):
        ref=f'grupo_{index}';mapa[ref]={'tipo':'area','id':f['area'],'titulo':f['area']}
        public['metricas'].append({'ref':ref,'tipo':'tarefas','previstas':f['total'],'conclusoes_registradas':f['done'],'evidencia':state['evidencia']})
    for index,a in enumerate(locais):
        if a['tipo']!='livro':continue
        book=next(b for b in bundle['leitura']['livros'] if b['id']==a['id'])
        points=[{'dia':o['dia'],'progresso_bp':o['progresso_bp']} for o in book['observacoes'] if o['dia']<=hoje]
        result=pacing(points,today=hoje,deadline=book.get('prazo') or None,reading_days=book.get('dias_semana'))
        public['metricas'].append({'ref':f'item_{index}','tipo':'leitura','calculo':result})
    return {'publico':public,'mapa_local':mapa}


def executar(operacao, i):
    if operacao == 'triagem.catalogo': return CATALOGO
    if operacao == 'triagem.contexto': return contexto(i['bundle'],i['rascunhos'],i['hoje'])
    if operacao == 'triagem.preparar': return preparar(i['bundle'],i['rascunhos'],i['relacoes'],i['id'])
    if operacao == 'triagem.aplicar': return aplicar(i['bundle'],i['proposta'],i['confirmado'],i['hoje'],i['tempo_ms'])
    if operacao == 'triagem.validar': return {'valido':bool(validar_bundle(i['bundle'])),'base_hash':resumo(i['bundle'])}
    raise ValueError('Operação de triagem indisponível')


def validar_publico(p):
    """Fronteira independente: nenhuma string livre chega ao transporte."""
    exigir(exato(p,['schema_version','itens','rascunhos','opcoes','relacoes','metricas','limitado']) and inteiro(p['schema_version'],1,1) and type(p['limitado']) is bool)
    exigir(isinstance(p['itens'],list) and len(p['itens'])<=100 and isinstance(p['rascunhos'],list) and 1<=len(p['rascunhos'])<=20)
    byref={}
    for prefix,items in [('item',p['itens']),('rascunho',p['rascunhos'])]:
        for i,a in enumerate(items):
            exigir(exato(a,['ref','tipo','preenchidos','faltantes','valores','calculos']) and a['ref']==f'{prefix}_{i}' and a['tipo'] in TIPOS)
            specs=TIPOS[a['tipo']]['campos']
            for k in ['preenchidos','faltantes']:
                exigir(isinstance(a[k],list) and len(a[k])==len(set(a[k])) and set(a[k])<=set(specs) and all(specs[v]['presenca_publica'] for v in a[k]))
            exigir(a['faltantes']==[k for k,s in specs.items() if s['obrigatorio'] and k not in a['preenchidos']])
            exigir(set(a['valores'])=={k for k in a['preenchidos'] if specs[k]['publicavel']})
            validar_campos(a['tipo'],a['valores'],False)
            exigir(isinstance(a['calculos'],list) and len(a['calculos'])<=1)
            for c in a['calculos']:
                values=a['valores'];exigir(a['tipo']=='objetivo' and exato(c,['metodo','numerador','denominador','resultado']))
                exigir(c['metodo']=='razao_bp' and c['numerador']==values.get('atual') and c['denominador']==values.get('meta') and inteiro(c['denominador'],1,10**9) and inteiro(c['numerador'],0,10**9))
                exigir(inteiro(c['resultado'],0,10000) and c['resultado']==min(10000,c['numerador']*10000//c['denominador']))
            byref[a['ref']]=a
    exigir(isinstance(p['opcoes'],list) and 1<=len(p['opcoes'])<=100)
    for i,o in enumerate(p['opcoes']):
        exigir(exato(o,['id','acao','rascunho','campo','alvo']) and o['id']==f'opcao_{i}' and o['rascunho'] in byref and o['rascunho'].startswith('rascunho_'))
        d=byref[o['rascunho']];specs=TIPOS[d['tipo']]['campos'];k=o['campo']
        if o['acao']=='perguntar': exigir(k in d['faltantes'] and o['alvo'] is None)
        elif o['acao']=='revisar': exigir(not d['faltantes'] and k is None and o['alvo'] is None)
        elif o['acao']=='sugerir_valor': exigir(k in specs and specs[k]['tipo']=='inteiro' and k not in d['preenchidos'] and o['alvo'] is None)
        elif o['acao']=='correlacionar': exigir(o['alvo'] in byref and o['alvo'].startswith('item_') and k is None)
        else: exigir(False)
    exigir(isinstance(p['relacoes'],list) and len(p['relacoes'])<=3000)
    for r in p['relacoes']: exigir(exato(r,['de','para','tipo']) and r['de'] in byref and r['para'] in byref and r['tipo'] in CATALOGO['relacoes'])
    exigir(isinstance(p['metricas'],list) and len(p['metricas'])<=106)
    for m in p['metricas']:
        if m['tipo']=='tarefas':
            exigir(exato(m,['ref','tipo','previstas','conclusoes_registradas','evidencia']) and bool(re.fullmatch('grupo_[0-5]',m['ref'])))
            exigir(inteiro(m['previstas'],0,3000) and inteiro(m['conclusoes_registradas'],0,m['previstas']) and m['evidencia'] in ['sem_metas','sem_registro','parcial','completa'])
        elif m['tipo']=='leitura':
            exigir(exato(m,['ref','tipo','calculo']) and m['ref'] in byref and byref[m['ref']]['tipo']=='livro')
            calc=m['calculo'];integer_keys=['progresso_bp','amostras','intervalo_dias','avanco_bp','previsao_dias','prazo_dias','necessario_bp_dia','meta_bp_sessao']
            exigir(exato(calc,integer_keys+['estado','historico_reiniciado','preliminar']) and calc['estado'] in ['sem_dados','desatualizado','calibrando','sem_avanco','estimado','no_fim'])
            exigir(all(calc[k] is None or inteiro(calc[k],-4000000,40000000000) for k in integer_keys) and type(calc['historico_reiniciado']) is bool and type(calc['preliminar']) is bool)
        else:exigir(False)
    return p


MOTIVOS=['preencher_necessario','revisar_em_lote','evitar_duplicata','ritmo_realista','contexto_relacionado']


def schema_sugestao(p):
    validar_publico(p)
    return {'type':'object','additionalProperties':False,'required':['escolha','valor','motivo'], 'properties':{
        'escolha':{'type':'string','enum':[o['id'] for o in p['opcoes']]},
        'valor':{'type':['integer','null']},'motivo':{'type':'string','enum':MOTIVOS}}}


def validar_sugestao(p,s):
    validar_publico(p)
    exigir(exato(s,['escolha','valor','motivo']) and s['motivo'] in MOTIVOS)
    op=next((o for o in p['opcoes'] if o['id']==s['escolha']),None);exigir(op is not None)
    if op['acao']=='sugerir_valor':
        d=next(d for d in p['rascunhos'] if d['ref']==op['rascunho']); spec=TIPOS[d['tipo']]['campos'][op['campo']]
        exigir(inteiro(s['valor'],spec['minimo'],spec['maximo']))
    else: exigir(s['valor'] is None)
    return {'opcao':op,'valor':s['valor'],'motivo':s['motivo'],'origem':'openai'}
