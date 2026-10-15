"""Agente preenche contratos por referências locais, nunca por texto remoto."""
import copy
import re
import unicodedata
from . import triagem_universal as t

import json
from pathlib import Path
POLITICA=json.loads((Path(__file__).parent/'rules'/'triagem-agente.json').read_text())
CONCEITOS=POLITICA['conceitos']

def normal(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if unicodedata.category(c)!='Mn')


def contexto(bundle,drafts,hoje):
    base=t.contexto(bundle,drafts,hoje)
    values=[]; local={}; opaque={}
    def add(owner,field,value,kind,papel='campo'):
        if len(values)>=512:return
        ref=f'valor_{len(values)}'
        entry={'ref':ref,'dono':owner,'campo':field,'tipo':kind,'papel':papel}
        if kind in ['inteiro','booleano','opcao']:entry['valor']=value
        if kind=='texto':
            text=normal(value);words=set(re.findall(r'[a-z]+',text))
            tokens=re.findall(r'[a-z0-9]+',text)[:200];sequence=[]
            for token in tokens:
                code=POLITICA['lexico'].get(token)
                if code is None:
                    if token not in opaque:opaque[token]=f'opaco_{len(opaque)}'
                    code=opaque[token]
                sequence.append(code)
            entry['estrutura']=sequence
            entry['conceitos']=[k for k,terms in CONCEITOS.items() if words.intersection(terms)]
            if 'todo dia' in text or 'todos os dias' in text:entry['conceitos'].append('recorrente')
        values.append(entry);local[ref]={'valor':value,'campo':field,'tipo':kind,'dono':owner}
    # Somente rascunhos fornecem valores: o agente não copia fatos de outra pessoa/asset.
    for index,d in enumerate(drafts):
        owner=f'rascunho_{index}'
        for field,spec in t.TIPOS[d['tipo']]['campos'].items():
            value=d['campos'].get(field)
            if not spec['presenca_publica'] or value is None or value=='':continue
            add(owner,field,value,spec['tipo'])
            if spec['tipo']=='texto' and field in ['titulo','descricao']:
                text=normal(value)
                for m in re.finditer(r'(?<![\w.,])([0-7])\s*(?:dias?|vezes|x)\s*(?:por\s*|na\s*|/\s*)(?:semana)(?!\w)',text):
                    if int(m[1])>0:add(owner,'dias_semana',int(m[1]),'inteiro','extraido')
                for m in re.finditer(r'(?:ja\s+li|estou\s+em|progresso\s*(?:de|:)?)\s*([0-9]{1,3})(?:[,.]([0-9]{1,2}))?\s*%(?!\w)',text):
                    value_bp=int(m[1])*100+int((m[2] or '').ljust(2,'0'))
                    if value_bp<=10000:add(owner,'progresso_bp',value_bp,'inteiro','extraido')
                for m in re.finditer(r'(?<![\w.,])([0-9]{1,4})\s*(?:minutos?|min)(?!\w)',text):
                    if int(m[1])<=1440 and re.search(r'\b(fiquei|usei|registrar|registro|uso)\b',text):add(owner,'minutos',int(m[1]),'inteiro','extraido')
                for m in re.finditer(r'r\$\s*([0-9.,]+)',text):
                    if re.fullmatch(r'[0-9]+(?:[.,][0-9]{1,2})?',m[1]):
                        pieces=re.split('[.,]',m[1]);amount=int(pieces[0])*100+int(pieces[1].ljust(2,'0') if len(pieces)>1 else '0')
                        if amount<=9_000_000_000_000:add(owner,'valor_centavos',amount,'inteiro','extraido')
                # Título/trecho permanecem locais; só o papel é publicado.
                quoted=re.search(r'[“"]([^”"]{1,300})[”"]',value)
                short=quoted[1] if quoted else None
                if not short:
                    reading=re.search(r'^(?:(?:quero|pretendo|planejo)\s+)?(?:(?:comecar a|estou)\s+)?(?:ler|lendo)\s+(.+)$',text)
                    # Índices do texto normalizado não são usados para recortar Unicode privado.
                    original=re.search(r'^(?:(?:quero|pretendo|planejo)\s+)?(?:(?:começar a|estou)\s+)?(?:ler|lendo)\s+(.+)$',value,re.I)
                    candidate=original[1] if reading and original else value if d['tipo']=='livro' else None
                    if candidate:
                        candidate=re.split(r'\s+(?=\d+\s*(?:dias?|vezes|x|minutos?|min)\b|(?:e\s+)?(?:terminar|acabar)\b|porque\b|at[eé]\b|todos os dias\b)',candidate,1,flags=re.I)[0].strip()
                        if candidate and not re.match(r'^(mais|menos|um|uma|todo|todos|melhor)\b',normal(candidate)) and candidate!=value:short=candidate
                if short:
                    add(owner,'titulo',short,'texto','titulo_curto')
                    if d['tipo']=='livro' or set(re.findall(r'[a-z]+',text)).intersection(CONCEITOS['leitura']):add(owner,'titulo','Ler '+short,'texto','acao_leitura')
    add('catalogo','inicio',hoje,'data','padrao_hoje')
    add('catalogo','repetir',False,'booleano','padrao')
    add('catalogo','repetir',True,'booleano','recorrente')
    for kind,c in t.TIPOS.items():
        for field,spec in c['campos'].items():
            if spec['tipo']=='opcao':
                for value in spec['opcoes']:
                    if not any(v['dono']=='catalogo' and v['campo']==field and v.get('valor')==value for v in values):add('catalogo',field,value,'opcao')
    public={**base['publico'],'limitado':base['publico']['limitado'] or len(values)>=512,'valores_disponiveis':values,
            'contratos':{kind:{f:{k:copy.deepcopy(v) for k,v in s.items() if k in ['tipo','obrigatorio','minimo','maximo','opcoes']} for f,s in c['campos'].items() if s['presenca_publica']} for kind,c in t.TIPOS.items()}}
    return {'publico':public,'valores_locais':local,'mapa_local':base['mapa_local']}


