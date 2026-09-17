"""MCP server do FinTips (stdio).

Roda na SUA máquina, lê a pasta local e devolve dados já calculados.
O Claude nunca recebe o extrato bruto — só o modelo canônico e os agregados.

    python -m fintips.mcp_server --root "C:/Users/<voce>/Documents/FinTips"
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import plans as plans_mod
from . import purchases, report
from .analysis import baseline
from .categorize import Categorizer, norm
from .parsers.ofx import parse_ofx
from .workspace import Workspace

mcp = FastMCP("fintips")
_ROOT = Path(os.environ.get("FINTIPS_ROOT", Path.home() / "Documents" / "FinTips"))


def _ws() -> Workspace:
    return Workspace.open(_ROOT)


def _stmt(ws: Workspace):
    files = sorted(ws.extratos.glob("*.ofx"))
    if not files:
        raise ValueError("nenhum extrato em data/extratos")
    cfg = ws.config
    st = parse_ofx(files[-1], salt=ws.salt)
    Categorizer(
        aliases=cfg.get("apelidos") or {},
        my_names=cfg.get("meus_nomes") or [],
        salt=ws.salt,
        local_rules_path=ws.regras_locais_path,
    ).apply_all(st.transactions)
    return st


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
def ingerir_extrato(caminho: str) -> str:
    """Processa um arquivo OFX novo e grava o YAML canônico. Use quando o
    usuário baixar um extrato novo do banco."""
    ws = _ws()
    src = Path(caminho).expanduser()
    dest = ws.extratos / src.name
    if src.resolve() != dest.resolve():
        dest.write_bytes(src.read_bytes())
    stmt, out = report.ingest(ws, dest)
    ok, diff = stmt.reconciles()
    return _json({
        "transacoes": len(stmt.transactions),
        "periodo": [str(stmt.period_start), str(stmt.period_end)],
        "saldo": float(stmt.ledger_balance),
        "conciliacao_ok": ok,
        "diferenca": float(diff),
        "canonico": str(out),
    })


@mcp.tool()
def analise_completa() -> str:
    """Panorama financeiro: baseline, score, meses, categorias, recorrências,
    gastos invisíveis, eventos atípicos e status dos planos."""
    ws = _ws()
    data = report.analyze(ws, _stmt(ws))
    report.save_report(ws, data)
    return _json(data)


@mcp.tool()
def score_financeiro() -> str:
    """Só o score e suas dimensões — resposta curta para checagem rápida."""
    ws = _ws()
    return _json(report.analyze(ws, _stmt(ws))["score"])


@mcp.tool()
def listar_planos() -> str:
    """Planos cadastrados com viabilidade recalculada contra o extrato atual."""
    ws = _ws()
    st = _stmt(ws)
    return _json(plans_mod.evaluate_all(plans_mod.load_plans(ws.planos_path), st, baseline(st)))


@mcp.tool()
def salvar_plano(
    id: str,
    nome: str,
    custo_alvo: float,
    data_alvo: str | None = None,
    tipo: str = "outro",
    prioridade: str = "media",
    aporte_mensal: float = 0,
    guardado: float = 0,
    merchants: list[str] | None = None,
    categorias: list[str] | None = None,
    notas: str = "",
) -> str:
    """Cria ou atualiza um plano financeiro (viagem, compra, reserva...).
    `merchants` e `categorias` ligam o plano a gastos reais do extrato."""
    ws = _ws()
    items = [p for p in plans_mod.load_plans(ws.planos_path) if p.id != id]
    novo = plans_mod.Plan(
        id=id, nome=nome, tipo=tipo,
        custo_alvo=Decimal(str(custo_alvo)),
        data_alvo=date.fromisoformat(data_alvo) if data_alvo else None,
        prioridade=prioridade,
        aporte_mensal=Decimal(str(aporte_mensal)),
        guardado=Decimal(str(guardado)),
        merchants=merchants or [], categorias=categorias or [], notas=notas,
    )
    items.append(novo)
    plans_mod.save_plans(ws.planos_path, items)
    st = _stmt(ws)
    return _json(plans_mod.evaluate(novo, st, baseline(st)))


@mcp.tool()
def avaliar_compra(
    item: str,
    preco: float,
    categoria: str = "compras",
    urgencia: str = "media",
    parcelas_possiveis: int = 1,
    juros_parcelamento: float = 0.0,
    substitui: str = "",
    palavras_chave: list[str] | None = None,
) -> str:
    """Avalia uma intenção de compra contra o histórico: impacto no caixa,
    custo em meses de sobra, conflito com planos, risco de arrependimento e
    melhor estratégia (à vista, juntar, parcelar)."""
    ws = _ws()
    st = _stmt(ws)
    base = baseline(st)
    plan_res = plans_mod.evaluate_all(plans_mod.load_plans(ws.planos_path), st, base)
    patr = ws.load_patrimonio()
    intent = purchases.PurchaseIntent(
        item=item, preco=Decimal(str(preco)), categoria=categoria,
        urgencia=urgencia, parcelas_possiveis=parcelas_possiveis,
        juros_parcelamento=juros_parcelamento, substitui=substitui,
        tags=palavras_chave or [],
    )
    return _json(purchases.evaluate(
        intent, st, base, plan_res,
        saldo_conta=st.ledger_balance,
        patrimonio=Decimal(str(patr.get("total", 0))),
        reserva_alvo_meses=float(ws.config.get("reserva_alvo_meses", 6)),
    ))


@mcp.tool()
def patrimonio(
    definir: bool = False,
    conta: float | None = None,
    investido: float | None = None,
) -> str:
    """Lê ou atualiza o que você tem guardado (conta + investimentos)."""
    ws = _ws()
    if not definir:
        return _json(ws.load_patrimonio())
    pos = []
    if conta is not None:
        pos.append({"nome": "Conta corrente", "tipo": "conta", "valor": conta, "liquidez": "imediata"})
    if investido is not None:
        pos.append({"nome": "Investimentos", "tipo": "renda_fixa", "valor": investido, "liquidez": "d0"})
    return _json(ws.save_patrimonio(pos))


@mcp.tool()
def buscar_transacoes(
    texto: str = "",
    categoria: str = "",
    mes: str = "",
    fluxo: str = "",
    valor_minimo: float = 0,
    limite: int = 50,
) -> str:
    """Busca transações no extrato atual. `mes` no formato AAAA-MM."""
    ws = _ws()
    st = _stmt(ws)
    alvo = norm(texto)
    out = []
    for t in st.transactions:
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


def main() -> None:
    global _ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(_ROOT))
    args = ap.parse_args()
    _ROOT = Path(args.root).expanduser()
    mcp.run()


if __name__ == "__main__":
    main()
