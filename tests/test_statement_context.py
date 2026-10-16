from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ouro_extratos import ofx, gerar
from fintips.statement_context import statement_context
import pytest


def test_overlapping_refund_and_literal_id_preserve_three_transactions():
    case=next(c for c in gerar()['casos'] if c['nome']=='sobreposicao_estorno_id_literal')
    result=case['esperado']
    assert result['transacoes']==3
    assert result['entradas_centavos']==20300
    assert result['saidas_centavos']==20000
    assert 'CANARY' not in str(result)
    assert result['saldo_disponivel_centavos'] is None


def test_opening_optional_and_discrepancy_is_recorded_not_hidden():
    cases={c['nome']:c['esperado'] for c in gerar()['casos']}
    assert cases['sem_saldo_inicial']['conciliacao']['nao_conferidos']==1
    assert cases['conferido']['conciliacao']['conferidos']==1
    assert cases['divergente']['conciliacao']['divergentes']==1
    assert cases['sem_saldo_declarado']['conciliacao']['nao_conferidos']==1
    assert cases['contas_bancos_distintos']['transacoes']==4


@pytest.mark.parametrize('raw',["not an ofx",ofx([('a',1,'2')]).replace('<CURDEF>BRL','<CURDEF>USD'),ofx([('a',1,'2')]).replace('<ACCTID>ACCT_CANARY',''),ofx([('a',1,'999999999999999999999999999999')]),ofx([('a',1,'2')]).replace('<FITID>a',''),ofx([('a',1,'2')]).replace('</STMTTRN>','')])
def test_bad_source_never_becomes_empty_financial_context(raw):
    with pytest.raises((ValueError,OverflowError)):
        statement_context([{'ofx':raw}], 'test')
