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
from decimal import Decimal
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import levers, mapping, plans as plans_mod
from . import projection as proj_mod
from . import purchases, report
from .analysis import baseline
from .categorize import norm
from .contracts import Proveniencia
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
# LER
# ==========================================================================

@mcp.tool()
def analise_completa() -> str:
    """Contexto inteiro: baseline, score, meses, categorias, contrapartes, regras,
    custos fixos definidos, candidatos, projeção, contexto do usuário e triagem.
    Primeira parada de quase toda conversa."""
    ws = _ws()
    data = report.analyze(ws)
    report.save_report(ws, data)
    return _json(data)


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
    estratégias possíveis com o trade-off de cada uma."""
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
    ))


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
