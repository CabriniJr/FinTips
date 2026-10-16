from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ouro_fluxos import gerar, rows, ofx_flows
from fintips.statement_context import statement_views
from fintips.import_flows import import_group, validate_flow_summary


def test_investment_turnover_is_not_income_or_consumption_and_pix_is_unresolved():
    observed, result = statement_views([{'ofx': ofx_flows(rows())}], 'test')
    groups = {g['fluxo']: g for g in result['grupos']}
    assert groups['income']['entradas_centavos'] == 200300
    assert groups['expense']['saidas_centavos'] == 15000
    assert groups['savings_out']['saidas_centavos'] == 120000
    assert groups['savings_in']['entradas_centavos'] == 60000
    assert groups['refund']['entradas_centavos'] == 1200
    assert groups['pendente']['transacoes'] == 6
    assert sum(g['entradas_centavos'] for g in result['grupos']) == observed['entradas_centavos']
    assert sum(g['saidas_centavos'] for g in result['grupos']) == observed['saidas_centavos']
    assert sum(g['transacoes'] for g in result['grupos']) == observed['transacoes']
    assert 'CANARY' not in str(result)
    validate_flow_summary(result)


def test_overlap_does_not_duplicate_and_shared_fitid_refund_is_preserved():
    cases={c['nome']:c['esperado'] for c in gerar()['casos']}
    assert cases['separa_giro_investimentos_pix_e_estorno'] == cases['repeticao_sobreposicao']
    assert cases['mesmo_fitid_estorno']['transacoes'] == 2
    assert {g['fluxo'] for g in cases['mesmo_fitid_estorno']['grupos']} == {'expense','refund'}


def test_unknown_conflicting_signs_and_all_pix_channels_remain_pending():
    for memo, value in [('Estorno',-1),('Cartão de Débito',1),('Rendimento da conta',0),('Unknown - CDB resgate',100),('Pix recebido - EMPRESA LTDA',300),('Pix recebido - NOME CANARY',300),('Pix Automático enviado',-300)]:
        assert import_group(memo,value) == 'pendente'
    assert import_group('Renda Fixa - Aplicação CDB',-300) == 'savings_out'
    assert import_group('  renda   fixa - resgate CDB',300) == 'savings_in'


def test_closed_transport_rejects_identity_extra_fields_units_and_false_monthly_totals():
    checks=gerar()['validacoes']
    assert checks[0]['aceito']
    assert all(not c['aceito'] for c in checks[1:])
