#!/usr/bin/env python3
"""Gera os arquivos de ouro que o motor Kotlin tem que reproduzir.

A porta para Kotlin é módulo a módulo, e a única forma de saber que nada mudou
de comportamento no caminho é ter os dois motores respondendo a mesma pergunta
e comparar. Este script é o lado Python dessa conversa: ele roda o motor atual
e grava a resposta em JSON, num formato que o teste Kotlin lê.

O ouro é **gerado**, nunca escrito à mão. Ouro escrito à mão é a opinião de
quem escreveu sobre o que o motor deveria fazer; ouro gerado é o que ele faz.
A diferença aparece exatamente nos casos esquisitos, que são os que importam.

    python3 scripts/gerar-ouro.py

Regravar o ouro depois de mudar o motor Python é normal e esperado — o diff do
arquivo passa a mostrar, em números, o que a mudança causou.
"""

from __future__ import annotations

import json
import sys
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

DESTINO = RAIZ / "kotlin" / "motor" / "src" / "jvmTest" / "resources" / "ouro"

from fintips.parsers.ofx import parse_amount  # noqa: E402


def centavos(valor: Decimal) -> int:
    """A mesma conversão que o motor Kotlin faz ao guardar em Long."""
    return int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def ouro_dinheiro() -> dict:
    """Leitura de valor e arredondamento — a base de tudo que vem depois.

    Os textos incluem os formatos que aparecem em extrato brasileiro e os
    casos de fronteira do arredondamento: empate exato (1.005 e 1.015, que vão
    para lados diferentes porque meio-para-o-par olha a paridade) e o `"1.234"`
    ambíguo, que o motor lê como um real e vinte e três.
    """
    textos = [
        "-23.21", "R$ 1.234,56", "1,234.56", "1.234", "1.23", "1,234",
        "5", "5,5", "0", "", "12,30", "-1.234,56", "(45.60)",
        "1.2345", "1.235", "1.005", "1.015", "0.005", "0.015",
        "1234567.89", "-0.01", "  42,00  ",
    ]
    leituras = []
    for t in textos:
        v = parse_amount(t)
        leituras.append({"texto": t, "centavos": centavos(v), "decimal": str(v)})

    divisoes = []
    for c, d in [
        (5, 2), (7, 2), (3, 2), (1, 2), (10, 3), (11, 3), (100, 7),
        (-5, 2), (-7, 2), (-10, 3), (-1, 2), (6001, 3), (0, 5),
        (123456, 6), (99999, 7), (250, 4), (150, 4),
    ]:
        q = (Decimal(c) / Decimal(d)).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
        divisoes.append({"centavos": c, "divisor": d, "esperado": int(q)})

    return {
        "o_que_e": "leitura de valor e divisão com arredondamento meio-para-o-par",
        "gerado_por": "fintips.parsers.ofx.parse_amount + Decimal.quantize",
        "leituras": leituras,
        "divisoes": divisoes,
    }


# Sal fixo para o ouro. O sal real do usuário mora em `.fintips-salt` e nunca
# sai da máquina; aqui ele precisa ser conhecido dos dois lados, senão o hash
# da conta jamais bateria e o teste falharia por motivo errado.
SAL_DO_OURO = "ouro-do-harness"


def ouro_ofx() -> dict:
    """O canônico inteiro do fixture, transação a transação.

    Este é o ouro que pega de verdade: ele cobre leitura de tag SGML, data com
    fuso, valor em pt-BR, deduplicação por (FITID, valor, data), desambiguação
    de FITID repetido, ordenação e conciliação. Se o leitor Kotlin errar em
    qualquer um desses, o teste aponta a transação.
    """
    from fintips.parsers.ofx import parse_ofx

    stmt = parse_ofx(RAIZ / "tests" / "fixture.ofx", salt=SAL_DO_OURO)
    bate, diff = stmt.reconciles()
    return {
        "o_que_e": "canônico completo do tests/fixture.ofx",
        "gerado_por": "fintips.parsers.ofx.parse_ofx",
        "sal": SAL_DO_OURO,
        "conta": {
            "id_hash": stmt.account.id_hash,
            "instituicao": stmt.account.institution,
            "id_banco": stmt.account.bank_id,
            "tipo": stmt.account.type,
            "moeda": stmt.account.currency,
        },
        "origem": stmt.source,
        "periodo": {
            "inicio": stmt.period_start.isoformat(),
            "fim": stmt.period_end.isoformat(),
        },
        "saldo": {
            "centavos": centavos(stmt.ledger_balance),
            "em": stmt.balance_as_of.isoformat(),
        },
        "conciliacao": {"bate": bate, "diferenca_centavos": centavos(diff)},
        "transacoes": [
            {
                "id": t.id,
                "data": t.ts.strftime("%Y-%m-%d"),
                "hora": t.ts.strftime("%H:%M"),
                "mes": t.month,
                "centavos": centavos(t.amount),
                "memo": t.memo_raw,
                "conta_id": t.account_id,
            }
            for t in stmt.transactions
        ],
    }


