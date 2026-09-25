"""Triagem: a fila de decisões que o agente conduz e o usuário assina.

O app não decide nada aqui — ele **calcula o que está em aberto e quanto custa
deixar em aberto**, em reais por mês. O agente pega a fila, investiga com as
ferramentas, pergunta ao usuário o que for preciso e grava a decisão. Na
próxima importação a fila é recalculada: o que foi decidido não volta.

Tipos de item:

- `contraparte_nova`        — apareceu no extrato e ninguém classificou
- `classificacao_fraca`     — está classificada só por heurística, e pesa dinheiro
- `candidato_custo_fixo`    — o padrão parece fixo, mas ninguém confirmou
- `custo_fixo_derivou`      — o valor declarado não bate mais com o observado
- `fato_ausente`            — falta uma peça do núcleo do contexto
- `fato_vencido`            — uma informação com prazo expirou
- `evento_sem_explicacao`   — movimento grande e atípico sem nota
"""

from __future__ import annotations

import statistics
from datetime import date
from pathlib import Path

import yaml

from .causes import CauseStore
from .decisions import DecisionStore
from .contracts import ItemDeTriagem, agora, novo_id
from .context import ContextStore
from .entities import Counterparty
from .models import Statement

TRIAGE_SCHEMA = 1


class TriageStore:
    """Guarda o que já foi resolvido ou adiado, para a fila não repetir."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.resolvidos: dict[str, dict] = {}
        self.sessoes: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        self.resolvidos = data.get("resolvidos") or {}
        self.sessoes = data.get("sessoes") or []

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": TRIAGE_SCHEMA,
                    "atualizado_em": agora(),
                    "resolvidos": self.resolvidos,
                    "sessoes": self.sessoes[-20:],
                },
                allow_unicode=True, sort_keys=False,
            ),
            encoding="utf-8",
        )

    def resolver(self, item_id: str, resolucao: dict, *, estado: str = "resolvido") -> dict:
        registro = {"estado": estado, "quando": agora(), "resolucao": resolucao}
        self.resolvidos[item_id] = registro
        self.save()
        return registro

    def adiar(self, item_id: str, motivo: str = "") -> dict:
        return self.resolver(item_id, {"motivo": motivo}, estado="adiado")

    def estado(self, item_id: str) -> dict | None:
        return self.resolvidos.get(item_id)

    def abrir_sessao(self, gatilho: str, n_itens: int) -> dict:
        s = {"id": novo_id("t", agora()), "gatilho": gatilho,
             "aberta_em": agora(), "itens_na_abertura": n_itens}
        self.sessoes.append(s)
        self.save()
        return s


# --------------------------------------------------------------------------
# construção da fila
# --------------------------------------------------------------------------

def construir(
    stmt: Statement,
    cps: list[Counterparty],
    *,
    base: dict,
    ctx_store: ContextStore,
    custos_fixos: list[dict],
    candidatos_fixos: list[dict],
    store: TriageStore,
    causas: "CauseStore | None" = None,
    decisoes: "DecisionStore | None" = None,
    fallback: str = "outros",
    limite: int = 40,
) -> list[ItemDeTriagem]:
    itens: list[ItemDeTriagem] = []
    n_meses = max(len({t.month for t in stmt.transactions}), 1)

    # 1. contrapartes que ninguém classificou
    for c in cps:
        if c.category != fallback or c.kind == "self":
            continue
        itens.append(ItemDeTriagem(
            id=novo_id("cp", c.id),
            tipo="contraparte_nova",
            titulo=f"{c.display} — sem categoria",
            impacto_mensal=float(c.monthly_cost),
            porque_importa=(
                "enquanto estiver em 'outros', esse dinheiro não entra em nenhuma "
                "análise de categoria nem pode virar custo fixo"
            ),
            evidencia={
                "contraparte_id": c.id, "transacoes": c.n_tx, "meses": c.months,
                "valor_tipico": float(c.median_amount), "cadencia": c.cadence,
                "tipo": c.kind, "variacoes": c.aliases[:5],
            },
        ))

    # 2. dinheiro classificado só por palpite
    por_cat_heuristica: dict[str, float] = {}
    for t in stmt.transactions:
        if t.flow != "expense" or t.category == fallback:
            continue
        if t.category_source in ("usuario", "agente"):
            continue
        por_cat_heuristica[t.category] = por_cat_heuristica.get(t.category, 0) + abs(float(t.amount))
    for cat, total in por_cat_heuristica.items():
        mensal = total / n_meses
        if mensal < 40:
            continue
        itens.append(ItemDeTriagem(
            id=novo_id("cf", cat),
            tipo="classificacao_fraca",
            titulo=f"{cat}: {mensal:.0f}/mês classificados só por heurística",
            impacto_mensal=mensal,
            porque_importa=(
                "a lista embutida no pacote é palpite, não conhecimento sobre você; "
                "enquanto ninguém confirmar, qualquer conclusão sobre essa categoria "
                "carrega o erro do palpite"
            ),
            evidencia={"categoria": cat, "total_periodo": round(total, 2)},
        ))

    # 3. candidatos a custo fixo (detectados, não definidos)
    definidos = {f.get("base", {}).get("ref") for f in custos_fixos}
    for cand in candidatos_fixos:
        ref = cand.get("chave")
        if ref in definidos:
            continue
        itens.append(ItemDeTriagem(
            id=novo_id("cx", str(ref)),
            tipo="candidato_custo_fixo",
            titulo=f"{cand.get('rotulo')} parece previsível ({cand.get('por_mes'):.0f}/mês)",
            impacto_mensal=float(cand.get("por_mes", 0)),
            porque_importa=(
                "custo fixo entra na projeção como compromisso e sai do relatório de "
                "gasto invisível; o padrão sugere previsibilidade, mas só você sabe "
                "se é compromisso ou coincidência"
            ),
            evidencia=cand,
            sugestao={"natureza": cand.get("natureza"), "valor_mensal": cand.get("por_mes"),
                      "origem_da_sugestao": "heuristica"},
        ))

    # 4. custo fixo declarado que não bate mais com o observado
    for f in custos_fixos:
        obs = _observado(stmt, f, n_meses)
        declarado = float(f.get("valor_mensal", 0))
        if obs is None or declarado <= 0:
            continue
        deriva = abs(obs - declarado) / declarado
        if deriva < 0.25:
            continue
        itens.append(ItemDeTriagem(
            id=novo_id("dr", f["id"], f"{obs:.0f}"),
            tipo="custo_fixo_derivou",
            titulo=f"{f['rotulo']}: declarado {declarado:.0f}, observado {obs:.0f}/mês",
            impacto_mensal=abs(obs - declarado),
            porque_importa=(
                "a projeção usa o valor declarado; se a vida mudou, a projeção está "
                "descrevendo um mês que não existe mais"
            ),
            evidencia={"custo_fixo_id": f["id"], "declarado": declarado,
                       "observado": round(obs, 2), "deriva_pct": round(deriva * 100, 1)},
        ))

    # 5. lacunas do contexto
    for lac in ctx_store.lacunas(base):
        itens.append(ItemDeTriagem(
            id=novo_id("ft", lac["chave"]),
            tipo="fato_vencido" if lac["o_que_e"].startswith("fato vencido") else "fato_ausente",
            titulo=f"contexto: {lac['chave']}",
            impacto_mensal=lac["impacto_estimado_mes"],
            porque_importa=lac["porque_importa"],
            evidencia={"chave": lac["chave"], "o_que_e": lac["o_que_e"],
                       "tipo": lac["tipo"], "opcoes": lac["opcoes"], "afeta": lac["afeta"]},
        ))

    # 6. dinheiro que sai sem ninguém saber por quê
    #
    # Note a diferença para o item 2: lá o gasto está no balde errado, aqui ele
    # pode estar no balde certo e ainda assim ninguém sabe o motivo. Classificar
    # delivery como "alimentacao" não explica por que ele acontece toda terça.
    if causas is not None:
        cob = causas.cobertura(stmt)
        for linha in cob["maiores_sem_causa"]:
            if linha["por_mes"] < 20:
                continue  # abaixo disso a pergunta custa mais atenção do que rende
            itens.append(ItemDeTriagem(
                id=novo_id("ca", "categoria", linha["categoria"]),
                tipo="causa_ausente",
                titulo=f"sem causa: {linha['categoria']}",
                impacto_mensal=linha["por_mes"],
                porque_importa=(
                    "o valor está classificado, mas ninguém escreveu por que esse "
                    "dinheiro sai. Sem isso, qualquer sugestão de corte é chute — e "
                    "o consultor de compras não tem com o que comparar uma compra nova"
                ),
                evidencia={"categoria": linha["categoria"], "por_mes": linha["por_mes"],
                           "total_no_periodo": linha["total"]},
            ))

        for c in causas.vencidas():
            itens.append(ItemDeTriagem(
                id=novo_id("cr", c.id),
                tipo="causa_a_revisar",
                titulo=f"revisar causa: {c.enunciado[:60]}",
                impacto_mensal=0.0,
                porque_importa=(
                    "causa de comportamento envelhece: o prazo de revisão venceu, e "
                    "continuar calculando sobre ela é supor que a vida não mudou"
                ),
                evidencia={"causa_id": c.id, "alvo": c.alvo, "natureza": c.natureza,
                           "atitude": c.atitude, "revisar_em": c.revisar_em},
            ))

        for c in causas.sem_atitude():
            itens.append(ItemDeTriagem(
                id=novo_id("cd", c.id),
                tipo="causa_sem_atitude",
                titulo=f"decidir sobre: {c.enunciado[:60]}",
                impacto_mensal=0.0,
                porque_importa=(
                    "a causa está entendida e nada foi decidido. Entender sem decidir "
                    "é diagnóstico sem tratamento — inclusive 'aceitar' é uma decisão, "
                    "e tira o gasto da lista de culpa"
                ),
                evidencia={"causa_id": c.id, "alvo": c.alvo, "natureza": c.natureza},
            ))

    # 6b. bifurcações em aberto, e escolhas cujo resultado ninguém registrou
    #
    # Nenhum destes tem impacto em reais calculável — o custo de não decidir a
    # troca do celular não está no extrato, está na vida. Eles entram pelo peso
    # do tipo, e o valor em reais carrega o que a escolha custa quando existe,
    # para a fila não os tratar como se fossem de graça.
    if decisoes is not None:
        for d in decisoes.abertas():
            maior = max((a.custo for a in d.alternativas), default=0.0)
            itens.append(ItemDeTriagem(
                id=novo_id("da", d.id),
                tipo="decisao_aberta",
                titulo=f"decidir: {d.titulo[:60]}",
                impacto_mensal=round(maior / 12, 2),
                porque_importa=(
                    "a pergunta está registrada e a resposta não. Enquanto isso, o "
                    "dinheiro fica parado esperando ou sai sem que ninguém tenha "
                    "comparado as alternativas que já foram escritas"
                ),
                evidencia={"decisao_id": d.id, "pergunta": d.pergunta,
                           "alternativas": [a.nome for a in d.alternativas]},
            ))

        for d in decisoes.sem_desfecho():
            itens.append(ItemDeTriagem(
                id=novo_id("dd", d.id),
                tipo="decisao_sem_desfecho",
                titulo=f"no que deu: {d.titulo[:60]}",
                impacto_mensal=0.0,
                porque_importa=(
                    "decisão sem desfecho é história, não aprendizado: a próxima "
                    "escolha parecida vai ser feita do zero. E ainda dá para lembrar "
                    "por que esta foi tomada"
                ),
                evidencia={"decisao_id": d.id, "escolheu": d.escolhida,
                           "decidido_em": d.decidido_em, "custo": d.custo_da_escolha},
            ))

        for d in decisoes.a_revisar():
            itens.append(ItemDeTriagem(
                id=novo_id("dr", d.id),
                tipo="decisao_a_revisar",
                titulo=f"revisar decisão: {d.titulo[:60]}",
                impacto_mensal=0.0,
                porque_importa=(
                    "o prazo que a própria decisão pediu para ser reaberta venceu — "
                    "era o momento de conferir se a escolha ainda serve"
                ),
                evidencia={"decisao_id": d.id, "revisar_em": d.revisar_em,
                           "escolheu": d.escolhida or "— ainda aberta"},
            ))

    # 7. eventos grandes sem explicação
    for t in sorted(stmt.transactions, key=lambda x: abs(x.amount), reverse=True)[:40]:
        if abs(float(t.amount)) < 800 or t.flow not in ("expense", "transfer"):
            continue
        itens.append(ItemDeTriagem(
            id=novo_id("ev", t.id),
            tipo="evento_sem_explicacao",
            titulo=f"{t.day.isoformat()}: {float(t.amount):.2f} com {t.counterparty}",
            impacto_mensal=abs(float(t.amount)) / n_meses,
            porque_importa=(
                "evento único fica fora da linha de base; se for recorrente ou "
                "parcelado, precisa entrar antes de você planejar sobre uma sobra "
                "que não existe"
            ),
            evidencia={"transacao_id": t.id, "data": t.day.isoformat(),
                       "valor": float(t.amount), "fluxo": t.flow,
                       "contraparte": t.counterparty, "categoria": t.category},
        ))

    # o que já foi decidido não volta para a fila
    vivos = []
    for it in itens:
        reg = store.estado(it.id)
        if reg and reg.get("estado") == "resolvido":
            continue
        if reg and reg.get("estado") == "adiado":
            it.estado = "adiado"
        vivos.append(it)

    vivos.sort(key=lambda i: (i.estado == "adiado", -i.prioridade))
    return vivos[:limite]


def _observado(stmt: Statement, fixo: dict, n_meses: int) -> float | None:
    """Quanto a base do custo fixo realmente gastou por mês, em meses completos."""
    base = fixo.get("base") or {}
    tipo, ref = base.get("tipo"), base.get("ref")
    if tipo not in ("categoria", "contraparte"):
        return None
    por_mes: dict[str, float] = {}
    for t in stmt.transactions:
        if t.flow != "expense":
            continue
        chave = t.category if tipo == "categoria" else t.counterparty
        if chave != ref:
            continue
        por_mes[t.month] = por_mes.get(t.month, 0) + abs(float(t.amount))
    if len(por_mes) < 2:
        return None
    return float(statistics.median(list(por_mes.values())))


def resumo(itens: list[ItemDeTriagem]) -> dict:
    abertos = [i for i in itens if i.estado == "aberto"]
    por_tipo: dict[str, int] = {}
    for i in abertos:
        por_tipo[i.tipo] = por_tipo.get(i.tipo, 0) + 1
    return {
        "abertos": len(abertos),
        "adiados": len(itens) - len(abertos),
        "por_tipo": por_tipo,
        "impacto_mensal_em_aberto": round(sum(abs(i.impacto_mensal) for i in abertos), 2),
        "primeiro": abertos[0].to_dict() if abertos else None,
    }
