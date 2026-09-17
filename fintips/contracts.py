"""Contratos do FinTips.

Estes tipos são a fronteira entre o que o **app** garante e o que o **agente**
decide. O app guarda, valida a forma, aplica de maneira determinística e
recalcula. O agente descobre, pergunta ao usuário e escreve aqui o que aprendeu.

A regra que sustenta o resto: **nada é verdade sem proveniência**. Toda
classificação, custo fixo e fato do perfil carrega quem decidiu, com que
confiança, com base em qual evidência e quando. Uma heurística embutida no
pacote não vale mais do que um palpite — ela ranqueia o que deve ser olhado
primeiro, nunca conclui.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

CONTRACTS_SCHEMA = 1

# Quem decidiu. A ordem é de autoridade crescente.
Origem = Literal["heuristica", "importacao", "agente", "usuario"]

AUTORIDADE: dict[str, int] = {
    "heuristica": 0,   # lista embutida no pacote: só sinal, nunca conclusão
    "importacao": 1,   # derivado dos próprios dados (cadência, agrupamento)
    "agente": 2,       # o agente concluiu, normalmente após conversar
    "usuario": 3,      # a pessoa afirmou. Vence tudo.
}


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def novo_id(prefixo: str, *partes: str) -> str:
    h = hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()[:8]
    return f"{prefixo}-{h}"


@dataclass
class Proveniencia:
    origem: Origem = "heuristica"
    confianca: float = 0.4
    porque: str = ""
    evidencia: list[str] = field(default_factory=list)
    quando: str = field(default_factory=agora)
    por_quem: str = ""          # identificador livre do agente/sessão

    @property
    def autoridade(self) -> int:
        return AUTORIDADE.get(self.origem, 0)

    @property
    def e_verdade(self) -> bool:
        """Só conta como fato estabelecido o que veio do usuário ou do agente."""
        return self.autoridade >= AUTORIDADE["agente"]

    def to_dict(self) -> dict:
        return {
            "origem": self.origem,
            "confianca": round(float(self.confianca), 2),
            "porque": self.porque,
            "evidencia": self.evidencia,
            "quando": self.quando,
            "por_quem": self.por_quem,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "Proveniencia":
        d = d or {}
        return cls(
            origem=d.get("origem", "heuristica"),
            confianca=float(d.get("confianca", 0.4)),
            porque=d.get("porque", ""),
            evidencia=list(d.get("evidencia") or []),
            quando=d.get("quando") or agora(),
            por_quem=d.get("por_quem", ""),
        )


@dataclass
class Categoria:
    """Uma categoria existe porque alguém a criou — não porque está no código."""

    id: str
    nome: str
    descricao: str = ""
    essencial: bool | None = None        # None = ainda não se sabe
    pai: str | None = None
    proveniencia: Proveniencia = field(default_factory=Proveniencia)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "descricao": self.descricao,
            "essencial": self.essencial,
            "pai": self.pai,
            "proveniencia": self.proveniencia.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Categoria":
        return cls(
            id=d["id"], nome=d.get("nome", d["id"]),
            descricao=d.get("descricao", ""),
            essencial=d.get("essencial"),
            pai=d.get("pai"),
            proveniencia=Proveniencia.from_dict(d.get("proveniencia")),
        )


@dataclass
class Condicao:
    """O `quando` de uma regra. Campos vazios não restringem.

    Tudo é comparável de forma determinística — nada aqui depende do humor do
    modelo no dia. O agente é quem escolhe a condição; o app só a aplica.
    """

    contraparte_id: str = ""
    contraparte_contem: str = ""
    memo_casa: str = ""              # expressão regular
    canal: str = ""
    fluxo: str = ""
    categoria_atual: str = ""
    valor_min: float | None = None
    valor_max: float | None = None
    dias_semana: list[int] = field(default_factory=list)   # 0=segunda
    hora_min: int | None = None
    hora_max: int | None = None

    def vazia(self) -> bool:
        return not any(
            [self.contraparte_id, self.contraparte_contem, self.memo_casa, self.canal,
             self.fluxo, self.categoria_atual, self.valor_min is not None,
             self.valor_max is not None, self.dias_semana,
             self.hora_min is not None, self.hora_max is not None]
        )

    def especificidade(self) -> int:
        """Regra mais específica vence a mais genérica."""
        pesos = [
            (self.contraparte_id, 5), (self.memo_casa, 4), (self.contraparte_contem, 3),
            (self.canal, 2), (self.fluxo, 1), (self.categoria_atual, 1),
            (self.valor_min is not None or self.valor_max is not None, 2),
            (bool(self.dias_semana), 2),
            (self.hora_min is not None or self.hora_max is not None, 2),
        ]
        return sum(p for v, p in pesos if v)

    def to_dict(self) -> dict:
        d = {
            "contraparte_id": self.contraparte_id,
            "contraparte_contem": self.contraparte_contem,
            "memo_casa": self.memo_casa,
            "canal": self.canal,
            "fluxo": self.fluxo,
            "categoria_atual": self.categoria_atual,
            "valor_min": self.valor_min,
            "valor_max": self.valor_max,
            "dias_semana": self.dias_semana,
            "hora_min": self.hora_min,
            "hora_max": self.hora_max,
        }
        return {k: v for k, v in d.items() if v not in ("", None, [])}

    @classmethod
    def from_dict(cls, d: dict) -> "Condicao":
        return cls(
            contraparte_id=d.get("contraparte_id", ""),
            contraparte_contem=d.get("contraparte_contem", ""),
            memo_casa=d.get("memo_casa", ""),
            canal=d.get("canal", ""),
            fluxo=d.get("fluxo", ""),
            categoria_atual=d.get("categoria_atual", ""),
            valor_min=d.get("valor_min"),
            valor_max=d.get("valor_max"),
            dias_semana=list(d.get("dias_semana") or []),
            hora_min=d.get("hora_min"),
            hora_max=d.get("hora_max"),
        )


@dataclass
class Efeito:
    """O `então` de uma regra."""

    categoria: str = ""
    fluxo: str = ""
    marcar: list[str] = field(default_factory=list)
    rotulo: str = ""

    def to_dict(self) -> dict:
        d = {"categoria": self.categoria, "fluxo": self.fluxo,
             "marcar": self.marcar, "rotulo": self.rotulo}
        return {k: v for k, v in d.items() if v not in ("", None, [])}

    @classmethod
    def from_dict(cls, d: dict) -> "Efeito":
        return cls(
            categoria=d.get("categoria", ""), fluxo=d.get("fluxo", ""),
            marcar=list(d.get("marcar") or []), rotulo=d.get("rotulo", ""),
        )


@dataclass
class Regra:
    id: str
    quando: Condicao
    entao: Efeito
    proveniencia: Proveniencia = field(default_factory=Proveniencia)
    ativa: bool = True
    nota: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "quando": self.quando.to_dict(),
            "entao": self.entao.to_dict(),
            "proveniencia": self.proveniencia.to_dict(),
            "ativa": self.ativa,
            "nota": self.nota,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Regra":
        return cls(
            id=d["id"],
            quando=Condicao.from_dict(d.get("quando") or {}),
            entao=Efeito.from_dict(d.get("entao") or {}),
            proveniencia=Proveniencia.from_dict(d.get("proveniencia")),
            ativa=bool(d.get("ativa", True)),
            nota=d.get("nota", ""),
        )

    def prioridade(self) -> tuple[int, int, float]:
        p = self.proveniencia
        return (p.autoridade, self.quando.especificidade(), p.confianca)


@dataclass
class CustoFixo:
    """Compromisso mensal DEFINIDO — não detectado.

    A detecção continua existindo, mas só produz candidatos para a triagem.
    Custo fixo de verdade é o que alguém afirmou, com base declarada.
    """

    id: str
    rotulo: str
    base_tipo: str                   # categoria | contraparte | regra | valor
    base_ref: str
    valor_mensal: float
    metodo: str = "declarado"        # declarado | mediana_meses_completos | media
    natureza: str = "rotina"         # contratual | rotina | outro (o agente nomeia)
    ativo: bool = True
    proveniencia: Proveniencia = field(default_factory=Proveniencia)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rotulo": self.rotulo,
            "base": {"tipo": self.base_tipo, "ref": self.base_ref},
            "valor_mensal": round(float(self.valor_mensal), 2),
            "valor_anual": round(float(self.valor_mensal) * 12, 2),
            "metodo": self.metodo,
            "natureza": self.natureza,
            "ativo": self.ativo,
            "proveniencia": self.proveniencia.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CustoFixo":
        base = d.get("base") or {}
        return cls(
            id=d["id"], rotulo=d.get("rotulo", d["id"]),
            base_tipo=base.get("tipo", "categoria"), base_ref=base.get("ref", ""),
            valor_mensal=float(d.get("valor_mensal", 0)),
            metodo=d.get("metodo", "declarado"),
            natureza=d.get("natureza", "rotina"),
            ativo=bool(d.get("ativo", True)),
            proveniencia=Proveniencia.from_dict(d.get("proveniencia")),
        )


@dataclass
class Fato:
    """Um pedaço de contexto sobre o usuário, com o que o sustenta."""

    chave: str
    valor: Any
    tipo: str = "texto"              # texto | numero | dinheiro | bool | lista | data
    proveniencia: Proveniencia = field(default_factory=Proveniencia)
    expira_em: str | None = None     # ISO date; None = não expira
    substituiu: str | None = None    # valor anterior, para histórico curto

    def vencido(self, hoje: date | None = None) -> bool:
        if not self.expira_em:
            return False
        try:
            return date.fromisoformat(self.expira_em) < (hoje or date.today())
        except ValueError:
            return False

    def to_dict(self) -> dict:
        return {
            "chave": self.chave,
            "valor": self.valor,
            "tipo": self.tipo,
            "expira_em": self.expira_em,
            "substituiu": self.substituiu,
            "vencido": self.vencido(),
            "proveniencia": self.proveniencia.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Fato":
        return cls(
            chave=d["chave"], valor=d.get("valor"), tipo=d.get("tipo", "texto"),
            expira_em=d.get("expira_em"), substituiu=d.get("substituiu"),
            proveniencia=Proveniencia.from_dict(d.get("proveniencia")),
        )


@dataclass
class ItemDeTriagem:
    """Algo que precisa de decisão humana, com o custo de não decidir."""

    id: str
    tipo: str                        # contraparte_nova | classificacao_fraca |
                                     # candidato_custo_fixo | custo_fixo_derivou |
                                     # fato_ausente | fato_vencido | evento_sem_explicacao
    titulo: str
    impacto_mensal: float            # em reais — é o que ordena a fila
    porque_importa: str              # qual cálculo muda quando isto for resolvido
    evidencia: dict = field(default_factory=dict)
    sugestao: dict | None = None     # hipótese da heurística, sempre rotulada como tal
    estado: str = "aberto"           # aberto | resolvido | adiado
    resolucao: dict | None = None
    criado_em: str = field(default_factory=agora)

    @property
    def prioridade(self) -> float:
        peso_tipo = {
            "fato_ausente": 1.3, "custo_fixo_derivou": 1.2, "contraparte_nova": 1.0,
            "candidato_custo_fixo": 1.0, "classificacao_fraca": 0.9,
            "evento_sem_explicacao": 0.8, "fato_vencido": 0.8,
        }.get(self.tipo, 1.0)
        return round(abs(self.impacto_mensal) * peso_tipo, 2)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "titulo": self.titulo,
            "impacto_mensal": round(float(self.impacto_mensal), 2),
            "impacto_anual": round(float(self.impacto_mensal) * 12, 2),
            "prioridade": self.prioridade,
            "porque_importa": self.porque_importa,
            "evidencia": self.evidencia,
            "sugestao": self.sugestao,
            "estado": self.estado,
            "resolucao": self.resolucao,
            "criado_em": self.criado_em,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ItemDeTriagem":
        return cls(
            id=d["id"], tipo=d["tipo"], titulo=d.get("titulo", ""),
            impacto_mensal=float(d.get("impacto_mensal", 0)),
            porque_importa=d.get("porque_importa", ""),
            evidencia=d.get("evidencia") or {},
            sugestao=d.get("sugestao"),
            estado=d.get("estado", "aberto"),
            resolucao=d.get("resolucao"),
            criado_em=d.get("criado_em") or agora(),
        )


def valida_regex(padrao: str) -> str:
    """Impede que uma regra do agente derrube a importação inteira."""
    if not padrao:
        return ""
    try:
        re.compile(padrao, re.I)
    except re.error as e:
        raise ValueError(f"expressão regular inválida: {padrao!r} ({e})") from e
    return padrao
