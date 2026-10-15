#!/usr/bin/env python3
"""Catálogo único → constante Kotlin e JSON Schema público. Sem dados pessoais."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'fintips/rules/triagem-catalogo.json'
c=json.loads(source.read_text())
raw=json.dumps(c,ensure_ascii=False,separators=(',',':'))
kt='// Gerado por scripts/gerar-contratos-triagem.py; não editar.\npackage com.fintips.motor.triagem\n\ninternal const val CATALOGO_JSON = """'+raw+'"""\n'
variants=[]
for name,spec in c['tipos'].items():
 fields={};required=[]
 for k,f in spec['campos'].items():
  t=f['tipo'];v={'type':{'texto':'string','data':'string','opcao':'string','inteiro':'integer','booleano':'boolean'}[t]}
  if t=='inteiro':v.update(minimum=f['minimo'],maximum=f['maximo'])
  elif t=='texto':v.update(minLength=1,maxLength=4000)
  elif t=='data':v.update(format='date')
  elif t=='opcao':v.update(enum=f['opcoes'])
  if f['obrigatorio']:required.append(k)
  if not f['obrigatorio']:v={'anyOf':[v,{'type':'null'},{'const':''}]}
  fields[k]=v
 variants.append({'type':'object','additionalProperties':False,'required':['id','tipo','campos','porque','acao'],'properties':{
 'id':{'type':'string','minLength':1,'maxLength':128},'tipo':{'const':name},'acao':{'enum':['criar','atualizar']},'porque':{'type':'string','minLength':1,'maxLength':4000},
 'campos':{'type':'object','additionalProperties':False,'properties':fields,'required':required}}})
ref={'type':'object','additionalProperties':False,'required':['tipo','id'],'properties':{'tipo':{'enum':list(c['tipos'])},'id':{'type':'string','minLength':1,'maxLength':128}}}
rel={'type':'object','additionalProperties':False,'required':['de','para','tipo','porque'],'properties':{'de':ref,'para':ref,'tipo':{'enum':c['relacoes']},'porque':{'type':'string','minLength':1,'maxLength':4000}}}
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://raw.githubusercontent.com/CabriniJr/FinTips/main/docs/contratos/triagem-v1.schema.json','title':'FinTips triagem v1 — proposta local revisável',
 'type':'object','additionalProperties':False,'required':['schema_version','id','base_hash','operacoes','relacoes'],'properties':{'schema_version':{'const':1},'id':{'type':'string','minLength':1,'maxLength':128},'base_hash':{'type':'string','pattern':'^[a-f0-9]{64}$'},'operacoes':{'type':'array','minItems':1,'maxItems':20,'items':{'oneOf':variants}},'relacoes':{'type':'array','maxItems':30,'items':rel}}}
outputs={ROOT/'kotlin/motor/src/commonMain/kotlin/com/fintips/motor/triagem/CatalogoGerado.kt':kt,ROOT/'docs/contratos/triagem-v1.schema.json':json.dumps(schema,ensure_ascii=False,indent=2)+'\n'}
for p,text in outputs.items():
 if '--conferir' in sys.argv:
  if not p.exists() or p.read_text()!=text:raise SystemExit(f'Contrato desatualizado: {p.relative_to(ROOT)}')
 else:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
print('ok: catálogo, Kotlin e JSON Schema de triagem conferem')
