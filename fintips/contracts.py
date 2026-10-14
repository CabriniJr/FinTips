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
