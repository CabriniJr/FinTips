"""Casos sintéticos de contexto observado, sem dados pessoais."""
from fintips.statement_context import statement_context, validate_statement_context


def ofx(rows, bank='001', account='ACCT_CANARY'):
    entries=''.join(f'<STMTTRN><DTPOSTED>202610{day:02d}120000[-3:BRT]<TRNAMT>{value}<FITID>{id}<MEMO>DESTINO_CANARY</STMTTRN>' for id,day,value in rows)
    return f'<OFX><BANKID>{bank}<ACCTID>{account}<CURDEF>BRL<BANKTRANLIST>{entries}</BANKTRANLIST><LEDGERBAL><BALAMT>750.00<DTASOF>20261031</LEDGERBAL></OFX>'


def gerar():
    base=ofx([('a',1,'1000.00'),('b',2,'-250.00')])
    repeated=ofx([('x',3,'-200.00'),('x',3,'200.00'),('x#2',3,'3.00')])
    cases=[
        ('vazio',[]),
        ('sem_saldo_inicial',[{'ofx':base}]),
        ('conferido',[{'ofx':base,'saldo_inicial':'0'}]),
        ('divergente',[{'ofx':base,'saldo_inicial':'1'}]),
        ('sem_saldo_declarado',[{'ofx':base.replace('<BALAMT>750.00',''),'saldo_inicial':'0'}]),
        ('conciliacao_canonica_centavos',[{'ofx':ofx([('s',1,'1.005')]).replace('<BALAMT>750.00','<BALAMT>1.00'),'saldo_inicial':'0'}]),
        ('mesmo_arquivo',[{'ofx':base},{'ofx':base}]),
        ('sobreposicao_estorno_id_literal',[{'ofx':repeated},{'ofx':ofx([('x',3,'200.00'),('x#2',3,'3.00')])}]),
        ('contas_bancos_distintos',[{'ofx':base},{'ofx':ofx([('a',1,'1000.00'),('b',2,'-250.00')],bank='002')}]),
    ]
    from copy import deepcopy
    valid=statement_context([], 'test')
    contexts=[valid,dict(valid,memo='CANARY'),dict(valid,entradas_centavos='1'),dict(valid,inicio='invalid'),dict(valid,conciliacao={'conferidos':-1,'divergentes':0,'nao_conferidos':0})]
    checks=[]
    for c in contexts:
        try: validate_statement_context(c); accepted=True
        except (ValueError,TypeError,KeyError): accepted=False
        checks.append({'entrada':c,'aceito':accepted})
    return {'validacoes':checks,'casos':[{'nome':name,'arquivos':files,'sal':'sal-sintetico-local','esperado':statement_context(files,'sal-sintetico-local')} for name,files in cases]}
