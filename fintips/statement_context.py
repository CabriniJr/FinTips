"""Contexto observacional de OFX importados. Não classifica renda ou despesa."""
from collections import defaultdict
from decimal import Decimal
import re
from .parsers.ofx import parse_ofx_text, parse_amount

MAX_SAFE = 9007199254740991


def safe(n):
    if type(n) is not int or abs(n) > MAX_SAFE:
        raise ValueError("valor fora do limite")
    return n


def cents(value):
    if not value.is_finite() or abs(value) > Decimal(MAX_SAFE) / 100:
        raise ValueError("valor fora do limite")
    return safe(int((value * 100).quantize(Decimal('1'))))


def statement_context(files: list[dict], salt: str) -> dict:
    if len(files) > 20:
        raise ValueError('limite de arquivos')
    seen, accounts, months, starts, ends = set(), set(), defaultdict(list), [], []
    checked = divergent = unchecked = 0
    for entry in files:
        raw = entry['ofx']
        if len(raw.encode('utf-8')) > 1024 * 1024 or len(re.findall(r'<BANKTRANLIST>', raw, re.I)) != 1 or not re.search(r'<ACCTID>\s*[^<\s]', raw, re.I):
            raise ValueError('use um OFX de uma conta')
        blocks=re.findall(r'<STMTTRN>(.*?)</STMTTRN>',raw,re.I|re.S)
        if len(re.findall(r'<STMTTRN>',raw,re.I))!=len(blocks) or not re.search(r'</BANKTRANLIST>',raw,re.I) or any(not re.search(r'<FITID>\s*[^<\s]',b,re.I) for b in blocks):
            raise ValueError('arquivo incompleto ou sem identificador')
        has_balance=bool(re.search(r'<BALAMT>\s*[^<\s]',raw,re.I))
        originals = {}
        stmt = parse_ofx_text(raw, salt=salt, original_ids=originals)
        if stmt.account.currency != 'BRL' or len(stmt.transactions) > 10000:
            raise ValueError('moeda ou limite inválido')
        account = (stmt.account.id_hash, stmt.account.bank_id, stmt.account.institution)
        accounts.add(account)
        starts.append(stmt.period_start.isoformat()); ends.append(stmt.period_end.isoformat())
        cents(stmt.ledger_balance); safe(sum(cents(t.amount) for t in stmt.transactions))
        opening = entry.get('saldo_inicial')
        if opening is None or not has_balance:
            unchecked += 1
        else:
            if not re.fullmatch(r'-?\d{1,12}([.,]\d{1,2})?', opening):
                raise ValueError('saldo inicial inválido')
            same, _ = stmt.reconciles(parse_amount(opening))
            checked += int(same); divergent += int(not same)
        for tx in stmt.transactions:
            value = cents(tx.amount)
            key = (account, originals[tx.id], tx.ts, value)
            if key not in seen:
                seen.add(key); months[tx.month].append(value)
        if len(seen) > 50000:
            raise ValueError('limite de transações')
    rows = []
    for month, values in sorted(months.items()):
        incoming = safe(sum(v for v in values if v > 0)); outgoing = safe(-sum(v for v in values if v < 0))
        rows.append(dict(mes=month, transacoes=len(values), entradas_centavos=incoming, saidas_centavos=outgoing, liquido_centavos=safe(incoming-outgoing)))
    return dict(schema_version=1, estado='importado' if files else 'sem_extrato', arquivos=len(files), contas=len(accounts), transacoes=len(seen),
        inicio=min(starts) if starts else None, fim=max(ends) if ends else None,
        entradas_centavos=safe(sum(r['entradas_centavos'] for r in rows)), saidas_centavos=safe(sum(r['saidas_centavos'] for r in rows)),
        liquido_centavos=safe(sum(r['liquido_centavos'] for r in rows)), meses=rows,
        conciliacao=dict(conferidos=checked, divergentes=divergent, nao_conferidos=unchecked), classificacao='pendente', saldo_disponivel_centavos=None)


def validate_statement_context(c: dict) -> dict:
    """Fronteira fechada de transporte, espelhada no Kotlin."""
    from datetime import date
    keys={'schema_version','estado','arquivos','contas','transacoes','inicio','fim','entradas_centavos','saidas_centavos','liquido_centavos','meses','conciliacao','classificacao','saldo_disponivel_centavos'}
    if set(c)!=keys or type(c['schema_version']) is not int or c['schema_version']!=1 or c['estado'] not in ('importado','sem_extrato') or c['classificacao']!='pendente' or c['saldo_disponivel_centavos'] is not None:
        raise ValueError('contrato financeiro inválido')
    def amount(k, data):
        n=safe(data[k])
        if n<0 and k!='liquido_centavos':
            raise ValueError('quantidade inválida')
    for k in ('arquivos','contas','transacoes','entradas_centavos','saidas_centavos','liquido_centavos'):
        amount(k,c)
    for k in ('inicio','fim'):
        if c[k] is not None:
            if type(c[k]) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',c[k]):
                raise ValueError('data inválida')
            date.fromisoformat(c[k])
    if type(c['meses']) is not list or len(c['meses'])>1200:
        raise ValueError('meses inválidos')
    for row in c['meses']:
        if set(row)!={'mes','transacoes','entradas_centavos','saidas_centavos','liquido_centavos'} or type(row['mes']) is not str or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',row['mes']):
            raise ValueError('mês inválido')
        for k in ('transacoes','entradas_centavos','saidas_centavos','liquido_centavos'):
            amount(k,row)
    conc=c['conciliacao']
    if set(conc)!={'conferidos','divergentes','nao_conferidos'} or any(type(n) is not int or not 0<=n<=20 for n in conc.values()):
        raise ValueError('conciliação inválida')
    return c
