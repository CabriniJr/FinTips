"""Causas: por que o dinheiro sai, e o que se decidiu sobre isso.

O motor sempre soube **o quê** (transação, contraparte, categoria) e **quanto**
(baseline, compromisso, projeção). Faltava o **porquê** — e sem ele qualquer
conselho é palpite bem calculado.

A diferença é prática, não filosófica. Duas pessoas gastam R$ 400/mês em
delivery. Na primeira, é jornada dupla e chegar em casa às 22h; cortar é
aumentar o custo de outra coisa (sono, tempo com a filha). Na segunda, é
tédio de domingo; cortar é fácil e ela já tentou. Mesmo número, mesma
categoria, respostas opostas — e nenhum extrato do mundo distingue as duas.

Por isso este módulo não tem detecção. Não existe `detectar_causas()` aqui e
não deve existir: causa nasce de conversa, com origem `agente` ou `usuario`.
O que o módulo faz é guardar a causa ligada ao dinheiro que ela explica,
cobrar revisão quando ela envelhece, e medir quanto da despesa ainda não tem
explicação nenhuma.

A `atitude` é o que fecha o ciclo. Entender e não decidir nada é diagnóstico
sem tratamento; e `aceitar` é decisão legítima — tira o gasto da lista de
culpa e o põe na de escolhas.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from .contracts import ATITUDES, Causa, Proveniencia, agora, novo_id
from .models import Statement

CAUSES_SCHEMA = 1

EFEITOS = ("categoria", "contraparte", "padrao", "mes", "plano", "compromisso")


class CauseStore:
    """Causas gravadas, indexadas pelo que elas explicam."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.causas: dict[str, Causa] = {}
        self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> None:
        if not self.path.exists():
            return
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        for d in data.get("causas") or []:
            self.causas[d["id"]] = Causa.from_dict(d)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": CAUSES_SCHEMA,
                    "atualizado_em": agora(),
                    "causas": [c.to_dict() for c in sorted(self.causas.values(), key=lambda c: c.alvo)],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    # -------------------------------------------------------------- escrita
    def gravar(
        self,
        *,
        efeito_tipo: str,
        efeito_ref: str,
        natureza: str,
        enunciado: str,
        proveniencia: Proveniencia,
        atitude: str = "nenhuma",
        atitude_nota: str = "",
        evidencia: list[str] | None = None,
        revisar_em: str | None = None,
    ) -> Causa:
        """Grava uma causa. Recusa o que não pode ser afirmado.

        As três recusas são a regra do produto em código: origem sem
        autoridade (causa não se deriva), `porque` vazio (sem isso não há
        auditoria) e enunciado vazio (uma causa sem frase é um rótulo).
        """
        if not proveniencia.e_verdade:
            raise ValueError(
                "causa só aceita origem 'agente' ou 'usuario'. Não existe causa "
                "derivada dos dados: o extrato mostra o gasto, nunca o motivo"
            )
        if not proveniencia.porque:
            raise ValueError("gravar uma causa exige `porque` — o que te fez concluir isso")
        if not enunciado.strip():
            raise ValueError("causa sem enunciado é rótulo; escreva a frase que a pessoa disse")
        if efeito_tipo not in EFEITOS:
            raise ValueError(f"efeito_tipo deve ser um de {EFEITOS}")
        if not efeito_ref.strip():
            raise ValueError("causa precisa apontar o que ela explica (efeito_ref)")
        if atitude not in ATITUDES:
            raise ValueError(f"atitude deve ser uma de {ATITUDES}")
        if not natureza.strip():
            raise ValueError("causa precisa de natureza — ver NATUREZAS_SUGERIDAS, mas a lista é aberta")

        cid = novo_id("causa", efeito_tipo, efeito_ref, natureza)
        atual = self.causas.get(cid)
        if atual and atual.proveniencia.autoridade > proveniencia.autoridade and not atual.vencida():
            return atual

        causa = Causa(
            id=cid,
            efeito_tipo=efeito_tipo,
            efeito_ref=efeito_ref,
            natureza=natureza.strip(),
            enunciado=enunciado.strip(),
            atitude=atitude,
            atitude_nota=atitude_nota,
            evidencia=evidencia or [],
            proveniencia=proveniencia,
            revisar_em=revisar_em,
            criado_em=atual.criado_em if atual else agora(),
        )
        self.causas[cid] = causa
        self.save()
        return causa

    def decidir(self, causa_id: str, atitude: str, nota: str = "") -> Causa:
        """Registra a atitude sobre uma causa já entendida.

        Separado de `gravar` porque entender e decidir acontecem em momentos
        diferentes — às vezes com semanas de distância, que é o tempo normal
        de mudar de ideia sobre o próprio comportamento.
        """
        if atitude not in ATITUDES:
            raise ValueError(f"atitude deve ser uma de {ATITUDES}")
        causa = self.causas.get(causa_id)
        if not causa:
            raise ValueError(f"causa '{causa_id}' não existe")
        causa.atitude = atitude
        causa.atitude_nota = nota
        self.save()
        return causa

    def esquecer(self, causa_id: str) -> bool:
        if causa_id in self.causas:
            del self.causas[causa_id]
            self.save()
            return True
        return False

    # -------------------------------------------------------------- leitura
    def para(self, efeito_tipo: str, efeito_ref: str) -> list[Causa]:
        return [
            c for c in self.causas.values()
            if c.efeito_tipo == efeito_tipo and c.efeito_ref == efeito_ref
        ]

    def ativas(self, hoje: date | None = None) -> list[Causa]:
        return [c for c in self.causas.values() if not c.vencida(hoje)]

    def vencidas(self, hoje: date | None = None) -> list[Causa]:
        return [c for c in self.causas.values() if c.vencida(hoje)]

    def sem_atitude(self) -> list[Causa]:
        return [c for c in self.ativas() if c.atitude == "nenhuma"]

    def to_dicts(self) -> list[dict]:
        return [c.to_dict() for c in sorted(self.causas.values(), key=lambda c: c.alvo)]

    def por_alvo(self) -> dict[str, list[dict]]:
        """Índice pronto para correlação: alvo -> causas que o explicam."""
        out: dict[str, list[dict]] = {}
        for c in self.causas.values():
            out.setdefault(c.alvo, []).append(c.to_dict())
        return out

    # ------------------------------------------------------------ cobertura
    def cobertura(self, stmt: Statement, *, hoje: date | None = None) -> dict:
        """Quanto da despesa tem causa, e quanto ainda é dinheiro sem explicação.

        Espelha `mapping.cobertura`, que mede a classificação. A diferença
        entre as duas é a pergunta que cada uma responde: aquela diz se o
        dinheiro está no balde certo, esta diz se alguém sabe por que ele saiu.
        Ambas começam em 0%, e é assim que deve ser.
        """
        ativas = self.ativas(hoje)
        cats = {c.efeito_ref for c in ativas if c.efeito_tipo == "categoria"}
        cps = {c.efeito_ref for c in ativas if c.efeito_tipo == "contraparte"}

        total = explicado = 0.0
        sem_causa: dict[str, float] = {}
        for t in stmt.transactions:
            if t.flow != "expense":
                continue
            v = abs(float(t.amount))
            total += v
            if t.category in cats or t.counterparty in cps:
                explicado += v
            else:
                sem_causa[t.category] = sem_causa.get(t.category, 0.0) + v

        n_meses = max(len({t.month for t in stmt.transactions}), 1)
        return {
            "despesa_total": round(total, 2),
            "com_causa": round(explicado, 2),
            "sem_causa": round(total - explicado, 2),
            "cobertura_pct": round(explicado / total * 100, 1) if total else 0.0,
            "causas": len(self.causas),
            "sem_atitude": len(self.sem_atitude()),
            "a_revisar": len(self.vencidas(hoje)),
            "maiores_sem_causa": [
                {"categoria": k, "total": round(v, 2), "por_mes": round(v / n_meses, 2)}
                for k, v in sorted(sem_causa.items(), key=lambda kv: kv[1], reverse=True)[:8]
            ],
            "explicacao": (
                "percentual da despesa que alguém explicou. O resto é dinheiro "
                "saindo por um motivo que ninguém escreveu ainda"
            ),
        }
