"""O dossiê: um artefato, dois consumidores.

O contexto completo de `report.analyze` tem tudo e por isso não serve para
começar conversa: mandar aquilo inteiro para um agente gasta milhares de
tokens antes da primeira pergunta, e a maior parte não vai ser usada. Mas
resumir escondendo o que existe é pior — o agente passa a supor.

A saída é separar densidade de conteúdo:

- **briefing** — orçado em tokens. O que o agente precisa saber antes de
  abrir a boca: quem é a pessoa (perfil assinado), o que ainda é palpite,
  os números que enquadram tudo, as causas ativas com a atitude tomada, as
  alavancas de maior efeito e o que está pendente. Cada bloco carrega o
  **id** e a **ferramenta que expande** — o agente busca o detalhe quando
  precisar, em vez de recebê-lo por precaução.
- **correlações** — as ligações explícitas entre causa, dinheiro,
  compromisso, plano e alavanca. É o que permite ao agente responder "esse
  tablet atrasa a viagem em 3 meses e aciona a causa que você mesmo
  descreveu" sem inferir a ligação do zero a cada conversa.
- **observações** (`observacoes.jsonl`) — uma linha por observação, schema
  estável, formato longo. `pd.read_json(lines=True)` devolve um dataframe, e
  nenhuma dependência nova entra no pacote. É a fatia que serve para análise
  fora daqui, e a que o painel usa para desenhar correlação.

O dossiê é **derivado**: some e é remontado a cada análise. Nada aqui é fonte
de verdade — a verdade continua nos YAML do `data/`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DOSSIER_SCHEMA = 1

# 4 caracteres por token é a regra de bolso que erra para o lado seguro em
# português. O orçamento existe para o briefing caber com folga em qualquer
# janela de contexto, não para ser exato.
CHARS_POR_TOKEN = 4
ORCAMENTO_PADRAO = 3500


def montar(ctx: dict, *, orcamento_tokens: int = ORCAMENTO_PADRAO) -> dict:
    """Monta o dossiê a partir do contexto único."""
    briefing = _briefing(ctx)
    briefing, cortes = _caber(briefing, orcamento_tokens)
    return {
        "schema_version": DOSSIER_SCHEMA,
        "cabecalho": _cabecalho(ctx),
        "briefing": briefing,
        "correlacoes": correlacoes(ctx),
        "orcamento": {
            "tokens_alvo": orcamento_tokens,
            "tokens_estimados": _tokens(briefing),
            "cortes": cortes,
            "nota": (
                "o briefing é resumo com ponteiro, não substituto do contexto. "
                "Cada bloco traz o id e a ferramenta que devolve o detalhe"
            ),
        },
    }


# --------------------------------------------------------------------------
# cabeçalho: o que enquadra qualquer leitura do resto
# --------------------------------------------------------------------------
def _cabecalho(ctx: dict) -> dict:
    perfil = ctx.get("perfil") or {}
    causas = (ctx.get("causas") or {}).get("cobertura") or {}
    classificacao = ctx.get("cobertura_da_classificacao") or {}
    return {
        "periodo": ctx.get("periodo"),
        "conciliacao": ctx.get("conciliacao"),
        "coberturas": {
            "classificacao_pct": classificacao.get("cobertura_pct", 0.0),
            "perfil_pct": (perfil.get("cobertura") or {}).get("pct", 0.0),
            "causal_pct": causas.get("cobertura_pct", 0.0),
            "como_ler": (
                "as três medem a mesma coisa em camadas diferentes: se o dinheiro "
                "está no balde certo, se alguém disse quem a pessoa é, e se alguém "
                "disse por que o dinheiro sai. Todas começam em 0%"
            ),
        },
        "aviso": (
            "nada aqui com origem 'heuristica' ou 'importacao' vale como verdade "
            "sobre a pessoa. Confirme conversando antes de tratar como fato"
        ),
    }


# --------------------------------------------------------------------------
# briefing
# --------------------------------------------------------------------------
def _briefing(ctx: dict) -> dict:
    base = ctx.get("baseline") or {}
    score = ctx.get("score") or {}
    estrutura = ctx.get("estrutura_de_custo") or {}
    projecao = ctx.get("projecao") or {}
    perfil = ctx.get("perfil") or {}
    causas = ctx.get("causas") or {}
    triagem = ctx.get("triagem") or {}

    assinados = [
        {
            "eixo": e["eixo"],
            "arquetipo": e["assinado"]["nome"],
            "porque": e["assinado"]["proveniencia"]["porque"],
            "origem": e["assinado"]["proveniencia"]["origem"],
        }
        for e in perfil.get("eixos") or []
        if e.get("assinado")
    ]
    palpites = [
        {
            "eixo": e["eixo"],
            "sugestao": e["sugerido"]["nome"],
            "aderencia": e["sugerido"]["aderencia"],
            "confirmar_antes_de_usar": True,
        }
        for e in perfil.get("eixos") or []
        if e.get("sugerido") and not e.get("assinado")
    ]

    ativas = [
        {
            "id": c["id"],
            "alvo": c["alvo"],
            "natureza": c["natureza"],
            "enunciado": c["enunciado"],
            "atitude": c["atitude"],
            "origem": c["proveniencia"]["origem"],
        }
        for c in causas.get("itens") or []
        if not c.get("vencida")
    ]

    pendente = triagem.get("resumo") or {}
    return {
        "quem_e": {
            "assinado": assinados,
            "ainda_palpite": palpites,
            "expandir_com": "perfil",
        },
        "numeros": {
            "renda_mes": base.get("renda_media_mes"),
            "despesa_mes": base.get("despesa_media_mes"),
            "sobra_mes": base.get("sobra_media_mes"),
            "comprometido_mes": estrutura.get("comprometido_mes"),
            "comprometido_pct_renda": estrutura.get("comprometido_pct_renda"),
            "patrimonio": (ctx.get("patrimonio") or {}).get("total"),
            "saldo_conta": ctx.get("saldo_conta"),
            "score": score.get("score"),
            "faixa": score.get("faixa"),
            "meses_de_reserva": (score.get("indicadores") or {}).get("meses_de_reserva"),
            "expandir_com": "analise_completa",
        },
        "porque_o_dinheiro_sai": {
            "causas_ativas": ativas,
            "sem_explicacao_pct": round(
                100 - ((causas.get("cobertura") or {}).get("cobertura_pct", 0.0)), 1
            ),
            "maiores_sem_causa": (causas.get("cobertura") or {}).get("maiores_sem_causa", [])[:4],
            "expandir_com": "listar_causas",
        },
        "para_onde_vai": {
            "reserva_fecha_em": (projecao.get("reserva") or {}).get("atingida_em"),
            "planos": [
                {"id": p["id"], "nome": p["nome"], "conclui_em": p.get("conclui_em")}
                for p in projecao.get("planos") or []
            ],
            "expandir_com": "projecao",
        },
        "o_que_esta_aberto": {
            "itens": pendente.get("abertos", 0),
            "impacto_mensal": pendente.get("impacto_mensal_em_aberto", 0),
            "primeiro": (pendente.get("primeiro") or {}).get("titulo"),
            "expandir_com": "triagem",
        },
    }


# --------------------------------------------------------------------------
# correlações: as arestas entre causa, dinheiro, compromisso, plano e alavanca
# --------------------------------------------------------------------------
def correlacoes(ctx: dict) -> list[dict]:
    """Ligações explícitas, para o agente atravessar em vez de inferir.

    Cada aresta diz o tipo da relação e, quando existe, quanto dinheiro por
    mês ela move. É o que sustenta uma frase como "essa compra aciona a causa
    que você descreveu e atrasa a viagem" sem o modelo reconstruir a ligação
    do zero em cada conversa.
    """
    arestas: list[dict] = []
    n_meses = max(len(ctx.get("meses") or []), 1)
    por_cat = ctx.get("por_categoria_total") or {}
    mensal_cat = {k: round(v / n_meses, 2) for k, v in por_cat.items()}

    for c in (ctx.get("causas") or {}).get("itens") or []:
        tipo, ref = c["efeito"]["tipo"], c["efeito"]["ref"]
        arestas.append({
            "de": c["id"], "de_tipo": "causa",
            "para": c["alvo"], "para_tipo": tipo,
            "relacao": "explica",
            "valor_mensal": mensal_cat.get(ref) if tipo == "categoria" else None,
            "atitude": c["atitude"],
            "vencida": c.get("vencida", False),
        })

    for f in ctx.get("custos_fixos") or []:
        base = f.get("base") or {}
        arestas.append({
            "de": f["id"], "de_tipo": "compromisso",
            "para": f"{base.get('tipo')}:{base.get('ref')}", "para_tipo": base.get("tipo"),
            "relacao": "compromete",
            "valor_mensal": f.get("valor_mensal"),
            "natureza": f.get("natureza"),
        })

    for p in (ctx.get("projecao") or {}).get("planos") or []:
        arestas.append({
            "de": p["id"], "de_tipo": "plano",
            "para": p.get("conclui_em") or "fora_da_janela", "para_tipo": "mes",
            "relacao": "conclui_em",
            "valor_mensal": None,
            "falta": p.get("falta_ao_fim"),
        })

    for i in (ctx.get("triagem") or {}).get("itens") or []:
        if i.get("estado") != "aberto":
            continue
        ev = i.get("evidencia") or {}
        alvo = (
            f"categoria:{ev['categoria']}" if ev.get("categoria")
            else f"contraparte:{ev['contraparte_id']}" if ev.get("contraparte_id")
            else f"chave:{ev['chave']}" if ev.get("chave")
            else "geral"
        )
        arestas.append({
            "de": i["id"], "de_tipo": "triagem",
            "para": alvo, "para_tipo": alvo.split(":")[0],
            "relacao": "pendente_sobre",
            "valor_mensal": i.get("impacto_mensal"),
            "tipo_do_item": i.get("tipo"),
        })

    return arestas


# --------------------------------------------------------------------------
# observações: formato longo, uma linha por observação
# --------------------------------------------------------------------------
CAMPOS = (
    "tipo", "id", "rotulo", "alvo", "valor", "valor_mensal", "unidade",
    "mes", "categoria", "contraparte", "natureza", "atitude",
    "origem", "confianca", "vencida", "nota",
)


def observacoes(ctx: dict) -> list[dict]:
    """Tudo que o motor sabe, achatado em linhas de schema estável.

    Formato longo (uma observação por linha) em vez de largo (uma coluna por
    métrica) porque as observações não compartilham colunas: um mês tem renda,
    uma causa tem natureza, uma alavanca tem efeito. Em formato largo isso
    vira uma tabela esparsa que ninguém consegue ler nem agregar.
    """
    linhas: list[dict] = []

    def add(**kw: Any) -> None:
        linha = {c: kw.get(c) for c in CAMPOS}
        linhas.append(linha)

    for m in ctx.get("meses") or []:
        for chave in ("renda", "despesa", "aportes", "resgates", "sobra"):
            add(tipo="mes", id=f"mes:{m['mes']}:{chave}", rotulo=chave,
                alvo=f"mes:{m['mes']}", valor=m.get(chave), unidade="BRL", mes=m["mes"],
                origem="importacao")
        for cat, valor in (m.get("por_categoria") or {}).items():
            add(tipo="gasto_mes_categoria", id=f"mes:{m['mes']}:cat:{cat}", rotulo=cat,
                alvo=f"categoria:{cat}", valor=valor, unidade="BRL", mes=m["mes"],
                categoria=cat, origem="importacao")

    for cp in ctx.get("contrapartes") or []:
        add(tipo="contraparte", id=cp.get("id"), rotulo=cp.get("nome"),
            alvo=f"contraparte:{cp.get('id')}", valor=cp.get("total"),
            valor_mensal=cp.get("por_mes"), unidade="BRL",
            contraparte=cp.get("nome"), categoria=cp.get("categoria"),
            origem="importacao", nota=cp.get("cadencia"))

    for f in ctx.get("custos_fixos") or []:
        base = f.get("base") or {}
        add(tipo="compromisso", id=f["id"], rotulo=f.get("rotulo"),
            alvo=f"{base.get('tipo')}:{base.get('ref')}",
            valor=f.get("valor_anual"), valor_mensal=f.get("valor_mensal"), unidade="BRL",
            natureza=f.get("natureza"),
            origem=(f.get("proveniencia") or {}).get("origem"),
            confianca=(f.get("proveniencia") or {}).get("confianca"))

    for c in (ctx.get("causas") or {}).get("itens") or []:
        add(tipo="causa", id=c["id"], rotulo=c["enunciado"], alvo=c["alvo"],
            natureza=c.get("natureza"), atitude=c.get("atitude"),
            vencida=c.get("vencida"),
            categoria=c["efeito"]["ref"] if c["efeito"]["tipo"] == "categoria" else None,
            origem=(c.get("proveniencia") or {}).get("origem"),
            confianca=(c.get("proveniencia") or {}).get("confianca"),
            nota=(c.get("proveniencia") or {}).get("porque"))

    for e in (ctx.get("perfil") or {}).get("eixos") or []:
        if e.get("assinado"):
            a = e["assinado"]
            add(tipo="perfil_traco", id=f"perfil:{e['eixo']}", rotulo=a["nome"],
                alvo=f"eixo:{e['eixo']}",
                origem=a["proveniencia"]["origem"], confianca=a["proveniencia"]["confianca"],
                nota=a["proveniencia"]["porque"])
        elif e.get("sugerido"):
            add(tipo="perfil_sugestao", id=f"perfil:{e['eixo']}", rotulo=e["sugerido"]["nome"],
                alvo=f"eixo:{e['eixo']}", valor=e["sugerido"]["aderencia"], unidade="aderencia",
                origem="importacao", nota="palpite: confirmar antes de usar")

    for d in (ctx.get("score") or {}).get("dimensoes") or []:
        add(tipo="score_dimensao", id=f"score:{d['nome']}", rotulo=d["nome"],
            alvo="score", valor=d["pontos"], unidade="pontos",
            origem="importacao", nota=f"máximo {d['maximo']}")

    for p in ctx.get("planos") or []:
        add(tipo="plano", id=p["id"], rotulo=p.get("nome"), alvo=f"plano:{p['id']}",
            valor=p.get("custo_alvo"), valor_mensal=p.get("aporte_necessario_mes"),
            unidade="BRL", origem="usuario", nota=p.get("status"))

    for i in (ctx.get("triagem") or {}).get("itens") or []:
        add(tipo="triagem", id=i["id"], rotulo=i.get("titulo"), alvo=i.get("tipo"),
            valor_mensal=i.get("impacto_mensal"), unidade="BRL",
            origem="importacao", nota=i.get("estado"))

    return linhas


# --------------------------------------------------------------------------
# orçamento de tokens
# --------------------------------------------------------------------------
def _tokens(obj: Any) -> int:
    return len(json.dumps(obj, ensure_ascii=False)) // CHARS_POR_TOKEN


def _caber(briefing: dict, orcamento: int) -> tuple[dict, list[str]]:
    """Corta o briefing até caber, na ordem do que é mais dispensável.

    A ordem não é arbitrária: sai primeiro o que o agente consegue buscar
    depois com uma chamada barata, e nunca sai o perfil assinado nem as causas
    com atitude — é o que muda a conversa desde a primeira frase.
    """
    cortes: list[str] = []
    reducoes = [
        ("maiores_sem_causa", lambda b: b["porque_o_dinheiro_sai"].__setitem__(
            "maiores_sem_causa", b["porque_o_dinheiro_sai"]["maiores_sem_causa"][:2])),
        ("planos", lambda b: b["para_onde_vai"].__setitem__(
            "planos", b["para_onde_vai"]["planos"][:3])),
        ("ainda_palpite", lambda b: b["quem_e"].__setitem__(
            "ainda_palpite", b["quem_e"]["ainda_palpite"][:2])),
        ("causas_sem_atitude", lambda b: b["porque_o_dinheiro_sai"].__setitem__(
            "causas_ativas",
            [c for c in b["porque_o_dinheiro_sai"]["causas_ativas"] if c["atitude"] != "nenhuma"]
            or b["porque_o_dinheiro_sai"]["causas_ativas"][:3])),
    ]
    for nome, reduzir in reducoes:
        if _tokens(briefing) <= orcamento:
            break
        reduzir(briefing)
        cortes.append(nome)
    return briefing, cortes


# --------------------------------------------------------------------------
# io
# --------------------------------------------------------------------------
def salvar(relatorios: str | Path, ctx: dict, *, orcamento_tokens: int = ORCAMENTO_PADRAO) -> dict:
    """Grava dossie.json e observacoes.jsonl. Ambos derivados e descartáveis."""
    destino = Path(relatorios)
    destino.mkdir(parents=True, exist_ok=True)

    dossie = montar(ctx, orcamento_tokens=orcamento_tokens)
    caminho_json = destino / "dossie.json"
    caminho_json.write_text(
        json.dumps(dossie, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    linhas = observacoes(ctx)
    caminho_jsonl = destino / "observacoes.jsonl"
    caminho_jsonl.write_text(
        "\n".join(json.dumps(l, ensure_ascii=False, default=str) for l in linhas) + "\n",
        encoding="utf-8",
    )
    return {
        "dossie": str(caminho_json),
        "observacoes": str(caminho_jsonl),
        "linhas": len(linhas),
        "tokens_do_briefing": dossie["orcamento"]["tokens_estimados"],
    }
