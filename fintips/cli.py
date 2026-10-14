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
    fintips decisoes        [--abertas] [--historico ASSUNTO]
    fintips mcp-config      [--nome fintips]   config do cliente MCP
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
from . import life
from . import configuracao as cfg_mod
from . import licencas as lic_mod
from . import objetivos as objetivos_mod
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
        precedentes=st["decisoes"].semelhantes(
            f"{intent.item} {intent.categoria}", tipo="compra",
            ligacoes=[f"categoria:{intent.categoria}"],
        ),
        aprendizados=(ctx.get("decisoes") or {}).get("aprendizados"),
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

    if args.historico:
        loja = st["perfil"]
        travessias = loja.travessias(args.eixo or "")
        if not travessias:
            print("nenhuma travessia registrada ainda.")
            print("Reconfirmar não é mudar: só entra aqui quem virou outra coisa.")
            return
        for t in travessias:
            print(f"{t['quando'][:10]}  {t['eixo']}: {t['de']} → {t['para']}")
            if t["porque_antes"]:
                print(f"    antes: {t['porque_antes']}")
            print(f"    agora: {t['porque_agora']}")
        return

    if args.retrato:
        r = report.analyze(ws).get("retrato") or {}
        d = r.get("dinheiro", {})
        print(f"decidido: {d.get('decidido_pct', 0)}%  "
              f"ainda válido: {d.get('ainda_valido_pct', 0)}%")
        for e in d.get("eixos") or []:
            marca = " (reconfirmar)" if e["envelhecido"] else ""
            print(f"  {e['eixo']:<12} {e['arquetipo'] or '—'}{marca}")
            if e["porque"]:
                print(f"       {e['porque']}")
        c = r.get("compromissos", {})
        print(f"\ncompromissos: {len(c.get('objetivos') or [])} objetivo(s), "
              f"{c.get('etapas_atrasadas', 0)} etapa(s) atrasada(s), "
              f"R$ {c.get('restante_a_pagar', 0):.2f} a pagar")
        fracas = (r.get("vida") or {}).get("frentes_fracas_hoje") or []
        if fracas:
            print(f"frentes fracas hoje: {', '.join(fracas)}")
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


def cmd_decisoes(args) -> None:
    from .decisions import DecisionStore

    loja = DecisionStore(_ws(args).decisoes_path)

    if args.historico:
        precedentes = loja.semelhantes(args.historico)
        if not precedentes:
            print(f"nenhuma decisão parecida com '{args.historico}' no histórico")
            return
        for d in precedentes:
            print(f"{d['quando']}  {d['titulo']}")
            print(f"   escolheu: {d['escolheu']}  (R$ {d['custo']:.2f})  → {d['deu_em']}")
            print(f"   porque: {d['porque']}")
            for alt in d["descartou"]:
                print(f"   descartou {alt['nome']}: {alt['descartada_porque']}")
            print()
        return

    decisoes = loja.abertas() if args.abertas else list(
        sorted(loja.decisoes.values(), key=lambda d: d.criado_em, reverse=True))
    if not decisoes:
        print("nenhuma decisão registrada."
              if not args.abertas else "nenhuma decisão em aberto.")
        print("o agente abre uma com `abrir_decisao` quando a pergunta aparecer.")
        return

    for d in decisoes:
        marca = "•" if d.status == "aberta" else " "
        print(f"{marca} {d.id}  [{d.status}] {d.titulo}")
        print(f"   {d.pergunta}")
        for a in d.alternativas:
            escolha = "→" if a.nome == d.escolhida else " "
            por_mes = (f"  R$ {a.custo_por_mes_de_uso:.2f}/mês de uso"
                       if a.custo_por_mes_de_uso is not None else "")
            print(f"   {escolha} {a.nome}: R$ {a.custo:.2f}{por_mes}")
        if d.desfecho:
            print(f"   deu em: {d.desfecho['veredito']}  {d.desfecho.get('nota', '')}")
        print()

    ap = loja.aprendizados()
    print(f"{ap['decisoes_registradas']} decisão(ões), {ap['abertas']} em aberto, "
          f"{ap['com_desfecho']} com desfecho ({ap['cobertura_de_desfecho_pct']}% das tomadas)")