def schema(public):
    def obj(properties):return {'type':'object','additionalProperties':False,'required':list(properties),'properties':properties}
    def enum(values):return {'type':'string','enum':values}
    refs=[d['ref'] for d in public['rascunhos']]+[f'novo_{i}' for i in range(6)]
    fields=sorted({f for c in public['contratos'].values() for f in c})
    binding=obj({'campo':enum(fields),'valor':enum([v['ref'] for v in public['valores_disponiveis']])})
    record=obj({'ref':enum(refs),'tipo':enum(list(t.TIPOS)),'campos':{'type':'array','items':binding}})
    edge=obj({'de':enum(refs+[i['ref'] for i in public['itens']]),'para':enum(refs+[i['ref'] for i in public['itens']]),'tipo':enum(t.CATALOGO['relacoes'])})
    question=obj({'ref':enum(refs),'campo':enum(fields),'texto':{'type':'string'}})
    return obj({'registros':{'type':'array','items':record},'relacoes':{'type':'array','items':edge},'pergunta':{'anyOf':[question,{'type':'null'}]}})

INSTRUCOES=POLITICA['instrucoes']

def pedido(bundle,drafts,hoje):
    public=contexto(bundle,drafts,hoje)['publico']
    import json
    return {'model':'gpt-4.1-mini','store':False,'max_output_tokens':3000,'instructions':INSTRUCOES,
            'input':json.dumps(public,ensure_ascii=False,separators=(',',':')),
            'text':{'format':{'type':'json_schema','name':'fintips_agente_v2','strict':True,'schema':schema(public)}}}


