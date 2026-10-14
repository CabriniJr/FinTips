"""Objetivos: o plano decomposto em etapas, com prazo, custo e dependência.

Um plano financeiro responde "quanto e até quando". Isso é pouco para a maior
parte das coisas que alguém quer. Tirar uma certificação não é uma linha de
R$ 2.000 em dezembro: são três cursos com prazo cada um, uma prova marcada, um
voucher que vence, e o estudo diário que sustenta tudo. O dinheiro é **uma**
das frentes, e normalmente não é a que falha.

Este módulo guarda esse objeto composto e faz três coisas com ele — as mesmas
três que o motor faz em todo lugar: **guarda, aplica e calcula**.

- **Correlaciona** o que foi declarado: a etapa custa, e o custo encontra o
  plano financeiro; a etapa exige constância, e a constância encontra a missão.
  O motor nunca descobre esses laços: quem escreve `plano_id` e `missoes` é o
  agente, na conversa, e a pessoa assina. Laço que aponta para o vazio aparece
  em `orfaos` em vez de ser engolido.
- **Agenda**: quais etapas vencem na janela, qual está bloqueada por
  dependência não cumprida, e o que exatamente marcar.
- **Pontua**: um score por objetivo, cinco dimensões, fórmula visível em cada
  componente — como em `score.py`, e pelo mesmo motivo: número que ninguém
  consegue refazer à mão não muda comportamento, só decora tela.

## As três decisões que sustentam o módulo

**O rascunho não entra na agenda.** O agente cria o objetivo inteiro a partir
do texto da conversa, e isso nasce como `rascunho`. Objetivo só conta — na
agenda, no score, nos gauges — depois de `assinado`. Não é cerimônia: agenda
que se enche de item que a pessoa nunca combinou é o caminho mais curto para
ela desinstalar o app. O agente propõe a estrutura; a pessoa assina.

**O prazo original não se apaga.** Reajustar é o ponto do produto — "caso não
tenha feito, dá para ir reajustando" — e é também o buraco óbvio: se o score
olha só o prazo de agora, basta empurrar a data para estar sempre em 100%.
Então cada etapa guarda `prazo_original` e conta `adiamentos`, e **o adiamento
é uma das cinco dimensões do score**. Empurrar é permitido e fica registrado.

**O reajuste é aritmética, não opinião.** O motor calcula o atraso, empurra a
etapa para hoje, cascateia o mesmo deslocamento nas dependentes e diz se isso
estoura a data alvo. Ele não escolhe cortar etapa, não negocia prazo e não
aplica nada sozinho: a proposta sai com `origem: agente` e `assinado: false`.

## Onde estes dados moram

`data/objetivos.yaml` e `data/checks.jsonl`, no workspace, **fora do Git** —
pelo mesmo motivo de `missoes.yaml`: objetivo de vida tem empregador, salário,
nome de curso pago e data de prova. O pacote carrega só o molde em
`rules/exemplo-objetivos.yaml`.

Os checks vão num arquivo próprio, separado de `registros.jsonl`, porque o
carregador das missões recusa registro de missão desconhecida — e deve
continuar recusando. Misturar os dois transformaria essa recusa em ruído.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import yaml

from .plans import months_until
from .life import (
    AUTORIDADE_MINIMA_PARA_CUMPRIR,
    ORIGENS_DO_REGISTRO,
    CADENCIAS,
    Vida,
    estado_diario,
)

OBJETIVOS_SCHEMA = 1
Z = Decimal("0")

# O que uma etapa pode ser. Não é taxonomia fechada por gosto: o tipo muda o
# que o agente pergunta depois ("o curso tem certificado?" não cabe numa prova)
# e muda o que a tela mostra. Tipo desconhecido é recusado para não virar
# `outro` silencioso — rótulo errado some do relatório.
TIPOS_DE_ETAPA = ("curso", "prova", "leitura", "pratica", "compra", "entrega", "outro")

# Estados derivados, nunca gravados. Status em arquivo mente: ele envelhece
# sozinho quando o prazo passa e ninguém abriu o app.
STATUS = ("rascunho", "em_andamento", "atrasado", "concluido")

# Pesos do score, explícitos. Somam 100.
PESOS = {
    "prazo": 30,       # o que venceu, venceu feito?
    "adiamento": 15,   # quantas vezes a data foi empurrada
    "ritmo": 25,       # o progresso acompanha o tempo gasto?
    "dinheiro": 15,    # o plano financeiro cobre o que falta?
    "constancia": 15,  # as missões que sustentam o objetivo estão de pé?
}


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _faixa(score: float) -> str:
    if score >= 85:
        return "em_dia"
    if score >= 70:
        return "bom"
    if score >= 55:
        return "atencao"
    if score >= 40:
        return "em_risco"
    return "travado"


def _dia(v) -> date | None:
    if v is None or v == "":
        return None
    return date.fromisoformat(v) if isinstance(v, str) else v


# --------------------------------------------------------------------- tipos


@dataclass
class Etapa:
    """Um passo com prazo próprio. O objeto que a IA cria a partir do texto."""

    id: str
    titulo: str
    tipo: str = "outro"
    prazo: date | None = None
    # A data em que esta etapa foi prometida pela primeira vez. Nunca muda.
    prazo_original: date | None = None
    adiamentos: int = 0
    custo: Decimal = Z
    depende_de: list[str] = field(default_factory=list)
    obrigatoria: bool = True
    porque: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Etapa":
        tipo = str(d.get("tipo", "outro")).strip().lower()
        if tipo not in TIPOS_DE_ETAPA:
            raise ValueError(
                f"etapa '{d.get('id')}': tipo '{tipo}' não existe. "
                f"Os sete são {', '.join(TIPOS_DE_ETAPA)}"
            )
        prazo = _dia(d.get("prazo"))
        return cls(
            id=d["id"],
            titulo=d.get("titulo", d["id"]),
            tipo=tipo,
            prazo=prazo,
            # Quem não trouxe original é porque nunca foi adiado: o prazo de
            # agora é o primeiro. Assumir isso é seguro; inventar outro não.
            prazo_original=_dia(d.get("prazo_original")) or prazo,
            adiamentos=int(d.get("adiamentos", 0) or 0),
            custo=Decimal(str(d.get("custo", 0) or 0)),
            depende_de=[str(x) for x in (d.get("depende_de") or [])],
            obrigatoria=bool(d.get("obrigatoria", True)),
            porque=d.get("porque", "") or "",
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "titulo": self.titulo,
            "tipo": self.tipo,
            "prazo": self.prazo.isoformat() if self.prazo else None,
            "prazo_original": self.prazo_original.isoformat() if self.prazo_original else None,
            "adiamentos": self.adiamentos,
            "custo": float(self.custo),
            "depende_de": list(self.depende_de),
            "obrigatoria": self.obrigatoria,
            "porque": self.porque,
        }

    @property
    def dias_adiados(self) -> int:
        if not self.prazo or not self.prazo_original:
            return 0
        return max((self.prazo - self.prazo_original).days, 0)


@dataclass
class Objetivo:
    """Uma coisa que a pessoa quer, decomposta no que ela exige."""

    id: str
    titulo: str
    porque: str = ""
    comecou_em: date | None = None
    data_alvo: date | None = None
    # Os laços, declarados. O motor não descobre nenhum dos dois.
    plano_id: str = ""
    missoes: list[str] = field(default_factory=list)
    etapas: list[Etapa] = field(default_factory=list)
    # Quem escreveu, e por quê. `agente` cria; só `usuario` assina.
    origem: str = "agente"
    porque_da_origem: str = ""
    assinado_em: date | None = None
    arquivado: bool = False

    @property
    def assinado(self) -> bool:
        return self.assinado_em is not None

    @classmethod
    def from_dict(cls, d: dict) -> "Objetivo":
        origem = str(d.get("origem", "agente")).strip().lower()
        if origem not in ORIGENS_DO_REGISTRO:
            raise ValueError(
                f"objetivo '{d.get('id')}': origem '{origem}' não existe. As quatro "
                f"são {', '.join(ORIGENS_DO_REGISTRO)}"
            )
        if ORIGENS_DO_REGISTRO[origem] < AUTORIDADE_MINIMA_PARA_CUMPRIR:
            raise ValueError(
                f"objetivo '{d.get('id')}': origem '{origem}' não cria objetivo. "
                "Objetivo nasce de conversa (`agente`) ou da pessoa (`usuario`) — "
                "o app supor que você quer uma certificação não é você querer"
            )
        if not str(d.get("porque", "")).strip():
            raise ValueError(
                f"objetivo '{d.get('id')}' sem `porque` — objetivo que entra na "
                "agenda de alguém precisa dizer o que ele resolve"
            )
        etapas = [Etapa.from_dict(e) for e in (d.get("etapas") or [])]
        vistos: set[str] = set()
        for e in etapas:
            if e.id in vistos:
                raise ValueError(
                    f"objetivo '{d.get('id')}': etapa '{e.id}' aparece duas vezes"
                )
            vistos.add(e.id)
        for e in etapas:
            for dep in e.depende_de:
                if dep not in vistos:
                    raise ValueError(
                        f"etapa '{e.id}' depende de '{dep}', que não é etapa deste "
                        "objetivo — dependência pendurada trava a agenda em silêncio"
                    )
                if dep == e.id:
                    raise ValueError(f"etapa '{e.id}' depende de si mesma")
        return cls(
            id=d["id"],
            titulo=d.get("titulo", d["id"]),
            porque=str(d["porque"]).strip(),
            comecou_em=_dia(d.get("comecou_em")),
            data_alvo=_dia(d.get("data_alvo")),
            plano_id=d.get("plano_id", "") or "",
            missoes=[str(x) for x in (d.get("missoes") or [])],
            etapas=etapas,
            origem=origem,
            porque_da_origem=d.get("porque_da_origem", "") or "",
            assinado_em=_dia(d.get("assinado_em")),
            arquivado=bool(d.get("arquivado", False)),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "titulo": self.titulo,
            "porque": self.porque,
            "comecou_em": self.comecou_em.isoformat() if self.comecou_em else None,
            "data_alvo": self.data_alvo.isoformat() if self.data_alvo else None,
            "plano_id": self.plano_id,
            "missoes": list(self.missoes),
            "etapas": [e.to_dict() for e in self.etapas],
            "origem": self.origem,
            "porque_da_origem": self.porque_da_origem,
            "assinado_em": self.assinado_em.isoformat() if self.assinado_em else None,
            "arquivado": self.arquivado,
        }

    def etapa(self, etapa_id: str) -> Etapa | None:
        return next((e for e in self.etapas if e.id == etapa_id), None)

    @property
    def custo_total(self) -> Decimal:
        return sum((e.custo for e in self.etapas), Z)


@dataclass
class Check:
    """Uma etapa marcada como feita. Histórico, em append — nunca sobrescrito."""

    objetivo_id: str
    etapa_id: str
    dia: date
    origem: str
    nota: str = ""

    @property
    def conta_como_cumprido(self) -> bool:
        return ORIGENS_DO_REGISTRO[self.origem] >= AUTORIDADE_MINIMA_PARA_CUMPRIR

    @classmethod
    def from_dict(cls, d: dict) -> "Check":
        origem = str(d.get("origem", "")).strip().lower()
        if origem not in ORIGENS_DO_REGISTRO:
            raise ValueError(
                f"origem '{origem}' não existe. As quatro são "
                f"{', '.join(ORIGENS_DO_REGISTRO)}"
            )
        return cls(
            objetivo_id=d["objetivo_id"],
            etapa_id=d["etapa_id"],
            dia=_dia(d["dia"]),
            origem=origem,
            nota=d.get("nota", "") or "",
        )

    def to_dict(self) -> dict:
        return {
            "objetivo_id": self.objetivo_id,
            "etapa_id": self.etapa_id,
            "dia": self.dia.isoformat(),
            "origem": self.origem,
            "nota": self.nota,
        }


# --------------------------------------------------------------------- lojas


class ObjetivoStore:
    """Os objetivos da pessoa, como arquivo que ela pode abrir e ler."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.objetivos: dict[str, Objetivo] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        d = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        for o in d.get("objetivos") or []:
            obj = Objetivo.from_dict(o)
            if obj.id in self.objetivos:
                raise ValueError(f"objetivo '{obj.id}' aparece duas vezes")
            self.objetivos[obj.id] = obj

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": OBJETIVOS_SCHEMA,
                    "objetivos": [o.to_dict() for o in self.objetivos.values()],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    # ------------------------------------------------------------- escrita
    def criar(self, d: dict) -> Objetivo:
        """Grava o objetivo que a conversa montou. Nasce rascunho, sempre.

        Mesmo quando quem cria é o `usuario`: a assinatura é um segundo ato, e
        existe para que a decomposição — que foi o agente quem escreveu — passe
        pelos olhos de quem vai cumprir as etapas.
        """
        obj = Objetivo.from_dict({**d, "assinado_em": None})
        if obj.id in self.objetivos:
            raise ValueError(
                f"objetivo '{obj.id}' já existe. Para mudar, edite as etapas — "
                "recriar por cima apagaria os adiamentos já contados"
            )
        self.objetivos[obj.id] = obj
        return obj

    def assinar(self, objetivo_id: str, *, quando: date | None = None) -> Objetivo:
        """A pessoa confirma a decomposição. Só a partir daqui o objetivo conta."""
        obj = self.objetivos.get(objetivo_id)
        if obj is None:
            raise ValueError(f"objetivo '{objetivo_id}' não existe")
        if not obj.etapas:
            raise ValueError(
                f"objetivo '{objetivo_id}' não tem etapa nenhuma — assinar isso "
                "seria assinar uma intenção, e intenção não entra em agenda"
            )
        obj.assinado_em = quando or date.today()
        return obj

    def ativos(self) -> list[Objetivo]:
        return [o for o in self.objetivos.values() if o.assinado and not o.arquivado]

    def rascunhos(self) -> list[Objetivo]:
        return [o for o in self.objetivos.values() if not o.assinado and not o.arquivado]


