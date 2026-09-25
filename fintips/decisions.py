"""Decisões: a bifurcação, o que se considerou, e no que deu.

O motor já guardava o **quanto** (baseline, projeção), o **onde** (categoria,
contraparte) e o **porquê** recorrente (causas). Faltava o momento em que
alguém parou e escolheu — e é o que mais depressa se perde.

O celular quebra numa terça. Você considera consertar por R$ 700, trocar por
R$ 2.500 ou aguentar o aparelho antigo mais um semestre. Escolhe uma, e três
meses depois já não lembra que a assistência não cobria a placa, nem que
naquela semana a reserva estava em quatro meses e não em seis. Quando a mesma
pergunta voltar — e ela volta, com o notebook, com a geladeira, com o carro —
a conta é refeita do zero, com o mesmo esforço e sem o que se aprendeu.

Três decisões de projeto sustentam este módulo:

**Registra-se a pergunta, não só a resposta.** As alternativas descartadas
ficam gravadas com o motivo do descarte. "Comprei um celular novo" não informa
nada no futuro; "descartei o conserto porque não davam garantia da placa"
evita reabrir a mesma investigação.

**Os números ficam congelados.** `instantaneo` guarda o que o motor via no dia:
sobra, excedente sobre a reserva, score, planos em risco. É a única parte que o
app preenche sozinho, porque é a única que ele sabe — e é o que separa "decidi
errado" de "as condições eram outras". Sem isso, todo registro antigo vira
julgamento injusto do passado.

**Aprendizado exige desfecho.** Uma decisão sem `desfecho` é história, não
aprendizado: a fila de revisão cobra o veredito depois, e `cedo_para_saber` é
resposta válida — a decisão volta para a fila em vez de virar conclusão falsa.

Como nas causas, aqui não existe detecção. Nenhuma função deste módulo olha o
extrato e conclui que houve uma decisão: escolha nasce de `agente` ou
`usuario`, sempre. O extrato mostra que saíram R$ 2.500 numa loja de
eletrônicos; ele não sabe se foi troca planejada, emergência ou presente.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from .categorize import norm
from .contracts import (
    STATUS_DECISAO,
    TIPOS_DECISAO,
    VEREDITOS,
    Alternativa,
    Decisao,
    Proveniencia,
    agora,
    novo_id,
)

DECISIONS_SCHEMA = 1

# Depois de quantos meses uma decisão sem desfecho entra na fila de revisão.
# Três meses é tempo de o arrependimento aparecer e ainda se lembrar do porquê.
MESES_ATE_COBRAR_DESFECHO = 3


class DecisionStore:
    """Decisões gravadas, indexadas pelo que elas afetam."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.decisoes: dict[str, Decisao] = {}
        self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> None:
        if not self.path.exists():
            return
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        for d in data.get("decisoes") or []:
            self.decisoes[d["id"]] = Decisao.from_dict(d)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ordenadas = sorted(self.decisoes.values(), key=lambda d: d.criado_em, reverse=True)
        self.path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": DECISIONS_SCHEMA,
                    "atualizado_em": agora(),
                    "decisoes": [d.to_dict() for d in ordenadas],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    # -------------------------------------------------------------- escrita
    def abrir(
        self,
        *,
        titulo: str,
        situacao: str,
        pergunta: str,
        alternativas: list[dict],
        proveniencia: Proveniencia,
        tipo: str = "outro",
        ligacoes: list[str] | None = None,
        instantaneo: dict | None = None,
        revisar_em: str | None = None,
        substitui: str | None = None,
    ) -> Decisao:
        """Abre o registro com a pergunta e os caminhos, antes de escolher.

        Abrir antes de decidir não é burocracia: é o que garante que as
        alternativas sejam escritas enquanto ainda são alternativas de verdade.
        Listadas depois da escolha, elas viram justificativa — a pessoa lembra
        das opções que reforçam o que ela já fez.
        """
        if not proveniencia.e_verdade:
            raise ValueError(
                "decisão só aceita origem 'agente' ou 'usuario'. O extrato mostra o "
                "dinheiro saindo, nunca a escolha que o fez sair"
            )
        if not proveniencia.porque:
            raise ValueError("abrir uma decisão exige `porque` — o que trouxe essa pergunta agora")
        if not situacao.strip():
            raise ValueError("decisão sem situação é um título; escreva o que aconteceu")
        if not pergunta.strip():
            raise ValueError("decisão sem pergunta não é decisão; escreva o que precisa ser escolhido")
        if tipo not in TIPOS_DECISAO:
            raise ValueError(f"tipo deve ser um de {TIPOS_DECISAO}")
        alts = [Alternativa.from_dict(a) for a in alternativas or []]
        if len(alts) < 2:
            raise ValueError(
                "uma decisão precisa de pelo menos duas alternativas — com uma só não "
                "houve escolha, e não sobra o que comparar na próxima vez"
            )

        did = novo_id("dec", titulo, pergunta, agora())
        dec = Decisao(
            id=did,
            titulo=titulo.strip(),
            situacao=situacao.strip(),
            pergunta=pergunta.strip(),
            tipo=tipo,
            alternativas=alts,
            ligacoes=list(ligacoes or []),
            instantaneo=instantaneo or {},
            revisar_em=revisar_em,
            substitui=substitui,
            proveniencia=proveniencia,
        )
        self.decisoes[did] = dec
        if substitui and substitui in self.decisoes:
            anterior = self.decisoes[substitui]
            anterior.substituida_por = did
            anterior.status = "substituida"
        self.save()
        return dec

    def escolher(self, decisao_id: str, alternativa: str, porque: str,
                 *, revisar_em: str | None = None) -> Decisao:
        """Registra qual caminho foi tomado, e por quê."""
        dec = self._exige(decisao_id)
        if not porque.strip():
            raise ValueError("escolher exige `porque` — sem ele o registro não ensina nada depois")
        if not any(a.nome == alternativa for a in dec.alternativas):
            nomes = [a.nome for a in dec.alternativas]
            raise ValueError(f"'{alternativa}' não está entre as alternativas: {nomes}")
        dec.escolhida = alternativa
        dec.porque = porque.strip()
        dec.status = "decidida"
        dec.decidido_em = agora()
        if revisar_em:
            dec.revisar_em = revisar_em
        self.save()
        return dec

    def registrar_desfecho(self, decisao_id: str, veredito: str, nota: str = "",
                           *, custo_real: float | None = None) -> Decisao:
        """No que deu. É isto que vira histórico utilizável."""
        if veredito not in VEREDITOS:
            raise ValueError(f"veredito deve ser um de {VEREDITOS}")
        dec = self._exige(decisao_id)
        if dec.status == "aberta":
            raise ValueError("não há desfecho de decisão que ainda não foi tomada")
        dec.desfecho = {
            "veredito": veredito,
            "nota": nota,
            "custo_real": round(float(custo_real), 2) if custo_real is not None else None,
            "em": agora(),
        }
        # `cedo_para_saber` não fecha: a decisão continua na fila de revisão,
        # que é exatamente o ponto de existir esse veredito.
        dec.status = "revisada" if veredito != "cedo_para_saber" else dec.status
        self.save()
        return dec

    def esquecer(self, decisao_id: str) -> bool:
        if decisao_id in self.decisoes:
            del self.decisoes[decisao_id]
            self.save()
            return True
        return False

    def _exige(self, decisao_id: str) -> Decisao:
        dec = self.decisoes.get(decisao_id)
        if not dec:
            raise ValueError(f"decisão '{decisao_id}' não existe")
        return dec

    # -------------------------------------------------------------- leitura
    def abertas(self) -> list[Decisao]:
        return [d for d in self.decisoes.values() if d.status == "aberta"]

    def vigentes(self) -> list[Decisao]:
        """Decididas e ainda valendo — não substituídas por outra."""
        return [d for d in self.decisoes.values() if d.status in ("decidida", "revisada")]

    def a_revisar(self, hoje: date | None = None) -> list[Decisao]:
        return [d for d in self.decisoes.values()
                if d.status in ("decidida", "aberta") and d.vencida(hoje)]

    def sem_desfecho(self, hoje: date | None = None) -> list[Decisao]:
        """Decididas há tempo suficiente e ainda sem veredito registrado."""
        limite = _meses_atras(MESES_ATE_COBRAR_DESFECHO, hoje)
        out = []
        for d in self.decisoes.values():
            if d.status != "decidida" or d.aprendeu or not d.decidido_em:
                continue
            if d.decidido_em[:10] <= limite:
                out.append(d)
        return out

    def to_dicts(self) -> list[dict]:
        return [d.to_dict() for d in
                sorted(self.decisoes.values(), key=lambda d: d.criado_em, reverse=True)]

    def linha_do_tempo(self) -> list[dict]:
        """O histórico enxuto, do mais recente para o mais antigo."""
        out = []
        for d in sorted(self.decisoes.values(), key=lambda x: x.criado_em, reverse=True):
            out.append({
                "id": d.id,
                "quando": (d.decidido_em or d.criado_em)[:10],
                "titulo": d.titulo,
                "tipo": d.tipo,
                "escolheu": d.escolhida or "— ainda aberta",
                "custo": d.custo_da_escolha,
                "deu_em": (d.desfecho or {}).get("veredito") or "sem desfecho",
                "status": d.status,
            })
        return out

    # ------------------------------------------------------------ histórico
    def semelhantes(self, assunto: str, *, tipo: str = "", ligacoes: list[str] | None = None,
                    limite: int = 5) -> list[dict]:
        """Decisões passadas que se parecem com a que está sendo tomada agora.

        A semelhança é rasa de propósito — casa texto, tipo e ligação, e não
        tenta adivinhar analogia. Um falso positivo aqui custa uma linha a mais
        no contexto do agente; um falso negativo esconde justamente o registro
        que existia para não repetir o erro.
        """
        alvo = norm(assunto)
        termos = [t for t in alvo.split() if len(t) > 3]
        refs = set(ligacoes or [])
        achados: list[tuple[int, Decisao]] = []
        for d in self.decisoes.values():
            peso = 0
            texto = norm(" ".join([d.titulo, d.situacao, d.pergunta,
                                   " ".join(a.nome for a in d.alternativas)]))
            peso += sum(2 for t in termos if t in texto)
            if tipo and d.tipo == tipo:
                peso += 3
            peso += 3 * len(refs & set(d.ligacoes))
            if peso:
                # o que já ensinou alguma coisa vale mais que o que ainda não
                peso += 2 if d.aprendeu else 0
                achados.append((peso, d))

        achados.sort(key=lambda p: (p[0], p[1].criado_em), reverse=True)
        return [_como_precedente(d) for _, d in achados[:limite]]

    def aprendizados(self) -> dict:
        """O que o histórico permite afirmar — e só isso.

        Os números saem de decisões que a pessoa mesma julgou. Não há inferência
        de arrependimento a partir do extrato: gastar de novo na mesma categoria
        não é arrependimento, e não gastar não é acerto.
        """
        com_desfecho = [d for d in self.decisoes.values() if d.aprendeu]
        por_tipo: dict[str, dict] = {}
        for d in com_desfecho:
            alvo = por_tipo.setdefault(d.tipo, {"decisoes": 0, "arrependi": 0, "funcionou": 0})
            alvo["decisoes"] += 1
            v = d.desfecho["veredito"]
            if v in ("arrependi", "funcionou"):
                alvo[v] += 1
        for alvo in por_tipo.values():
            alvo["taxa_arrependimento_pct"] = round(
                alvo["arrependi"] / alvo["decisoes"] * 100, 1) if alvo["decisoes"] else 0.0

        total = len(self.decisoes)
        return {
            "decisoes_registradas": total,
            "abertas": len(self.abertas()),
            "com_desfecho": len(com_desfecho),
            "sem_desfecho": len(self.sem_desfecho()),
            "a_revisar": len(self.a_revisar()),
            "cobertura_de_desfecho_pct": (
                round(len(com_desfecho) / len([d for d in self.decisoes.values()
                                               if d.status != "aberta"]) * 100, 1)
                if any(d.status != "aberta" for d in self.decisoes.values()) else 0.0
            ),
            "por_tipo": por_tipo,
            "arrependimentos": [
                {"id": d.id, "titulo": d.titulo, "escolheu": d.escolhida,
                 "custo": d.custo_da_escolha, "nota": d.desfecho.get("nota", ""),
                 "quando": (d.decidido_em or d.criado_em)[:10]}
                for d in com_desfecho if d.desfecho["veredito"] == "arrependi"
            ],
            "explicacao": (
                "tudo aqui vem de desfecho que a própria pessoa registrou. O motor "
                "não deduz arrependimento do extrato — comprar de novo na mesma "
                "categoria não prova nada sobre a compra anterior"
            ),
        }