def resolver(bundle,drafts,hoje,response):
    ctx=contexto(bundle,drafts,hoje);local=ctx['valores_locais'];out=copy.deepcopy(drafts)
    t.exigir(t.exato(response,['registros','relacoes','pergunta']) and isinstance(response['registros'],list) and len(response['registros'])<=20 and isinstance(response['relacoes'],list) and len(response['relacoes'])<=30)
    refs={f'rascunho_{i}':d for i,d in enumerate(out)};seen=set()
    for r in response['registros']:
        t.exigir(t.exato(r,['ref','tipo','campos']) and r['tipo'] in t.TIPOS and r['ref'] not in seen);seen.add(r['ref'])
        ref=r['ref'];kind=r['tipo']
        if re.fullmatch(r'novo_[0-5]',ref):
            t.exigir(len(out)<20)
            d={'id':'agente-'+t.resumo([[v['id'] for v in drafts],ref])[:24],'tipo':kind,'campos':{},'acao':'criar','porque':'Organizado pelo agente a partir de referências da conversa; revisão da pessoa.'}
            out.append(d);refs[ref]=d
        else:
            t.exigir(ref in refs);d=refs[ref]
            t.exigir(d['acao']=='criar' or d['tipo']==kind)
            d['tipo']=kind;d['campos']={k:v for k,v in d['campos'].items() if k in t.TIPOS[kind]['campos']}
        t.exigir(isinstance(r['campos'],list) and len(r['campos'])<=30)
        used=set()
        for binding in r['campos']:
            t.exigir(t.exato(binding,['campo','valor']) and binding['campo'] not in used);used.add(binding['campo'])
            field=binding['campo'];source=local.get(binding['valor']);spec=t.TIPOS[kind]['campos'].get(field)
            t.exigir(source and spec and spec['presenca_publica'] and spec['tipo']==source['tipo'])
            if field in ['progresso_bp','minutos','atual']:
                owner=ref if ref.startswith('rascunho_') else next((local[b['valor']]['dono'] for b in r['campos'] if b['campo'] in ['titulo','rotulo'] and b['valor'] in local),None)
                t.exigir(source['dono']==owner)
            # Valores numéricos/enums/datas e motivos só migram entre campos equivalentes.
            if spec['tipo']!='texto' or field=='porque':t.exigir(source['campo']==field or field.endswith('_centavos') and source['campo'].endswith('_centavos'))
            # Preserva fatos explícitos: não sobrescrever um valor existente diferente.
            old=d['campos'].get(field)
            if spec['tipo'] not in ['texto'] and old is not None and old!='':t.exigir(old==source['valor'])
            d['campos'][field]=copy.deepcopy(source['valor'])
        t.validar_campos(kind,d['campos'],False)
    # Uma correspondência exata e única vira atualização; dados não fornecidos são preservados pelo aplicar.
    autofilled=set()
    for index,d in enumerate(out):
        title=d['campos'].get('titulo',d['campos'].get('rotulo',''))
        matches=[x for x in t.assets(bundle) if x['tipo']==d['tipo'] and (d['tipo']!='medida' or x['campos'].get('dia')==d['campos'].get('dia')) and normal(x['campos'].get('titulo',x['campos'].get('rotulo',''))).strip()==normal(title).strip()]
        if d['acao']=='criar' and d['porque']!='Registro separado por escolha explícita da pessoa na conversa.' and title and len(matches)==1:
            old=matches[0]
            t.exigir(not any(x is not d and x['id']==old['id'] and x['tipo']==old['tipo'] for x in out))
            d['id']=old['id'];d['acao']='atualizar'
            for f,s in t.TIPOS[d['tipo']]['campos'].items():
                if s['obrigatorio'] and d['campos'].get(f) in [None,''] and f in old['campos']:
                    d['campos'][f]=copy.deepcopy(old['campos'][f]);autofilled.add((index,f))
    mapping={**{k:{'id':v['id'],'tipo':v['tipo']} for k,v in ctx['mapa_local'].items() if k.startswith('item_')},**{k:{'id':v['id'],'tipo':v['tipo']} for k,v in refs.items()}}
    rels=[]
    for r in response['relacoes']:
        t.exigir(t.exato(r,['de','para','tipo']) and r['de'] in mapping and r['para'] in mapping)
        edge={'de':mapping[r['de']],'para':mapping[r['para']],'tipo':r['tipo'],'porque':'Relação proposta pelo agente a partir do contexto abstrato; revisão da pessoa.'}
        if r['de']!=r['para'] and edge['de']==edge['para']:continue
        t.validar_relacao(edge,{(v['tipo'],v['id']) for v in mapping.values()})
        t.exigir(edge not in rels);rels.append(edge)
    q=response['pergunta'];question=None
    if q is not None:
        t.exigir(t.exato(q,['ref','campo','texto']) and q['ref'] in refs)
        t.exigir(t.texto(q['texto'],500))
        for mention in re.findall(r'\{\{([^{}]+)\}\}',q['texto']):t.exigir(mention in refs)
        rendered=re.sub(r'\{\{([^{}]+)\}\}',lambda m:refs[m[1]]['campos'].get('titulo',refs[m[1]]['campos'].get('rotulo','este registro')),q['texto'])
        t.exigir(t.texto(rendered,5000))
        d=refs[q['ref']];spec=t.TIPOS[d['tipo']]['campos'].get(q['campo'])
        t.exigir(spec and spec['presenca_publica'])
        index=out.index(d)
        if (index,q['campo']) not in autofilled:
            t.exigir(d['campos'].get(q['campo']) in [None,''])
            question={'index':index,'field':q['campo'],'text':rendered}
    # Não aceitar 'pronto' se o modelo esqueceu obrigatórios. Recuperação local, sem outra chamada.
    if question is None:
        for i,d in enumerate(out):
            missing=[f for f,s in t.TIPOS[d['tipo']]['campos'].items() if s['obrigatorio'] and d['campos'].get(f) in [None,'']]
            if missing:question={'index':i,'field':missing[0]};break
    t.contexto(bundle,out,hoje)
    return {'rascunhos':out,'relacoes':rels,'pergunta':question,'origem':'openai'}
