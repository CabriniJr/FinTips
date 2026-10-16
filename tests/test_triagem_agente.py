import copy
import json
import sys
from pathlib import Path
import pytest
from jsonschema import validate
from fintips import triagem_universal as t
from fintips import triagem_agente as a
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ouro_agente import gerar


def test_agente_organiza_multiplos_campos_vincula_e_cria_assets():
    gold=gerar()
    for c in gold['casos']:
        assert t.executar(c['operacao'],c['entrada'])==c['resultado']
        if c['operacao']=='triagem.agente_aplicar':
            public=a.contexto(c['entrada']['bundle'],c['entrada']['rascunhos'],c['entrada']['hoje'])['publico']
            validate(c['entrada']['resposta'],a.schema(public))
    r=gold['casos'][2]['resultado'];assert r['rascunhos'][1]['campos']=={'titulo':'BOOK_CANARY','dias_semana':3,'progresso_bp':2500}
    assert r['pergunta'] is None and len(r['relacoes'])==1


def test_contratos_adversariais_nao_modificam_a_fonte():
    for c in gerar()['recusados']:
        original=copy.deepcopy(c['entrada'])
        with pytest.raises(Exception):t.executar(c['operacao'],c['entrada'])
        assert c['entrada']==original


def test_numeros_e_semantica_publicos_nunca_incluem_strings_privadas():
    for c in gerar()['casos']:
        if c['operacao']!='triagem.agente_contexto':continue
        i=c['entrada'];request=a.pedido(i['bundle'],i['rascunhos'],i['hoje'])
        raw=json.dumps(request)
        for forbidden in ['CANARY','plan-local','book-local','money-local','origem_real','destino_real','valores_locais','mapa_local']:assert forbidden not in raw
        assert request['store'] is False
        public=json.loads(request['input'])
        assert 'contratos' in public and 'valores_disponiveis' in public
        assert any(v['tipo']=='texto' and 'valor' not in v for v in public['valores_disponiveis'])
    assert '12345' in json.dumps(a.pedido(gerar()['casos'][5]['entrada']['bundle'],gerar()['casos'][5]['entrada']['rascunhos'],gerar()['casos'][5]['entrada']['hoje']))


def test_observacoes_ausentes_continuam_ausentes_e_valores_explicitos_nao_sao_trocados():
    i=gerar()['casos'][0]['entrada'];i['rascunhos'][1]['campos']={'titulo':'Livro CANARY','dias_semana':4}
    result=a.resolver(**{'bundle':i['bundle'],'drafts':i['rascunhos'],'hoje':i['hoje'],'response':{'registros':[],'relacoes':[],'pergunta':None}})
    assert 'progresso_bp' not in result['rascunhos'][1]['campos']
    vals=a.contexto(i['bundle'],i['rascunhos'],i['hoje'])['valores_locais']
    # Não há valor literal no contrato; referências não podem fabricar um 0.
    assert not any(v['campo']=='progresso_bp' for v in vals.values())


def test_estrutura_preserva_intencao_negacao_e_condicao_sem_mensagem_real():
    case=next(c for c in gerar()['casos'] if c['nome'].startswith('estrutura preserva'))
    public=case['resultado']['publico']
    entry=next(v for v in public['valores_disponiveis'] if v['dono']=='rascunho_0' and v['campo']=='titulo')
    assert entry['estrutura'][:3]==['not','want','gym']
    assert 'if' in entry['estrutura'] and 'reading' in entry['estrutura']
    assert 'CANARY' not in json.dumps(public) and any(v.startswith('opaco_') for v in entry['estrutura'])
    question=next(c for c in gerar()['casos'] if c['nome'].startswith('pergunta natural'))['resultado']['pergunta']['text']
    assert 'CANARY' in question and '{{' not in question
    other=next(c for c in gerar()['casos'] if c['nome'].startswith('título entre aspas'))['resultado']['publico']['valores_disponiveis']
    assert not any(v['dono']=='rascunho_0' and v['papel']=='acao_leitura' for v in other)
