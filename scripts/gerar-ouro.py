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
        AUTORIDADE, ATITUDES, STATUS_DECISAO, TIPOS_DECISAO, VEREDITOS,
        Alternativa, Causa, Condicao, CustoFixo, Decisao, Efeito, Fato,
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
                 "decisao_aberta", "decisao_a_revisar", "decisao_sem_desfecho",
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
    # Alternativas: a conta que decide troca. Os casos de fronteira são o que
    # o ouro existe para travar — sem horizonte não há custo por mês de uso, e
    # horizonte zero não pode virar divisão por zero em nenhum dos dois motores.
    alternativas = []
    for nome, desembolso, mensal, horizonte in (
        ("consertar", 700.0, 0.0, 8),
        ("comprar novo", 2500.0, 0.0, 36),
        ("com plano", 0.0, 90.0, 36),
        ("sem horizonte", 700.0, 0.0, None),
        ("horizonte zero", 700.0, 0.0, 0),
        ("empate de arredondamento", 100.0, 0.0, 3),
        ("centavo", 0.01, 0.0, 3),
    ):
        a = Alternativa(nome=nome, custo=desembolso, custo_mensal=mensal,
                        horizonte_meses=horizonte)
        alternativas.append({
            "nome": nome, "custo": desembolso, "custo_mensal": mensal,
            "horizonte_meses": horizonte,
            "custo_no_horizonte": a.custo_no_horizonte,
            "custo_por_mes_de_uso": a.custo_por_mes_de_uso,
        })

    decisao = Decisao(
        id="dec-abc", titulo="Celular quebrou",
        situacao="caiu na terça, tela e carregamento",
        pergunta="consertar, trocar ou aguentar?", tipo="troca",
        alternativas=[
            Alternativa(nome="consertar", custo=700.0, horizonte_meses=8,
                        consequencia="volta a funcionar, sem garantia de placa",
                        descartada_porque="assistência não cobre a placa"),
            Alternativa(nome="comprar novo", custo=2500.0, horizonte_meses=36,
                        consequencia="resolve por três anos"),
        ],
        escolhida="comprar novo", porque="o conserto não cobria o que quebrou",
        status="revisada", ligacoes=["categoria:eletronicos"],
        instantaneo={"em": "2026-06-15", "sobra_media_mes": 4963.1, "score": 55.0},
        desfecho={"veredito": "funcionou", "nota": "durou", "custo_real": 2480.0,
                  "em": QUANDO_FIXO},
        revisar_em="2027-01-01", proveniencia=prov,
        criado_em=QUANDO_FIXO, decidido_em=QUANDO_FIXO,
    )

    fato = Fato(chave="moradia.situacao", valor="com_familia", tipo="texto",
                proveniencia=prov, expira_em=None, substituiu=None)

    return {
        "o_que_e": "autoridade, ids, especificidade, prioridade e formato de gravação",
        "gerado_por": "fintips.contracts",
        "quando_fixo": QUANDO_FIXO,
        "autoridade": autoridade,
        "atitudes": list(ATITUDES),
        "status_decisao": list(STATUS_DECISAO),
        "tipos_decisao": list(TIPOS_DECISAO),
        "vereditos": list(VEREDITOS),
        "custo_de_alternativa": alternativas,
        "ids": ids,
        "especificidade": especificidade,
        "prioridade_de_regra": regras,
        "prioridade_de_triagem": itens,
        "serializacao": {
            "proveniencia": prov.to_dict(),
            "causa": causa.to_dict(),
            "decisao": decisao.to_dict(),
            "custo_fixo": custo.to_dict(),
            "fato": fato.to_dict(),
        },
    }