def _como_precedente(d: Decisao) -> dict:
    """Uma decisão passada apresentada como o que ela é: precedente, não regra."""
    descartadas = [
        {"nome": a.nome, "descartada_porque": a.descartada_porque, "custo": a.custo}
        for a in d.alternativas
        if a.nome != d.escolhida and a.descartada_porque
    ]
    return {
        "id": d.id,
        "quando": (d.decidido_em or d.criado_em)[:10],
        "titulo": d.titulo,
        "tipo": d.tipo,
        "situacao": d.situacao,
        "escolheu": d.escolhida,
        "porque": d.porque,
        "custo": d.custo_da_escolha,
        "descartou": descartadas,
        "numeros_da_epoca": d.instantaneo,
        "deu_em": (d.desfecho or {}).get("veredito") or "sem desfecho registrado",
        "nota_do_desfecho": (d.desfecho or {}).get("nota", ""),
        "como_usar": (
            "precedente, não regra: as condições da época estão em `numeros_da_epoca` "
            "e podem não ser as de hoje. Traga a frase dela, não um veredito seu"
        ),
    }


def _meses_atras(n: int, hoje: date | None = None) -> str:
    h = hoje or date.today()
    ano, mes = h.year, h.month - n
    while mes <= 0:
        mes += 12
        ano -= 1
    return date(ano, mes, min(h.day, 28)).isoformat()


def instantaneo_de(ctx: dict) -> dict:
    """Congela os números do motor que tornam a decisão legível daqui a um ano.

    Enxuto de propósito: o que muda a leitura de uma escolha, não o relatório
    inteiro. Um instantâneo que guarda tudo vira um segundo banco de dados
    desatualizado ao lado do primeiro.
    """
    base = ctx.get("baseline") or {}
    score = ctx.get("score") or {}
    indicadores = score.get("indicadores") or {}
    projecao = ctx.get("projecao") or {}
    return {
        "em": date.today().isoformat(),
        "renda_media_mes": base.get("renda_media_mes"),
        "despesa_media_mes": base.get("despesa_media_mes"),
        "sobra_media_mes": base.get("sobra_media_mes"),
        "score": score.get("score"),
        "faixa": score.get("faixa"),
        "reserva_meses": indicadores.get("meses_de_reserva"),
        "saldo_conta": ctx.get("saldo_conta"),
        "planos_em_risco": [
            p.get("nome") for p in (projecao.get("planos") or [])
            if p.get("status") in ("apertado", "inviavel_no_ritmo_atual")
        ],
        "nota": "números do motor no dia da decisão — servem para julgar a escolha pelo que se sabia então",
    }