def carregar_checks(path: str | Path) -> list[Check]:
    p = Path(path)
    if not p.exists():
        return []
    saida = []
    for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        linha = linha.strip()
        if not linha:
            continue
        try:
            saida.append(Check.from_dict(json.loads(linha)))
        except (KeyError, ValueError) as e:
            raise ValueError(f"{p.name}:{n}: {e}") from e
    return saida


def marcar(path: str | Path, check: Check) -> Check:
    """Grava um check, em append — como os registros de missão, e pelo mesmo
    motivo: reescrever o arquivo inteiro a cada marcação permite perder o
    passado num erro de escrita. Append só sabe crescer."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(check.to_dict(), ensure_ascii=False) + "\n")
    return check


# ------------------------------------------------------------------- estado


def cumprimento(objetivo: Objetivo, checks: list[Check]) -> dict[str, Check]:
    """O primeiro check válido de cada etapa deste objetivo.

    O primeiro, e não o último: quem marcou, marcou. Um segundo check — a
    pessoa reabrindo o app e clicando de novo — não deve mover a data que vale
    para o cálculo de prazo, ou marcar duas vezes pioraria a nota.
    """
    saida: dict[str, Check] = {}
    for c in sorted(checks, key=lambda c: c.dia):
        if c.objetivo_id != objetivo.id or not c.conta_como_cumprido:
            continue
        if objetivo.etapa(c.etapa_id) is None:
            continue
        saida.setdefault(c.etapa_id, c)
    return saida


def situacao_da_etapa(
    etapa: Etapa,
    feito: dict[str, Check],
    hoje: date,
) -> str:
    """`feita` | `bloqueada` | `atrasada` | `hoje` | `a_vencer` | `sem_prazo`."""
    if etapa.id in feito:
        return "feita"
    if any(dep not in feito for dep in etapa.depende_de):
        return "bloqueada"
    if etapa.prazo is None:
        return "sem_prazo"
    if etapa.prazo < hoje:
        return "atrasada"
    if etapa.prazo == hoje:
        return "hoje"
    return "a_vencer"


def status_do_objetivo(objetivo: Objetivo, checks: list[Check], hoje: date) -> str:
    if not objetivo.assinado:
        return "rascunho"
    feito = cumprimento(objetivo, checks)
    obrigatorias = [e for e in objetivo.etapas if e.obrigatoria]
    if obrigatorias and all(e.id in feito for e in obrigatorias):
        return "concluido"
    if any(situacao_da_etapa(e, feito, hoje) == "atrasada" for e in objetivo.etapas):
        return "atrasado"
    return "em_andamento"


# --------------------------------------------------------------- correlação


def _estado_de_missao(vida: Vida, missao_id: str, hoje: date) -> dict | None:
    m = next((m for m in vida.missoes if m.id == missao_id), None)
    if m is None:
        return None
    if m.cadencia == "diaria":
        e = estado_diario(m, vida.registros, hoje)
        return {
            "missao": m.id,
            "titulo": m.titulo,
            "atributo": m.atributo,
            "cadencia": m.cadencia,
            "de_pe": bool(e["cumprida_na_janela"] or e["sequencia"] > 0),
            "sequencia": e["sequencia"],
        }
    inicio = hoje - timedelta(days=CADENCIAS[m.cadencia] - 1)
    feita = any(
        r.missao_id == m.id and r.conta_como_cumprido and inicio <= r.dia <= hoje
        for r in vida.registros
    )
    return {
        "missao": m.id,
        "titulo": m.titulo,
        "atributo": m.atributo,
        "cadencia": m.cadencia,
        "de_pe": feita,
        "sequencia": None,
    }


def correlacionar(
    objetivo: Objetivo,
    checks: list[Check],
    *,
    planos: list[dict] | None = None,
    vida: Vida | None = None,
    hoje: date | None = None,
) -> dict:
    """Os laços que a conversa declarou, resolvidos contra o que existe.

    O dinheiro vem de `plano_id`; a constância vem de `missoes`. **Nenhum dos
    dois é descoberto aqui**: se o agente não escreveu o laço, ele não existe,
    e se escreveu apontando para o vazio ele aparece em `orfaos` em vez de ser
    engolido — laço quebrado em silêncio é a forma mais cara de erro, porque o
    número continua saindo e só o significado muda.
    """
    hoje = hoje or date.today()
    planos = planos or []
    feito = cumprimento(objetivo, checks)
    orfaos: list[dict] = []

    restante = sum((e.custo for e in objetivo.etapas if e.id not in feito), Z)
    ja_pago = sum((e.custo for e in objetivo.etapas if e.id in feito), Z)

    plano = None
    cobertura = None
    if objetivo.plano_id:
        p = next((r for r in planos if r.get("id") == objetivo.plano_id), None)
        if p is None:
            orfaos.append({
                "tipo": "plano",
                "id": objetivo.plano_id,
                "o_que_quebra": (
                    "o objetivo diz que o dinheiro dele vem deste plano, e o plano "
                    "não está cadastrado — a dimensão `dinheiro` do score fica sem base"
                ),
            })
        else:
            plano = {
                "id": p["id"],
                "nome": p.get("nome", p["id"]),
                "guardado": p.get("guardado", 0.0),
                "aporte_planejado_mes": p.get("aporte_planejado_mes", 0.0),
                "status": p.get("status"),
            }
            meses = months_until(objetivo.data_alvo, hoje)
            guardado = Decimal(str(p.get("guardado", 0) or 0))
            aporte = Decimal(str(p.get("aporte_planejado_mes", 0) or 0))
            disponivel = guardado + aporte * (meses if meses is not None else 0)
            cobertura = {
                "custo_restante": float(restante),
                "meses_ate_o_alvo": meses,
                "disponivel_ate_la": float(disponivel),
                "falta": float(max(restante - disponivel, Z)),
                "cobre": disponivel >= restante,
            }

    missoes = []
    for mid in objetivo.missoes:
        e = _estado_de_missao(vida, mid, hoje) if vida else None
        if e is None:
            orfaos.append({
                "tipo": "missao",
                "id": mid,
                "o_que_quebra": (
                    "o objetivo se apoia nesta missão e ela não está no catálogo — "
                    "a dimensão `constancia` do score fica sem base"
                ),
            })
            continue
        missoes.append(e)

    avisos = []
    if restante > 0 and not objetivo.plano_id:
        avisos.append(
            f"as etapas que faltam custam {float(restante):.2f} e nenhum plano "
            "financeiro está ligado a este objetivo. O motor não assume que sai "
            "da sobra do mês — quem liga o plano é você, na conversa"
        )
    if not objetivo.missoes:
        avisos.append(
            "nenhuma missão sustenta este objetivo. Objetivo de prazo longo sem "
            "hábito diário por trás costuma falhar na etapa do meio, não na última"
        )

    return {
        "objetivo": objetivo.id,
        "plano": plano,
        "custo_total": float(objetivo.custo_total),
        "custo_restante": float(restante),
        "custo_ja_comprometido": float(ja_pago),
        "cobertura_financeira": cobertura,
        "missoes": missoes,
        "orfaos": orfaos,
        "avisos": avisos,
        "nota": (
            "os laços são declarados, nunca descobertos: o motor não adivinha "
            "que um plano financia um objetivo nem que uma missão o sustenta"
        ),
    }


# ------------------------------------------------------------------- agenda


def agenda(
    objetivos: list[Objetivo],
    checks: list[Check],
    hoje: date | None = None,
    *,
    dias: int = 14,
) -> list[dict]:
    """O que vence na janela, e o que já venceu sem ter sido feito.

    Só objetivo assinado entra. Rascunho não ocupa a agenda de ninguém — é essa
    a diferença entre a IA propor e a IA mandar.

    Atrasada não tem limite inferior: o que venceu há 40 dias continua
    aparecendo. Sumir com o atraso é a forma mais educada de mentir.
    """
    hoje = hoje or date.today()
    limite = hoje + timedelta(days=dias)
    itens = []
    for o in objetivos:
        if not o.assinado or o.arquivado:
            continue
        feito = cumprimento(o, checks)
        for e in o.etapas:
            sit = situacao_da_etapa(e, feito, hoje)
            if sit in ("feita", "sem_prazo"):
                continue
            if e.prazo is not None and e.prazo > limite:
                continue
            itens.append({
                "objetivo": o.id,
                "objetivo_titulo": o.titulo,
                "etapa": e.id,
                "titulo": e.titulo,
                "tipo": e.tipo,
                "prazo": e.prazo.isoformat() if e.prazo else None,
                "dias_restantes": (e.prazo - hoje).days if e.prazo else None,
                "situacao": sit,
                "bloqueada_por": [
                    dep for dep in e.depende_de if dep not in feito
                ] if sit == "bloqueada" else [],
                "custo": float(e.custo),
                "adiamentos": e.adiamentos,
                "porque": e.porque,
                # O que o widget devolve quando a pessoa toca no quadradinho.
                "marcar": {"objetivo_id": o.id, "etapa_id": e.id},
            })
    # Prazo primeiro, e o que não tem prazo por último: dependência bloqueada
    # sem data não pode empurrar para baixo o que vence hoje.
    return sorted(
        itens,
        key=lambda i: (i["prazo"] or "9999-12-31", i["objetivo"], i["etapa"]),
    )


def checks_de_hoje(
    objetivos: list[Objetivo],
    checks: list[Check],
    vida: Vida | None = None,
    hoje: date | None = None,
) -> dict:
    """A lista única do widget: missões do dia e etapas que vencem.

    O widget mora na tela inicial do celular e tem espaço para poucas linhas,
    então a lista é uma só. Missão e etapa são coisas diferentes no motor e a
    mesma coisa para o dedo da pessoa — `tipo` diz qual é, e `marcar` carrega
    exatamente o que o app precisa devolver.
    """
    hoje = hoje or date.today()
    linhas: list[dict] = []

    if vida is not None:
        for m in vida.missoes:
            if not m.ativa or m.cadencia != "diaria":
                continue
            e = estado_diario(m, vida.registros, hoje)
            linhas.append({
                "tipo": "missao",
                "id": m.id,
                "titulo": m.titulo,
                "contexto": f"frente {m.atributo}",
                "feito": bool(e["cumprida_na_janela"]),
                "sequencia": e["sequencia"],
                "marcar": {"missao_id": m.id},
            })

    for item in agenda(objetivos, checks, hoje, dias=0):
        # Etapa bloqueada fica de fora do widget — e só dele. A agenda completa
        # continua mostrando, porque lá ela explica por que o prazo vai
        # estourar. No widget ela só ofereceria um quadradinho para marcar algo
        # que ainda não dá para fazer, e marcar fora de ordem estraga o
        # histórico que o resto do motor usa.
        if item["situacao"] == "bloqueada":
            continue
        linhas.append({
            "tipo": "etapa",
            "id": item["etapa"],
            "titulo": item["titulo"],
            "contexto": item["objetivo_titulo"],
            "feito": False,
            "situacao": item["situacao"],
            "marcar": item["marcar"],
        })

    feitos = sum(1 for l in linhas if l["feito"])
    return {
        "dia": hoje.isoformat(),
        "linhas": linhas,
        "feitos": feitos,
        "total": len(linhas),
        # Sem elogio e sem cobrança: a contagem, e só. Quem abre o app às 23h
        # depois de um dia ruim não precisa de um "você consegue!".
        "resumo": f"{feitos} de {len(linhas)} hoje",
    }



# -------------------------------------------------------------------- score


def score_do_objetivo(
    objetivo: Objetivo,
    checks: list[Check],
    hoje: date | None = None,
    *,
    correlacao: dict | None = None,
) -> dict:
    """0–100 em cinco dimensões, com a fórmula de cada uma à vista.

    Duas escolhas de projeto, as duas feitas contra o jeito fácil:

    **Dimensão sem base não vira zero.** Objetivo que começou ontem não tem
    etapa vencida; pontuar isso como 0 em `prazo` diria "você está falhando" a
    quem ainda não teve chance de falhar. Então a dimensão sai com `valor:
    null`, o peso dela não entra na conta, e `peso_aplicado` mostra sobre
    quanto o número foi calculado. Score de 100 sobre peso 15 é informação
    diferente de score de 100 sobre peso 100, e a tela precisa poder dizer isso.

    **Adiar custa.** `prazo` mede contra a data de hoje, o que sozinho seria
    gamificável: basta empurrar tudo para a frente e nada nunca vence atrasado.
    Por isso `adiamento` é dimensão própria, medindo contra `prazo_original`.
    Empurrar continua permitido — é o ponto do reajuste — mas aparece.
    """
    hoje = hoje or date.today()
    feito = cumprimento(objetivo, checks)
    componentes: list[dict] = []

    def dim(nome: str, valor: float | None, formula: str, detalhe: dict) -> None:
        componentes.append({
            "dimensao": nome,
            "peso": PESOS[nome],
            "valor": round(_clamp(valor), 4) if valor is not None else None,
            "pontos": round(_clamp(valor) * PESOS[nome], 2) if valor is not None else None,
            "formula": formula,
            **detalhe,
        })

    # 1. prazo — do que já venceu, quanto venceu feito
    cobraveis = [
        e for e in objetivo.etapas
        if e.id in feito or (e.prazo is not None and e.prazo < hoje)
    ]
    no_prazo = [
        e for e in cobraveis
        if e.id in feito and (e.prazo is None or feito[e.id].dia <= e.prazo)
    ]
    dim(
        "prazo",
        len(no_prazo) / len(cobraveis) if cobraveis else None,
        "etapas cumpridas até o prazo ÷ etapas que já venceram ou já foram feitas",
        {
            "etapas_cobraveis": len(cobraveis),
            "cumpridas_no_prazo": len(no_prazo),
            "sem_base": "nenhuma etapa venceu ainda" if not cobraveis else None,
        },
    )

    # 2. adiamento — quantas vezes a data foi empurrada
    com_prazo = [e for e in objetivo.etapas if e.prazo_original is not None]
    total_adiamentos = sum(e.adiamentos for e in com_prazo)
    dim(
        "adiamento",
        1 - (total_adiamentos / len(com_prazo)) if com_prazo else None,
        "1 − (adiamentos ÷ etapas com prazo); um adiamento por etapa zera",
        {
            "adiamentos": total_adiamentos,
            "etapas_com_prazo": len(com_prazo),
            "dias_empurrados": sum(e.dias_adiados for e in com_prazo),
            "sem_base": "nenhuma etapa tem prazo" if not com_prazo else None,
        },
    )

    # 3. ritmo — o progresso acompanha o tempo gasto?
    obrigatorias = [e for e in objetivo.etapas if e.obrigatoria]
    feitas_obrig = [e for e in obrigatorias if e.id in feito]
    valor_ritmo = None
    detalhe_ritmo: dict = {
        "sem_base": "objetivo sem `comecou_em` e `data_alvo` — sem janela para medir ritmo",
    }
    if objetivo.comecou_em and objetivo.data_alvo and obrigatorias:
        span = (objetivo.data_alvo - objetivo.comecou_em).days
        corrido = (hoje - objetivo.comecou_em).days
        if span > 0 and corrido > 0:
            tempo = _clamp(corrido / span)
            progresso = len(feitas_obrig) / len(obrigatorias)
            valor_ritmo = progresso / tempo if tempo > 0 else None
            detalhe_ritmo = {
                "tempo_decorrido": round(tempo, 4),
                "progresso": round(progresso, 4),
                "etapas_obrigatorias": len(obrigatorias),
                "feitas": len(feitas_obrig),
                "sem_base": None,
            }
        else:
            detalhe_ritmo = {
                "sem_base": "o objetivo começa hoje — ainda não há tempo decorrido",
            }
    dim(
        "ritmo",
        valor_ritmo,
        "(etapas obrigatórias feitas ÷ total) ÷ (dias corridos ÷ dias até o alvo)",
        detalhe_ritmo,
    )

    # 4. dinheiro — o plano ligado cobre o que falta
    cob = (correlacao or {}).get("cobertura_financeira")
    restante = Decimal(str((correlacao or {}).get("custo_restante", 0) or 0))
    valor_dinheiro = None
    detalhe_dinheiro: dict = {
        "sem_base": (
            "nenhum plano financeiro ligado, ou nada a pagar — o motor não "
            "supõe de onde o dinheiro sai"
        ),
    }
    if cob and restante > 0:
        disponivel = Decimal(str(cob["disponivel_ate_la"]))
        valor_dinheiro = float(disponivel / restante)
        detalhe_dinheiro = {
            "custo_restante": float(restante),
            "disponivel_ate_la": float(disponivel),
            "sem_base": None,
        }
    elif cob and restante == 0:
        detalhe_dinheiro = {"sem_base": "não falta nada a pagar neste objetivo"}
    dim(
        "dinheiro",
        valor_dinheiro,
        "disponível até a data alvo ÷ custo das etapas que faltam",
        detalhe_dinheiro,
    )

    # 5. constância — as missões declaradas estão de pé
    missoes = (correlacao or {}).get("missoes") or []
    dim(
        "constancia",
        sum(1 for m in missoes if m["de_pe"]) / len(missoes) if missoes else None,
        "missões ligadas que estão de pé na janela delas ÷ missões ligadas",
        {
            "missoes_ligadas": len(missoes),
            "de_pe": sum(1 for m in missoes if m["de_pe"]),
            "sem_base": "nenhuma missão ligada a este objetivo" if not missoes else None,
        },
    )

    com_base = [c for c in componentes if c["valor"] is not None]
    peso_aplicado = sum(c["peso"] for c in com_base)
    bruto = sum(c["pontos"] for c in com_base)
    score = round(bruto / peso_aplicado * 100, 1) if peso_aplicado else 0.0

    return {
        "objetivo": objetivo.id,
        "titulo": objetivo.titulo,
        "status": status_do_objetivo(objetivo, checks, hoje),
        "score": score,
        "faixa": _faixa(score) if peso_aplicado else "sem_base",
        "peso_aplicado": peso_aplicado,
        "peso_total": sum(PESOS.values()),
        "componentes": componentes,
        "nota": (
            "cada ponto tem fórmula visível e dimensão sem base não vira zero. "
            "Um score sobre peso parcial é um score sobre peso parcial, e a tela "
            "precisa dizer isso em vez de mostrar 100 como se fosse o todo"
        ),
    }


# ----------------------------------------------------------------- reajuste


def reajuste_proposto(
    objetivo: Objetivo,
    checks: list[Check],
    hoje: date | None = None,
) -> dict:
    """"Não deu para fazer" vira aritmética, não negociação.

    O cálculo é simples de propósito, para caber inteiro na cabeça de quem lê:
    cada etapa atrasada vai para hoje, e tudo que depende dela anda o mesmo
    tanto de dias. O deslocamento se propaga pela cadeia de dependências — se
    o curso 2 atrasou 12 dias, o curso 3 atrasa 12 dias, e a prova também.

    O que o motor **não** faz: não corta etapa, não sugere trocar o objetivo,
    não decide que ainda dá tempo. Ele diz quanto a folga até a data alvo
    encolheu e se ela acabou. A proposta sai com `assinado: false` — aplicar é
    outro ato, e é da pessoa.
    """
    hoje = hoje or date.today()
    feito = cumprimento(objetivo, checks)

    # Quanto cada etapa anda. Uma etapa atrasada define o próprio empurrão; as
    # demais herdam o maior empurrão de quem elas dependem.
    empurrao: dict[str, int] = {}
    for e in objetivo.etapas:
        if e.id in feito or e.prazo is None:
            continue
        if e.prazo < hoje:
            empurrao[e.id] = (hoje - e.prazo).days

    # Propaga pela cadeia. O laço roda no máximo uma vez por etapa: a cada
    # passada ou algo mudou, ou o ponto fixo foi alcançado.
    for _ in range(len(objetivo.etapas)):
        mudou = False
        for e in objetivo.etapas:
            if e.id in feito or e.prazo is None:
                continue
            herdado = max((empurrao.get(d, 0) for d in e.depende_de), default=0)
            if herdado > empurrao.get(e.id, 0):
                empurrao[e.id] = herdado
                mudou = True
        if not mudou:
            break

    movimentos = []
    for e in objetivo.etapas:
        d = empurrao.get(e.id, 0)
        if d <= 0 or e.prazo is None:
            continue
        movimentos.append({
            "etapa": e.id,
            "titulo": e.titulo,
            "de": e.prazo.isoformat(),
            "para": (e.prazo + timedelta(days=d)).isoformat(),
            "dias": d,
            "motivo": (
                "venceu sem check"
                if e.prazo < hoje and e.id not in feito
                else "depende de etapa que atrasou"
            ),
            "sera_o_adiamento": e.adiamentos + 1,
        })

    ultimo_atual = max(
        (e.prazo for e in objetivo.etapas if e.prazo is not None),
        default=None,
    )
    ultimo_depois = max(
        (
            e.prazo + timedelta(days=empurrao.get(e.id, 0))
            for e in objetivo.etapas
            if e.prazo is not None
        ),
        default=None,
    )
    folga_antes = (objetivo.data_alvo - ultimo_atual).days if (
        objetivo.data_alvo and ultimo_atual
    ) else None
    folga_depois = (objetivo.data_alvo - ultimo_depois).days if (
        objetivo.data_alvo and ultimo_depois
    ) else None

    return {
        "objetivo": objetivo.id,
        "titulo": objetivo.titulo,
        "calculado_em": hoje.isoformat(),
        "movimentos": movimentos,
        "data_alvo": objetivo.data_alvo.isoformat() if objetivo.data_alvo else None,
        "folga_antes_em_dias": folga_antes,
        "folga_depois_em_dias": folga_depois,
        "estoura_o_alvo": folga_depois is not None and folga_depois < 0,
        "origem": "agente",
        "assinado": False,
        "nota": (
            "cada etapa atrasada vai para hoje e a cadeia que depende dela anda "
            "o mesmo tanto. O motor não corta etapa nem renegocia a data alvo: "
            "ele mostra a folga que sobrou. Aplicar é um segundo ato, seu"
        ),
    }


def aplicar_reajuste(
    objetivo: Objetivo,
    proposta: dict,
    *,
    porque: str,
    origem: str = "usuario",
) -> Objetivo:
    """Move as datas que a proposta calculou. Exige assinatura e `porque`.

    O `prazo_original` de cada etapa não se mexe nunca e `adiamentos` sobe em
    um. É o que impede o reajuste de virar borracha: a nota de `adiamento` no
    score cai, e a história de quantas vezes aquela etapa foi empurrada fica
    legível no próprio catálogo, que é um arquivo que a pessoa abre.
    """
    if ORIGENS_DO_REGISTRO.get(origem, 0) < ORIGENS_DO_REGISTRO["usuario"]:
        raise ValueError(
            "reajuste só é aplicado pelo `usuario`. O agente propõe a conta; "
            "mexer na data de uma promessa é da pessoa que a fez"
        )
    if not porque.strip():
        raise ValueError(
            "reajustar exige `porque` — sem isso o catálogo perde a única coisa "
            "que distingue 'a semana virou' de 'eu não quis'"
        )
    if proposta.get("objetivo") != objetivo.id:
        raise ValueError(
            f"a proposta é do objetivo '{proposta.get('objetivo')}' e está sendo "
            f"aplicada em '{objetivo.id}'"
        )

    for mov in proposta.get("movimentos") or []:
        e = objetivo.etapa(mov["etapa"])
        if e is None:
            raise ValueError(f"a proposta move a etapa '{mov['etapa']}', que não existe mais")
        if e.prazo is None or e.prazo.isoformat() != mov["de"]:
            raise ValueError(
                f"etapa '{e.id}': a proposta saiu de {mov['de']} e o prazo agora é "
                f"{e.prazo}. Recalcule — aplicar uma conta velha move a data para o lugar errado"
            )
        e.prazo = date.fromisoformat(mov["para"])
        e.adiamentos += 1
        e.porque = (
            f"{e.porque} | adiada em {proposta['calculado_em']}: {porque.strip()}"
            if e.porque else f"adiada em {proposta['calculado_em']}: {porque.strip()}"
        )
    return objetivo


# --------------------------------------------------- o que a tela consome


def gauges(
    objetivos: list[Objetivo],
    checks: list[Check],
    vida: Vida | None = None,
    hoje: date | None = None,
    *,
    planos: list[dict] | None = None,
) -> dict:
    """O contrato da tela inicial: número, faixa e legenda. Nunca forma.

    O motor não sabe o que é um ponteiro, um arco ou uma barra — e não deve
    saber. Ele entrega `valor` em 0–100, a `faixa` que nomeia a zona e a
    `legenda` que diz o que o número conta. Mudar de arco para barra não pode
    exigir mudança no motor; mudar a fórmula não pode exigir mudança na tela.

    Há uma regra de conteúdo que atravessa a fronteira, e ela vale para a tela
    também: **nenhum texto daqui elogia nem cobra**. "2 de 4" é informação;
    "quase lá!" é opinião, e opinião do app sobre o dia de alguém é exatamente
    o que faz o app ser fechado.
    """
    hoje = hoje or date.today()
    from .life import forca_dos_atributos  # local: evita ciclo na importação

    frentes = []
    if vida is not None:
        for f in forca_dos_atributos(vida.missoes, vida.registros, hoje):
            frentes.append({
                "chave": f["atributo"],
                "rotulo": f["nome"],
                "valor": f["pct"],
                "faixa": _faixa(f["pct"]) if f["missoes"] else "sem_base",
                "legenda": f"{f['cumpridas']} de {f['missoes']} hoje",
                "sem_base": f["missoes"] == 0,
            })

    dos_objetivos = []
    for o in objetivos:
        if not o.assinado or o.arquivado:
            continue
        corr = correlacionar(o, checks, planos=planos, vida=vida, hoje=hoje)
        sc = score_do_objetivo(o, checks, hoje, correlacao=corr)
        feito = cumprimento(o, checks)
        proximos = sorted(
            (e for e in o.etapas if e.id not in feito and e.prazo is not None),
            key=lambda e: e.prazo,
        )
        dos_objetivos.append({
            "chave": o.id,
            "rotulo": o.titulo,
            "valor": sc["score"],
            "faixa": sc["faixa"],
            "legenda": f"{len(feito)} de {len(o.etapas)} etapas",
            "status": sc["status"],
            "peso_aplicado": sc["peso_aplicado"],
            "peso_total": sc["peso_total"],
            "proximo_prazo": proximos[0].prazo.isoformat() if proximos else None,
            "proxima_etapa": proximos[0].titulo if proximos else None,
            "dias_para_o_proximo": (proximos[0].prazo - hoje).days if proximos else None,
            "sem_base": sc["peso_aplicado"] == 0,
        })

    return {
        "dia": hoje.isoformat(),
        "frentes": frentes,
        "objetivos": dos_objetivos,
        "hoje": checks_de_hoje(objetivos, checks, vida, hoje),
        "nota": (
            "`valor` é 0–100 e `faixa` nomeia a zona; a forma é da tela. "
            "`sem_base` marca o que ainda não tem como ser medido — mostrar 0 "
            "ali seria afirmar um fracasso que não aconteceu"
        ),
    }


def contexto_de_perfil(
    objetivos: list[Objetivo],
    checks: list[Check],
    vida: Vida | None = None,
    hoje: date | None = None,
    *,
    planos: list[dict] | None = None,
) -> dict:
    """O que a IA lê antes de aconselhar qualquer coisa.

    Curto de propósito. Despejar o catálogo inteiro numa conversa gasta espaço
    com etapa que vence em outubro do ano que vem e deixa de fora o que
    importa: o que esta pessoa está perseguindo, o que está atrasado, e o que
    ela já declarou que não quer trocar por uma compra.

    Isto é contexto para decisão, não relatório. A pergunta que ele responde é
    "o que eu precisaria saber sobre esta pessoa antes de responder?".
    """
    hoje = hoje or date.today()
    ativos = [o for o in objetivos if o.assinado and not o.arquivado]
    rascunhos = [o for o in objetivos if not o.assinado and not o.arquivado]

    resumo = []
    for o in ativos:
        corr = correlacionar(o, checks, planos=planos, vida=vida, hoje=hoje)
        sc = score_do_objetivo(o, checks, hoje, correlacao=corr)
        resumo.append({
            "objetivo": o.id,
            "titulo": o.titulo,
            "porque": o.porque,
            "data_alvo": o.data_alvo.isoformat() if o.data_alvo else None,
            "status": sc["status"],
            "score": sc["score"],
            "peso_aplicado": sc["peso_aplicado"],
            "custo_restante": corr["custo_restante"],
            "plano_ligado": (corr["plano"] or {}).get("id"),
            "missoes_ligadas": [m["missao"] for m in corr["missoes"]],
            "avisos": corr["avisos"],
            "orfaos": corr["orfaos"],
        })

    atrasadas = [i for i in agenda(ativos, checks, hoje, dias=30) if i["situacao"] == "atrasada"]
    return {
        "dia": hoje.isoformat(),
        "objetivos": resumo,
        "rascunhos_aguardando_assinatura": [
            {"objetivo": o.id, "titulo": o.titulo, "etapas": len(o.etapas)}
            for o in rascunhos
        ],
        "etapas_atrasadas": atrasadas[:10],
        "compromisso_total_restante": round(
            sum(r["custo_restante"] for r in resumo), 2
        ),
        "como_usar": (
            "cite o objetivo pelo título e o `porque` que a pessoa escreveu. "
            "Um rascunho não é compromisso dela: ele está esperando assinatura, "
            "e tratar rascunho como promessa é cobrar por algo que ela não disse"
        ),
    }


# ----------------------------------------- o catálogo viajando para o aparelho

DEVICE_SCHEMA = 1


def exportar_para_aparelho(objetivos: list[Objetivo]) -> dict:
    """Os objetivos no formato que o app lê — JSON, como as missões.

    Dinheiro vai como string de duas casas (`199.90`, nunca `199.9`) pelo mesmo
    motivo de sempre: valor que atravessa `float` na fronteira entre dois
    motores volta diferente, e aqui ele atravessa duas vezes.

    Só objetivo assinado viaja. O rascunho é um objeto de conversa; mandá-lo
    para o aparelho faria o widget mostrar check de algo que a pessoa ainda não
    combinou — exatamente o que a assinatura existe para impedir.
    """
    def reais(v: Decimal) -> str:
        return f"{v.quantize(Decimal('0.01'))}"

    return {
        "schema_version": DEVICE_SCHEMA,
        "objetivos": [
            {
                "id": o.id,
                "titulo": o.titulo,
                "porque": o.porque,
                "comecou_em": o.comecou_em.isoformat() if o.comecou_em else None,
                "data_alvo": o.data_alvo.isoformat() if o.data_alvo else None,
                "plano_id": o.plano_id,
                "missoes": list(o.missoes),
                "etapas": [
                    {
                        "id": e.id,
                        "titulo": e.titulo,
                        "tipo": e.tipo,
                        "prazo": e.prazo.isoformat() if e.prazo else None,
                        "prazo_original": (
                            e.prazo_original.isoformat() if e.prazo_original else None
                        ),
                        "adiamentos": e.adiamentos,
                        "custo": reais(e.custo),
                        "depende_de": list(e.depende_de),
                        "obrigatoria": e.obrigatoria,
                        "porque": e.porque,
                    }
                    for e in o.etapas
                ],
            }
            for o in objetivos
            if o.assinado and not o.arquivado
        ],
    }


def importar_do_aparelho(checks_jsonl: str, conhecidos: set[str] | None = None) -> list[Check]:
    """Lê os checks que voltaram do celular.

    Check de objetivo que não está no catálogo é recusado em vez de guardado:
    ele não entraria em score nenhum e sumiria dos relatórios — e erro que não
    aparece é o pior tipo.
    """
    saida = []
    for n, linha in enumerate(checks_jsonl.splitlines(), 1):
        linha = linha.strip()
        if not linha:
            continue
        c = Check.from_dict(json.loads(linha))
        if conhecidos and c.objetivo_id not in conhecidos:
            raise ValueError(
                f"linha {n}: check do objetivo '{c.objetivo_id}', que não está no catálogo"
            )
        saida.append(c)
    return saida
