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
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Literal

CONTRACTS_SCHEMA = 3   # 3: entram os contratos Decisao e Alternativa

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


# Naturezas sugeridas para uma causa. A lista é aberta de propósito — o motor
# valida a forma, não o conteúdo, e a vida de alguém pode exigir uma palavra
# que não está aqui. Ela existe para o agente ter por onde começar e para o
# dossiê agrupar causas parecidas.
NATUREZAS_SUGERIDAS = (
    "gatilho",        # algo dispara o gasto (cansaço, plantão, sexta-feira)
    "necessidade",    # a vida exige, não há escolha real
    "obrigacao",      # alguém acordou isso antes (contrato, acordo familiar)
    "habito",         # repete por repetir, sem decisão a cada vez
    "compensacao",    # troca dinheiro por tempo, energia ou humor
    "evento",         # aconteceu uma vez, por um motivo que passou
    "estrutural",     # decorre de onde mora, como trabalha, com quem vive
)

# Atitudes são fechadas, ao contrário das naturezas: o dossiê e as alavancas
# calculam em cima delas. "Aceitar" e "reduzir" levam a contas diferentes, e
# uma atitude inventada no meio da conversa não teria como entrar em nenhuma.
ATITUDES = (
    "nenhuma",        # ainda não se decidiu nada
    "aceitar",        # fica como está, e agora isso é escolha, não descuido
    "reduzir",
    "eliminar",
    "substituir",
    "automatizar",    # vira aporte/pagamento automático, sai da decisão diária
    "observar",       # sem decisão ainda; olhar de novo em tal data
)