def ouro_datas() -> dict:
    """Leitura de data OFX, isolada do fixture.

    Este ouro nasceu de uma lacuna encontrada na prática: todo `DTPOSTED` do
    fixture traz `[-3:BRT]` explícito, então o fuso padrão nunca era
    exercitado. Trocar o padrão de -3 para -2 no leitor Kotlin não quebrava
    teste nenhum — não porque o harness fosse cego, mas porque o fixture não
    fazia a pergunta.

    Harness é tão bom quanto o dado que ele compara. Estes casos fazem a
    pergunta: data sem fuso, só com dia, com fuso fracionário, em dd/mm/aaaa.
    """
    from fintips.parsers.ofx import parse_datetime

    brutos = [
        "20260601100000[-3:BRT]",
        "20260601100000",             # sem fuso: cai no padrão
        "20260601",                   # só a data
        "20260601235959[-3:BRT]",
        "20260601000000[+0:GMT]",
        "20260601120000[-3.5:XXX]",   # fuso fracionário
        "30/06/2026",
        "1/1/2027",
    ]
    casos = []
    for b in brutos:
        dt = parse_datetime(b)
        casos.append({
            "bruto": b,
            "data": dt.strftime("%Y-%m-%d"),
            "hora": dt.strftime("%H:%M"),
            "mes": dt.strftime("%Y-%m"),
            "deslocamento_segundos": int(dt.utcoffset().total_seconds()),
        })
    return {
        "o_que_e": "leitura de data OFX, incluindo os casos que o fixture não cobre",
        "gerado_por": "fintips.parsers.ofx.parse_datetime",
        "casos": casos,
    }


def ouro_privacidade() -> dict:
    """Hash de conta e pseudônimo — precisam bater dígito por dígito.

    Se divergirem, o workspace de quem já usa o motor Python vira lixo na
    primeira importação pelo Kotlin: a mesma conta apareceria como duas.
    """
    from fintips.privacy import digest, hash_account, pseudonym

    entradas = ["12345678", "0001-9", "", "Conta Corrente 42", "ÁÉÍÕÇ", "acentuação"]
    return {
        "o_que_e": "hash truncado de conta e pseudônimo de pessoa física",
        "gerado_por": "fintips.privacy.digest / hash_account / pseudonym",
        "sal": SAL_DO_OURO,
        "casos": [
            {
                "valor": v,
                "digest": digest(v, SAL_DO_OURO),
                "hash_conta": hash_account(v, SAL_DO_OURO),
                "pseudonimo": pseudonym(v, SAL_DO_OURO),
            }
            for v in entradas
        ],
    }


QUANDO_FIXO = "2026-06-15T10:30:00"