def cmd_aparelho(args) -> None:
    """Exporta o catálogo de missões para o app Android.

    O celular é outra máquina: ele não lê o workspace. Este comando é a ponte —
    gera o JSON que o app carrega e, com `--registros`, absorve de volta o que
    foi marcado no aparelho.
    """
    ws = _ws(args)

    if args.exemplo:
        # O molde genérico do pacote, não o catálogo da pessoa. Existe para
        # quem trabalha na tela: desenhar precisa de dado, e exigir o workspace
        # de alguém para ver uma barra desenhada é fricção sem motivo. Zero
        # dado pessoal aqui — é o mesmo arquivo que o `check-pii.sh` conferiu.
        molde = Path(__file__).parent / "rules" / "exemplo-missoes.yaml"
        vida = life.carregar(molde)
        payload = life.exportar_para_aparelho(vida)
        texto = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.saida:
            Path(args.saida).expanduser().write_text(texto, encoding="utf-8")
            print(f"{len(payload['missoes'])} missões de EXEMPLO em {args.saida}")
            print("é o molde do pacote, não o seu catálogo — serve para desenhar a tela")
        else:
            print(texto, end="")
        return

    vida = report.load_vida(ws)

    if args.registros:
        caminho = Path(args.registros).expanduser()
        if not caminho.exists():
            raise SystemExit(f"não achei {caminho}")
        novos = life.importar_do_aparelho(
            caminho.read_text(encoding="utf-8"),
            {m.id for m in vida.missoes},
        )
        for r in novos:
            life.registrar(ws.registros_path, r)
        print(f"{len(novos)} registro(s) do aparelho gravados em {ws.registros_path}")
        return

    if vida.vazia:
        raise SystemExit(
            f"nenhuma missão em {ws.missoes_path}.\n"
            "Comece do molde: fintips/rules/exemplo-missoes.yaml"
        )

    payload = life.exportar_para_aparelho(vida)
    texto = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.saida:
        destino = Path(args.saida).expanduser()
        destino.write_text(texto, encoding="utf-8")
        print(f"{len(payload['missoes'])} missões em {destino}")
        print("copie para o aparelho como missoes.json")
    else:
        print(texto, end="")


def cmd_objetivos(args) -> None:
    """Mostra os objetivos: agenda da janela, score e o que está atrasado.

    Com `--reajustar`, calcula o que acontece com a cadeia se o atraso for
    absorvido — e **não aplica**: imprime os movimentos e a folga restante.
    Mexer na data de uma promessa é de quem fez a promessa, e pela CLI isso
    significa confirmar com `--aplicar` e dizer `--porque`.
    """
    ws = _ws(args)
    lista, checks = report.load_objetivos(ws)
    if not lista:
        raise SystemExit(
            f"nenhum objetivo em {ws.objetivos_path}.\n"
            "Eles nascem da conversa (ferramenta `criar_objetivo`), ou do molde "
            "em fintips/rules/exemplo-objetivos.yaml"
        )
    hoje = date.today()

    if args.reajustar:
        loja = objetivos_mod.ObjetivoStore(ws.objetivos_path)
        obj = loja.objetivos.get(args.reajustar)
        if obj is None:
            raise SystemExit(f"objetivo '{args.reajustar}' não existe")
        proposta = objetivos_mod.reajuste_proposto(obj, checks, hoje)
        for m in proposta["movimentos"]:
            print(f"  {m['etapa']:<22} {m['de']} → {m['para']}  (+{m['dias']}d, {m['motivo']})")
        if not proposta["movimentos"]:
            print("  nada a reajustar: nenhuma etapa venceu sem check")
        print(f"\nfolga até o alvo: {proposta['folga_antes_em_dias']}d → "
              f"{proposta['folga_depois_em_dias']}d")
        if proposta["estoura_o_alvo"]:
            print("ESTOURA a data alvo")
        if not args.aplicar:
            print("\nnada foi gravado. Para aplicar: --aplicar --porque '...'")
            return
        if not args.porque:
            raise SystemExit("--aplicar exige --porque")
        objetivos_mod.aplicar_reajuste(obj, proposta, porque=args.porque, origem="usuario")
        loja.save()
        print(f"\naplicado em {ws.objetivos_path}")
        return

    planos = report.analyze(ws)["planos"] if ws.latest_canonical() else []
    for g in objetivos_mod.gauges(lista, checks, report.load_vida(ws), hoje,
                                  planos=planos)["objetivos"]:
        parcial = "" if g["peso_aplicado"] == g["peso_total"] else \
            f"  (sobre peso {g['peso_aplicado']} de {g['peso_total']})"
        print(f"{g['valor']:>5.1f}  {g['faixa']:<10} {g['rotulo']}{parcial}")
        print(f"        {g['legenda']} · próxima: {g['proxima_etapa'] or '—'} "
              f"({g['proximo_prazo'] or 'sem prazo'})")

    atrasadas = [i for i in objetivos_mod.agenda(lista, checks, hoje, dias=args.dias)
                 if i["situacao"] == "atrasada"]
    if atrasadas:
        print(f"\n{len(atrasadas)} etapa(s) atrasada(s):")
        for i in atrasadas:
            print(f"  {i['prazo']}  {i['titulo']} ({i['objetivo_titulo']})")

    for o in lista:
        if not o.assinado and not o.arquivado:
            print(f"\nrascunho esperando sua assinatura: {o.titulo} "
                  f"({len(o.etapas)} etapas)")