@dataclass
class Causa:
    """Por que um padrão de gasto existe — e o que se decidiu sobre ele.

    Esta é a única camada do motor que fala de motivo, e por isso a mais
    perigosa. Um número o app calcula; um motivo ele não tem como saber. Duas
    pessoas com o mesmo extrato de delivery podem estar com jornada dupla ou
    com preguiça de cozinhar, e a conta seguinte é diferente em cada caso.

    Por isso a causa não é derivável: nasce de `agente` ou `usuario`, sempre.
    Não existe detecção de causa neste código, e não deve existir.

    `atitude` é o que fecha o ciclo. Entender por que o dinheiro sai e não
    decidir nada é diagnóstico sem tratamento — e `aceitar` é uma decisão
    legítima, que tira o gasto da lista de culpa e o coloca na de escolhas.
    """

    id: str
    efeito_tipo: str                 # categoria | contraparte | padrao | mes | plano | compromisso
    efeito_ref: str
    natureza: str                    # ver NATUREZAS_SUGERIDAS; lista aberta
    enunciado: str                   # a frase, nas palavras de quem disse
    atitude: str = "nenhuma"
    atitude_nota: str = ""
    evidencia: list[str] = field(default_factory=list)
    proveniencia: Proveniencia = field(default_factory=Proveniencia)
    revisar_em: str | None = None    # ISO date; causa de comportamento envelhece
    criado_em: str = field(default_factory=agora)

    def vencida(self, hoje: date | None = None) -> bool:
        if not self.revisar_em:
            return False
        try:
            return date.fromisoformat(self.revisar_em) < (hoje or date.today())
        except ValueError:
            return False

    @property
    def alvo(self) -> str:
        """Chave de correlação: é por aqui que o dossiê liga causa a dinheiro."""
        return f"{self.efeito_tipo}:{self.efeito_ref}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "efeito": {"tipo": self.efeito_tipo, "ref": self.efeito_ref},
            "alvo": self.alvo,
            "natureza": self.natureza,
            "enunciado": self.enunciado,
            "atitude": self.atitude,
            "atitude_nota": self.atitude_nota,
            "evidencia": self.evidencia,
            "revisar_em": self.revisar_em,
            "vencida": self.vencida(),
            "criado_em": self.criado_em,
            "proveniencia": self.proveniencia.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Causa":
        efeito = d.get("efeito") or {}
        return cls(
            id=d["id"],
            efeito_tipo=efeito.get("tipo", "categoria"),
            efeito_ref=efeito.get("ref", ""),
            natureza=d.get("natureza", ""),
            enunciado=d.get("enunciado", ""),
            atitude=d.get("atitude", "nenhuma"),
            atitude_nota=d.get("atitude_nota", ""),
            evidencia=list(d.get("evidencia") or []),
            revisar_em=d.get("revisar_em"),
            criado_em=d.get("criado_em") or agora(),
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
                                     # fato_ausente | fato_vencido | evento_sem_explicacao |
                                     # causa_ausente | causa_a_revisar | causa_sem_atitude |
                                     # decisao_aberta | decisao_a_revisar | decisao_sem_desfecho
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
            # causa ausente pesa como contraparte nova: é dinheiro sem leitura.
            # revisão e decisão pendentes não têm impacto em reais, então não
            # competem por posição na fila — entram pelo peso, não pelo valor.
            "causa_ausente": 1.1, "causa_a_revisar": 1.0, "causa_sem_atitude": 0.9,
            # decisão em aberto pesa mais que tudo: é a única fila em que a
            # pessoa está esperando para agir, e não o motor esperando dados.
            "decisao_aberta": 1.5, "decisao_a_revisar": 1.0, "decisao_sem_desfecho": 0.7,
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


# Estados de uma decisão. Fechados porque a triagem e o histórico contam em
# cima deles: uma decisão aberta cobra conclusão, uma decidida sem desfecho
# cobra revisão, e uma substituída sai da conta sem sumir do histórico.
STATUS_DECISAO = (
    "aberta",         # a pergunta existe, a resposta ainda não
    "decidida",       # escolheu-se uma alternativa, e está valendo
    "revisada",       # o desfecho foi registrado: sabe-se no que deu
    "substituida",    # outra decisão tomou o lugar desta
)

# O que se aprendeu depois. `cedo_para_saber` é resposta honesta e existe para
# a pessoa não ser forçada a inventar um veredito antes da hora — a decisão
# volta para a fila em vez de virar aprendizado falso.
VEREDITOS = ("funcionou", "arrependi", "indiferente", "cedo_para_saber")

# Que tipo de pergunta esta decisão responde. Lista fechada porque o histórico
# agrupa por ela: "como eu costumo decidir troca de equipamento" é uma pergunta
# respondível; "como eu costumo decidir coisas" não é.
TIPOS_DECISAO = (
    "troca",          # consertar, substituir, aguentar mais um tempo
    "compra",         # adquirir algo que não se tinha
    "contrato",       # assinar, cancelar, trocar de plano
    "divida",         # antecipar, parcelar, refinanciar
    "investimento",   # onde colocar dinheiro que sobrou
    "renda",          # aceitar um trabalho, mudar de arranjo
    "moradia",        # mudar, renovar, dividir
    "outro",
)


@dataclass
class Alternativa:
    """Um caminho considerado — inclusive os que não foram escolhidos.

    Guardar o que foi descartado é metade do valor de um registro de decisão.
    Daqui a um ano, "comprei um celular novo" não diz nada; "considerei
    consertar por R$ 700 e descartei porque a assistência não dava garantia da
    placa" diz por que a mesma pergunta não deve ser reaberta do zero.

    Os dois cálculos derivados existem porque são a conta que ninguém faz de
    cabeça e que decide a maioria dos casos de troca: R$ 700 que duram 8 meses
    custam mais por mês do que R$ 2.500 que duram 36.
    """

    nome: str
    custo: float = 0.0                    # desembolso imediato
    custo_mensal: float = 0.0             # o que ela acrescenta ao custo fixo
    horizonte_meses: int | None = None    # por quanto tempo resolve o problema
    consequencia: str = ""                # o que passa a ser verdade se for esta
    risco: str = ""
    descartada_porque: str = ""

    @property
    def custo_no_horizonte(self) -> float | None:
        if self.horizonte_meses is None:
            return None
        return round(float(self.custo) + float(self.custo_mensal) * self.horizonte_meses, 2)

    @property
    def custo_por_mes_de_uso(self) -> float | None:
        """A régua que compara alternativas de vida útil diferente."""
        total = self.custo_no_horizonte
        if total is None or not self.horizonte_meses:
            return None
        return round(total / self.horizonte_meses, 2)

    def to_dict(self) -> dict:
        return {
            "nome": self.nome,
            "custo": round(float(self.custo), 2),
            "custo_mensal": round(float(self.custo_mensal), 2),
            "horizonte_meses": self.horizonte_meses,
            "custo_no_horizonte": self.custo_no_horizonte,
            "custo_por_mes_de_uso": self.custo_por_mes_de_uso,
            "consequencia": self.consequencia,
            "risco": self.risco,
            "descartada_porque": self.descartada_porque,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Alternativa":
        return cls(
            nome=d["nome"],
            custo=float(d.get("custo", 0) or 0),
            custo_mensal=float(d.get("custo_mensal", 0) or 0),
            horizonte_meses=d.get("horizonte_meses"),
            consequencia=d.get("consequencia", ""),
            risco=d.get("risco", ""),
            descartada_porque=d.get("descartada_porque", ""),
        )


@dataclass
class Decisao:
    """Um ADR financeiro: a pergunta, o que se considerou, o que se escolheu,
    contra que números, e no que deu.

    A diferença para `Causa` é o tempo. Causa explica um padrão que se repete
    ("por que sai R$ 400 de delivery todo mês"). Decisão registra uma
    bifurcação pontual ("o celular quebrou: consertar ou trocar"), que acontece
    uma vez e some — e some justamente antes da próxima igual, quando ela seria
    útil.

    `instantaneo` é o que torna o registro legível depois. Uma escolha não é
    boa ou ruim em abstrato: comprar à vista com quatro meses de reserva é
    outra decisão que a mesma compra com duas semanas de caixa. Congelar os
    números do motor no momento da decisão é o que separa "eu errei" de "as
    condições eram outras" — e é a única parte deste contrato que o app
    preenche sozinho, porque é a única que ele sabe.

    `desfecho` fecha o ciclo, e é o que transforma registro em aprendizado: sem
    ele o histórico é uma lista de coisas que aconteceram, não uma base para
    decidir a próxima.
    """

    id: str
    titulo: str
    situacao: str                    # o que aconteceu, nas palavras da pessoa
    pergunta: str                    # o que precisa ser decidido
    tipo: str = "outro"              # ver TIPOS_DECISAO
    alternativas: list[Alternativa] = field(default_factory=list)
    escolhida: str = ""              # nome da alternativa; vazio enquanto aberta
    porque: str = ""                 # por que essa e não as outras
    status: str = "aberta"
    ligacoes: list[str] = field(default_factory=list)   # "categoria:x", "plano:y"
    instantaneo: dict = field(default_factory=dict)     # números congelados
    desfecho: dict | None = None
    substitui: str | None = None
    substituida_por: str | None = None
    revisar_em: str | None = None
    proveniencia: Proveniencia = field(default_factory=Proveniencia)
    criado_em: str = field(default_factory=agora)
    decidido_em: str | None = None

    def vencida(self, hoje: date | None = None) -> bool:
        if not self.revisar_em:
            return False
        try:
            return date.fromisoformat(self.revisar_em) < (hoje or date.today())
        except ValueError:
            return False

    @property
    def alternativa_escolhida(self) -> "Alternativa | None":
        return next((a for a in self.alternativas if a.nome == self.escolhida), None)

    @property
    def custo_da_escolha(self) -> float:
        a = self.alternativa_escolhida
        return float(a.custo) if a else 0.0

    @property
    def aprendeu(self) -> bool:
        """Só conta como aprendizado o desfecho que já dá para ler."""
        v = (self.desfecho or {}).get("veredito")
        return bool(v) and v != "cedo_para_saber"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "titulo": self.titulo,
            "situacao": self.situacao,
            "pergunta": self.pergunta,
            "tipo": self.tipo,
            "alternativas": [a.to_dict() for a in self.alternativas],
            "escolhida": self.escolhida,
            "porque": self.porque,
            "status": self.status,
            "ligacoes": self.ligacoes,
            "instantaneo": self.instantaneo,
            "desfecho": self.desfecho,
            "substitui": self.substitui,
            "substituida_por": self.substituida_por,
            "revisar_em": self.revisar_em,
            "vencida": self.vencida(),
            "custo_da_escolha": self.custo_da_escolha,
            "criado_em": self.criado_em,
            "decidido_em": self.decidido_em,
            "proveniencia": self.proveniencia.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Decisao":
        return cls(
            id=d["id"],
            titulo=d.get("titulo", ""),
            situacao=d.get("situacao", ""),
            pergunta=d.get("pergunta", ""),
            tipo=d.get("tipo", "outro"),
            alternativas=[Alternativa.from_dict(a) for a in d.get("alternativas") or []],
            escolhida=d.get("escolhida", ""),
            porque=d.get("porque", ""),
            status=d.get("status", "aberta"),
            ligacoes=list(d.get("ligacoes") or []),
            instantaneo=d.get("instantaneo") or {},
            desfecho=d.get("desfecho"),
            substitui=d.get("substitui"),
            substituida_por=d.get("substituida_por"),
            revisar_em=d.get("revisar_em"),
            criado_em=d.get("criado_em") or agora(),
            decidido_em=d.get("decidido_em"),
            proveniencia=Proveniencia.from_dict(d.get("proveniencia")),
        )


# --------------------------------------------------------------------------
# O registro dos depósitos
# --------------------------------------------------------------------------
#
# Cada arquivo que o app escreve na máquina da pessoa, declarado num lugar só.
#
# Isto nasceu de um erro concreto, e vale contar porque o erro é instrutivo: a
# aba de configuração mostra "onde os seus dados moram", e essa lista foi
# escrita à mão. O `Workspace` tinha dezenove arquivos; a lista tinha onze.
# Faltavam oito, entre eles `regras-locais.yaml`, que é um dos sensíveis. A
# tela afirmava mostrar onde os dados moram e mostrava pouco mais da metade.
#
# O mecanismo que impede isso é o mesmo das licenças: uma declaração única,
# cruzada contra o código, com o portão quebrando quando divergem. Acrescentar
# um depósito ao `Workspace` e esquecer de declará-lo aqui para de ser um erro
# silencioso e passa a ser um teste vermelho.
#
# A segunda coisa que o registro resolve é a migração. Dezenove arquivos
# carregam `schema_version`, e por muito tempo exatamente um deles sabia subir
# de versão. Os outros dezoito tinham um número que ninguém lia — e o dia em
# que um formato mudasse, o app leria um arquivo que não entende e escolheria
# entre recusar o perfil de alguém ou interpretá-lo errado em silêncio. Aqui
# cada depósito declara o esquema que escreve e o migrador que o acompanha, e
# a regra é simples: **esquema acima de 1 sem migrador é recusado**. Ninguém
# precisa escrever migrador antes da hora; quem bumpar a versão é obrigado a
# escrever o degrau no mesmo commit.


@dataclass(frozen=True)
class Deposito:
    """Um arquivo que o app escreve, e o que o app promete sobre ele."""

    chave: str
    atributo: str          # a propriedade do Workspace que dá o caminho
    guarda: str            # o que mora ali, em português, para a tela
    formato: str           # yaml | jsonl | texto | diretorio
    esquema: int = 1
    # Dado pessoal que o `check-pii.sh` colhe para impedir que vaze num commit.
    sensivel: bool = False
    # "modulo:funcao" que sobe uma versão antiga para a atual, se existir.
    migrador: str = ""
    # Só o app escreve, ou a pessoa edita à mão?
    editavel_a_mao: bool = True

    @property
    def precisa_de_migrador(self) -> bool:
        return self.esquema > 1


DEPOSITOS: tuple[Deposito, ...] = (
    Deposito("config", "config_path", "seus nomes em Pix e apelidos de pessoas",
             "yaml", sensivel=True),
    Deposito("salt", "salt_path",
             "o segredo que pseudonimiza nomes — sem ele os apelidos não voltam",
             "texto", sensivel=True, editavel_a_mao=False),
    Deposito("taxonomia", "taxonomia_path", "suas categorias, com quem as criou", "yaml"),
    Deposito("regras", "regras_path", "regras de classificação com proveniência", "yaml"),
    Deposito("regras_locais", "regras_locais_path",
             "estabelecimentos do seu dia a dia", "yaml", sensivel=True),
    Deposito("contexto", "contexto_path", "fatos sobre você, com evidência", "yaml",
             sensivel=True),
    Deposito("perfil", "perfil_path", "traços de perfil assinados por você", "yaml",
             esquema=2, migrador="fintips.profile:migrar"),
    Deposito("causas", "causas_path", "por que o dinheiro sai, nas suas palavras",
             "yaml", sensivel=True),
    Deposito("decisoes", "decisoes_path",
             "bifurcações: alternativas, escolha e desfecho", "yaml", sensivel=True),
    Deposito("custos_fixos", "custos_fixos_path", "compromissos definidos", "yaml"),
    Deposito("contrapartes", "contrapartes_path",
             "quem recebe o seu dinheiro, agrupado", "yaml", sensivel=True),
    Deposito("triagem", "triagem_path", "o que já foi resolvido ou adiado", "yaml"),
    Deposito("planos", "planos_path", "metas financeiras", "yaml"),
    Deposito("patrimonio", "patrimonio_path", "saldo e investimentos", "yaml",
             sensivel=True),
    Deposito("compras", "compras_path", "intenções de compra em avaliação", "yaml"),
    Deposito("missoes", "missoes_path",
             "as seis frentes e as regras que você assinou", "yaml", sensivel=True),
    Deposito("registros", "registros_path",
             "cumprimento das missões, em append", "jsonl", editavel_a_mao=False),
    Deposito("objetivos", "objetivos_path",
             "objetivos, etapas, prazos e custos", "yaml", sensivel=True),
    Deposito("checks", "checks_path",
             "etapas marcadas como feitas, em append", "jsonl", editavel_a_mao=False),
)

POR_CHAVE: dict[str, Deposito] = {d.chave: d for d in DEPOSITOS}


def conferir_depositos(workspace_cls: Any) -> dict:
    """O registro ainda descreve o `Workspace` de verdade?

    Duas direções, e as duas são jeitos de a tela de configuração mentir:
    depósito que existe no código e não está declarado some da tela; depósito
    declarado que não existe mais no código aparece numa tela apontando para
    um arquivo que ninguém escreve.

    A terceira pergunta é sobre migração: esquema acima de 1 sem migrador
    significa que alguém mudou o formato de um arquivo que mora na máquina da
    pessoa sem escrever o degrau para subir o que já está lá.
    """
    no_codigo = {
        n for n in dir(workspace_cls)
        if n.endswith("_path") and isinstance(getattr(workspace_cls, n, None), property)
    }
    declarados = {d.atributo for d in DEPOSITOS}
    sem_migrador = [
        d.chave for d in DEPOSITOS if d.precisa_de_migrador and not d.migrador
    ]
    return {
        "ok": not (no_codigo - declarados or declarados - no_codigo or sem_migrador),
        "no_codigo_e_nao_declarados": sorted(no_codigo - declarados),
        "declarados_e_fora_do_codigo": sorted(declarados - no_codigo),
        "esquema_novo_sem_migrador": sorted(sem_migrador),
        "quantos": len(DEPOSITOS),
        "como_corrigir": (
            "declare o depósito em contracts.DEPOSITOS, ou remova a declaração "
            "se o arquivo saiu. Se o esquema subiu, escreva o migrador no mesmo "
            "commit — o arquivo antigo já está na máquina de alguém"
        ),
    }


def migrar(chave: str, data: dict) -> dict:
    """Sobe um arquivo lido do disco para o esquema de hoje.

    Despacha para o migrador que o depósito declara. Depósito sem migrador
    devolve o dado como veio — o que é correto enquanto o esquema for 1, e
    `conferir_depositos` é quem garante que continue sendo.
    """
    dep = POR_CHAVE.get(chave)
    if dep is None:
        raise ValueError(
            f"depósito '{chave}' não existe. Os declarados são "
            f"{', '.join(sorted(POR_CHAVE))}"
        )
    if not dep.migrador:
        return data
    import importlib

    modulo, _, funcao = dep.migrador.partition(":")
    return getattr(importlib.import_module(modulo), funcao)(data)

# --------------------------------------------------------------------------
# A fronteira de saída: política por campo
# --------------------------------------------------------------------------
#
# O registro acima diz onde os dados moram. Este diz o que sai do aparelho
# quando o agente é um modelo que roda em outro lugar.
#
# O esclarecimento do usuário em 16/10/2026 desenhou a linha num lugar
# específico, e ele é mais estreito do que "não mandar nada": **texto de
# planejamento sai, valor sai, identidade financeira não sai.** O agente
# precisa ler "certificação de observabilidade" e "parcelar em doze" para
# decompor um objetivo; ele não precisa saber de quem a pessoa recebe nem para
# qual estabelecimento o dinheiro foi.
#
# Isso não é a mesma política do `privacy.py`, e as duas não devem ser
# "harmonizadas" por quem passar aqui depois. O `privacy.py` governa o que o
# app escreve no YAML **local** — e lá o nome do estabelecimento fica em claro,
# porque é ele que dá sentido à análise de gastos na máquina da pessoa. Aqui a
# pergunta é outra: o que atravessa a rede. Um campo pode ser legítimo no disco
# e proibido na saída.
#
# Mecanismo, igual ao dos depósitos e ao das licenças: declarar uma vez, e
# cruzar no portão. A diferença é o default. Depósito não declarado é erro;
# campo não declarado **fecha** — ele simplesmente não sai — e o portão quebra
# para avisar que alguém acrescentou um campo a um tipo da fronteira e não
# disse o que fazer com ele. Fechar por omissão é a escolha segura; fechar em
# silêncio, sem ninguém saber que fechou, é como se perde um campo que devia
# sair. O portão resolve os dois.
#
# O `porque` acompanha a **abertura**, não o fechamento. Não sair é o padrão e
# não precisa de defesa; sair é a exceção e precisa.


# O que a política permite. Não há código para "fechado": fechado é a ausência.
POLITICAS_DE_SAIDA: dict[str, str] = {
    "texto_planejamento": (
        "sai com o significado inteiro: título de objetivo, curso, livro, "
        "produto, e o porquê da pessoa"
    ),
    "valor_financeiro": "sai com unidade declarada — centavos, dias, pontos-base",
    "identidade_financeira_local": (
        "sai só como alias emitido no aparelho; o mapa de volta fica local"
    ),
    "rotulo_tecnico": (
        "código, data, booleano ou referência interna: estrutura sem nome "
        "próprio de ninguém"
    ),
    "segredo_local": "não sai de forma nenhuma",
}

# As unidades que o contrato do turno aceita para um valor.
UNIDADES = ("centavos_brl", "minutos", "pontos_base", "dias", "numero")

FECHADO = "fechado"


@dataclass(frozen=True)
class CampoAberto:
    """Um campo que atravessa a fronteira, e sob que condição."""

    campo: str
    politica: str
    porque: str
    unidade: str = ""     # obrigatório quando a política é valor_financeiro


@dataclass(frozen=True)
class TipoDaFronteira:
    """Um tipo que o agente pode ler, com todos os campos classificados.

    `abre` e `fecha` juntos têm que cobrir exatamente os campos da classe —
    é isso que `conferir_fronteira` cobra. Campo novo não cai em nenhum dos
    dois lados e quebra o portão, que é o ponto.
    """

    nome: str
    classe: str                           # "modulo:Classe", resolvido na hora
    abre: tuple[CampoAberto, ...]
    # Nunca sai, de nenhuma forma.
    fecha: tuple[str, ...] = ()
    # Não sai *neste* campo: é um tipo da fronteira por si, projetado item por
    # item pela política dele. A distinção importa porque as duas aparecem na
    # aba de privacidade, e dizer "a IA nunca recebe as etapas do objetivo" é
    # mentira — ela recebe cada etapa, com a política de `etapa`.
    projeta_a_parte: tuple[str, ...] = ()

    @property
    def por_campo(self) -> dict[str, CampoAberto]:
        return {c.campo: c for c in self.abre}

    @property
    def nao_sai_neste_campo(self) -> tuple[str, ...]:
        return self.fecha + self.projeta_a_parte


TIPOS_DA_FRONTEIRA: tuple[TipoDaFronteira, ...] = (
    TipoDaFronteira(
        "transacao", "fintips.models:Transaction",
        abre=(
            CampoAberto("amount", "valor_financeiro",
                        "sem o valor o agente não compara cenário nenhum",
                        unidade="centavos_brl"),
            CampoAberto("ts", "rotulo_tecnico", "a data situa o valor no tempo"),
            CampoAberto("flow", "rotulo_tecnico", "entrada ou saída, sem nome de ninguém"),
            CampoAberto("category", "rotulo_tecnico",
                        "a categoria é vocabulário do app, não o estabelecimento"),
            CampoAberto("channel", "rotulo_tecnico", "pix, cartão, boleto: forma, não quem"),
            CampoAberto("counterparty_kind", "rotulo_tecnico",
                        "pessoa, empresa ou você mesmo — o tipo muda o conselho"),
            CampoAberto("counterparty", "identidade_financeira_local",
                        "o agente precisa poder dizer 'esse mesmo destino de novo' "
                        "sem saber quem é"),
            CampoAberto("category_source", "rotulo_tecnico",
                        "quem classificou: heurística não vale conclusão"),
        ),
        fecha=(
            "id",                   # FITID: identificador de transação do banco
            "memo_raw",             # o texto cru do extrato
            "city",                 # localiza a pessoa
            "tags",                 # texto livre, pode trazer qualquer coisa
            "account_id",           # dado de conta
            "category_confidence",  # fração sem unidade inteira no contrato do turno
            "rule_id",              # aponta para regra local
        ),
    ),
    TipoDaFronteira(
        "objetivo", "fintips.objetivos:Objetivo",
        abre=(
            CampoAberto("id", "rotulo_tecnico", "a referência que amarra etapas e checks"),
            CampoAberto("titulo", "texto_planejamento",
                        "é o objeto do planejamento: sem ele não há decomposição"),
            CampoAberto("porque", "texto_planejamento",
                        "o motivo da pessoa é o que faz o agente perguntar a coisa certa"),
            CampoAberto("comecou_em", "rotulo_tecnico", "data"),
            CampoAberto("data_alvo", "rotulo_tecnico", "o prazo é metade do problema"),
            CampoAberto("origem", "rotulo_tecnico", "quem escreveu este objetivo"),
            CampoAberto("porque_da_origem", "texto_planejamento",
                        "a justificativa da escrita, auditável depois"),
            CampoAberto("assinado_em", "rotulo_tecnico",
                        "sem isto o agente não sabe se é rascunho ou compromisso"),
            CampoAberto("arquivado", "rotulo_tecnico", "booleano"),
            CampoAberto("plano_id", "rotulo_tecnico",
                        "referência ao plano financeiro, não o plano"),
            CampoAberto("missoes", "rotulo_tecnico", "referências às frentes de vida"),
        ),
        # Cada etapa passa pela política de `etapa` em vez de atravessar
        # aninhada aqui dentro.
        projeta_a_parte=("etapas",),
    ),
    TipoDaFronteira(
        "etapa", "fintips.objetivos:Etapa",
        abre=(
            CampoAberto("id", "rotulo_tecnico", "referência do check e da dependência"),
            CampoAberto("titulo", "texto_planejamento", "o nome do curso, da prova, da leitura"),
            CampoAberto("tipo", "rotulo_tecnico", "curso, prova, leitura: vocabulário do app"),
            CampoAberto("prazo", "rotulo_tecnico", "data"),
            CampoAberto("prazo_original", "rotulo_tecnico",
                        "o prazo que foi empurrado — adiamento vale 15 pontos do score"),
            CampoAberto("adiamentos", "rotulo_tecnico", "contagem", unidade="numero"),
            CampoAberto("custo", "valor_financeiro",
                        "é o que liga a etapa ao plano financeiro", unidade="centavos_brl"),
            CampoAberto("depende_de", "rotulo_tecnico", "referências, para a cadeia"),
            CampoAberto("obrigatoria", "rotulo_tecnico", "booleano"),
            CampoAberto("porque", "texto_planejamento", "por que esta etapa existe"),
        ),
    ),
    TipoDaFronteira(
        "check", "fintips.objetivos:Check",
        abre=(
            CampoAberto("objetivo_id", "rotulo_tecnico", "referência"),
            CampoAberto("etapa_id", "rotulo_tecnico", "referência"),
            CampoAberto("dia", "rotulo_tecnico", "data"),
            CampoAberto("origem", "rotulo_tecnico",
                        "quem marcou: presumido nunca conta como feito"),
            CampoAberto("nota", "texto_planejamento", "o que a pessoa escreveu ao marcar"),
        ),
    ),
    TipoDaFronteira(
        "alternativa", "fintips.contracts:Alternativa",
        abre=(
            CampoAberto("nome", "texto_planejamento", "qual caminho é este"),
            CampoAberto("custo", "valor_financeiro", "à vista", unidade="centavos_brl"),
            CampoAberto("custo_mensal", "valor_financeiro", "por mês", unidade="centavos_brl"),
            CampoAberto("horizonte_meses", "valor_financeiro", "prazo", unidade="numero"),
            CampoAberto("consequencia", "texto_planejamento", "no que dá"),
            CampoAberto("risco", "texto_planejamento", "o que pode dar errado"),
            CampoAberto("descartada_porque", "texto_planejamento",
                        "por que não esta — é o que evita repetir a conversa"),
        ),
    ),
    TipoDaFronteira(
        "traco_de_perfil", "fintips.profile:TracoDePerfil",
        abre=(
            CampoAberto("eixo", "rotulo_tecnico", "qual eixo do catálogo"),
            CampoAberto("arquetipo", "rotulo_tecnico", "a chave do arquétipo"),
            CampoAberto("nome", "texto_planejamento", "o rótulo legível do arquétipo"),
            CampoAberto("descricao", "texto_planejamento",
                        "o texto do catálogo embutido, não uma frase sobre a pessoa"),
            CampoAberto("substituiu", "rotulo_tecnico", "a travessia anterior"),
        ),
        projeta_a_parte=("proveniencia",),
    ),
    TipoDaFronteira(
        "missao", "fintips.life:Missao",
        abre=(
            CampoAberto("id", "rotulo_tecnico", "referência"),
            CampoAberto("titulo", "texto_planejamento", "a frente de vida, nas palavras dela"),
            CampoAberto("atributo", "rotulo_tecnico", "qual atributo esta missão move"),
            CampoAberto("cadencia", "rotulo_tecnico", "diária, semanal"),
            CampoAberto("como_medir", "texto_planejamento",
                        "o critério escolhido — o agente não inventa outro"),
            CampoAberto("sensor_possivel", "rotulo_tecnico", "booleano"),
            CampoAberto("porque", "texto_planejamento", "por que esta missão existe"),
            CampoAberto("ativa", "rotulo_tecnico", "booleano"),
            CampoAberto("valor_mensal", "valor_financeiro",
                        "o que ela custa por mês", unidade="centavos_brl"),
            CampoAberto("colide_com", "rotulo_tecnico", "referências"),
        ),
    ),
    TipoDaFronteira(
        # A proveniência atravessa porque é ela que diz ao agente se algo foi
        # concluído ou só ranqueado — sem isso ele trata palpite como fato.
        "proveniencia", "fintips.contracts:Proveniencia",
        abre=(
            CampoAberto("origem", "rotulo_tecnico",
                        "heurística nunca conclui; só agente e usuário concluem"),
            CampoAberto("confianca", "rotulo_tecnico", "fração do próprio app"),
            CampoAberto("porque", "texto_planejamento",
                        "a justificativa escrita na hora — é o que torna auditável"),
            CampoAberto("quando", "rotulo_tecnico", "data"),
            CampoAberto("por_quem", "rotulo_tecnico", "identificador de sessão do agente"),
        ),
        fecha=("evidencia",),   # cita memo de transação
    ),
    TipoDaFronteira(
        "decisao", "fintips.contracts:Decisao",
        abre=(
            CampoAberto("id", "rotulo_tecnico", "referência"),
            CampoAberto("titulo", "texto_planejamento", "a bifurcação, em uma linha"),
            CampoAberto("situacao", "texto_planejamento",
                        "o que aconteceu: é uma intenção de compra, que o plano libera"),
            CampoAberto("pergunta", "texto_planejamento", "o que precisa ser decidido"),
            CampoAberto("tipo", "rotulo_tecnico", "vocabulário do app"),
            CampoAberto("escolhida", "texto_planejamento", "o nome da alternativa"),
            CampoAberto("porque", "texto_planejamento",
                        "por que essa e não as outras — o que evita repetir a decisão"),
            CampoAberto("status", "rotulo_tecnico", "aberta, decidida"),
            CampoAberto("ligacoes", "rotulo_tecnico", "categoria:x, plano:y"),
            CampoAberto("revisar_em", "rotulo_tecnico", "data"),
            CampoAberto("substitui", "rotulo_tecnico", "referência"),
            CampoAberto("substituida_por", "rotulo_tecnico", "referência"),
            CampoAberto("criado_em", "rotulo_tecnico", "data"),
            CampoAberto("decidido_em", "rotulo_tecnico", "data"),
        ),
        fecha=(
            "instantaneo",    # números congelados num dict livre: sem política por campo
            "desfecho",       # idem
        ),
        projeta_a_parte=("alternativas", "proveniencia"),
    ),
    TipoDaFronteira(
        "causa", "fintips.contracts:Causa",
        # Causa é o tipo mais fechado dos nove, de propósito. Ela explica um
        # padrão **do extrato** — "por que sai R$ 400 de delivery todo mês" —
        # e a tabela do plano libera objetivo, curso, livro, produto e intenção
        # de compra, não isso. O `enunciado` está nas palavras da pessoa sobre
        # para onde o dinheiro vai, e é o lugar mais provável de um nome de
        # estabelecimento aparecer sem ninguém ter decidido liberá-lo. Fica
        # fechado até o usuário decidir: é uma pergunta de produto, não minha.
        abre=(
            CampoAberto("id", "rotulo_tecnico", "referência"),
            CampoAberto("efeito_tipo", "rotulo_tecnico", "categoria, contraparte, plano"),
            CampoAberto("natureza", "rotulo_tecnico", "vocabulário do app"),
            CampoAberto("atitude", "rotulo_tecnico", "manter, reduzir, cortar"),
            CampoAberto("revisar_em", "rotulo_tecnico", "data"),
            CampoAberto("criado_em", "rotulo_tecnico", "data"),
        ),
        fecha=(
            "efeito_ref",     # aponta para categoria OU contraparte
            "enunciado",      # as palavras dela sobre o extrato
            "atitude_nota",   # texto livre
            "evidencia",      # cita transações
        ),
        projeta_a_parte=("proveniencia",),
    ),
)

POR_TIPO: dict[str, TipoDaFronteira] = {t.nome: t for t in TIPOS_DA_FRONTEIRA}


def politica_do_campo(tipo: str, campo: str) -> str:
    """Que política vale para este campo. Campo não declarado é `fechado`."""
    t = POR_TIPO.get(tipo)
    if t is None:
        return FECHADO
    aberto = t.por_campo.get(campo)
    return aberto.politica if aberto else FECHADO


def _centavos(valor: Any) -> int | None:
    """Reais para centavos, com o mesmo arredondamento do resto do motor.

    HALF_EVEN porque é o que o `round()` do Python faz e o que o porte Kotlin
    replica em `arredondar()`. Dinheiro atravessa a fronteira como inteiro,
    nunca como fração.
    """
    if valor is None:
        return None
    d = Decimal(str(valor)) * 100
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def alias_financeiro(valor: str, *, identidades: dict[str, str], salt: str = "") -> str:
    """O alias que substitui uma identidade financeira na saída.

    Primeiro o mapa local, que dá um rótulo legível e estável escolhido no
    aparelho. Sem entrada no mapa, o próprio aparelho emite um pseudônimo com
    o salt — que também é local, e é o que torna o alias estável entre
    chamadas sem nunca mandar o nome.
    """
    from . import privacy

    # Normaliza os dois lados: quem escreve o mapa à mão escreve "loja do zé",
    # e o extrato traz "LOJA DO ZE LTDA". Comparar as duas formas cruas erra
    # sempre, e errar aqui significa emitir pseudônimo onde havia um rótulo.
    # Nome vazio não tem identidade para proteger, e emitir pseudônimo de ""
    # criaria um alias estável para "ninguém" — que depois junta transações sem
    # contraparte como se fossem o mesmo destino.
    if not valor.strip():
        return ""
    procurado = privacy._norm(valor)
    for bruto, alias in identidades.items():
        if privacy._norm(bruto) == procurado:
            return alias
    if not salt:
        return ""
    return privacy.pseudonym(valor, salt)


def _texto_sem_identidades(texto: str, identidades: dict[str, str]) -> tuple[str, bool]:
    """Troca por alias as identidades **conhecidas** que aparecem no texto.

    E o limite é esse mesmo, dito aqui para não ser prometido mais tarde: isto
    substitui o que está no mapa local. Não detecta o nome de um
    estabelecimento que ninguém cadastrou, e nenhuma expressão regular ou
    instrução de redação detecta. Por isso a fronteira é por campo e fecha por
    omissão: a proteção vem de o campo não sair, não de uma varredura no texto.
    """
    import re as _re

    from . import privacy

    trocou = False
    saida = texto
    for bruto, alias in sorted(identidades.items(), key=lambda kv: -len(kv[0])):
        if not bruto:
            continue
        padrao = _re.compile(_re.escape(bruto), _re.IGNORECASE)
        novo = padrao.sub(alias, saida)
        if novo != saida:
            saida, trocou = novo, True
        # O mapa é indexado pela forma normalizada; tenta também sem acento.
        if privacy._norm(bruto) != bruto.lower():
            padrao = _re.compile(_re.escape(privacy._norm(bruto)), _re.IGNORECASE)
            novo = padrao.sub(alias, saida)
            if novo != saida:
                saida, trocou = novo, True
    return saida, trocou


def projetar(
    tipo: str,
    dados: dict,
    *,
    identidades: dict[str, str] | None = None,
    salt: str = "",
) -> dict:
    """O que deste artefato pode atravessar a fronteira.

    Devolve o que sai e, separado, o que ficou retido com o motivo. O nome do
    campo retido sai; o valor dele não — saber que existe uma lacuna é o que
    permite ao agente pedir a informação pelo caminho certo, em vez de
    adivinhar. É a mesma escolha da tela de licenças: diga, em vez de esconder.
    """
    t = POR_TIPO.get(tipo)
    if t is None:
        raise ValueError(
            f"tipo '{tipo}' não está na fronteira. Os declarados são "
            f"{', '.join(sorted(POR_TIPO))}"
        )
    identidades = {k: v for k, v in (identidades or {}).items()}
    campos: dict[str, Any] = {}
    retidos: list[dict] = []
    aberto_por_campo = t.por_campo

    for campo, valor in dados.items():
        regra = aberto_por_campo.get(campo)
        if regra is None:
            # Os dois motivos levam ao mesmo lugar e dizem coisas diferentes:
            # declarado em `fecha` é uma decisão tomada; ausente é um campo que
            # ninguém classificou — seguro, e sinal de que o portão vai quebrar.
            retidos.append({
                "campo": campo,
                "politica": FECHADO,
                "porque": (
                    "fechado por declaração" if campo in t.fecha
                    else f"sai pelo tipo próprio, item por item: projete '{campo}'"
                    if campo in t.projeta_a_parte
                    else "não classificado na fronteira deste tipo: fecha por "
                         "omissão, e o portão cobra"
                ),
            })
            continue
        if valor is None:
            campos[campo] = None
            continue
        if regra.politica == "identidade_financeira_local" and not str(valor).strip():
            campos[campo] = {"tipo": "codigo", "valor": ""}
            continue
        if regra.politica == "segredo_local":
            retidos.append({"campo": campo, "politica": regra.politica,
                            "porque": POLITICAS_DE_SAIDA[regra.politica]})
        elif regra.politica == "valor_financeiro":
            if regra.unidade == "centavos_brl":
                campos[campo] = {"tipo": "quantidade", "valor": _centavos(valor),
                                 "unidade": "centavos_brl"}
            else:
                campos[campo] = {"tipo": "quantidade", "valor": int(valor),
                                 "unidade": regra.unidade or "numero"}
        elif regra.politica == "identidade_financeira_local":
            alias = alias_financeiro(str(valor), identidades=identidades, salt=salt)
            if alias:
                campos[campo] = {"tipo": "codigo", "valor": alias}
            else:
                retidos.append({
                    "campo": campo,
                    "politica": regra.politica,
                    "porque": "sem alias e sem salt para emitir um no aparelho",
                })
        elif regra.politica == "texto_planejamento":
            texto, trocou = _texto_sem_identidades(str(valor), identidades)
            campos[campo] = {"tipo": "texto_planejamento", "valor": texto}
            if trocou:
                campos[campo]["identidade_substituida"] = True
        elif isinstance(valor, (date, datetime)):   # rotulo_tecnico temporal
            campos[campo] = valor.isoformat()
        else:   # rotulo_tecnico
            campos[campo] = valor

    return {
        "tipo": tipo,
        "campos": campos,
        "retidos": retidos,
        "aviso": (
            "a proteção é por campo: um campo fechado não sai. A substituição "
            "em texto cobre só as identidades do mapa local — não existe "
            "detecção de nome que ninguém cadastrou"
        ),
    }


def conferir_fronteira() -> dict:
    """A política ainda classifica todos os campos dos tipos da fronteira?

    Quatro jeitos de a fronteira se tornar mentira:

    - campo novo na classe, sem política: ele fecha, o que é seguro, mas em
      silêncio — e quem o acrescentou talvez quisesse que ele saísse;
    - política declarada para campo que não existe mais: a projeção para de
      emitir um campo que a tela ou o agente esperam, sem ninguém saber;
    - política fora do vocabulário, que o executor não sabe aplicar;
    - `valor_financeiro` sem unidade, que atravessa como número sem escala —
      é assim que centavo vira real.
    """
    import importlib
    from dataclasses import fields as campos_de

    sem_politica: list[str] = []
    fora_do_codigo: list[str] = []
    politica_invalida: list[str] = []
    valor_sem_unidade: list[str] = []
    tipos_quebrados: list[str] = []

    for t in TIPOS_DA_FRONTEIRA:
        modulo, _, classe = t.classe.partition(":")
        try:
            alvo = getattr(importlib.import_module(modulo), classe)
            na_classe = {f.name for f in campos_de(alvo)}
        except (ImportError, AttributeError, TypeError):
            tipos_quebrados.append(t.nome)
            continue
        declarados = {c.campo for c in t.abre} | set(t.nao_sai_neste_campo)
        sem_politica += [f"{t.nome}.{c}" for c in sorted(na_classe - declarados)]
        fora_do_codigo += [f"{t.nome}.{c}" for c in sorted(declarados - na_classe)]
        for c in t.abre:
            if c.politica not in POLITICAS_DE_SAIDA:
                politica_invalida.append(f"{t.nome}.{c.campo}={c.politica}")
            if c.politica == "valor_financeiro" and c.unidade not in UNIDADES:
                valor_sem_unidade.append(f"{t.nome}.{c.campo}")

    abertos = sum(len(t.abre) for t in TIPOS_DA_FRONTEIRA)
    fechados = sum(len(t.fecha) for t in TIPOS_DA_FRONTEIRA)
    a_parte = sum(len(t.projeta_a_parte) for t in TIPOS_DA_FRONTEIRA)
    return {
        "ok": not (sem_politica or fora_do_codigo or politica_invalida
                   or valor_sem_unidade or tipos_quebrados),
        "campo_sem_politica": sem_politica,
        "declarado_e_fora_do_codigo": fora_do_codigo,
        "politica_desconhecida": politica_invalida,
        "valor_financeiro_sem_unidade": valor_sem_unidade,
        "tipo_que_nao_resolve": tipos_quebrados,
        "quantos": {"tipos": len(TIPOS_DA_FRONTEIRA), "abertos": abertos,
                    "fechados": fechados, "projetados_a_parte": a_parte},
        "como_corrigir": (
            "classifique o campo em TIPOS_DA_FRONTEIRA: em `abre`, com política "
            "e porquê, se ele deve sair; em `fecha`, se não deve. Não sair é o "
            "padrão e não precisa de justificativa — sair precisa"
        ),
    }