def ouro_contratos() -> dict:
    """Autoridade, ids, especificidade, prioridade e o formato de gravação.

    As duas primeiras partes protegem comportamento; a última protege
    compatibilidade de arquivo. Se `to_dict` mudar de chave ou de ordem, o YAML
    que o motor Kotlin gravar deixa de ser legível pelo Python e vice-versa —
    e quem estiver migrando perde o histórico de decisões.
    """
    from fintips.contracts import (
        AUTORIDADE, ATITUDES, Causa, Condicao, CustoFixo, Efeito, Fato,
        ItemDeTriagem, Proveniencia, Regra, novo_id,
    )

    autoridade = [
        {"origem": o, "autoridade": AUTORIDADE[o],
         "e_verdade": Proveniencia(origem=o).e_verdade}
        for o in ("heuristica", "importacao", "agente", "usuario")
    ]

    ids = [
        {"prefixo": "causa", "partes": ["categoria", "alimentacao", "gatilho"]},
        {"prefixo": "cf", "partes": ["categoria", "transporte"]},
        {"prefixo": "r", "partes": ["uber", "lazer"]},
        {"prefixo": "x", "partes": [""]},
        {"prefixo": "acento", "partes": ["alimentação", "café"]},
    ]
    for caso in ids:
        caso["id"] = novo_id(caso["prefixo"], *caso["partes"])

    condicoes = [
        {},
        {"contraparte_id": "uber"},
        {"memo_casa": "(bilhete|TOP SP)"},
        {"contraparte_contem": "ifood"},
        {"canal": "pix", "fluxo": "expense"},
        {"valor_min": 10.0, "valor_max": 100.0},
        {"dias_semana": [5, 6]},
        {"hora_min": 20, "hora_max": 23},
        {"contraparte_id": "uber", "dias_semana": [5, 6], "hora_min": 20},
    ]
    especificidade = []
    for c in condicoes:
        cond = Condicao.from_dict(c)
        especificidade.append({
            "quando": c,
            "especificidade": cond.especificidade(),
            "vazia": cond.vazia(),
            "serializado": cond.to_dict(),
        })

    regras = []
    for origem, conf, quando in [
        ("usuario", 1.0, {"contraparte_id": "uber"}),
        ("agente", 0.9, {"contraparte_id": "uber", "dias_semana": [5, 6]}),
        ("heuristica", 0.4, {"memo_casa": "uber"}),
        ("importacao", 0.6, {"canal": "pix"}),
    ]:
        r = Regra(
            id="r-teste", quando=Condicao.from_dict(quando), entao=Efeito(categoria="lazer"),
            proveniencia=Proveniencia(origem=origem, confianca=conf, porque="ouro"),
        )
        regras.append({
            "origem": origem, "confianca": conf, "quando": quando,
            "prioridade": list(r.prioridade()),
        })

    itens = []
    for tipo in ("fato_ausente", "custo_fixo_derivou", "contraparte_nova",
                 "candidato_custo_fixo", "classificacao_fraca",
                 "evento_sem_explicacao", "fato_vencido",
                 "causa_ausente", "causa_a_revisar", "causa_sem_atitude",
                 "tipo_que_nao_existe"):
        for impacto in (100.0, 33.33, 0.0, -50.0):
            it = ItemDeTriagem(id="t", tipo=tipo, titulo="", impacto_mensal=impacto,
                               porque_importa="")
            itens.append({"tipo": tipo, "impacto_mensal": impacto,
                          "prioridade": it.prioridade})

    prov = Proveniencia(origem="usuario", confianca=1.0, porque="a pessoa afirmou",
                        evidencia=["tx-1", "tx-2"], quando=QUANDO_FIXO, por_quem="claude")
    causa = Causa(
        id="causa-abc", efeito_tipo="categoria", efeito_ref="alimentacao",
        natureza="gatilho", enunciado="peço delivery depois do plantão",
        atitude="aceitar", atitude_nota="é o custo de trabalhar à noite",
        evidencia=["tx-9"], proveniencia=prov, revisar_em="2027-01-01",
        criado_em=QUANDO_FIXO,
    )
    custo = CustoFixo(
        id="cf-abc", rotulo="Transporte trabalho", base_tipo="categoria",
        base_ref="transporte-trabalho", valor_mensal=79.5,
        metodo="mediana_meses_completos", natureza="rotina", proveniencia=prov,
    )
    fato = Fato(chave="moradia.situacao", valor="com_familia", tipo="texto",
                proveniencia=prov, expira_em=None, substituiu=None)

    return {
        "o_que_e": "autoridade, ids, especificidade, prioridade e formato de gravação",
        "gerado_por": "fintips.contracts",
        "quando_fixo": QUANDO_FIXO,
        "autoridade": autoridade,
        "atitudes": list(ATITUDES),
        "ids": ids,
        "especificidade": especificidade,
        "prioridade_de_regra": regras,
        "prioridade_de_triagem": itens,
        "serializacao": {
            "proveniencia": prov.to_dict(),
            "causa": causa.to_dict(),
            "custo_fixo": custo.to_dict(),
            "fato": fato.to_dict(),
        },
    }