def cmd_config(args) -> None:
    """A aba de configuração: privacidade, dados, ligação com a IA e licenças.

    Com `--conferir`, só cruza os manifestos com a declaração de licenças e
    devolve código de saída 1 se divergirem — é o formato que serve ao portão
    de push e ao CI.
    """
    ws = _ws(args)
    raiz = Path(__file__).resolve().parent.parent

    if args.conferir:
        from .contracts import conferir_depositos

        dep = conferir_depositos(type(ws))
        if not dep["ok"]:
            print("REGISTRO DE DEPÓSITOS DESATUALIZADO:")
            for chave, rotulo in (
                ("no_codigo_e_nao_declarados", "existe no Workspace e não está declarado"),
                ("declarados_e_fora_do_codigo", "declarado e já não existe no código"),
                ("esquema_novo_sem_migrador", "esquema acima de 1 sem migrador"),
            ):
                for item in dep[chave]:
                    print(f"  {item}: {rotulo}")
            print()
            print(dep["como_corrigir"])
            raise SystemExit(1)
        print(f"ok: {dep['quantos']} depósitos declarados batem com o Workspace")

        r = lic_mod.conferir(raiz)
        if r["ok"]:
            c = r["conferidos"]
            print(f"ok: licenças conferem ({c['declarados']} declarados, "
                  f"{c['gradle']} do Gradle, {c['python']} do Python, "
                  f"{c['npm_que_embarca']} do npm que embarcam)")
            return
        print("LICENÇAS DESATUALIZADAS:")
        for chave, rotulo in (
            ("nao_declarados", "sem declaração de licença"),
            ("declarados_sem_uso", "declarados e já fora do projeto"),
            ("sem_licenca_conhecida", "licença que não sabemos tratar"),
            ("licenca_que_bloqueia", "copyleft forte — decisão de produto"),
        ):
            for item in r[chave]:
                print(f"  {item}: {rotulo}")
        print()
        print(r["como_corrigir"])
        raise SystemExit(1)

    if args.licencas:
        for c in lic_mod.inventario(raiz, args.superficie):
            v = f" {c['versao']}" if c["versao"] else ""
            print(f"{c['nome']}{v}  —  {c['licenca_nome']}")
            if c["url"]:
                print(f"    {c['url']}")
        return

    d = cfg_mod.montar(ws, raiz)
    priv = d["privacidade"]
    print(f"workspace: {d['app']['workspace']}")
    print(f"permissões do app: {', '.join(priv['permissoes_do_app']) or 'nenhuma'}")
    print(f"backup automático: {priv['backup_automatico']}")
    print()
    print(priv["resumo"])
    print()
    print("onde os seus dados moram:")
    for a in d["dados"]["arquivos"]:
        print(f"  {a['arquivo']}")
        print(f"      {a['guarda']}")
    print()
    print(f"licenças que embarcam no app: {len(d['licencas']['componentes'])}"
          f" (confere: {'sim' if d['licencas']['conferencia_ok'] else 'NÃO'})")
    print("o que não existe aqui: " + "; ".join(d["o_que_nao_existe_aqui"]))