def ouro_projecao() -> dict:
    """Projeção de caixa: cenários, consumo da sobra pelos planos e reserva.

    O ponto delicado deste módulo não é a fórmula, é **quando se arredonda**. O
    Python multiplica a renda pelo fator do cenário em `Decimal` de precisão
    cheia e só arredonda na saída de cada mês; o patrimônio, porém, acumula o
    valor **não arredondado** ao longo dos doze meses. Uma porta que arredonde
    a renda para centavos antes do laço acerta o primeiro mês e erra o décimo
    segundo por alguns centavos — o tipo de divergência que ninguém vê revisando
    código e que aparece como saldo estranho no app.

    Por isso os casos incluem renda que não fecha em centavo depois do fator
    (3333.33 × 0.9 = 2999.997) e cenário conservador, que multiplica o variável
    por 1.15. Sem eles o ouro passa e o erro dorme.

    O segundo caso de fronteira é o mês da reserva: o Python compara o
    patrimônio **já arredondado** da linha contra o alvo **não arredondado**.
    Trocar uma coisa pela outra muda o mês em que a meta fecha, que é a
    pergunta que o usuário faz.
    """
    from datetime import date as _date

    from fintips import projection

    def plano(pid, nome, falta, prioridade="media", aporte=None, status="em_andamento"):
        d = {"id": pid, "nome": nome, "falta": falta, "prioridade": prioridade,
             "status": status}
        if aporte is not None:
            d["aporte_planejado_mes"] = aporte
        return d

    casos = []
    entradas = [
        # o caso simples: sobra folgada, nenhum plano, reserva fecha cedo
        {"nome": "sem_planos", "cenario": "base", "meses": 6,
         "baseline": {"renda_media_mes": 5000.0, "despesa_media_mes": 3000.0,
                      "reserva_alvo_meses": 6},
         "fixed_monthly": 1200.0, "saldo_conta": 2000.0, "patrimonio": 5000.0,
         "planos": []},

        # renda que não fecha em centavo depois do fator: 3333.33 * 0.9
        {"nome": "fator_nao_fecha_em_centavo", "cenario": "conservador", "meses": 12,
         "baseline": {"renda_media_mes": 3333.33, "despesa_media_mes": 2222.22,
                      "reserva_alvo_meses": 6},
         "fixed_monthly": 1111.11, "saldo_conta": 500.0, "patrimonio": 1500.0,
         "planos": []},

        # o variável multiplicado por 1.15, com plano consumindo a sobra
        {"nome": "conservador_com_planos", "cenario": "conservador", "meses": 12,
         "baseline": {"renda_media_mes": 6000.0, "despesa_media_mes": 4000.0,
                      "reserva_alvo_meses": 6},
         "fixed_monthly": 1500.0, "saldo_conta": 3000.0, "patrimonio": 10000.0,
         "planos": [plano("viagem", "Viagem", 8000.0, "alta", 500.0),
                    plano("notebook", "Notebook", 4000.0, "baixa"),
                    plano("curso", "Curso", 2000.0, "media", 300.0)]},

        # otimista: renda 1.05, variável 0.90
        {"nome": "otimista", "cenario": "otimista", "meses": 12,
         "baseline": {"renda_media_mes": 4500.0, "despesa_media_mes": 3100.0,
                      "reserva_alvo_meses": 3},
         "fixed_monthly": 900.0, "saldo_conta": 1000.0, "patrimonio": 4000.0,
         "planos": [plano("reforma", "Reforma", 15000.0, "alta")]},

        # sobra negativa todo mês: o caixa afunda e a reserva nunca fecha
        {"nome": "sobra_negativa", "cenario": "base", "meses": 12,
         "baseline": {"renda_media_mes": 2500.0, "despesa_media_mes": 3200.0,
                      "reserva_alvo_meses": 6},
         "fixed_monthly": 2000.0, "saldo_conta": 4000.0, "patrimonio": 6000.0,
         "planos": [plano("divida", "Quitar dívida", 3000.0, "alta")]},

        # plano concluído entra? não deve. E o custo fixo maior que a despesa
        # total zera o variável em vez de virar negativo.
        {"nome": "fixo_maior_que_despesa", "cenario": "base", "meses": 4,
         "baseline": {"renda_media_mes": 5000.0, "despesa_media_mes": 1000.0,
                      "reserva_alvo_meses": 6},
         "fixed_monthly": 1800.0, "saldo_conta": 1000.0, "patrimonio": 2000.0,
         "planos": [plano("feito", "Já concluído", 0.0, "alta", status="concluido"),
                    plano("aberto", "Em aberto", 1200.0, "media")]},

        # renda zero: fixo_pct_da_renda não pode dividir por zero
        {"nome": "renda_zero", "cenario": "base", "meses": 3,
         "baseline": {"renda_media_mes": 0.0, "despesa_media_mes": 800.0,
                      "reserva_alvo_meses": 6},
         "fixed_monthly": 500.0, "saldo_conta": 900.0, "patrimonio": 900.0,
         "planos": []},

        # resto de plano que NÃO fecha em centavo: o Python serializa
        # `falta_ao_fim` sem quantize, então 2666.674 sai com três casas. Uma
        # porta que guarde o resto em centavos arredonda e diverge.
        {"nome": "resto_de_plano_com_mais_de_duas_casas", "cenario": "conservador",
         "meses": 12,
         "baseline": {"renda_media_mes": 3333.33, "despesa_media_mes": 2222.22,
                      "reserva_alvo_meses": 6},
         "fixed_monthly": 1111.11, "saldo_conta": 0.0, "patrimonio": 0.0,
         "planos": [plano("longo", "Plano longo", 10000.0, "alta")]},

        # O mês da reserva compara o patrimônio **já arredondado** da linha
        # contra o alvo **não arredondado**. Aqui o alvo exato é 14333,6640 e o
        # publicado é 14333,66 — o patrimônio do primeiro mês bate exatamente no
        # publicado, e a resposta certa mesmo assim é o segundo mês. Sem este
        # caso, uma porta que compare contra o alvo arredondado passa limpa: foi
        # o que aconteceu na primeira rodada deste harness.
        {"nome": "reserva_no_fio_do_sub_centavo", "cenario": "conservador", "meses": 4,
         "baseline": {"renda_media_mes": 3333.33, "despesa_media_mes": 2222.27,
                      "reserva_alvo_meses": 6},
         "fixed_monthly": 1111.11, "saldo_conta": 0.0, "patrimonio": 13722.61,
         "planos": []},

        # cenário desconhecido cai no base, em vez de estourar
        {"nome": "cenario_desconhecido", "cenario": "inventado", "meses": 3,
         "baseline": {"renda_media_mes": 4000.0, "despesa_media_mes": 2500.0,
                      "reserva_alvo_meses": 6},
         "fixed_monthly": 1000.0, "saldo_conta": 1000.0, "patrimonio": 1000.0,
         "planos": []},

        # o plano de prioridade alta come a sobra antes, e a ordem entre dois
        # de mesma prioridade é a de entrada (ordenação estável)
        {"nome": "prioridade_ordena_e_empate_mantem_ordem", "cenario": "base", "meses": 8,
         "baseline": {"renda_media_mes": 5000.0, "despesa_media_mes": 3500.0,
                      "reserva_alvo_meses": 6},
         "fixed_monthly": 2000.0, "saldo_conta": 0.0, "patrimonio": 0.0,
         "planos": [plano("b_baixa", "Baixa", 2000.0, "baixa"),
                    plano("m1", "Média primeira", 1000.0, "media"),
                    plano("m2", "Média segunda", 1000.0, "media"),
                    plano("a_alta", "Alta", 3000.0, "alta")]},
    ]

    for e in entradas:
        saida = projection.project(
            baseline=e["baseline"], fixed_monthly=e["fixed_monthly"],
            saldo_conta=e["saldo_conta"], patrimonio=e["patrimonio"],
            planos=e["planos"], meses=e["meses"], cenario=e["cenario"],
            inicio=_date(2026, 6, 15),
        )
        casos.append({"nome": e["nome"], "entrada": e, "saida": saida})

    # a virada de ano dentro do laço: _add_months tem que somar mês, não dia
    virada = projection.project(
        baseline={"renda_media_mes": 4000.0, "despesa_media_mes": 2000.0,
                  "reserva_alvo_meses": 6},
        fixed_monthly=800.0, saldo_conta=0.0, patrimonio=0.0, planos=[],
        meses=14, cenario="base", inicio=_date(2026, 11, 30),
    )

    return {
        "o_que_e": "projeção de caixa: cenários, consumo da sobra pelos planos e mês da reserva",
        "gerado_por": "fintips.projection",
        "inicio_fixo": "2026-06-15",
        "cenarios": projection.CENARIOS,
        "casos": casos,
        "virada_de_ano": {
            "inicio": "2026-11-30",
            "meses": [l["mes"] for l in virada["linhas"]],
        },
    }