def ouro_texto() -> dict:
    """Normalização caractere a caractere.

    Parece o ouro mais bobo da lista e é um dos mais importantes: `norm` é a
    base de toda comparação de nome do motor. Divergir num acento faz a mesma
    padaria virar duas contrapartes, e o custo mensal dela se parte ao meio sem
    nenhum erro aparecer.
    """
    from fintips.categorize import norm
    from fintips.entities import canonical_name, slug

    textos = [
        "Padaria São João", "CAFÉ AÇÚCAR", "  espaços   demais  ",
        "Gelato Roma-LJ0046", "Gelato Roma-LJ0084", "EMV CMT*144318981",
        "MERCADO 1234", "LOJA UN 7", "Farmácia III", "PF:ab12cd",
        "", "   ", "ÁÉÍÓÚ àèìòù âêîôû ãõ ç ñ", "ÿ Ÿ œ Œ ß",
        "Restaurante do Zé - FIL 02", "posto ipiranga*9988",
        "naïve café", "1234", "---", "A*B",
    ]
    return {
        "o_que_e": "normalização, slug e nome canônico de contraparte",
        "gerado_por": "fintips.categorize.norm / entities.slug / entities.canonical_name",
        "casos": [
            {"texto": t, "norm": norm(t), "slug": slug(t), "canonico": canonical_name(t)}
            for t in textos
        ],
    }


