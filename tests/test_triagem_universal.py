import copy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from fintips import triagem_universal as t
from fintips.api import app
from fintips.triagem_openai import pedido

GOLD=Path(__file__).resolve().parents[1]/'kotlin/motor/src/jvmTest/resources/ouro/triagem-universal.json'

def gold():return json.loads(GOLD.read_text())

def test_ouro_tem_todos_os_tipos_e_aplicacao_e_rejeicoes():
    g=gold()
    assert {d['tipo'] for d in g['casos'][0]['entrada']['rascunhos']}==set(t.TIPOS)
    for c in g['casos']:assert t.executar(c['operacao'],c['entrada'])==c['resultado']
    for c in g['recusados']:
        before=copy.deepcopy(c['entrada'])
        with pytest.raises(Exception):t.executar(c['operacao'],c['entrada'])
        assert c['entrada']==before


def test_publico_retem_valores_calculo_e_nao_texto_nem_endpoints_reais():
    c=next(c for c in gold()['casos'] if c['operacao']=='triagem.contexto')
    projection=t.executar(c['operacao'],c['entrada']);p=projection['publico']
    assert t.validar_publico(p)==p
    raw=json.dumps(pedido(p));assert 'CANARY' not in raw and 'asset-local' not in raw and 'mapa_local' not in raw
    assert 'razao_bp' in raw and '123' in raw
    assert 'origem_real' not in raw and 'destino_real' not in raw
    assert 'CANARY' in json.dumps(projection['mapa_local'])


@pytest.mark.parametrize('mutation',[lambda p:p.update(mensagem='PRIVATE_CANARY'),lambda p:p['itens'][0]['valores'].update(titulo='PRIVATE_CANARY'),lambda p:p['itens'][0].update(ref='real-id'),lambda p:p['opcoes'][0].update(alvo='real-id')])
def test_fronteira_publica_recusa_texto_livre_e_referencias_reais(mutation):
    p=copy.deepcopy(next(c for c in gold()['casos'] if c['operacao']=='triagem.contexto')['resultado']['publico']);mutation(p)
    with pytest.raises(Exception):pedido(p)


def test_sugestao_precisa_usar_opcao_e_limites_do_contrato():
    p=next(c for c in gold()['casos'] if c['operacao']=='triagem.contexto')['resultado']['publico']
    o=p['opcoes'][0]
    r=t.validar_sugestao(p,{'escolha':o['id'],'valor':None,'motivo':'preencher_necessario'})
    assert r['opcao']==o
    for choice in [{'escolha':'nao-existe','valor':None,'motivo':'preencher_necessario'},{'escolha':o['id'],'valor':42,'motivo':'preencher_necessario'},{'escolha':o['id'],'valor':None,'motivo':'PRIVATE_CANARY'}]:
        with pytest.raises(Exception):t.validar_sugestao(p,choice)


def test_api_local_usa_mesmo_contrato_e_nao_escreve_workspace(tmp_path,monkeypatch):
    monkeypatch.setenv('FINTIPS_ROOT',str(tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8420',client=('127.0.0.1',45000)) as c:
        assert c.get('/api/triagem/catalogo').json()==t.CATALOGO
        case=gold()['casos'][1]
        assert c.post('/api/triagem/aplicar',json=case['entrada']).json()==case['resultado']
        assert not list(tmp_path.iterdir())
        body=copy.deepcopy(case['entrada']);body['confirmado']=False
        assert c.post('/api/triagem/aplicar',json=body).status_code==400
        assert c.post('/api/triagem/aplicar',json=case['entrada'],headers={'Origin':'https://evil.example'}).status_code==403
        assert c.get('/api/triagem/catalogo',headers={'Host':'evil.example'}).status_code==403


def test_zero_e_dado_e_ausencia_nao_vira_zero():
    d={'id':'l','tipo':'livro','campos':{'titulo':'Livro sintético'},'porque':'Escolhido pela pessoa','acao':'criar'}
    p=t.contexto(t.vazio(),[d],'2026-10-15')['publico'];assert 'progresso_bp' not in p['rascunhos'][0]['valores']
    d['campos']['progresso_bp']=0
    assert t.contexto(t.vazio(),[d],'2026-10-15')['publico']['rascunhos'][0]['valores']['progresso_bp']==0


def test_cliente_openai_envia_somente_publico_e_recusa_envio_sem_consentimento(monkeypatch):
    import io
    import urllib.request
    from fintips.triagem_openai import sugerir
    case=next(c for c in gold()['casos'] if c['operacao']=='triagem.contexto')['entrada']
    captured=[]
    class Opener:
        def open(self,request,timeout):
            captured.append(request)
            text=json.dumps({'escolha':'opcao_0','valor':None,'motivo':'preencher_necessario'})
            return io.BytesIO(json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':text}]}]}).encode())
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    key='sk-'+'T'*40
    with pytest.raises(ValueError):sugerir(case['bundle'],case['rascunhos'],key,False,case['hoje'])
    assert not captured
    assert sugerir(case['bundle'],case['rascunhos'],key,True,case['hoje'])['opcao']['acao']=='perguntar'
    req=captured[0];raw=req.data.decode()
    assert req.full_url=='https://api.openai.com/v1/responses'
    assert 'CANARY' not in raw and 'asset-local' not in raw and 'mapa_local' not in raw and key not in raw
    assert 'origem_real' not in raw and 'destino_real' not in raw
    assert 'razao_bp' in raw and 'metricas' in raw and json.loads(raw)['store'] is False


def test_json_schema_publicado_aceita_as_mesmas_propostas_inclusive_opcionais_nulos():
    import jsonschema
    schema=json.loads((Path(__file__).resolve().parents[1]/'docs/contratos/triagem-v1.schema.json').read_text())
    validator=jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker())
    for c in gold()['casos']:
        if c['operacao']=='triagem.aplicar':validator.validate(c['entrada']['proposta'])
        if c['operacao']=='triagem.preparar':validator.validate(c['resultado'])


def test_api_nao_aceita_cliente_remoto_com_host_loopback_falsificado():
    with TestClient(app,base_url='http://127.0.0.1:8420',client=('198.51.100.7',45000)) as c:
        assert c.get('/api/triagem/catalogo').status_code==403
