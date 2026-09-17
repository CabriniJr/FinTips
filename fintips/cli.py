"""CLI do FinTips.

    fintips init            [--root PASTA]
    fintips ingest EXTRATO.ofx
    fintips analyze         [--json]
    fintips score
    fintips plan add --id trekking --nome "Trekking" --custo 8000 --data 2027-03-01
    fintips plan list
    fintips holdings set --conta 1500 --investido 20000
    fintips buy --item "Fone X" --preco 1800 [--parcelas 10] [--urgencia baixa]
    fintips serve           [--port 8420]      abre o painel no navegador
    fintips triagem         [--resolver ID] [--limite N]
    fintips contexto        [--gravar chave --valor V]
    fintips categorias      [--criar id --nome "Nome"]
    fintips regras          [--remover ID]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

from . import levers
from . import plans as plans_mod
from . import purchases, report
from .analysis import baseline
from .workspace import Workspace

DEFAULT_ROOT = Path.home() / "Documents" / "FinTips"


def _ws(args) -> Workspace:
    return Workspace.open(args.root or DEFAULT_ROOT)


def _load_statement(ws: Workspace):
    try:
        return report.load_statement(ws)
    except FileNotFoundError as e:
        sys.exit(f"{e} — rode 'fintips ingest arquivo.ofx'")


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
    st = report.stores(ws)
    stmt = _load_statement(ws)
    report.enrich(ws, stmt, st)
    # o contexto inteiro, para a compra ser lida à luz do perfil assinado e das
    # causas gravadas — e não só do saldo
    ctx = report.analyze(ws, stmt=stmt, st=st)
    base = ctx["baseline"]
    plan_res = ctx["planos"]
    patr = ctx["patrimonio"]
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
        reserva_alvo_meses=float(base.get("reserva_alvo_meses", 6)),
        perfil=ctx.get("perfil"),
        causas=(ctx.get("causas") or {}).get("itens"),
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))


def cmd_serve(args) -> None:
    from .api import serve

    root = str(_ws(args).root)
    url = f"http://{args.host}:{args.port}"
    print(f"FinTips em {url}   (workspace: {root})")
    print("ctrl+c para parar")
    if not args.no_browser:
        import threading
        import webbrowser

        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    serve(host=args.host, port=args.port, root=root)


def cmd_triagem(args) -> None:
    ws = _ws(args)
    st = report.stores(ws)
    ctx = report.analyze(ws, st=st)
    t = ctx["triagem"]
    if args.resolver:
        item = next((i for i in t["itens"] if i["id"] == args.resolver), None)
        if not item:
            sys.exit(f"item '{args.resolver}' não está na fila")
        reg = st["triagem"].resolver(args.resolver, {"nota": args.nota or "resolvido via CLI"})
        print(json.dumps({args.resolver: reg}, ensure_ascii=False, indent=2))
        return
    r = t["resumo"]
    print(f"{r['abertos']} em aberto · impacto R$ {r['impacto_mensal_em_aberto']:,.2f}/mês")
    print(f"por tipo: {r['por_tipo']}\n")
    for i in t["itens"][: args.limite]:
        print(f"[{i['prioridade']:>8.2f}] {i['id']}  {i['tipo']}")
        print(f"   {i['titulo']}")
        print(f"   por quê: {i['porque_importa'][:110]}")


def cmd_perfil(args) -> None:
    """Mostra o perfil, ou assina um eixo.

    Sem argumentos é só leitura: o que o catálogo sugere por número, o que já
    foi assinado e quanto do perfil é decisão. Assinar pelo terminal grava com
    origem `usuario` — porque quem está digitando é a pessoa.
    """
    from .contracts import Proveniencia

    ws = _ws(args)
    st = report.stores(ws)
    if args.assinar:
        if not args.porque:
            sys.exit("assinar um traço de perfil exige --porque")
        try:
            traco = st["perfil"].assinar(
                args.assinar, args.arquetipo or "",
                nome=args.nome or "", descricao=args.descricao or "",
                proveniencia=Proveniencia(origem="usuario", confianca=1.0, porque=args.porque),
            )
        except ValueError as e:
            sys.exit(str(e))
        print(json.dumps(traco.to_dict(), ensure_ascii=False, indent=2))
        return
    if args.esquecer:
        print(json.dumps({"esquecido": st["perfil"].esquecer(args.esquecer)},
                         ensure_ascii=False, indent=2))
        return

    perfil = report.analyze(ws, st=st)["perfil"]
    cob = perfil["cobertura"]
    print(f"perfil assinado: {cob['assinados']}/{cob['eixos']} eixos ({cob['pct']}%)")
    print("o resto é sugestão do catálogo contra os seus números — palpite\n")
    for e in perfil["eixos"]:
        assinado = e["assinado"]
        sug = e["sugerido"]
        marca = "assinado" if assinado else "sugestão"
        if assinado:
            quem = assinado["proveniencia"]["origem"]
            print(f"{e['eixo']:11} {assinado['nome']}  [{marca}: {quem}]")
            print(f"            porque: {assinado['proveniencia']['porque'][:90]}")
            if e["diverge_da_sugestao"]:
                print(f"            (os números sugeririam '{sug['id']}')")
        elif sug:
            print(f"{e['eixo']:11} {sug['nome']}  [{marca}, aderência {sug['aderencia']}]")
            for ev in sug["evidencia"]:
                print(f"            {ev}")
        else:
            print(f"{e['eixo']:11} sem leitura — {e['sem_leitura_porque']}")


def cmd_alavancas(args) -> None:
    ws = _ws(args)
    out = levers.calcular(report.analyze(ws))
    print(f"{out['total']} alavancas · ordenadas por {out['ordenado_por']}\n")
    for a in out["alavancas"][: args.limite]:
        unidade = {"BRL/mes": "/mês", "BRL": "", "coeficiente": " (coef.)"}.get(a["unidade"], "")
        print(f"[{a['tipo']:8}] {a['titulo']}")
        print(f"   {a['numero']}{unidade}")
        for k, v in a["efeito"].items():
            if v is not None:
                print(f"   {k}: {v}")
        print()


def cmd_contexto(args) -> None:
    from .context import ContextStore
    from .contracts import Proveniencia

    ws = _ws(args)
    loja = ContextStore(ws.contexto_path)
    if args.gravar:
        fato = loja.gravar(
            args.gravar, args.valor,
            proveniencia=Proveniencia(origem="usuario", confianca=1.0,
                                      porque=args.porque or "informado no terminal"),
        )
        print(json.dumps(fato.to_dict(), ensure_ascii=False, indent=2))
        return
    print(json.dumps(loja.resumo(), ensure_ascii=False, indent=2))


def cmd_categorias(args) -> None:
    from .contracts import Proveniencia

    ws = _ws(args)
    st = report.stores(ws)
    tax = st["taxonomia"]
    if args.criar:
        cat = tax.criar(
            args.criar, args.nome or args.criar, descricao=args.descricao or "",
            essencial=args.essencial,
            proveniencia=Proveniencia(origem="usuario", confianca=1.0,
                                      porque="criada no terminal"),
        )
        print(json.dumps(cat.to_dict(), ensure_ascii=False, indent=2))
        return
    ctx = report.analyze(ws, st=st)
    for c in ctx["taxonomia"]:
        marca = "·" if c["proveniencia"]["origem"] in ("usuario", "agente") else "?"
        print(f"{marca} {c['id']:<16} {c['nome']:<18} "
              f"R$ {c['total_no_periodo']:>10,.2f}  origem={c['proveniencia']['origem']}")
    print(f"\n? = ainda não revisada por você ou pelo agente")


def cmd_regras(args) -> None:
    from .mapping import RuleStore

    ws = _ws(args)
    loja = RuleStore(ws.regras_path)
    if args.remover:
        print("removida" if loja.remover(args.remover) else "não encontrada")
        return
    for r in loja.to_dicts():
        print(f"{r['id']}  quando={r['quando']}  então={r['entao']}  "
              f"origem={r['proveniencia']['origem']}")
    print(f"\n{len(loja.regras)} regra(s)")


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

    sv = sub.add_parser("serve"); sv.add_argument("--port", type=int, default=8420)
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--no-browser", action="store_true")
    sv.set_defaults(func=cmd_serve)

    tr = sub.add_parser("triagem"); tr.add_argument("--resolver"); tr.add_argument("--nota")
    tr.add_argument("--limite", type=int, default=12)
    tr.set_defaults(func=cmd_triagem)

    cx = sub.add_parser("contexto"); cx.add_argument("--gravar"); cx.add_argument("--valor")
    cx.add_argument("--porque")
    cx.set_defaults(func=cmd_contexto)

    ct = sub.add_parser("categorias"); ct.add_argument("--criar"); ct.add_argument("--nome")
    ct.add_argument("--descricao"); ct.add_argument("--essencial", type=bool, default=None)
    ct.set_defaults(func=cmd_categorias)

    rg = sub.add_parser("regras"); rg.add_argument("--remover")
    rg.set_defaults(func=cmd_regras)

    pf = sub.add_parser("perfil")
    pf.add_argument("--assinar", metavar="EIXO",
                    help="fase | renda | custo | consumo | constancia")
    pf.add_argument("--arquetipo", help="id do catálogo, ou 'personalizado'")
    pf.add_argument("--nome"); pf.add_argument("--descricao")
    pf.add_argument("--porque", help="obrigatório ao assinar")
    pf.add_argument("--esquecer", metavar="EIXO")
    pf.set_defaults(func=cmd_perfil)

    al = sub.add_parser("alavancas"); al.add_argument("--limite", type=int, default=8)
    al.set_defaults(func=cmd_alavancas)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