def cmd_mcp_config(args) -> None:
    """Imprime a config do cliente MCP com os caminhos desta máquina.

    Existe porque a config genérica (`"command": "python"`) falha calado na
    maioria das instalações: o cliente sobe o servidor de um diretório
    qualquer, e o `python` do PATH quase nunca é o interpretador onde o
    fintips foi instalado — venv, pyenv, ou um Debian onde `python` sequer
    existe. O caminho absoluto de `sys.executable` não tem esse problema.
    """
    import sys

    ws = _ws(args)
    servidor = {
        "command": sys.executable,
        "args": ["-m", "fintips.mcp_server", "--root", str(ws.root)],
    }
    config = {"mcpServers": {args.nome: servidor}}

    if args.claude_code:
        print(f"claude mcp add-json {args.nome} '{json.dumps(servidor)}'")
        return

    print(json.dumps(config, ensure_ascii=False, indent=2))
    print(f"\n# interpretador: {sys.executable}", file=sys.stderr)
    print(f"# workspace:     {ws.root}", file=sys.stderr)
    print("#", file=sys.stderr)
    print("# Claude Desktop: cole em claude_desktop_config.json", file=sys.stderr)
    print("# Claude Code:    fintips mcp-config --claude-code", file=sys.stderr)


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
    pf.add_argument("--historico", action="store_true",
                    help="as travessias: onde ela deixou de ser uma coisa e virou outra")
    pf.add_argument("--retrato", action="store_true",
                    help="dinheiro, vida e compromissos numa leitura só")
    pf.add_argument("--eixo", help="filtra o histórico por eixo")
    pf.set_defaults(func=cmd_perfil)

    al = sub.add_parser("alavancas"); al.add_argument("--limite", type=int, default=8)
    al.set_defaults(func=cmd_alavancas)

    de = sub.add_parser("decisoes")
    de.add_argument("--abertas", action="store_true", help="só o que ainda não foi decidido")
    de.add_argument("--historico", metavar="ASSUNTO", help="precedentes parecidos com ASSUNTO")
    de.set_defaults(func=cmd_decisoes)

    ap = sub.add_parser("aparelho", help="catálogo de missões para o app Android")
    ap.add_argument("--saida", metavar="ARQUIVO", help="grava em vez de imprimir")
    ap.add_argument("--registros", metavar="JSONL",
                    help="absorve o histórico que voltou do aparelho")
    ap.add_argument("--exemplo", action="store_true",
                    help="exporta o molde do pacote em vez do seu catálogo "
                         "(para trabalhar na tela sem workspace)")
    ap.set_defaults(func=cmd_aparelho)

    ob = sub.add_parser("objetivos", help="objetivos, agenda e score")
    ob.add_argument("--dias", type=int, default=14, help="janela da agenda")
    ob.add_argument("--reajustar", metavar="ID",
                    help="calcula o reajuste de um objetivo (não aplica)")
    ob.add_argument("--aplicar", action="store_true",
                    help="grava o reajuste calculado; exige --porque")
    ob.add_argument("--porque", default="", help="o motivo do reajuste")
    ob.set_defaults(func=cmd_objetivos)

    cf = sub.add_parser("config", help="privacidade, dados, IA e licenças")
    cf.add_argument("--conferir", action="store_true",
                    help="cruza os manifestos com a declaração de licenças; sai 1 se divergir")
    cf.add_argument("--licencas", action="store_true", help="só as atribuições")
    cf.add_argument("--superficie", default="apk",
                    choices=list(lic_mod.SUPERFICIES), help="de que superfície")
    cf.set_defaults(func=cmd_config)

    mc = sub.add_parser("mcp-config")
    mc.add_argument("--nome", default="fintips", help="nome do servidor no cliente")
    mc.add_argument("--claude-code", action="store_true",
                    help="imprime o comando `claude mcp add-json` em vez do JSON")
    mc.set_defaults(func=cmd_mcp_config)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
