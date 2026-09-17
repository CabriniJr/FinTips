"""CLI do FinTips.

    fintips init            [--root PASTA]
    fintips ingest EXTRATO.ofx
    fintips analyze         [--json]
    fintips score
    fintips plan add --id trekking --nome "Trekking" --custo 8000 --data 2027-03-01
    fintips plan list
    fintips holdings set --conta 1500 --investido 20000
    fintips buy --item "Fone X" --preco 1800 [--parcelas 10] [--urgencia baixa]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

from . import plans as plans_mod
from . import purchases, report
from .analysis import baseline
from .categorize import Categorizer
from .parsers.ofx import parse_ofx
from .workspace import Workspace

DEFAULT_ROOT = Path.home() / "Documents" / "FinTips"


def _ws(args) -> Workspace:
    return Workspace.open(args.root or DEFAULT_ROOT)


def _load_statement(ws: Workspace):
    """Reprocessa o OFX mais recente (o YAML canônico é saída, não entrada)."""
    files = sorted(ws.extratos.glob("*.ofx"))
    if not files:
        sys.exit("nenhum extrato em data/extratos — rode 'fintips ingest arquivo.ofx'")
    cfg = ws.config
    stmt = parse_ofx(files[-1], salt=ws.salt)
    Categorizer(
        aliases=cfg.get("apelidos") or {},
        my_names=cfg.get("meus_nomes") or [],
        salt=ws.salt,
        local_rules_path=ws.regras_locais_path,
    ).apply_all(stmt.transactions)
    return stmt


def cmd_init(args) -> None:
    ws = _ws(args)
    print(f"workspace pronto em {ws.root}")


def cmd_ingest(args) -> None:
    ws = _ws(args)
    src = Path(args.arquivo).expanduser()
    dest = ws.extratos / src.name
    if src.resolve() != dest.resolve():
        dest.write_bytes(src.read_bytes())
    stmt, out = report.ingest(ws, dest)
    ok, diff = stmt.reconciles()
    print(f"{len(stmt.transactions)} transações  {stmt.period_start} → {stmt.period_end}")
    print(f"saldo declarado R$ {stmt.ledger_balance}  conciliação: {'ok' if ok else f'divergência {diff}'}")
    print(f"canônico: {out}")


def cmd_analyze(args) -> None:
    ws = _ws(args)
    stmt = _load_statement(ws)
    data = report.analyze(ws, stmt)
    out = report.save_report(ws, data)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        return
    b, s = data["baseline"], data["score"]
    print(f"score {s['score']}/100 ({s['faixa']})")
    print(f"renda média  R$ {b['renda_media_mes']:>10,.2f}")
    print(f"despesa média R$ {b['despesa_media_mes']:>10,.2f}")
    print(f"sobra média   R$ {b['sobra_media_mes']:>10,.2f}   ({b['taxa_poupanca_media']*100:.1f}%)")
    inv = data["gastos_invisiveis"]
    print(f"invisível/mês R$ {inv['taxas_e_seguros']['por_mes'] + inv['micro_gastos']['por_mes']:>10,.2f}")
    print(f"relatório: {out}")


def cmd_score(args) -> None:
    ws = _ws(args)
    data = report.analyze(ws, _load_statement(ws))
    print(json.dumps(data["score"], ensure_ascii=False, indent=2))


def cmd_plan(args) -> None:
    ws = _ws(args)
    items = plans_mod.load_plans(ws.planos_path)
    if args.acao == "list":
        stmt = _load_statement(ws)
        res = plans_mod.evaluate_all(items, stmt, baseline(stmt))
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    novo = plans_mod.Plan(
        id=args.id,
        nome=args.nome or args.id,
        tipo=args.tipo,
        custo_alvo=Decimal(str(args.custo)),
        data_alvo=date.fromisoformat(args.data) if args.data else None,
        prioridade=args.prioridade,
        aporte_mensal=Decimal(str(args.aporte or 0)),
        guardado=Decimal(str(args.guardado or 0)),
        merchants=(args.merchants or "").split(",") if args.merchants else [],
    )
    items = [p for p in items if p.id != novo.id] + [novo]
    plans_mod.save_plans(ws.planos_path, items)
    print(f"plano '{novo.id}' salvo em {ws.planos_path}")


def cmd_holdings(args) -> None:
    ws = _ws(args)
    pos = []
    if args.conta is not None:
        pos.append({"nome": "Conta PagBank", "tipo": "conta", "valor": float(args.conta), "liquidez": "imediata"})
    if args.investido is not None:
        pos.append({"nome": "Investimentos", "tipo": "renda_fixa", "valor": float(args.investido), "liquidez": "d0"})
    data = ws.save_patrimonio(pos)
    print(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def cmd_buy(args) -> None:
    ws = _ws(args)
    stmt = _load_statement(ws)
    base = baseline(stmt)
    plan_res = plans_mod.evaluate_all(plans_mod.load_plans(ws.planos_path), stmt, base)
    patr = ws.load_patrimonio()
    intent = purchases.PurchaseIntent(
        item=args.item,
        preco=Decimal(str(args.preco)),
        categoria=args.categoria,
        urgencia=args.urgencia,
        parcelas_possiveis=args.parcelas,
        juros_parcelamento=args.juros,
    )
    res = purchases.evaluate(
        intent, stmt, base, plan_res,
        saldo_conta=stmt.ledger_balance,
        patrimonio=Decimal(str(patr.get("total", 0))),
        reserva_alvo_meses=float(ws.config.get("reserva_alvo_meses", 6)),
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fintips", description="motor financeiro pessoal")
    p.add_argument("--root", help="pasta do workspace", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(func=cmd_init)

    ing = sub.add_parser("ingest"); ing.add_argument("arquivo"); ing.set_defaults(func=cmd_ingest)

    an = sub.add_parser("analyze"); an.add_argument("--json", action="store_true"); an.set_defaults(func=cmd_analyze)

    sub.add_parser("score").set_defaults(func=cmd_score)

    pl = sub.add_parser("plan"); pl.add_argument("acao", choices=["add", "list"])
    pl.add_argument("--id"); pl.add_argument("--nome"); pl.add_argument("--tipo", default="outro")
    pl.add_argument("--custo", type=float, default=0); pl.add_argument("--data")
    pl.add_argument("--prioridade", default="media"); pl.add_argument("--aporte", type=float)
    pl.add_argument("--guardado", type=float); pl.add_argument("--merchants")
    pl.set_defaults(func=cmd_plan)

    ho = sub.add_parser("holdings"); ho.add_argument("acao", choices=["set"], nargs="?", default="set")
    ho.add_argument("--conta", type=float); ho.add_argument("--investido", type=float)
    ho.set_defaults(func=cmd_holdings)

    bu = sub.add_parser("buy"); bu.add_argument("--item", required=True); bu.add_argument("--preco", type=float, required=True)
    bu.add_argument("--categoria", default="compras"); bu.add_argument("--urgencia", default="media")
    bu.add_argument("--parcelas", type=int, default=1); bu.add_argument("--juros", type=float, default=0.0)
    bu.set_defaults(func=cmd_buy)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