def ouro_regras() -> dict:
    """O motor de regras, isolado da heurística.

    O estado inicial das transações é escrito aqui à mão, e não produzido pelo
    `Categorizer`. Isso é de propósito: a heurística ainda não foi portada, e
    um ouro que dependesse dela testaria duas coisas ao mesmo tempo — quando
    falhasse, ninguém saberia qual das duas quebrou.

    O estado escolhido exercita todos os campos de condição: contraparte por
    id, por conteúdo, memo, canal, fluxo, categoria atual, faixa de valor, dia
    da semana e hora.
    """
    from fintips.contracts import Condicao, Efeito, Proveniencia, Regra
    from fintips.mapping import aplicar, casa, cobertura
    from fintips.parsers.ofx import parse_ofx

    class LojaFalsa:
        def __init__(self, regras):
            self.regras = regras

        def ativas(self):
            return sorted(
                [r for r in self.regras if r.ativa],
                key=lambda r: r.prioridade(), reverse=True,
            )

    # Estado inicial explícito, por posição no extrato ordenado.
    ESTADO = [
        {"contraparte": "Gelato Roma-LJ0046", "categoria": "outros", "canal": "debit_card", "fluxo": "expense"},
        {"contraparte": "PAGSEGURO INTERNET", "categoria": "renda", "canal": "salary", "fluxo": "income"},
        {"contraparte": "Seguro Cartão", "categoria": "taxas", "canal": "fee", "fluxo": "expense"},
        {"contraparte": "iFood", "categoria": "alimentacao", "canal": "pix", "fluxo": "expense"},
        {"contraparte": "Uber", "categoria": "transporte", "canal": "debit_card", "fluxo": "expense"},
        {"contraparte": "Café Açúcar", "categoria": "alimentacao", "canal": "debit_card", "fluxo": "expense"},
        {"contraparte": "EMV CMT*144318981", "categoria": "transporte", "canal": "transit_topup", "fluxo": "expense"},
        {"contraparte": "", "categoria": "outros", "canal": "other", "fluxo": "expense"},
        {"contraparte": "PF:ab12cd", "categoria": "pessoas", "canal": "pix", "fluxo": "expense"},
    ]

    definicoes = [
        ("r-heuristica-ampla", "heuristica", 0.4, {"fluxo": "expense"},
         {"categoria": "outros-heuristica"}),
        ("r-usuario-ampla", "usuario", 1.0, {"fluxo": "expense"},
         {"categoria": "decidido-pelo-usuario"}),
        ("r-agente-especifica", "agente", 0.9,
         {"fluxo": "expense", "valor_min": 1.0, "valor_max": 50.0},
         {"categoria": "pequeno", "marcar": ["micro"]}),
        ("r-por-contraparte-id", "usuario", 1.0, {"contraparte_id": "gelato-roma"},
         {"categoria": "sobremesa"}),
        ("r-por-contraparte-contem", "usuario", 1.0, {"contraparte_contem": "cafe"},
         {"categoria": "cafeteria", "rotulo": "Cafeteria do bairro"}),
        ("r-por-memo", "usuario", 1.0, {"memo_casa": "(CDB|Renda Fixa)"},
         {"categoria": "investimento", "fluxo": "savings_out"}),
        ("r-por-canal", "agente", 0.8, {"canal": "transit_topup"},
         {"categoria": "transporte-trabalho", "marcar": ["rotina"]}),
        ("r-por-categoria-atual", "agente", 0.7, {"categoria_atual": "pessoas"},
         {"marcar": ["repasse"]}),
        ("r-fim-de-semana", "usuario", 1.0, {"dias_semana": [5, 6]},
         {"categoria": "lazer-fds"}),
        ("r-noturna", "usuario", 1.0, {"hora_min": 20, "hora_max": 23},
         {"categoria": "noturno", "rotulo": "Compra noturna"}),
    ]
    regras = [
        Regra(id=rid, quando=Condicao.from_dict(q), entao=Efeito.from_dict(e),
              proveniencia=Proveniencia(origem=o, confianca=c, porque="ouro"))
        for rid, o, c, q, e in definicoes
    ]

    stmt = parse_ofx(RAIZ / "tests" / "fixture.ofx", salt=SAL_DO_OURO)
    for tx, estado in zip(stmt.transactions, ESTADO):
        tx.counterparty = estado["contraparte"]
        tx.category = estado["categoria"]
        tx.channel = estado["canal"]
        tx.flow = estado["fluxo"]
        tx.category_source = "heuristica"
        tx.category_confidence = 0.4
        tx.tags = []

    estado_inicial = [
        {
            "id": t.id, "contraparte": t.counterparty, "categoria": t.category,
            "canal": t.channel, "fluxo": t.flow,
            "dia_semana": t.ts.weekday(), "hora": t.ts.hour,
            "centavos": centavos(t.amount), "memo": t.memo_raw,
        }
        for t in stmt.transactions
    ]

    casamentos = [
        {"transacao": t.id, "casa_com": [r.id for r in regras if casa(r, t)]}
        for t in stmt.transactions
    ]

    precedencia = [
        {"id": r.id, "prioridade": list(r.prioridade())}
        for r in LojaFalsa(regras).ativas()
    ]

    resultado = aplicar(LojaFalsa(regras), stmt)
    cob = cobertura(stmt)

    return {
        "o_que_e": "precedência, casamento, aplicação e cobertura, isolados da heurística",
        "gerado_por": "fintips.mapping.casa / aplicar / cobertura",
        "sal": SAL_DO_OURO,
        "regras": [
            {"id": rid, "origem": o, "confianca": c, "quando": q, "entao": e}
            for rid, o, c, q, e in definicoes
        ],
        "estado_inicial": estado_inicial,
        "precedencia": precedencia,
        "casamentos": casamentos,
        "resultado": resultado,
        "cobertura": cob,
        "transacoes_depois": [
            {
                "id": t.id,
                "categoria": t.category,
                "fluxo": t.flow,
                "contraparte": t.counterparty,
                "etiquetas": sorted(t.tags),
                "origem_categoria": t.category_source,
                "confianca": round(t.category_confidence, 2),
                "regra": t.rule_id,
            }
            for t in stmt.transactions
        ],
    }


def _extrato_sintetico(meses: list[dict], inicio_dia: int = 1, fim_dia: int = 28):
    """Monta um extrato com renda e despesa exatas por mês.

    Existe porque o fixture tem um mês só, e com um mês a volatilidade é
    sempre 0.0 — o cálculo mais delicado do baseline nunca seria exercitado.
    É a mesma lição de `ouro/datas.json`: harness é tão bom quanto o dado que
    ele compara.
    """
    from datetime import date, datetime, timedelta, timezone
    from decimal import Decimal
    from fintips.models import Account, Statement, Transaction

    tz = timezone(timedelta(hours=-3))
    txs = []
    for i, m in enumerate(meses):
        ano, mes = (int(x) for x in m["mes"].split("-"))
        if m.get("renda_centavos"):
            txs.append(Transaction(
                id=f"i{i}", ts=datetime(ano, mes, 5, 10, 0, tzinfo=tz),
                amount=Decimal(m["renda_centavos"]) / 100, memo_raw="renda",
                flow="income", category="renda", counterparty="Empregador",
            ))
        if m.get("despesa_centavos"):
            txs.append(Transaction(
                id=f"e{i}", ts=datetime(ano, mes, 15, 10, 0, tzinfo=tz),
                amount=-Decimal(m["despesa_centavos"]) / 100, memo_raw="gasto",
                flow="expense", category=m.get("categoria", "outros"),
                counterparty=m.get("contraparte", "Loja"),
            ))
    primeiro = min(t.ts.date() for t in txs)
    ultimo = max(t.ts.date() for t in txs)
    return Statement(
        account=Account(id_hash="acct:teste"),
        period_start=date(primeiro.year, primeiro.month, inicio_dia),
        period_end=date(ultimo.year, ultimo.month, fim_dia),
        ledger_balance=Decimal("0"),
        balance_as_of=ultimo,
        transactions=txs,
        source="sintetico",
    )


