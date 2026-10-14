"""MCP do FinTips: primitivas, não conclusões.

O app não sabe o que é "transporte de rotina" na vida de alguém — e não deveria
fingir que sabe. Ele guarda, aplica e calcula. Estas ferramentas são o que o
agente usa para investigar, perguntar ao usuário e **gravar a decisão** de um
jeito reproduzível: toda escrita carrega origem, confiança, motivo e evidência.

Roda na máquina do usuário:

    python -m fintips.mcp_server --root "C:/Users/<voce>/Documents/FinTips"
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import causes as causes_mod
from . import decisions
from . import dossier, levers, life, mapping, plans as plans_mod
from . import objetivos as objetivos_mod
from . import projection as proj_mod
from . import purchases, report
from .analysis import baseline
from .categorize import norm
from .contracts import ATITUDES, NATUREZAS_SUGERIDAS, Proveniencia
from .entities import canonical_name, slug
from .workspace import Workspace

mcp = FastMCP("fintips")
_ROOT = Path(os.environ.get("FINTIPS_ROOT", Path.home() / "Documents" / "FinTips"))


def _ws() -> Workspace:
    return Workspace.open(_ROOT)


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _prov(origem: str, confianca: float, porque: str,
          evidencia: list[str] | None = None) -> Proveniencia:
    if origem not in ("agente", "usuario"):
        origem = "agente"
    if not porque:
        raise ValueError("toda decisão precisa de `porque` — é o que a torna auditável")
    return Proveniencia(
        origem=origem, confianca=float(confianca), porque=porque,
        evidencia=evidencia or [], por_quem="claude",
    )


# ==========================================================================
# RECURSOS — o que o cliente carrega antes da conversa começar
#
# A diferença para uma ferramenta importa: recurso o cliente pode ler sozinho,
# sem gastar um turno. O agente chega sabendo quem é a pessoa e por que o
# dinheiro dela sai, em vez de descobrir isso na terceira pergunta.
# ==========================================================================

@mcp.resource(
    "fintips://briefing",
    name="Briefing do usuário",
    description=(
        "Perfil assinado, o que ainda é palpite, números que enquadram, causas "
        "ativas com a atitude tomada, planos e o que está em aberto. Resumo com "
        "ponteiro: cada bloco diz qual ferramenta devolve o detalhe."
    ),
    mime_type="application/json",
)
def recurso_briefing() -> str:
    ws = _ws()
    try:
        ctx = report.analyze(ws)
    except FileNotFoundError:
        return _json({
            "sem_dados": True,
            "o_que_fazer": "nenhum extrato importado ainda — use `ingerir_extrato`",
        })
    d = dossier.montar(ctx)
    return _json({"cabecalho": d["cabecalho"], "briefing": d["briefing"],
                  "correlacoes": d["correlacoes"]})


@mcp.resource(
    "fintips://spec",
    name="Contratos do FinTips",
    description=(
        "A regra de proveniência, os contratos e os vocabulários. Leia antes de "
        "gravar qualquer coisa: é o que separa o que o app garante do que só "
        "você pode concluir."
    ),
    mime_type="application/json",
)
def recurso_spec() -> str:
    return _json(_SPEC)


# A spec é montada a partir do próprio código: vocabulário que mudar em
# contracts.py muda aqui junto, e o agente nunca recebe uma lista desatualizada.
_SPEC = {
    "principio": (
        "O app guarda, aplica e calcula. O agente descobre, pergunta e decide. "
        "O usuário assina. Nada é verdade sem proveniência."
    ),
    "proveniencia": {
        "nota": (
            "existem DUAS escadas, porque são duas perguntas diferentes. A do "
            "dinheiro responde 'quem classificou esta transação'; a da vida "
            "responde 'como sabemos que isso foi feito'"
        ),
        "ordem_de_autoridade": ["heuristica", "importacao", "agente", "usuario"],
        "vale_como_verdade": ["agente", "usuario"],
        "nunca_vale": {
            "heuristica": "lista embutida no pacote; ranqueia o que olhar, não conclui",
            "importacao": "derivado dos dados (cadência, arquétipo casado, alavanca)",
        },
        "regra": "origem menor nunca sobrescreve origem maior, por mais confiante que esteja",
    },
    "proveniencia_da_vida": {
        "ordem_de_autoridade": list(life.ORIGENS_DO_REGISTRO),
        "vale_como_cumprido": ["agente", "sensor", "usuario"],
        "nunca_vale": {
            "presumido": "o app supôs pela rotina — supor que ela treinou não é ela ter treinado",
        },
        "por_que_sensor_acima_de_agente": (
            "'você treinou hoje?' é pergunta factual. Se o aparelho mediu, a "
            "medida vale mais que a sua interpretação da conversa"
        ),
        "por_que_usuario_acima_de_sensor": (
            "o aparelho erra de um jeito que a pessoa sabe explicar: celular em "
            "casa, tela em outro aparelho, treino na rua"
        ),
    },
    "contratos": {
        "Categoria": "uma categoria existe porque alguém a criou",
        "Regra": "quando -> então, determinística e simulável antes de gravar",
        "CustoFixo": "compromisso DEFINIDO; a detecção só produz candidato",
        "Fato": "um pedaço de contexto, com evidência e prazo opcional",
        "Causa": "por que o dinheiro sai + a atitude tomada; nunca derivável",
        "TracoDePerfil": "um eixo do perfil, assinado por quem tem autoridade",
        "ItemDeTriagem": "algo em aberto, com o custo mensal de não decidir",
        "Missao": "o que a pessoa combinou consigo; nasce dela, nunca do app",
        "RegistroDeMissao": "um cumprimento + como se soube dele",
        "RegraDeclarada": (
            "regra que ela assina para si (ex.: esperar N dias acima de X). É a "
            "ÚNICA coisa do lado da vida que mexe em veredito de compra, e por "
            "isso exige `porque`: a conversa cita a regra dela, não um conselho seu"
        ),
    },
    "vocabularios": {
        "causa.efeito_tipo": list(causes_mod.EFEITOS),
        "causa.natureza": {
            "sugeridas": list(NATUREZAS_SUGERIDAS),
            "lista_aberta": True,
            "nota": "invente a palavra que a vida da pessoa pedir; o app valida a forma",
        },
        "causa.atitude": {
            "valores": list(ATITUDES),
            "lista_fechada": True,
            "nota": "o dossiê e as alavancas calculam em cima disso",
        },
        "perfil.eixos": ["fase", "renda", "custo", "consumo", "constancia"],
        "vida.atributos": {
            "valores": {k: v for k, v in life.ATRIBUTOS.items()},
            "nota": (
                "as seis frentes. Dinheiro (OURO) é uma delas, não o centro — o "
                "motor financeiro inteiro vive dentro dessa barra"
            ),
        },
        "vida.cadencias": list(life.CADENCIAS),
        "objetivo.tipos_de_etapa": list(objetivos_mod.TIPOS_DE_ETAPA),
        "objetivo.nasce_rascunho": (
            "você decompõe o que ela contou; ela assina. Até a assinatura o "
            "objetivo não entra na agenda, nos gauges nem no score — agenda que "
            "se enche sozinha de item não combinado é app desinstalado"
        ),
        "objetivo.lacos_sao_declarados": (
            "`plano_id` e `missoes` só existem porque você escreveu. O motor "
            "nunca descobre que um plano financia um objetivo. Laço apontando "
            "para o vazio volta em `orfaos`, não some"
        ),
        "objetivo.score": {
            "dimensoes": dict(objetivos_mod.PESOS),
            "peso_aplicado": (
                "dimensão sem base não vira zero — ela sai de fora da conta e o "
                "peso aplicado encolhe. Score 100 sobre peso 15 quer dizer 'nada "
                "falhou ainda', não 'está indo bem'"
            ),
            "adiar_custa": (
                "`prazo_original` não se apaga e `adiamento` é dimensão própria. "
                "Sem isso bastaria empurrar a data para estar sempre em dia"
            ),
        },
        "vida.sem_xp_e_sem_nivel": (
            "de propósito. Nível só sobe e não consegue dizer 'esta semana foi "
            "pior que a passada', que é a única informação que muda comportamento"
        ),
    },
    "toda_escrita_exige": ["porque"],
    "como_expandir": {
        "perfil": "perfil",
        "causas": "listar_causas",
        "numeros": "analise_completa",
        "projecao": "projecao",
        "pendencias": "triagem",
        "alavancas": "alavancas",
        "uma_contraparte": "investigar",
        "seis_frentes": "frentes",
        "aporte_contra_planos": "aporte_vs_planos",
        "objetivos_e_prazos": "objetivos",
    },
    "erros_que_o_motor_recusa": [
        "assinar perfil ou gravar causa com origem heuristica/importacao",
        "gravar qualquer decisão sem `porque`",
        "causa sem enunciado (rótulo não é causa)",
        "atitude fora do vocabulário fechado",
        "registrar missão com origem fora da escada da vida",
        "registrar missão que não está no catálogo da pessoa",
        "regra declarada sem `porque` (ela mexe em veredito; precisa de origem)",
    ],
}


# ==========================================================================
# LER
# ==========================================================================

@mcp.tool()
def analise_completa(topo: int = 8) -> str:
    """Panorama: baseline, score, meses, estrutura de custo, gasto invisível,
    conciliação, patrimônio e contexto do usuário — inteiros.

    Os blocos que têm ferramenta própria vêm resumidos, cada um com `quantas` e
    `detalhe_em` apontando para ela: perfil, taxonomia, contrapartes, triagem,
    projeção, causas, decisões e regras. Isso é corte de tamanho, não de
    informação — se a resposta depender do que não veio, chame a ferramenta que
    o bloco indica em vez de supor.

    O relatório completo continua sendo gravado em `relatorios/analise.yaml` a
    cada chamada, e o painel lê aquele, não este.

    `topo` ajusta quantos itens vêm nas listas resumidas (contrapartes maiores,
    primeiros da triagem)."""
    ws = _ws()
    data = report.analyze(ws)
    report.save_report(ws, data)
    return _json(report.para_agente(data, topo=topo))


@mcp.tool()
def triagem(limite: int = 10, tipo: str = "") -> str:
    """A fila de decisões em aberto, ordenada pelo impacto em reais de não decidir.

    Cada item traz `porque_importa` (qual cálculo muda) e `evidencia`. Use
    `investigar` antes de perguntar, e resolva com as ferramentas de escrita —
    nunca conclua sozinho o que depende da vida do usuário."""
    ws = _ws()
    ctx = report.analyze(ws)
    itens = ctx["triagem"]["itens"]
    if tipo:
        itens = [i for i in itens if i["tipo"] == tipo]
    return _json({"resumo": ctx["triagem"]["resumo"], "itens": itens[:limite]})


@mcp.tool()
def investigar(contraparte_id: str = "", categoria: str = "", texto: str = "",
               transacao_id: str = "") -> str:
    """Todas as evidências sobre uma contraparte, categoria, texto ou transação.

    Devolve padrão temporal (dia da semana, hora), distribuição de valores,
    presença mensal, canais e exemplos. É com isto que se descobre, por exemplo,
    que um mesmo aplicativo de transporte tem um uso de dia útil às 8h e outro de
    sábado à noite — dois comportamentos, não um."""
    ws = _ws()
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    report.enrich(ws, stmt, st)

    alvo = []
    for t in stmt.transactions:
        if contraparte_id and slug(canonical_name(t.counterparty or "")) != contraparte_id:
            continue
        if categoria and t.category != categoria:
            continue
        if texto and norm(texto) not in norm(t.counterparty or "") \
                and norm(texto) not in norm(t.memo_raw):
            continue
        if transacao_id and t.id != transacao_id:
            continue
        alvo.append(t)
    if not alvo:
        return _json({"encontrado": 0, "aviso": "nenhuma transação casou com o filtro"})

    valores = [abs(float(t.amount)) for t in alvo]
    por_mes: dict[str, float] = {}
    for t in alvo:
        por_mes[t.month] = round(por_mes.get(t.month, 0) + abs(float(t.amount)), 2)
    dias = Counter(["seg", "ter", "qua", "qui", "sex", "sáb", "dom"][t.ts.weekday()] for t in alvo)
    horas = Counter(f"{t.ts.hour:02d}h" for t in alvo)
    meses_no_extrato = len({t.month for t in stmt.transactions}) or 1

    return _json({
        "encontrado": len(alvo),
        "total": round(sum(valores), 2),
        "por_mes": por_mes,
        "meses_presentes": f"{len(por_mes)}/{meses_no_extrato}",
        "valor": {
            "minimo": round(min(valores), 2),
            "mediana": round(float(statistics.median(valores)), 2),
            "maximo": round(max(valores), 2),
            "desvio_relativo": round(
                statistics.pstdev(valores) / statistics.fmean(valores), 2
            ) if len(valores) > 1 and statistics.fmean(valores) else 0.0,
        },
        "dias_da_semana": dict(dias.most_common()),
        "horas": dict(horas.most_common(6)),
        "canais": dict(Counter(t.channel for t in alvo)),
        "fluxos": dict(Counter(t.flow for t in alvo)),
        "categorias_atuais": dict(Counter(t.category for t in alvo)),
        "origem_da_classificacao": dict(Counter(t.category_source for t in alvo)),
        "variacoes_de_nome": sorted({t.counterparty for t in alvo})[:8],
        "exemplos": [t.to_yaml_dict() for t in sorted(alvo, key=lambda x: x.ts, reverse=True)[:8]],
    })


@mcp.tool()
def listar_taxonomia() -> str:
    """As categorias que existem, quem as criou e quanto passou por cada uma.
    Origem 'heuristica' = sugestão do pacote, ainda não é conhecimento sobre
    este usuário."""
    ws = _ws()
    ctx = report.analyze(ws)
    return _json({
        "categorias": ctx["taxonomia"],
        "nao_revisadas": [c["id"] for c in ctx["categorias_nao_revisadas"]],
        "cobertura_da_classificacao": ctx["cobertura_da_classificacao"],
    })


@mcp.tool()
def listar_regras() -> str:
    """As regras de classificação vigentes, em ordem de precedência."""
    ws = _ws()
    st = report.stores(ws)
    return _json({"regras": st["regras"].to_dicts()})


@mcp.tool()
def contexto_do_usuario() -> str:
    """O que se sabe sobre o usuário: núcleo (moradia, cartão, renda, reserva),
    fatos específicos criados pelo agente, cobertura e lacunas com impacto."""
    ws = _ws()
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    loja = st["contexto"]
    return _json({
        "resumo": loja.resumo(),
        "fatos": loja.todos(),
        "lacunas": loja.lacunas(baseline(stmt)),
    })


@mcp.tool()
def custos_fixos() -> str:
    """Compromissos DEFINIDOS e candidatos detectados. Só os definidos entram na
    projeção e saem do relatório de gasto invisível."""
    ws = _ws()
    ctx = report.analyze(ws)
    return _json({
        "definidos": ctx["custos_fixos"],
        "candidatos": ctx["candidatos_custo_fixo"],
        "estrutura": ctx["estrutura_de_custo"],
    })


@mcp.tool()
def buscar_transacoes(texto: str = "", categoria: str = "", mes: str = "",
                      fluxo: str = "", valor_minimo: float = 0, limite: int = 50) -> str:
    """Busca transações no extrato atual. `mes` no formato AAAA-MM."""
    ws = _ws()
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    report.enrich(ws, stmt, st)
    alvo = norm(texto)
    out = []
    for t in stmt.transactions:
        if alvo and alvo not in norm(t.counterparty):
            continue
        if categoria and t.category != categoria:
            continue
        if mes and t.month != mes:
            continue
        if fluxo and t.flow != fluxo:
            continue
        if abs(float(t.amount)) < valor_minimo:
            continue
        out.append(t.to_yaml_dict())
    out.sort(key=lambda d: abs(d["valor"]), reverse=True)
    return _json({"total": len(out), "transacoes": out[:limite]})


@mcp.tool()
def projecao(cenario: str = "base", meses: int = 12) -> str:
    """Projeção de caixa mês a mês. Cenários: base, conservador, otimista."""
    ws = _ws()
    ctx = report.analyze(ws)
    return _json(proj_mod.project(
        baseline=ctx["baseline"],
        fixed_monthly=ctx["estrutura_de_custo"]["comprometido_mes"],
        saldo_conta=ctx["saldo_conta"],
        patrimonio=ctx["patrimonio"].get("total", 0),
        planos=ctx["planos"], meses=meses, cenario=cenario,
    ))


# ==========================================================================
# SIMULAR — antes de gravar
# ==========================================================================

@mcp.tool()
def briefing() -> str:
    """Comece por aqui. O retrato enxuto de quem é a pessoa e do que está aberto.

    Mesmo conteúdo do recurso `fintips://briefing`, para clientes que não
    carregam recursos sozinhos. É resumo com ponteiro: cada bloco traz
    `expandir_com`, o nome da ferramenta que devolve aquilo em detalhe. Puxe o
    detalhe quando precisar dele, não por precaução — o contexto inteiro custa
    caro e a maior parte não vai ser usada nesta conversa.

    Leia o `cabecalho` antes do resto: as três coberturas (classificação,
    perfil, causal) dizem quanto disso alguém decidiu e quanto ainda é o app
    achando coisa."""
    ws = _ws()
    d = dossier.montar(report.analyze(ws))
    return _json({"cabecalho": d["cabecalho"], "briefing": d["briefing"],
                  "correlacoes": d["correlacoes"], "orcamento": d["orcamento"]})


@mcp.tool()
def listar_causas(alvo: str = "", incluir_vencidas: bool = True) -> str:
    """As causas gravadas: por que o dinheiro sai e o que se decidiu sobre isso.

    `alvo` filtra por quem a causa explica, no formato 'categoria:mercado' ou
    'contraparte:ifood'. Sem filtro, vem tudo, mais a cobertura causal — o
    percentual da despesa que alguém já explicou, e as categorias onde falta.

    Uma causa vencida (passou do `revisar_em`) continua listada, marcada. Isso
    é de propósito: causa de comportamento envelhece, e saber que a explicação
    é velha vale mais do que não ter explicação."""
    ws = _ws()
    st = report.stores(ws)
    loja = st["causas"]
    itens = loja.to_dicts()
    if alvo:
        itens = [c for c in itens if c["alvo"] == alvo]
    if not incluir_vencidas:
        itens = [c for c in itens if not c["vencida"]]
    stmt = report.load_statement(ws, st)
    report.enrich(ws, stmt, st)
    return _json({
        "causas": itens,
        "cobertura": loja.cobertura(stmt),
        "vocabulario": {"naturezas_sugeridas": list(NATUREZAS_SUGERIDAS),
                        "atitudes": list(ATITUDES)},
    })


@mcp.tool()
def perfil() -> str:
    """O perfil financeiro: o que os números sugerem e o que foi assinado.

    Cinco eixos independentes (fase, renda, custo, consumo, constância). Em
    cada um vem o arquétipo que o catálogo casou contra o extrato, com a
    aderência e a evidência que a sustenta — e o traço assinado, se já houver.

    Leia isto assim: a **sugestão é palpite**, derivada dos números, e não
    vale como verdade. Ela existe para você ter por onde começar a conversa,
    não para ser repetida ao usuário como diagnóstico. Confirme conversando e
    só então chame `assinar_perfil`. `cobertura` diz quanto do perfil já é
    decisão — começa em 0%, e é assim que deve começar mesmo."""
    return _json(report.analyze(_ws())["perfil"])


@mcp.tool()
def alavancas() -> str:
    """O que muda cada número, e quanto — com o motor rodado de novo.

    Cada alavanca traz um valor (reais por mês, em geral) e o efeito
    recalculado: score depois da mudança, mês em que a reserva fecha, mês em
    que cada plano conclui. Nenhuma delas é conselho, de propósito.

    O conselho é seu: você sabe o que aquele gasto significa para a pessoa, se
    o corte é viável, o que já foi tentado. Use os números como régua e
    escreva a leitura — mas grave o que concluir com `gravar_fato` ou
    `assinar_perfil`, para a próxima conversa não recomeçar do zero."""
    return _json(levers.calcular(report.analyze(_ws())))


@mcp.tool()
def simular_regra(quando: dict, entao: dict) -> str:
    """Mostra o que uma regra faria, sem gravar nada.

    Use SEMPRE antes de `definir_regra`: se a regra pega mais ou menos
    transações do que você esperava, a hipótese está errada e a pergunta ao
    usuário deve ser outra."""
    from .contracts import Condicao, Efeito, Regra

    ws = _ws()
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    regra = Regra(id="simulacao", quando=Condicao.from_dict(quando),
                  entao=Efeito.from_dict(entao))
    if regra.quando.vazia():
        return _json({"erro": "condição vazia casaria com tudo"})

    casadas = [t for t in stmt.transactions if mapping.casa(regra, t)]
    if not casadas:
        return _json({"casariam": 0, "aviso": "nenhuma transação casa — a hipótese não se sustenta"})
    total = sum(abs(float(t.amount)) for t in casadas)
    meses = len({t.month for t in stmt.transactions}) or 1
    nova_cat = (entao or {}).get("categoria")
    return _json({
        "casariam": len(casadas),
        "de_um_total_de": len(stmt.transactions),
        "valor_total": round(total, 2),
        "valor_por_mes": round(total / meses, 2),
        "mudariam_de_categoria": len([t for t in casadas if nova_cat and t.category != nova_cat]),
        "categorias_afetadas": dict(Counter(t.category for t in casadas)),
        "exemplos": [t.to_yaml_dict()
                     for t in sorted(casadas, key=lambda x: abs(x.amount), reverse=True)[:6]],
    })


# ==========================================================================
# ESCREVER — toda escrita exige `porque`
# ==========================================================================

@mcp.tool()
def criar_categoria(id: str, nome: str, porque: str, descricao: str = "",
                    essencial: bool | None = None, pai: str = "",
                    origem: str = "agente", confianca: float = 0.85) -> str:
    """Cria uma categoria na taxonomia do usuário.

    A taxonomia não é fixa: se a vida da pessoa separa "transporte para o
    trabalho" de "transporte de lazer", crie as duas. Use `origem` 'usuario'
    quando a pessoa afirmou, 'agente' quando for sua conclusão."""
    ws = _ws()
    st = report.stores(ws)
    try:
        cat = st["taxonomia"].criar(
            id, nome, descricao=descricao, essencial=essencial, pai=pai or None,
            proveniencia=_prov(origem, confianca, porque),
        )
    except ValueError as e:
        return _json({"erro": str(e)})
    return _json(cat.to_dict())


@mcp.tool()
def definir_regra(quando: dict, entao: dict, porque: str,
                  origem: str = "agente", confianca: float = 0.85,
                  evidencia: list[str] | None = None, nota: str = "") -> str:
    """Grava uma regra de classificação permanente e reprocessa o extrato.

    `quando`: contraparte_id, contraparte_contem, memo_casa (regex), canal,
    fluxo, categoria_atual, valor_min, valor_max, dias_semana (0=segunda),
    hora_min, hora_max.
    `entao`: categoria, fluxo, marcar (tags), rotulo.

    Prefira condições que descrevam o comportamento real ("uber acima de 30
    reais, sábado e domingo") a condições que apenas renomeiem ("uber é lazer").
    Simule antes."""
    ws = _ws()
    st = report.stores(ws)
    cat = (entao or {}).get("categoria")
    if cat and not st["taxonomia"].existe(cat):
        return _json({"erro": f"categoria '{cat}' não existe — crie antes com criar_categoria",
                      "existentes": st["taxonomia"].ids()})
    try:
        regra = st["regras"].criar(
            quando, entao,
            proveniencia=_prov(origem, confianca, porque, evidencia), nota=nota,
        )
    except ValueError as e:
        return _json({"erro": str(e)})

    stmt = report.load_statement(ws, st)
    return _json({"regra": regra.to_dict(),
                  "efeito": mapping.aplicar(st["regras"], stmt),
                  "cobertura": mapping.cobertura(stmt)})


@mcp.tool()
def remover_regra(regra_id: str) -> str:
    """Apaga uma regra. Use quando o usuário discordar de uma classificação."""
    ws = _ws()
    st = report.stores(ws)
    return _json({"removida": st["regras"].remover(regra_id)})


@mcp.tool()
def definir_custo_fixo(rotulo: str, base_tipo: str, base_ref: str, porque: str,
                       valor_mensal: float | None = None,
                       metodo: str = "mediana_meses_completos",
                       natureza: str = "rotina",
                       origem: str = "agente", confianca: float = 0.85,
                       evidencia: list[str] | None = None) -> str:
    """Define um compromisso mensal — o que a projeção repete como certo.

    `base_tipo`: categoria | contraparte | regra | valor.
    `natureza`: você nomeia (contratual, rotina, sazonal, reembolsado...). Não há
    lista fixa: o que é compromisso depende da vida da pessoa.
    Sem `valor_mensal`, o app calcula pelo extrato usando `metodo`.

    Só chame depois que o usuário confirmar: isto muda a projeção e tira o valor
    do relatório de gasto invisível."""
    ws = _ws()
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    try:
        item = st["compromissos"].definir(
            rotulo, base_tipo, base_ref,
            valor_mensal=valor_mensal, metodo=metodo, natureza=natureza,
            proveniencia=_prov(origem, confianca, porque, evidencia),
            stmt=stmt, meses_completos=baseline(stmt).get("meses_considerados"),
        )
    except ValueError as e:
        return _json({"erro": str(e)})
    return _json({"custo_fixo": item.to_dict(),
                  "total_comprometido_mes": st["compromissos"].total_mensal(),
                  "por_natureza": st["compromissos"].por_natureza()})


@mcp.tool()
def remover_custo_fixo(custo_id: str) -> str:
    """Desfaz um compromisso — a projeção volta a tratar aquilo como variável."""
    ws = _ws()
    st = report.stores(ws)
    return _json({"removido": st["compromissos"].remover(custo_id)})


@mcp.tool()
def gravar_fato(chave: str, valor: Any, porque: str, tipo: str = "",
                origem: str = "agente", confianca: float = 0.9,
                evidencia: list[str] | None = None, expira_em: str = "") -> str:
    """Grava um fato sobre o usuário no contexto.

    Chaves do núcleo (moradia.situacao, cartao_credito.usa, renda.natureza,
    patrimonio.contas_externas, reserva.alvo_meses, objetivos.horizonte,
    dependentes.quantos) alimentam cálculos diretamente. Qualquer outra chave é
    livre — crie as que a vida da pessoa exigir, como
    'transporte.reembolsado_pela_empresa' ou 'almoco.pago_pelo_trabalho'.

    `origem` 'usuario' quando a pessoa afirmou, 'agente' quando você concluiu.
    `expira_em` (AAAA-MM-DD) para o que tem prazo: vence e volta para a triagem."""
    ws = _ws()
    st = report.stores(ws)
    try:
        fato = st["contexto"].gravar(
            chave, valor, tipo=tipo,
            proveniencia=_prov(origem, confianca, porque, evidencia),
            expira_em=expira_em or None,
        )
    except ValueError as e:
        return _json({"erro": str(e)})
    return _json({"fato": fato.to_dict(), "cobertura": st["contexto"].cobertura()})


@mcp.tool()
def esquecer_fato(chave: str) -> str:
    """Apaga um fato do contexto — quando o usuário corrige ou a vida mudou."""
    ws = _ws()
    st = report.stores(ws)
    return _json({"esquecido": st["contexto"].esquecer(chave)})


@mcp.tool()
def gravar_causa(efeito_tipo: str, efeito_ref: str, natureza: str, enunciado: str,
                 porque: str, atitude: str = "nenhuma", atitude_nota: str = "",
                 origem: str = "agente", confianca: float = 0.9,
                 evidencia: list[str] | None = None, revisar_em: str = "") -> str:
    """Grava por que um gasto existe. Só depois de a pessoa ter contado.

    Esta é a ferramenta mais fácil de usar errado do FinTips inteiro, porque o
    padrão nos dados *parece* explicar o gasto. Ele não explica. Duas pessoas
    pedem delivery toda terça: uma faz plantão até 22h, a outra odeia cozinhar
    e já tentou parar três vezes. O extrato é idêntico; a conversa seguinte é
    oposta. Se você não perguntou, você não sabe — e a ferramenta recusa
    origem derivada justamente para isso.

    `efeito_tipo`: categoria | contraparte | padrao | mes | plano | compromisso.
    `enunciado`: a frase, o mais perto possível das palavras da pessoa. Não
    traduza "não tenho energia para cozinhar depois do plantão" para
    "conveniência" — a primeira versão é o que vai fazer sentido para ela
    daqui a seis meses.
    `natureza`: use uma das sugeridas se servir, invente se não servir.
    `atitude`: deixe 'nenhuma' se ainda não decidiram nada — a triagem vai
    cobrar a decisão depois, que é melhor do que fingir que houve uma.
    `revisar_em` (AAAA-MM-DD): para causa que provavelmente muda (um projeto
    que acaba, um período de obra, um estágio)."""
    st = report.stores(_ws())
    try:
        causa = st["causas"].gravar(
            efeito_tipo=efeito_tipo, efeito_ref=efeito_ref, natureza=natureza,
            enunciado=enunciado, atitude=atitude, atitude_nota=atitude_nota,
            evidencia=evidencia or [], revisar_em=revisar_em or None,
            proveniencia=_prov(origem, confianca, porque, evidencia),
        )
    except ValueError as e:
        return _json({"erro": str(e)})
    return _json({"causa": causa.to_dict()})


@mcp.tool()
def decidir_causa(causa_id: str, atitude: str, nota: str = "") -> str:
    """Registra o que se decidiu sobre uma causa já entendida.

    Separado de `gravar_causa` porque entender e decidir acontecem em momentos
    diferentes — às vezes com semanas entre um e outro, que é o tempo normal
    de alguém mudar de ideia sobre o próprio comportamento.

    `atitude`: nenhuma | aceitar | reduzir | eliminar | substituir |
    automatizar | observar. Note que **aceitar é uma decisão legítima**: tira o
    gasto da lista de culpa e o coloca na de escolhas. Nem toda causa precisa
    virar corte, e empurrar corte onde a pessoa já disse que não vai cortar é
    o jeito mais rápido de ela parar de usar isso aqui."""
    st = report.stores(_ws())
    try:
        causa = st["causas"].decidir(causa_id, atitude, nota)
    except ValueError as e:
        return _json({"erro": str(e)})
    return _json({"causa": causa.to_dict()})


@mcp.tool()
def esquecer_causa(causa_id: str) -> str:
    """Apaga uma causa — quando o usuário corrige, ou quando a vida mudou."""
    return _json({"esquecido": report.stores(_ws())["causas"].esquecer(causa_id)})


@mcp.tool()
def assinar_perfil(eixo: str, arquetipo: str, porque: str, nome: str = "",
                   descricao: str = "", origem: str = "agente",
                   confianca: float = 0.9, evidencia: list[str] | None = None) -> str:
    """Assina o traço de um eixo do perfil. Só depois de conversar.

    `eixo`: fase | renda | custo | consumo | constancia.
    `arquetipo`: um id do catálogo daquele eixo, ou 'personalizado' com `nome`
    e `descricao` seus — use isso quando nenhum recorte pronto descreve a
    pessoa, o que é comum e não é problema.

    `origem` 'usuario' quando a pessoa afirmou, 'agente' quando você concluiu.
    O casamento por número NÃO pode assinar: se o único fundamento for "os
    indicadores casaram", ainda não há perfil — há palpite, e a ferramenta
    recusa. Pergunte antes."""
    st = report.stores(_ws())
    try:
        traco = st["perfil"].assinar(
            eixo, arquetipo, nome=nome, descricao=descricao,
            proveniencia=_prov(origem, confianca, porque, evidencia),
        )
    except ValueError as e:
        return _json({"erro": str(e)})
    return _json({"traco": traco.to_dict()})


@mcp.tool()
def esquecer_traco(eixo: str) -> str:
    """Apaga o traço de um eixo — quando o usuário corrige ou a vida mudou."""
    return _json({"esquecido": report.stores(_ws())["perfil"].esquecer(eixo)})


@mcp.tool()
def resolver_item(item_id: str, o_que_foi_feito: str, adiar: bool = False) -> str:
    """Marca um item da triagem como resolvido (ou adiado).

    Chame DEPOIS de gravar a decisão (regra, custo fixo, fato). Resolver sem ter
    gravado nada só esconde a pergunta — ela volta na próxima importação."""
    ws = _ws()
    st = report.stores(ws)
    loja = st["triagem"]
    reg = (loja.adiar(item_id, o_que_foi_feito) if adiar
           else loja.resolver(item_id, {"o_que_foi_feito": o_que_foi_feito}))
    ctx = report.analyze(ws, st=st)
    return _json({"item": item_id, "registro": reg, "fila_agora": ctx["triagem"]["resumo"]})


# ==========================================================================
# PLANOS, COMPRAS, DADOS
# ==========================================================================

@mcp.tool()
def listar_planos() -> str:
    """Planos cadastrados com viabilidade recalculada contra o extrato atual."""
    ws = _ws()
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    return _json(plans_mod.evaluate_all(
        plans_mod.load_plans(ws.planos_path), stmt, baseline(stmt)))


@mcp.tool()
def salvar_plano(id: str, nome: str, custo_alvo: float, data_alvo: str = "",
                 tipo: str = "outro", prioridade: str = "media",
                 aporte_mensal: float = 0, guardado: float = 0,
                 merchants: list[str] | None = None, categorias: list[str] | None = None,
                 notas: str = "") -> str:
    """Cria ou atualiza um plano. `merchants` e `categorias` ligam o plano a
    gastos reais do extrato, para medir execução e não só intenção."""
    from datetime import date

    ws = _ws()
    st = report.stores(ws)
    items = [p for p in plans_mod.load_plans(ws.planos_path) if p.id != id]
    novo = plans_mod.Plan(
        id=id, nome=nome, tipo=tipo, custo_alvo=Decimal(str(custo_alvo)),
        data_alvo=date.fromisoformat(data_alvo) if data_alvo else None,
        prioridade=prioridade, aporte_mensal=Decimal(str(aporte_mensal)),
        guardado=Decimal(str(guardado)), merchants=merchants or [],
        categorias=categorias or [], notas=notas,
    )
    items.append(novo)
    plans_mod.save_plans(ws.planos_path, items)
    stmt = report.load_statement(ws, st)
    return _json(plans_mod.evaluate(novo, stmt, baseline(stmt)))


@mcp.tool()
def avaliar_compra(item: str, preco: float, categoria: str = "compras",
                   urgencia: str = "media", parcelas_possiveis: int = 1,
                   juros_parcelamento: float = 0.0, substitui: str = "",
                   palavras_chave: list[str] | None = None) -> str:
    """Avalia uma intenção de compra: impacto no caixa, custo em meses de sobra,
    conflito com planos, sinais de arrependimento tirados do histórico e as
    estratégias possíveis com o trade-off de cada uma.

    Quando existe catálogo de missões, a resposta traz `contexto_de_vida`: qual
    sequência esta compra põe em risco, o preço traduzido em meses de aporte e
    como estão as seis frentes hoje. Leia o bloco antes de escrever: ele diz o
    que trazer para a conversa.

    Uma coisa só de lá mexe no veredito — `regra_declarada_aplicada`, a regra
    de espera que a própria pessoa escreveu. Quando ela aparecer, **cite a
    regra dela, com o `porque` que vem junto**. Não é conselho seu: é decisão
    que ela já tomou e pediu para o app aplicar."""
    ws = _ws()
    st = report.stores(ws)
    ctx = report.analyze(ws, st=st)
    stmt = report.load_statement(ws, st)
    report.enrich(ws, stmt, st)
    intent = purchases.PurchaseIntent(
        item=item, preco=Decimal(str(preco)), categoria=categoria, urgencia=urgencia,
        parcelas_possiveis=parcelas_possiveis, juros_parcelamento=juros_parcelamento,
        substitui=substitui, tags=palavras_chave or [],
    )
    return _json(purchases.evaluate(
        intent, stmt, ctx["baseline"], ctx["planos"],
        saldo_conta=ctx["saldo_conta"],
        patrimonio=ctx["patrimonio"].get("total", 0),
        reserva_alvo_meses=float(ctx["baseline"].get("reserva_alvo_meses", 6)),
        perfil=ctx.get("perfil"),
        causas=(ctx.get("causas") or {}).get("itens"),
        precedentes=st["decisoes"].semelhantes(
            f"{intent.item} {intent.categoria}", tipo="compra",
            ligacoes=[f"categoria:{intent.categoria}"],
        ),
        aprendizados=(ctx.get("decisoes") or {}).get("aprendizados"),
        vida=report.load_vida(ws),
    ))


@mcp.tool()
def frentes(cadencia: str = "diaria") -> str:
    """As seis frentes de hoje: FOR, AGI, VIT, INT, FOC e OURO.

    Devolve sempre as seis, mesmo vazias — frente sem missão mostra o que a
    pessoa não está treinando, e esconder a barra esconderia a lacuna.

    Não existe XP e não existe nível, de propósito: nível é número que só sobe
    e não consegue dizer "esta semana foi pior que a passada". O que existe é
    a janela atual, a sequência e o recorde.

    `cobertura_de_evidencia` diz quanto do que o app afirma veio de medida de
    aparelho e quanto é memória. Use isso antes de afirmar qualquer coisa sobre
    hábito: memória de tempo de tela distorce a favor de quem lembra."""
    ws = _ws()
    vida = report.load_vida(ws)
    if vida.vazia:
        return _json({
            "sem_missoes_cadastradas": True,
            "como_cadastrar": (
                f"escreva {ws.missoes_path} a partir do molde em "
                "fintips/rules/exemplo-missoes.yaml. Missão nasce da pessoa: o "
                "app não sabe quantas vezes alguém deve treinar"
            ),
        })
    hoje = date.today()
    return _json({
        "hoje": hoje.isoformat(),
        "frentes": life.forca_dos_atributos(vida.missoes, vida.registros, hoje, cadencia),
        "missoes_do_dia": [
            life.estado_diario(m, vida.registros, hoje)
            for m in vida.missoes if m.ativa and m.cadencia == "diaria"
        ],
        "cobertura_de_evidencia": life.cobertura_de_evidencia(vida.missoes, vida.registros),
    })


@mcp.tool()
def registrar_missao(missao_id: str, origem: str = "agente", medida: str = "",
                     nota: str = "", dia: str = "") -> str:
    """Grava que uma missão foi cumprida, dizendo **como se soube**.

    `origem` é a escada de proveniência do lado da vida, e ela não é a mesma
    do lado financeiro:

      presumido  o app supôs pela rotina — NUNCA conta como cumprido
      agente     você concluiu a partir da conversa
      sensor     o aparelho mediu (tempo de tela, passos, horário)
      usuario    a pessoa marcou; vence tudo

    Use `agente` só quando ela te disse, nesta conversa, que fez. "Deve ter
    treinado, é terça" é `presumido`, e `presumido` existe para não contar: o
    app supor que ela treinou não é ela ter treinado.

    Quando houver número, mande em `medida` ("0 min de tela", "12 km"). É o
    que separa medida de memória na cobertura de evidência."""
    ws = _ws()
    vida = report.load_vida(ws)
    if vida.missoes and missao_id not in {m.id for m in vida.missoes}:
        return _json({
            "erro": f"missão '{missao_id}' não está no catálogo",
            "catalogo": [m.id for m in vida.missoes],
        })
    try:
        registro = life.RegistroDeMissao.from_dict({
            "missao_id": missao_id,
            "dia": dia or date.today().isoformat(),
            "origem": origem,
            "medida": medida,
            "nota": nota,
        })
    except ValueError as e:
        return _json({"erro": str(e)})
    life.registrar(ws.registros_path, registro)
    missao = next(m for m in vida.missoes if m.id == missao_id)
    return _json({
        "gravado": registro.to_dict(),
        "conta_como_cumprido": registro.conta_como_cumprido,
        "estado": life.estado_diario(missao, report.load_vida(ws).registros, date.today()),
    })


@mcp.tool()
def aporte_vs_planos() -> str:
    """O aporte que ela assinou contra o que os planos exigem por mês.

    Compromisso declarado de um lado, necessidade dos planos do outro. Quando
    não fecham, o motor mostra a diferença e para aí: subir o aporte, esticar
    o prazo ou cortar plano é escolha dela, não cálculo."""
    ws = _ws()
    ctx = report.analyze(ws)
    return _json(life.contexto_de_planos(report.load_vida(ws), ctx["planos"]))


@mcp.tool()
def objetivos(incluir_rascunhos: bool = True) -> str:
    """Os objetivos da pessoa: etapas, prazos, score e o que está atrasado.

    **Leia isto antes de aconselhar qualquer coisa.** É o perfil dela em
    forma de compromisso: o que ela está perseguindo, com que prazo, quanto
    disso custa e o que já escorregou. Uma recomendação de compra feita sem
    saber que a prova dela é em três semanas não é um conselho, é um palpite.

    Duas leituras que mudam o que você pode dizer:

    `rascunhos_aguardando_assinatura` são objetivos que **você** propôs e ela
    ainda não assinou. Não são compromisso dela — cobrar por eles é cobrar por
    algo que ela não disse. Pergunte se ainda valem.

    `peso_aplicado` em cada score diz sobre quanto o número foi calculado.
    Score 100 sobre peso 15 significa "nada falhou ainda", não "está indo
    bem". Dizer a segunda coisa é inventar notícia boa."""
    ws = _ws()
    lista, checks = report.load_objetivos(ws)
    if not lista:
        return _json({
            "sem_objetivos_cadastrados": True,
            "como_criar": (
                "use `criar_objetivo`. Você decompõe o que ela contou em etapas "
                "com prazo; ela assina depois. O molde está em "
                "fintips/rules/exemplo-objetivos.yaml"
            ),
        })
    ctx = report.analyze(ws)
    vida = report.load_vida(ws)
    perfil = objetivos_mod.contexto_de_perfil(
        lista, checks, vida, date.today(), planos=ctx["planos"]
    )
    if not incluir_rascunhos:
        perfil.pop("rascunhos_aguardando_assinatura", None)
    return _json(perfil)


@mcp.tool()
def criar_objetivo(id: str, titulo: str, porque: str, etapas: list[dict],
                   data_alvo: str = "", comecou_em: str = "",
                   plano_id: str = "", missoes: list[str] | None = None) -> str:
    """Transforma o que ela contou em objetos ligados. **Nasce rascunho.**

    Este é o seu trabalho pesado neste app: ela descreve em texto corrido o
    que quer, e você devolve a estrutura. Uma certificação não é uma linha de
    R$ 2.000 em dezembro — são cursos com prazo cada um, uma prova marcada, e
    o estudo diário que sustenta tudo.

    Cada item de `etapas` aceita:

      id            obrigatório, estável — é por ele que o check volta
      titulo        o que ela vai ler no widget
      tipo          curso | prova | leitura | pratica | compra | entrega | outro
      prazo         AAAA-MM-DD
      custo         "180.00" — só o que realmente sai do bolso nesta etapa
      depende_de    ids de etapas DESTE objetivo que precisam vir antes
      obrigatoria   false para o que ajuda mas não trava (padrão: true)
      porque        por que esta etapa existe

    `plano_id` e `missoes` são os dois laços, e **só existem se você escrever**:
    o motor nunca descobre que um plano financia um objetivo nem que uma missão
    o sustenta. Ligue o plano quando a etapa custa dinheiro; ligue a missão
    quando há um hábito diário por trás — objetivo de prazo longo sem hábito
    costuma falhar na etapa do meio.

    Depois de criar, **mostre a decomposição e peça confirmação**. Enquanto ela
    não assinar, nada disso entra na agenda dela, e isso é de propósito."""
    ws = _ws()
    loja = objetivos_mod.ObjetivoStore(ws.objetivos_path)
    try:
        obj = loja.criar({
            "id": id, "titulo": titulo, "porque": porque, "etapas": etapas,
            "data_alvo": data_alvo or None,
            "comecou_em": comecou_em or date.today().isoformat(),
            "plano_id": plano_id, "missoes": missoes or [],
            "origem": "agente",
            "porque_da_origem": porque,
        })
    except (ValueError, KeyError) as e:
        return _json({"erro": str(e)})
    loja.save()
    ctx = report.analyze(ws)
    corr = objetivos_mod.correlacionar(
        obj, [], planos=ctx["planos"], vida=report.load_vida(ws), hoje=date.today()
    )
    return _json({
        "criado": obj.to_dict(),
        "assinado": False,
        "correlacao": corr,
        "proximo_passo": (
            "mostre as etapas e os prazos para ela e chame `assinar_objetivo` "
            "quando ela confirmar. Sem assinatura isto não entra na agenda, "
            "nos gauges nem no score"
        ),
    })


@mcp.tool()
def assinar_objetivo(objetivo_id: str) -> str:
    """Ela confirmou a decomposição. **Só chame depois de ela dizer que sim.**

    A assinatura é o que separa "a IA propôs" de "eu me comprometi". Assinar
    por conta própria porque a proposta parecia boa enche a agenda dela de
    item que ela nunca combinou — que é o caminho mais curto para o app ser
    desinstalado."""
    ws = _ws()
    loja = objetivos_mod.ObjetivoStore(ws.objetivos_path)
    try:
        obj = loja.assinar(objetivo_id)
    except ValueError as e:
        return _json({"erro": str(e)})
    loja.save()
    _, checks = report.load_objetivos(ws)
    return _json({
        "assinado": obj.to_dict(),
        "agenda_agora": objetivos_mod.agenda([obj], checks, date.today(), dias=14),
    })


@mcp.tool()
def marcar_etapa(objetivo_id: str, etapa_id: str, origem: str = "agente",
                 dia: str = "", nota: str = "") -> str:
    """Grava que uma etapa foi feita, dizendo **como se soube**.

    Mesma escada das missões: `presumido` nunca conta, `agente` é quando ela
    te disse nesta conversa, `usuario` é quando ela marcou no app. "O prazo
    era ontem, deve ter feito" é `presumido`, e `presumido` existe para não
    contar.

    A data importa mais do que parece: é `dia` contra o prazo da etapa que
    decide se ela entrou como cumprida no prazo. Se ela fez na semana passada
    e só está te contando agora, mande a data em que fez."""
    ws = _ws()
    lista, _ = report.load_objetivos(ws)
    obj = next((o for o in lista if o.id == objetivo_id), None)
    if obj is None:
        return _json({"erro": f"objetivo '{objetivo_id}' não existe",
                      "catalogo": [o.id for o in lista]})
    if obj.etapa(etapa_id) is None:
        return _json({"erro": f"etapa '{etapa_id}' não existe neste objetivo",
                      "etapas": [e.id for e in obj.etapas]})
    try:
        c = objetivos_mod.Check.from_dict({
            "objetivo_id": objetivo_id, "etapa_id": etapa_id,
            "dia": dia or date.today().isoformat(), "origem": origem, "nota": nota,
        })
    except ValueError as e:
        return _json({"erro": str(e)})
    objetivos_mod.marcar(ws.checks_path, c)

    _, checks = report.load_objetivos(ws)
    ctx = report.analyze(ws)
    corr = objetivos_mod.correlacionar(
        obj, checks, planos=ctx["planos"], vida=report.load_vida(ws), hoje=date.today()
    )
    return _json({
        "gravado": c.to_dict(),
        "conta_como_cumprido": c.conta_como_cumprido,
        "score": objetivos_mod.score_do_objetivo(obj, checks, date.today(), correlacao=corr),
    })


@mcp.tool()
def reajustar(objetivo_id: str, aplicar: bool = False, porque: str = "") -> str:
    """"Não deu para fazer" vira conta: quanto a cadeia anda e quanto sobra.

    Cada etapa atrasada vai para hoje e tudo que depende dela anda o mesmo
    tanto de dias. O motor não corta etapa, não sugere trocar o objetivo e não
    decide que ainda dá tempo — ele mostra a folga que restou até a data alvo
    e se ela acabou.

    Chame primeiro **sem** `aplicar`, mostre os movimentos e a folga, e só
    aplique quando ela disser para aplicar, com o motivo dela em `porque`.

    Adiar é permitido e **custa**: `prazo_original` não se apaga e o score tem
    uma dimensão só para isso. Se não custasse, bastaria empurrar tudo para
    estar sempre em dia — e o score não mediria nada."""
    ws = _ws()
    lista, checks = report.load_objetivos(ws)
    obj = next((o for o in lista if o.id == objetivo_id), None)
    if obj is None:
        return _json({"erro": f"objetivo '{objetivo_id}' não existe"})

    proposta = objetivos_mod.reajuste_proposto(obj, checks, date.today())
    if not aplicar:
        return _json({
            "proposta": proposta,
            "proximo_passo": (
                "mostre os movimentos e a folga restante. Para aplicar, chame de "
                "novo com aplicar=true e o `porque` que ela deu"
            ),
        })
    loja = objetivos_mod.ObjetivoStore(ws.objetivos_path)
    try:
        objetivos_mod.aplicar_reajuste(
            loja.objetivos[objetivo_id], proposta, porque=porque, origem="usuario"
        )
    except (ValueError, KeyError) as e:
        return _json({"erro": str(e)})
    loja.save()
    return _json({"aplicado": proposta["movimentos"],
                  "objetivo": loja.objetivos[objetivo_id].to_dict()})


@mcp.tool()
def patrimonio(definir: bool = False, conta: float | None = None,
               investido: float | None = None) -> str:
    """Lê ou atualiza o que o usuário tem guardado (conta + investimentos)."""
    ws = _ws()
    if not definir:
        return _json(ws.load_patrimonio())
    pos = []
    if conta is not None:
        pos.append({"nome": "Conta corrente", "tipo": "conta",
                    "valor": conta, "liquidez": "imediata"})
    if investido is not None:
        pos.append({"nome": "Investimentos", "tipo": "renda_fixa",
                    "valor": investido, "liquidez": "d0"})
    return _json(ws.save_patrimonio(pos))


@mcp.tool()
def ingerir_extrato(caminho: str) -> str:
    """Processa um OFX novo, grava o canônico e abre uma sessão de triagem com o
    que mudou. Confirme `conciliacao_ok` antes de analisar."""
    ws = _ws()
    src = Path(caminho).expanduser()
    dest = ws.extratos / src.name
    if src.resolve() != dest.resolve():
        dest.write_bytes(src.read_bytes())
    stmt, out = report.ingest(ws, dest)
    ok, diff = stmt.reconciles()
    ctx = report.analyze(ws)
    return _json({
        "transacoes": len(stmt.transactions),
        "periodo": [str(stmt.period_start), str(stmt.period_end)],
        "saldo": float(stmt.ledger_balance),
        "conciliacao_ok": ok, "diferenca": float(diff),
        "canonico": str(out),
        "triagem": ctx["triagem"]["resumo"],
    })


# ==========================================================================
# PROMPTS — conversas que valem a pena começar já carregadas
# ==========================================================================

@mcp.prompt(
    name="conversa_de_compra",
    title="Avaliar uma compra",
    description=(
        "Carrega perfil, causas, planos e reserva antes de discutir uma compra. "
        "Use quando a pessoa disser que está pensando em comprar alguma coisa."
    ),
)
def conversa_de_compra(item: str, preco: str = "", prazo: str = "") -> str:
    """Monta o roteiro da conversa de compra com o contexto já em mãos."""
    return f"""A pessoa está pensando em comprar: {item}{f' (R$ {preco})' if preco else ''}{f', prazo: {prazo}' if prazo else ''}.

Antes de responder qualquer coisa, carregue o contexto:

1. `briefing` — quem ela é, o que já foi assinado e o que ainda é palpite.
2. `avaliar_compra` com o item e o preço — a conta: impacto na reserva, o que
   a compra atrasa em cada plano, cenários de pagamento e o risco de
   arrependimento tirado do histórico dela.
3. `listar_causas` — se existe causa gravada para a categoria dessa compra, ela
   muda a conversa inteira.

Depois responda como alguém que a conhece, não como uma calculadora:

- **Comece pelo veredito**, com o número que o sustenta. "Cabe, e atrasa a
  viagem em 2 meses" é resposta; "depende de vários fatores" não é.
- **Cruze com o perfil assinado.** Renda variável muda o que é prudente; custo
  sufocado muda o que é possível. Se o eixo relevante ainda for palpite, diga
  que está supondo e pergunte.
- **Traga a causa, se houver.** Se ela mesma descreveu um gatilho para essa
  categoria, e esta compra parece acionado por ele, aponte — com a frase dela,
  não com um diagnóstico seu. Se a atitude registrada foi `aceitar`, não
  transforme isso em cobrança: ela já decidiu, e a decisão vale.
- **Diga o que a compra custa em coisas, não só em reais.** Mês de reserva,
  meses de atraso numa meta, aportes que deixam de acontecer.
- **Se for para desaconselhar, desaconselhe.** Com o dado na mão. Ela quer um
  consultor, não aplauso.
- **Ofereça o caminho do meio** quando existir: esperar até tal mês, comprar a
  versão anterior, parcelar sem juros mantendo o aporte, vender o que ela
  substitui.

Se a pessoa não disse preço ou prazo, pergunte antes de calcular — decidir por
ela qual é o preço é o erro mais bobo possível aqui.

Se algo relevante estiver em branco (sem plano cadastrado, patrimônio
desatualizado, categoria dessa compra sem causa), diga que a leitura é
preliminar e qual decisão fecharia a maior lacuna."""


@mcp.prompt(
    name="entender_um_gasto",
    title="Investigar por que um gasto existe",
    description=(
        "Roteiro para descobrir a causa de um padrão de gasto e registrá-la com "
        "evidência. Use quando aparecer 'sem causa' na triagem."
    ),
)
def entender_um_gasto(alvo: str) -> str:
    """Roteiro da entrevista de causa para uma categoria ou contraparte."""
    return f"""Objetivo: entender por que o dinheiro sai em {alvo} — e registrar isso.

1. `investigar` primeiro. Dia da semana, hora, distribuição de valores,
   presença mensal, exemplos. Você precisa chegar na conversa com o padrão
   concreto, não com a categoria.
2. **Traga o padrão, não o rótulo.** "Sete das onze compras são depois das 21h,
   e cinco delas em dias de semana" é observação que a pessoa confirma ou
   corrige. "Você gasta muito com delivery" é julgamento que ela só pode
   aceitar ou negar.
3. **Pergunte uma coisa por vez** e deixe ela contar. A causa quase nunca é a
   primeira resposta — "é mais prático" costuma virar "chego destruído às 22h"
   depois de mais uma pergunta.
4. `gravar_causa` com o enunciado nas **palavras dela**. Não traduza para
   vocabulário de finanças: a frase original é o que vai fazer sentido para ela
   daqui a seis meses.
5. **Pergunte o que ela quer fazer a respeito**, e registre com `decidir_causa`.
   `aceitar` é uma resposta boa: nomeia o gasto como escolha, e escolha
   consciente não é vazamento. Não empurre corte.
6. Se for algo que provavelmente muda (projeto que acaba, obra, estágio),
   marque `revisar_em` — a causa vai voltar para a fila quando vencer.
7. `resolver_item` no item da triagem, dizendo o que foi gravado."""


# ==========================================================================
# decisões: a bifurcação, o que se considerou, e no que deu
# ==========================================================================


@mcp.tool()
def abrir_decisao(titulo: str, situacao: str, pergunta: str, alternativas: list[dict],
                  porque: str, tipo: str = "outro", ligacoes: list[str] | None = None,
                  revisar_em: str = "", substitui: str = "",
                  origem: str = "agente", confianca: float = 0.9) -> str:
    """Abre o registro de uma decisão: a situação, a pergunta e os caminhos.

    Use **antes** de a pessoa escolher, não depois. Alternativa listada depois
    da escolha vira justificativa: ela lembra melhor das opções que confirmam o
    que já fez. Escritas antes, são comparação de verdade — e são elas que
    sobram para a próxima vez que a mesma pergunta aparecer.

    O app congela sozinho os números do motor no momento da abertura (sobra,
    reserva, score, planos em risco). É o que permite julgar a escolha, depois,
    pelo que se sabia na época — e não pelo que se sabe hoje.

    `alternativas`: no mínimo duas, cada uma
    `{nome, custo, custo_mensal, horizonte_meses, consequencia, risco,
    descartada_porque}`. Preencha `horizonte_meses` sempre que a opção tiver
    prazo de validade: é o que deixa o motor comparar R$ 700 que duram 8 meses
    com R$ 2.500 que duram 36 — a conta que decide a maioria das trocas e que
    ninguém faz de cabeça.
    `tipo`: troca | compra | contrato | divida | investimento | renda | moradia | outro.
    `ligacoes`: "categoria:eletronicos", "plano:viagem" — é por elas que esta
    decisão vai aparecer como precedente da próxima.
    `substitui`: id da decisão que esta substitui, quando se muda de ideia (a
    anterior não some do histórico; passa a apontar para esta)."""
    ws = _ws()
    st = report.stores(ws)
    try:
        ctx = report.analyze(ws, st=st)
        dec = st["decisoes"].abrir(
            titulo=titulo, situacao=situacao, pergunta=pergunta,
            alternativas=alternativas, tipo=tipo, ligacoes=ligacoes or [],
            instantaneo=decisions.instantaneo_de(ctx),
            revisar_em=revisar_em or None, substitui=substitui or None,
            proveniencia=_prov(origem, confianca, porque),
        )
    except ValueError as e:
        return _json({"erro": str(e)})
    return _json({
        "decisao": dec.to_dict(),
        "proximo_passo": (
            "compare `custo_por_mes_de_uso` das alternativas com a pessoa e chame "
            "`escolher_alternativa` quando ela decidir"
        ),
    })


@mcp.tool()
def escolher_alternativa(decisao_id: str, alternativa: str, porque: str,
                         revisar_em: str = "") -> str:
    """Registra qual caminho foi tomado, e por quê.

    O `porque` nas palavras dela é o que o registro tem de mais útil depois: o
    número volta a ser calculável a qualquer momento, o motivo não.

    `revisar_em` (AAAA-MM-DD) para escolha que tem prazo de conferência — o
    conserto que precisa durar até o meio do ano, o plano que tem fidelidade."""
    st = report.stores(_ws())
    try:
        dec = st["decisoes"].escolher(decisao_id, alternativa, porque,
                                      revisar_em=revisar_em or None)
    except ValueError as e:
        return _json({"erro": str(e)})
    return _json({"decisao": dec.to_dict()})


@mcp.tool()
def registrar_desfecho(decisao_id: str, veredito: str, nota: str = "",
                       custo_real: float | None = None) -> str:
    """No que deu. É isto que transforma histórico em base para decidir.

    `veredito`: funcionou | arrependi | indiferente | cedo_para_saber.
    `cedo_para_saber` é resposta boa: a decisão continua na fila e volta a ser
    perguntada depois, em vez de virar um aprendizado que ninguém verificou.
    `custo_real` quando saiu diferente do previsto — a diferença entre o
    estimado e o real é, sozinha, um aprendizado sobre como ela orça."""
    st = report.stores(_ws())
    try:
        dec = st["decisoes"].registrar_desfecho(decisao_id, veredito, nota,
                                                custo_real=custo_real)
    except ValueError as e:
        return _json({"erro": str(e)})
    return _json({"decisao": dec.to_dict()})


@mcp.tool()
def listar_decisoes(apenas_abertas: bool = False) -> str:
    """Histórico de decisões e o que ele já permite afirmar."""
    st = report.stores(_ws())
    loja = st["decisoes"]
    if apenas_abertas:
        return _json({"abertas": [d.to_dict() for d in loja.abertas()]})
    return _json({
        "linha_do_tempo": loja.linha_do_tempo(),
        "aprendizados": loja.aprendizados(),
        "detalhe": "use `historico_de_decisoes` para os precedentes de um assunto",
    })


@mcp.tool()
def historico_de_decisoes(assunto: str, tipo: str = "",
                          ligacoes: list[str] | None = None) -> str:
    """Decisões passadas parecidas com a que está sendo tomada agora.

    Chame isto **antes** de ajudar em qualquer escolha — inclusive antes de
    `avaliar_compra`. É o que evita refazer do zero uma conta que já foi feita,
    e o que traz de volta o detalhe que sempre some: por que a alternativa
    óbvia foi descartada da última vez.

    Cada precedente vem com `numeros_da_epoca`. Use-os: a mesma escolha com
    quatro meses de reserva e com duas semanas de caixa são decisões
    diferentes, e cobrar coerência entre elas é injusto com a pessoa."""
    st = report.stores(_ws())
    return _json({
        "assunto": assunto,
        "precedentes": st["decisoes"].semelhantes(assunto, tipo=tipo, ligacoes=ligacoes),
        "aprendizados": st["decisoes"].aprendizados(),
    })


@mcp.tool()
def esquecer_decisao(decisao_id: str) -> str:
    """Apaga uma decisão registrada por engano."""
    st = report.stores(_ws())
    return _json({"removida": st["decisoes"].esquecer(decisao_id)})


@mcp.tool()
def abrir_painel(porta: int = 8420) -> str:
    """Como o usuário abre o painel visual local (o servidor roda no terminal dele)."""
    return _json({
        "comando": f"fintips serve --port {porta}",
        "url": f"http://127.0.0.1:{porta}",
        "observacao": "o painel lê exatamente a mesma análise que estas ferramentas",
    })


def main() -> None:
    global _ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(_ROOT))
    args = ap.parse_args()
    _ROOT = Path(args.root).expanduser()
    mcp.run()


if __name__ == "__main__":
    main()
