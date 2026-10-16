"""Casos inventados: nenhum valor, data ou memo vem de extrato pessoal."""
from copy import deepcopy
from fintips.statement_context import statement_views
from fintips.import_flows import validate_flow_summary


def ofx_flows(rows, account='FLOW_ACCOUNT_CANARY'):
    entries = ''.join(f'<STMTTRN><DTPOSTED>{day}120000[-3:BRT]<TRNAMT>{value}<FITID>{id}<MEMO>{memo}</STMTTRN>' for id, day, value, memo in rows)
    return f'<OFX><ORG>BANK_CANARY<BANKID>999<ACCTID>{account}<CURDEF>BRL<BANKTRANLIST>{entries}</BANKTRANLIST><LEDGERBAL><BALAMT>0<DTASOF>20261031</LEDGERBAL></OFX>'


def rows():
    return [
        ('salary', '20260901', '2000', 'Salário/Remuneração - ORIGIN_CANARY'),
        ('yield', '20260902', '3', 'Rendimento da conta'),
        ('expense', '20260903', '-150', 'Cartão de Débito - DESTINATION_CANARY'),
        ('deposit', '20260904', '-1200', 'Renda Fixa - Aplicação CDB'),
        ('withdraw', '20261001', '600', 'Renda Fixa - Resgate CDB'),
        ('pix-in', '20261002', '300', 'Pix recebido - SOURCE_CANARY'),
        ('pix-out', '20261003', '-80', 'QR Code Pix enviado - DEST_CANARY'),
        ('refund', '20261004', '12', 'Estorno - DEST_CANARY'),
        ('unknown-in', '20261005', '10', 'UNKNOWN_CANARY'),
        ('unknown-out', '20261005', '-20', 'UNKNOWN_CANARY'),
        ('wrong-sign', '20261006', '20', 'Renda Fixa - Aplicação CDB'),
        ('zero', '20261006', '0', 'Salário/Remuneração'),
    ]


def gerar():
    base = ofx_flows(rows())
    cases = [
        ('vazio', []),
        ('separa_giro_investimentos_pix_e_estorno', [{'ofx': base}]),
        ('repeticao_sobreposicao', [{'ofx': base}, {'ofx': ofx_flows(rows()[3:8])}]),
        ('canal_normalizado', [{'ofx': ofx_flows([('a','20261001','-71.45','  RENDA   FIXA - APLICACAO CDB'),('b','20261002','70','renda fixa - resgate cdb')])}]),
        ('sinais_incompativeis', [{'ofx': ofx_flows([('a','20261001','-40','Rendimento da conta'),('b','20261002','40','Cartão de Débito'),('c','20261003','-12','Estorno')])}]),
        ('mesmo_fitid_estorno', [{'ofx': ofx_flows([('a','20261001','-44','Cartão de Débito'),('a','20261001','44','Estorno')])}]),
    ]
    valid = statement_views([{'ofx': base}], 'test')[1]
    inputs = [valid]
    for key, value in [('memo','PII_CANARY'), ('origem','usuario'), ('transacoes',True), ('revisao_regras','NAME_CANARY')]:
        d = deepcopy(valid);d[key] = value;inputs.append(d)
    for key,value in [('fluxo','arbitrario'),('entradas_centavos','200300'),('saidas_centavos',1),('transacoes',0),('memo','PII_CANARY')]:
        d = deepcopy(valid);d['grupos'][0][key] = value;inputs.append(d)
    d=deepcopy(valid);d['grupos'].append(deepcopy(d['grupos'][0]));inputs.append(d)
    d=deepcopy(valid);d['meses'].append(deepcopy(d['meses'][0]));inputs.append(d)
    d=deepcopy(valid);d['meses'][0]['grupos'][0]['entradas_centavos']+=1;inputs.append(d)
    checks=[]
    for d in inputs:
        try: validate_flow_summary(d);accepted=True
        except (ValueError,TypeError,KeyError): accepted=False
        checks.append(dict(entrada=d, aceito=accepted))
    return dict(validacoes=checks, casos=[dict(nome=n, arquivos=fs, sal='synthetic-flow-salt', esperado=statement_views(fs,'synthetic-flow-salt')[1]) for n,fs in cases])