def ouro_analise() -> dict:
    """Baseline, mês a mês, recorrências e eventos atípicos.

    Aqui entram os dois cálculos que o resto do motor usa como referência e que
    dependem de estatística: volatilidade (desvio padrão sobre a média) e
    mediana. São também os únicos pontos onde o Python usa `float` de propósito
    — e onde o Kotlin precisa usar `Double` para comparar maçã com maçã.
    """
    from fintips import analysis

    series = [
        {"nome": "um_mes", "meses": [
            {"mes": "2026-01", "renda_centavos": 500000, "despesa_centavos": 300000}]},
        {"nome": "dois_meses_iguais", "meses": [
            {"mes": "2026-01", "renda_centavos": 500000, "despesa_centavos": 300000},
            {"mes": "2026-02", "renda_centavos": 500000, "despesa_centavos": 300000}]},
        {"nome": "tres_meses_variando", "meses": [
            {"mes": "2026-01", "renda_centavos": 500000, "despesa_centavos": 280000},
            {"mes": "2026-02", "renda_centavos": 500000, "despesa_centavos": 350000},
            {"mes": "2026-03", "renda_centavos": 500000, "despesa_centavos": 310000}]},
        {"nome": "mes_no_vermelho", "meses": [
            {"mes": "2026-01", "renda_centavos": 300000, "despesa_centavos": 280000},
            {"mes": "2026-02", "renda_centavos": 300000, "despesa_centavos": 450000},
            {"mes": "2026-03", "renda_centavos": 300000, "despesa_centavos": 290000}]},
        {"nome": "sem_renda", "meses": [
            {"mes": "2026-01", "renda_centavos": 0, "despesa_centavos": 100000},
            {"mes": "2026-02", "renda_centavos": 0, "despesa_centavos": 120000}]},
        {"nome": "divisao_nao_exata", "meses": [
            {"mes": "2026-01", "renda_centavos": 100001, "despesa_centavos": 33334},
            {"mes": "2026-02", "renda_centavos": 100000, "despesa_centavos": 33333},
            {"mes": "2026-03", "renda_centavos": 100000, "despesa_centavos": 33333}]},
        {"nome": "cinco_meses", "meses": [
            {"mes": "2026-01", "renda_centavos": 412345, "despesa_centavos": 298711},
            {"mes": "2026-02", "renda_centavos": 398000, "despesa_centavos": 301299},
            {"mes": "2026-03", "renda_centavos": 455010, "despesa_centavos": 277654},
            {"mes": "2026-04", "renda_centavos": 402222, "despesa_centavos": 350001},
            {"mes": "2026-05", "renda_centavos": 399999, "despesa_centavos": 289888}]},
    ]

    casos = []
    for serie in series:
        stmt = _extrato_sintetico(serie["meses"])
        base = analysis.baseline(stmt)
        meses = analysis.monthly(stmt)
        completos = analysis.full_months(stmt)
        casos.append({
            "nome": serie["nome"],
            "entrada": serie["meses"],
            "baseline": base,
            "meses": [
                {"mes": m.month, "renda_centavos": centavos(m.income),
                 "despesa_centavos": centavos(m.expense),
                 "sobra_centavos": centavos(m.net),
                 "taxa_poupanca": m.savings_rate}
                for m in meses
            ],
            "meses_completos": [m.month for m in completos],
        })

    # recorte parcial nas pontas: o que `full_months` descarta
    recortes = []
    for inicio_dia, fim_dia in [(1, 28), (5, 28), (1, 10), (5, 10)]:
        stmt = _extrato_sintetico(
            [{"mes": "2026-01", "renda_centavos": 500000, "despesa_centavos": 300000},
             {"mes": "2026-02", "renda_centavos": 500000, "despesa_centavos": 320000},
             {"mes": "2026-03", "renda_centavos": 500000, "despesa_centavos": 310000}],
            inicio_dia=inicio_dia, fim_dia=fim_dia,
        )
        recortes.append({
            "inicio_dia": inicio_dia, "fim_dia": fim_dia,
            "meses_completos": [m.month for m in analysis.full_months(stmt)],
        })

    # recorrências: mediana com contagem par e ímpar, e as três cadências
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal as D
    from fintips.models import Account, Statement, Transaction

    tz = timezone(timedelta(hours=-3))
    def tx(i, mes, dia, valor, parte, cat="outros"):
        return Transaction(
            id=f"r{i}", ts=datetime(2026, mes, dia, 12, 0, tzinfo=tz),
            amount=-D(valor) / 100, memo_raw="", flow="expense",
            category=cat, counterparty=parte,
        )

    txs = []
    n = 0
    # assinatura: mesmo valor, uma vez por mês (contagem ímpar de 3)
    for mes in (1, 2, 3):
        txs.append(tx(n := n + 1, mes, 10, 2990, "Streaming", "assinaturas"))
    # sangria: muitas compras por mês (contagem par de 12)
    for mes in (1, 2, 3):
        for dia in (3, 9, 17, 25):
            txs.append(tx(n := n + 1, mes, dia, 1500 + dia, "Padaria", "alimentacao"))
    # recorrente: valor variando, uma ou duas por mês (contagem par de 4)
    for mes, dia, valor in ((1, 5, 8000), (1, 20, 12000), (2, 7, 9500), (3, 12, 15000)):
        txs.append(tx(n := n + 1, mes, dia, valor, "Mercado", "mercado"))
    # abaixo do mínimo de meses: não deve aparecer
    for mes in (1, 2):
        txs.append(tx(n := n + 1, mes, 8, 5000, "Farmacia", "saude"))

    stmt_rec = Statement(
        account=Account(id_hash="acct:teste"),
        period_start=datetime(2026, 1, 1, tzinfo=tz).date(),
        period_end=datetime(2026, 3, 28, tzinfo=tz).date(),
        ledger_balance=D("0"), balance_as_of=datetime(2026, 3, 28, tzinfo=tz).date(),
        transactions=txs, source="sintetico",
    )
    recs = analysis.recurrences(stmt_rec)
    atipicos = analysis.outliers(stmt_rec)

    return {
        "o_que_e": "baseline, mês a mês, recorrências e eventos atípicos",
        "gerado_por": "fintips.analysis",
        "casos": casos,
        "recortes_de_ponta": recortes,
        "recorrencias": {
            "entrada": [
                {"id": t.id, "mes": t.month, "contraparte": t.counterparty,
                 "categoria": t.category, "centavos": centavos(t.amount)}
                for t in txs
            ],
            "saida": [
                {"contraparte": r.counterparty, "categoria": r.category,
                 "tipo": r.kind, "meses": r.months, "vezes": r.occurrences,
                 "valor_tipico": float(r.median_amount),
                 "custo_mensal_centavos": centavos(r.monthly_cost)}
                for r in recs
            ],
            "atipicos": [t.id for t in atipicos],
        },
    }


GERADORES = {
    "dinheiro.json": ouro_dinheiro,
    "datas.json": ouro_datas,
    "privacidade.json": ouro_privacidade,
    "ofx.json": ouro_ofx,
    "contratos.json": ouro_contratos,
    "texto.json": ouro_texto,
    "regras.json": ouro_regras,
    "analise.json": ouro_analise,
    # Os próximos entram aqui, na ordem da porta:
    #   "classificacao.json" — regras determinísticas e cobertura
    #   "analise.json"       — baseline, meses, recorrências
}


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nome, gerar in GERADORES.items():
        dados = gerar()
        caminho = DESTINO / nome
        caminho.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        n = sum(len(v) for v in dados.values() if isinstance(v, list))
        print(f"{caminho.relative_to(RAIZ)}  ({n} casos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
