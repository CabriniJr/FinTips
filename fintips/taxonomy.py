"""Taxonomia: as categorias pertencem ao usuário, não ao código.

Antes existia um enum `CATEGORIES` no `models.py`. Isso decidia, pelo usuário,
que "transporte" é uma coisa só — quando no extrato dele há deslocamento de
trabalho e Uber de fim de semana, que não têm nada a ver um com o outro.

Agora a taxonomia é dado. O pacote traz um conjunto **sugerido**, marcado como
heurística: ele serve para a partida a frio e para ranquear o que olhar, e cada
sugestão só vira categoria de verdade quando o agente ou o usuário a adota.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .contracts import Categoria, Proveniencia, agora

TAXONOMY_SCHEMA = 1

# Conjunto sugerido. NÃO é a verdade sobre ninguém: é ponto de partida.
# `essencial` fica None de propósito — se um gasto é essencial depende da vida
# da pessoa, e é exatamente o tipo de coisa que o agente deve perguntar.
SUGESTOES: list[dict] = [
    {"id": "alimentacao", "nome": "Alimentação", "descricao": "Comer fora, delivery, lanches"},
    {"id": "mercado", "nome": "Mercado", "descricao": "Compra de casa, supermercado, feira"},
    {"id": "transporte", "nome": "Transporte", "descricao": "Deslocamento de qualquer natureza"},
    {"id": "moradia", "nome": "Moradia", "descricao": "Aluguel, condomínio, contas da casa"},
    {"id": "saude", "nome": "Saúde", "descricao": "Farmácia, consultas, exames, plano"},
    {"id": "vestuario", "nome": "Vestuário", "descricao": "Roupa, calçado, equipamento pessoal"},
    {"id": "lazer", "nome": "Lazer", "descricao": "Cultura, eventos, passeio, hobby"},
    {"id": "educacao", "nome": "Educação", "descricao": "Curso, livro técnico, mensalidade"},
    {"id": "assinaturas", "nome": "Assinaturas", "descricao": "Serviço recorrente contratado"},
    {"id": "servicos", "nome": "Serviços", "descricao": "Serviço avulso contratado"},
    {"id": "compras", "nome": "Compras", "descricao": "Bens não recorrentes, e-commerce"},
    {"id": "doacoes", "nome": "Doações", "descricao": "Doação, dízimo, ajuda"},
    {"id": "taxas", "nome": "Taxas", "descricao": "Tarifa bancária, seguro embutido, juros"},
    {"id": "viagem", "nome": "Viagem", "descricao": "Passagem, hospedagem, viagem"},
    {"id": "pessoas", "nome": "Pessoas", "descricao": "Transferência entre pessoas"},
    {"id": "investimento", "nome": "Investimento", "descricao": "Aporte e resgate"},
    {"id": "renda", "nome": "Renda", "descricao": "Entrada de dinheiro"},
    {"id": "outros", "nome": "Outros", "descricao": "Ainda não classificado"},
]

# A única categoria que o motor precisa existir sempre, porque é o estado
# "ninguém decidiu ainda".
FALLBACK = "outros"


class Taxonomy:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.categorias: dict[str, Categoria] = {}
        self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> None:
        if self.path.exists():
            data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
            for d in data.get("categorias") or []:
                self.categorias[d["id"]] = Categoria.from_dict(d)
        if FALLBACK not in self.categorias:
            self.categorias[FALLBACK] = Categoria(
                id=FALLBACK, nome="Outros",
                descricao="Ainda não classificado — estado inicial, não uma categoria real",
                proveniencia=Proveniencia(origem="heuristica", confianca=1.0,
                                          porque="estado obrigatório do motor"),
            )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": TAXONOMY_SCHEMA,
                    "atualizado_em": agora(),
                    "categorias": [c.to_dict() for c in self.ordenadas()],
                },
                allow_unicode=True, sort_keys=False,
            ),
            encoding="utf-8",
        )

    # --------------------------------------------------------------- acesso
    def ordenadas(self) -> list[Categoria]:
        return sorted(self.categorias.values(), key=lambda c: c.id)

    def existe(self, cat_id: str) -> bool:
        return cat_id in self.categorias

    def get(self, cat_id: str) -> Categoria | None:
        return self.categorias.get(cat_id)

    def ids(self) -> list[str]:
        return sorted(self.categorias)

    # -------------------------------------------------------------- escrita
    def criar(
        self,
        cat_id: str,
        nome: str,
        *,
        descricao: str = "",
        essencial: bool | None = None,
        pai: str | None = None,
        proveniencia: Proveniencia | None = None,
    ) -> Categoria:
        """Cria (ou atualiza) uma categoria. Quem cria assina."""
        if pai and pai not in self.categorias:
            raise ValueError(f"categoria pai inexistente: {pai}")
        atual = self.categorias.get(cat_id)
        prov = proveniencia or Proveniencia(origem="agente", confianca=0.8)
        if atual and atual.proveniencia.autoridade > prov.autoridade:
            # não deixa uma heurística sobrescrever o que o usuário definiu
            return atual
        cat = Categoria(
            id=cat_id, nome=nome, descricao=descricao,
            essencial=essencial if essencial is not None else (atual.essencial if atual else None),
            pai=pai, proveniencia=prov,
        )
        self.categorias[cat_id] = cat
        self.save()
        return cat

    def remover(self, cat_id: str) -> bool:
        if cat_id == FALLBACK or cat_id not in self.categorias:
            return False
        del self.categorias[cat_id]
        self.save()
        return True

    def adotar_sugestoes(self, ids: list[str] | None = None) -> list[Categoria]:
        """Materializa sugestões do pacote como categorias de verdade.

        Usado na partida a frio, e sempre com proveniência 'heuristica' até que
        alguém confirme — assim a triagem sabe que ainda são palpite.
        """
        alvo = set(ids) if ids else {s["id"] for s in SUGESTOES}
        criadas = []
        for s in SUGESTOES:
            if s["id"] in alvo and s["id"] not in self.categorias:
                criadas.append(
                    self.criar(
                        s["id"], s["nome"], descricao=s["descricao"],
                        proveniencia=Proveniencia(
                            origem="heuristica", confianca=0.5,
                            porque="conjunto sugerido pelo pacote, ainda não revisado",
                        ),
                    )
                )
        return criadas

    def nao_revisadas(self) -> list[Categoria]:
        """Categorias que ninguém confirmou ainda."""
        return [c for c in self.ordenadas()
                if c.id != FALLBACK and not c.proveniencia.e_verdade]

    def uso(self, categorias_usadas: dict[str, float]) -> list[dict]:
        """Taxonomia + quanto dinheiro passou por cada categoria."""
        out = []
        for c in self.ordenadas():
            out.append({
                **c.to_dict(),
                "total_no_periodo": round(float(categorias_usadas.get(c.id, 0)), 2),
                "em_uso": c.id in categorias_usadas,
            })
        return out