def ouro_planos() -> dict:
    """Planos: viabilidade, ritmo necessário e o que o extrato já gastou neles.

    Três armadilhas de porte moram aqui, e as três são silenciosas.

    **`if meses` trata zero como ausente.** Prazo vencido devolve `0` em
    `months_until`, e `0` é falso em Python: o aporte necessário vira o valor
    inteiro que falta, não uma divisão por zero. Uma porta que teste
    `meses != null` divide por zero ou devolve infinito.

    **Os limiares são `<=`, não `<`.** Um plano cujo aporte necessário bate
    exatamente em 60% da capacidade é *confortável*; exatamente na capacidade é
    *apertado*. Os dois casos de borda estão no ouro de propósito.

    **O ritmo arredonda para cima.** Faltando R$ 1.000,01 com aporte de
    R$ 500,00 são três meses, não dois — quem trunca promete uma data que não
    acontece.
    """
    from datetime import date as _date

    from fintips import plans as plans_mod

    hoje = _date(2026, 6, 15)

    # um extrato com gastos que os planos vão querer reconhecer como seus
    stmt = _extrato_sintetico([
        {"mes": "2026-04", "renda_centavos": 500000, "despesa_centavos": 120000,
         "categoria": "viagem", "contraparte": "Companhia Aérea"},
        {"mes": "2026-05", "renda_centavos": 500000, "despesa_centavos": 80000,
         "categoria": "educacao", "contraparte": "Curso de Inglês"},
        {"mes": "2026-06", "renda_centavos": 500000, "despesa_centavos": 60000,
         "categoria": "outros", "contraparte": "Padaria"},
    ])

    entradas = [
        # prazo folgado: necessário bem abaixo de 60% da capacidade
        {"nome": "confortavel", "sobra": 3000.0,
         "plano": {"id": "viagem", "nome": "Viagem", "tipo": "viagem",
                   "custo_alvo": 6000.0, "data_alvo": "2027-06-01",
                   "aporte_mensal": 500.0, "guardado": 0.0,
                   "categorias": ["viagem"]}},

        # borda exata do limiar de 60%: necessário == 0.6 * capacidade
        {"nome": "borda_exata_dos_60_pct", "sobra": 1000.0,
         "plano": {"id": "borda", "nome": "Borda", "custo_alvo": 3600.0,
                   "data_alvo": "2026-12-01", "guardado": 0.0}},

        # borda exata da capacidade: necessário == capacidade
        {"nome": "borda_exata_da_capacidade", "sobra": 600.0,
         "plano": {"id": "limite", "nome": "No limite", "custo_alvo": 3600.0,
                   "data_alvo": "2026-12-01", "guardado": 0.0}},

        # um centavo além da capacidade: vira inviável
        {"nome": "um_centavo_alem_da_capacidade", "sobra": 600.0,
         "plano": {"id": "estourou", "nome": "Estourou", "custo_alvo": 3600.06,
                   "data_alvo": "2026-12-01", "guardado": 0.0}},

        # prazo vencido: months_until devolve 0, e 0 é falso em Python
        {"nome": "prazo_vencido_nao_divide_por_zero", "sobra": 2000.0,
         "plano": {"id": "atrasado", "nome": "Atrasado", "custo_alvo": 1500.0,
                   "data_alvo": "2026-01-01", "guardado": 200.0}},

        # sem prazo nenhum
        {"nome": "sem_prazo", "sobra": 2000.0,
         "plano": {"id": "algum_dia", "nome": "Algum dia", "custo_alvo": 9000.0,
                   "guardado": 1000.0}},

        # já concluído: guardado passou do alvo
        {"nome": "concluido", "sobra": 1000.0,
         "plano": {"id": "feito", "nome": "Feito", "custo_alvo": 2000.0,
                   "data_alvo": "2026-12-01", "guardado": 2500.0}},

        # sobra negativa: a capacidade vira zero, não um número negativo
        {"nome": "sobra_negativa_zera_a_capacidade", "sobra": -800.0,
         "plano": {"id": "sonho", "nome": "Sonho", "custo_alvo": 5000.0,
                   "data_alvo": "2027-01-01", "guardado": 0.0}},

        # custo alvo zero: progresso não pode dividir por zero
        {"nome": "custo_alvo_zero", "sobra": 1000.0,
         "plano": {"id": "vazio", "nome": "Vazio", "custo_alvo": 0.0,
                   "data_alvo": "2026-12-01", "guardado": 0.0}},

        # ritmo que não divide exato: arredonda para cima
        {"nome": "ritmo_arredonda_para_cima", "sobra": 2000.0,
         "plano": {"id": "ritmo", "nome": "Ritmo", "custo_alvo": 1000.01,
                   "aporte_mensal": 500.0, "guardado": 0.0}},

        # divisão que não fecha em centavo: 1000 / 3
        {"nome": "aporte_necessario_nao_fecha_em_centavo", "sobra": 2000.0,
         "plano": {"id": "terco", "nome": "Um terço", "custo_alvo": 1000.0,
                   "data_alvo": "2026-09-01", "guardado": 0.0}},

        # casamento por contraparte, com acento e caixa diferentes
        {"nome": "casa_por_contraparte_com_acento", "sobra": 2000.0,
         "plano": {"id": "ingles", "nome": "Inglês", "custo_alvo": 4000.0,
                   "data_alvo": "2027-01-01", "guardado": 0.0,
                   "merchants": ["CURSO DE INGLES"]}},

        # casamento por categoria
        {"nome": "casa_por_categoria", "sobra": 2000.0,
         "plano": {"id": "viagem2", "nome": "Viagem 2", "custo_alvo": 8000.0,
                   "data_alvo": "2027-01-01", "guardado": 0.0,
                   "categorias": ["viagem"]}},

        # nem contraparte nem categoria: não conta gasto nenhum
        {"nome": "sem_casamento_nao_conta_gasto", "sobra": 2000.0,
         "plano": {"id": "solto", "nome": "Solto", "custo_alvo": 3000.0,
                   "data_alvo": "2027-01-01", "guardado": 0.0}},
    ]

    casos = []
    for e in entradas:
        plano = plans_mod.Plan.from_dict(e["plano"])
        base = {"sobra_media_mes": e["sobra"]}
        casos.append({
            "nome": e["nome"],
            "entrada": {"plano": e["plano"], "sobra_media_mes": e["sobra"]},
            "saida": plans_mod.evaluate(plano, stmt, base, today=hoje),
        })

    meses_ate = [
        {"alvo": alvo, "meses": plans_mod.months_until(
            _date.fromisoformat(alvo) if alvo else None, hoje)}
        for alvo in ("2026-06-01", "2026-06-30", "2026-07-01", "2027-06-15",
                     "2025-01-01", "2026-12-31", None)
    ]

    return {
        "o_que_e": "planos: viabilidade, ritmo necessário e gasto já feito no plano",
        "gerado_por": "fintips.plans",
        "hoje_fixo": hoje.isoformat(),
        "extrato": [
            {"id": t.id, "dia": t.day.isoformat(), "valor_centavos": centavos(t.amount),
             "fluxo": t.flow, "categoria": t.category, "contraparte": t.counterparty}
            for t in stmt.transactions
        ],
        "meses_ate_o_alvo": meses_ate,
        "casos": casos,
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


def ouro_score() -> dict:
    """As cinco dimensões, os limites e a alavanca de maior ganho.

    Os casos foram escolhidos pelas fronteiras, não pela média: despesa zero
    (divisão por zero), sem plano cadastrado (meia nota por convenção),
    poupança acima do teto, reserva acima do alvo, e quatro meses no vermelho
    — que zera a estabilidade por multiplicação, um caso que ninguém escreve
    sem querer.
    """
    from fintips import score as score_mod

    def invisivel(taxas_mes=0.0, micro_mes=0.0):
        return {
            "taxas_e_seguros": {"por_mes": taxas_mes},
            "micro_gastos": {"por_mes": micro_mes},
        }

    def base(renda, despesa, taxa, vol=0.0, vermelhos=0):
        return {
            "renda_media_mes": renda, "despesa_media_mes": despesa,
            "taxa_poupanca_media": taxa, "volatilidade_despesa": vol,
            "meses_no_vermelho": vermelhos,
        }

    casos = [
        {
            "nome": "saudavel",
            "base": base(5000, 3000, 0.40, 0.05), "invisivel": invisivel(50, 80),
            "planos": [{"aporte_necessario_mes": 500, "capacidade_mensal_real": 600}],
            "patrimonio": 18000.0,
        },
        {
            "nome": "zerado",
            "base": base(0, 0, 0.0), "invisivel": invisivel(),
            "planos": [], "patrimonio": 0.0,
        },
        {
            "nome": "despesa_zero",
            "base": base(4000, 0, 1.0), "invisivel": invisivel(10, 10),
            "planos": [], "patrimonio": 5000.0,
        },
        {
            "nome": "poupanca_acima_do_teto",
            "base": base(5000, 1000, 0.80, 0.02), "invisivel": invisivel(),
            "planos": [], "patrimonio": 60000.0,
        },
        {
            "nome": "quatro_meses_no_vermelho",
            "base": base(3000, 3400, -0.13, 0.30, 4), "invisivel": invisivel(200, 300),
            "planos": [], "patrimonio": 500.0,
        },
        {
            "nome": "volatilidade_estourada",
            "base": base(4000, 3000, 0.25, 0.9), "invisivel": invisivel(20, 20),
            "planos": [], "patrimonio": 9000.0,
        },
        {
            "nome": "invisivel_acima_do_teto",
            "base": base(4000, 2000, 0.50, 0.1), "invisivel": invisivel(200, 200),
            "planos": [], "patrimonio": 12000.0,
        },
        {
            "nome": "planos_variados",
            "base": base(6000, 4000, 0.33, 0.12), "invisivel": invisivel(60, 40),
            "planos": [
                {"status": "concluido"},
                {"aporte_necessario_mes": 0, "capacidade_mensal_real": 500},
                {"aporte_necessario_mes": 1000, "capacidade_mensal_real": 250},
                {"aporte_necessario_mes": 300, "capacidade_mensal_real": 900},
            ],
            "patrimonio": 15000.0,
        },
        {
            "nome": "reserva_muito_acima",
            "base": base(5000, 2000, 0.60, 0.03), "invisivel": invisivel(10, 10),
            "planos": [], "patrimonio": 200000.0,
        },
    ]

    saida = []
    for c in casos:
        r = score_mod.compute(
            c["base"], c["invisivel"], c["planos"], patrimonio_liquido=c["patrimonio"],
        )
        saida.append({**c, "resultado": r})

    return {
        "o_que_e": "score em cinco dimensões, com pesos e limites explícitos",
        "gerado_por": "fintips.score.compute",
        "pesos": dict(score_mod.WEIGHTS),
        "casos": saida,
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
    "score.json": ouro_score,
    "projecao.json": ouro_projecao,
    "planos.json": ouro_planos,
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
