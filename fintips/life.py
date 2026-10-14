"""As seis frentes como contexto de decisão financeira.

Este módulo existe por um motivo só, e não é gamificação: **dar contexto para
decisão de dinheiro e para plano**. Uma compra não disputa espaço apenas com a
reserva e com o plano — ela disputa com o que a pessoa combinou consigo mesma.

A diferença aparece num exemplo. Duas pessoas olham um tablet de R$ 2.500 com
a mesma sobra, a mesma reserva e o mesmo plano. Na primeira, o tablet é o
aparelho de estudo que falta. Na segunda, é a porta de entrada do vídeo curto
que ela está cortando há 40 dias — e nenhum extrato do mundo distingue as
duas. O que distingue é a missão que ela declarou e a sequência que ela tem
hoje.

Por isso o módulo não infere nada. Ele não decide que tablet é vício: a
colisão só existe porque a pessoa escreveu `colide_com` na missão dela, com
`porque`. O que o motor faz é o que sempre fez — **guardar, aplicar e
calcular**: converter preço em meses de aporte, dizer qual sequência está em
jogo, e aplicar a regra de espera que ela mesma declarou.

Nada aqui vira veredito próprio. A única coisa que mexe no veredito é a regra
que a própria pessoa assinou, e ela vai nomeada na saída, com o `porque`
dela ao lado — para que a conversa seja "a sua regra diz" e nunca "o app acha".

## Onde estes dados moram

`data/missoes.yaml` e `data/registros.jsonl`, dentro do workspace, **fora do
Git** — como `regras-locais.yaml` e por um motivo mais forte: plano de vida
tem salário, empregador, nome de gente e hora de dormir. O pacote carrega só
o molde em `rules/exemplo-missoes.yaml`, e o `scripts/check-pii.sh` colhe os
termos destes arquivos justamente para impedir que um título de missão vaze
num commit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import yaml

from .categorize import norm

LIFE_SCHEMA = 1

# As seis frentes. As siglas são as do plano de quem usa — ler o plano e gerar
# missão sem passo de tradução no meio, que é onde erro se esconde.
ATRIBUTOS: dict[str, str] = {
    "FOR": "Força",
    "AGI": "Agilidade",
    "VIT": "Vitalidade",
    "INT": "Intelecto",
    "FOC": "Foco",
    "OURO": "Ouro",
}

# Janela de cada cadência, em dias.
CADENCIAS: dict[str, int] = {
    "diaria": 1,
    "semanal": 7,
    "mensal": 30,
    "trimestral": 90,
    "anual": 365,
}

# Como se soube que a missão foi cumprida, em autoridade crescente.
#
# `sensor` acima de `agente` porque "você treinou?" é pergunta factual: se o
# aparelho mediu, a medida vale mais que a interpretação de quem conversou. E
# `usuario` acima de tudo porque o sensor erra de um jeito que a pessoa sabe
# explicar — o celular ficou em casa, o vídeo foi visto no computador.
#
# Esta escada é separada da financeira (`contracts.ORIGENS`) de propósito: lá
# a pergunta é "quem classificou esta transação", aqui é "como sabemos que isso
# foi feito". Fundir as duas obrigaria o motor Kotlin a divergir do Python.
ORIGENS_DO_REGISTRO: dict[str, int] = {
    "presumido": 0,
    "agente": 1,
    "sensor": 2,
    "usuario": 3,
}

# `presumido` nunca conta: o app supor que você treinou não é você ter treinado.
AUTORIDADE_MINIMA_PARA_CUMPRIR = ORIGENS_DO_REGISTRO["agente"]

TIPOS_DE_REGRA = ("espera_antes_de_comprar",)


@dataclass
class Missao:
    id: str
    titulo: str
    atributo: str
    cadencia: str
    como_medir: str = ""
    sensor_possivel: bool = False
    porque: str = ""
    ativa: bool = True
    # Quanto a missão move por mês, quando ela é de dinheiro. É o que permite
    # converter preço em meses de aporte.
    valor_mensal: Decimal | None = None
    # O que esta missão considera conflito. **Declarado pela pessoa**, nunca
    # inferido: é a única porta pela qual uma compra toca uma frente não
    # financeira.
    colide_com: list[str] = field(default_factory=list)

    @property
    def janela_em_dias(self) -> int:
        return CADENCIAS[self.cadencia]

    @classmethod
    def from_dict(cls, d: dict) -> "Missao":
        atributo = str(d["atributo"]).strip().upper()
        cadencia = str(d["cadencia"]).strip().lower()
        if atributo not in ATRIBUTOS:
            raise ValueError(
                f"missão '{d.get('id')}': atributo '{atributo}' não existe. "
                f"Os seis são {', '.join(ATRIBUTOS)}"
            )
        if cadencia not in CADENCIAS:
            raise ValueError(
                f"missão '{d.get('id')}': cadência '{cadencia}' não existe. "
                f"As cinco são {', '.join(CADENCIAS)}"
            )
        valor = d.get("valor_mensal")
        return cls(
            id=d["id"],
            titulo=d.get("titulo", d["id"]),
            atributo=atributo,
            cadencia=cadencia,
            como_medir=d.get("como_medir", "") or "",
            sensor_possivel=bool(d.get("sensor_possivel", False)),
            porque=d.get("porque", "") or "",
            ativa=bool(d.get("ativa", True)),
            valor_mensal=Decimal(str(valor)) if valor is not None else None,
            colide_com=[str(x) for x in (d.get("colide_com") or [])],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "titulo": self.titulo,
            "atributo": self.atributo,
            "cadencia": self.cadencia,
            "como_medir": self.como_medir,
            "sensor_possivel": self.sensor_possivel,
            "porque": self.porque,
            "ativa": self.ativa,
            "valor_mensal": float(self.valor_mensal) if self.valor_mensal is not None else None,
            "colide_com": list(self.colide_com),
        }


@dataclass
class RegistroDeMissao:
    missao_id: str
    dia: date
    origem: str
    medida: str = ""
    nota: str = ""

    @property
    def conta_como_cumprido(self) -> bool:
        return ORIGENS_DO_REGISTRO[self.origem] >= AUTORIDADE_MINIMA_PARA_CUMPRIR

    @classmethod
    def from_dict(cls, d: dict) -> "RegistroDeMissao":
        origem = str(d.get("origem", "")).strip().lower()
        if origem not in ORIGENS_DO_REGISTRO:
            raise ValueError(
                f"origem '{origem}' não existe. As quatro são "
                f"{', '.join(ORIGENS_DO_REGISTRO)}"
            )
        dia = d["dia"]
        return cls(
            missao_id=d["missao_id"],
            dia=date.fromisoformat(dia) if isinstance(dia, str) else dia,
            origem=origem,
            medida=d.get("medida", "") or "",
            nota=d.get("nota", "") or "",
        )

    def to_dict(self) -> dict:
        return {
            "missao_id": self.missao_id,
            "dia": self.dia.isoformat(),
            "origem": self.origem,
            "medida": self.medida,
            "nota": self.nota,
        }


@dataclass
class RegraDeclarada:
    """Uma regra que a pessoa escreveu para si. O motor aplica, não opina."""

    id: str
    tipo: str
    acima_de: Decimal
    dias: int
    porque: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "RegraDeclarada":
        tipo = str(d.get("tipo", "")).strip()
        if tipo not in TIPOS_DE_REGRA:
            raise ValueError(
                f"regra '{d.get('id')}': tipo '{tipo}' não é suportado. "
                f"Suportados: {', '.join(TIPOS_DE_REGRA)}"
            )
        if not str(d.get("porque", "")).strip():
            raise ValueError(
                f"regra '{d.get('id')}' sem `porque` — regra que mexe em veredito "
                "precisa dizer de onde veio, ou vira opinião do app"
            )
        return cls(
            id=d["id"],
            tipo=tipo,
            acima_de=Decimal(str(d.get("acima_de", 0))),
            dias=int(d.get("dias", 0)),
            porque=d["porque"].strip(),
        )


@dataclass
class Vida:
    """O catálogo da pessoa e os registros dela, como lidos do workspace."""

    missoes: list[Missao] = field(default_factory=list)
    registros: list[RegistroDeMissao] = field(default_factory=list)
    regras: list[RegraDeclarada] = field(default_factory=list)

    @property
    def vazia(self) -> bool:
        return not self.missoes


def carregar(missoes_path: str | Path, registros_path: str | Path | None = None) -> Vida:
    """Lê `data/missoes.yaml` e `data/registros.jsonl`.

    Ausência não é erro: quem nunca cadastrou missão tem o motor financeiro
    inteiro funcionando, só sem a camada de contexto.
    """
    missoes_path = Path(missoes_path)
    vida = Vida()
    if missoes_path.exists():
        d = yaml.safe_load(missoes_path.read_text(encoding="utf-8")) or {}
        vida.missoes = [Missao.from_dict(m) for m in d.get("missoes") or []]
        vida.regras = [RegraDeclarada.from_dict(r) for r in d.get("regras") or []]
        vistos: set[str] = set()
        for m in vida.missoes:
            if m.id in vistos:
                raise ValueError(f"missão '{m.id}' aparece duas vezes no catálogo")
            vistos.add(m.id)

    if registros_path:
        registros_path = Path(registros_path)
        if registros_path.exists():
            conhecidas = {m.id for m in vida.missoes}
            for n, linha in enumerate(registros_path.read_text(encoding="utf-8").splitlines(), 1):
                linha = linha.strip()
                if not linha:
                    continue
                r = RegistroDeMissao.from_dict(json.loads(linha))
                if conhecidas and r.missao_id not in conhecidas:
                    raise ValueError(
                        f"{registros_path.name}:{n}: registro de missão "
                        f"'{r.missao_id}', que não está no catálogo"
                    )
                vida.registros.append(r)
    return vida


def registrar(
    registros_path: str | Path,
    registro: RegistroDeMissao,
) -> RegistroDeMissao:
    """Grava um registro, em append. JSONL porque registro é histórico.

    Reescrever o arquivo inteiro a cada marcação permitiria perder o passado
    num erro de escrita; append só sabe crescer.
    """
    p = Path(registros_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(registro.to_dict(), ensure_ascii=False) + "\n")
    return registro


# ------------------------------------------------------------------- estado


def estado_diario(
    missao: Missao,
    registros: list[RegistroDeMissao],
    hoje: date,
) -> dict:
    """Sequência e recorde de uma missão diária.

    Duas regras de produto, as duas vindas de plano de recaída e não de
    cálculo:

    - **hoje ainda não cumprido não quebra a sequência** — o dia não acabou, e
      zerar às 9h da manhã puniria alguém por não ter feito o que ainda dá
      tempo de fazer;
    - **o recorde não zera na recaída** — "nunca dois dias seguidos; caiu hoje,
      amanhã é dia limpo". Zerar tudo junto transformaria um tropeço em perda
      total, que é exatamente o pensamento que faz alguém largar o app.
    """
    cumpridos = {
        r.dia for r in registros
        if r.missao_id == missao.id and r.conta_como_cumprido
    }

    sequencia = 0
    dia = hoje
    if dia not in cumpridos:
        dia -= timedelta(days=1)
    while dia in cumpridos:
        sequencia += 1
        dia -= timedelta(days=1)

    recorde = corrente = 0
    anterior: date | None = None
    for d in sorted(cumpridos):
        corrente = corrente + 1 if anterior and anterior + timedelta(days=1) == d else 1
        recorde = max(recorde, corrente)
        anterior = d

    ultimos = [r for r in registros if r.missao_id == missao.id and r.conta_como_cumprido]
    ultimo = max(ultimos, key=lambda r: r.dia) if ultimos else None
    return {
        "missao": missao.id,
        "titulo": missao.titulo,
        "atributo": missao.atributo,
        "cumprida_na_janela": hoje in cumpridos,
        "sequencia": sequencia,
        "recorde": recorde,
        "ultimo_registro": ultimo.to_dict() if ultimo else None,
    }


def forca_dos_atributos(
    missoes: list[Missao],
    registros: list[RegistroDeMissao],
    hoje: date,
    cadencia: str = "diaria",
) -> list[dict]:
    """Quanto de cada frente foi cumprido na janela.

    Devolve **sempre as seis**, mesmo vazias: frente sem missão cadastrada é
    informação — mostra o que a pessoa não está treinando. Esconder a barra
    esconderia a lacuna.

    Não existe XP e não existe nível, de propósito. Nível é um número que só
    sobe e, por construção, não consegue dizer "esta semana foi pior que a
    passada" — que é a única informação que muda comportamento.
    """
    do_periodo = [m for m in missoes if m.ativa and m.cadencia == cadencia]
    inicio = hoje - timedelta(days=CADENCIAS[cadencia] - 1)

    por_missao: dict[str, list[RegistroDeMissao]] = {}
    for r in registros:
        if r.conta_como_cumprido and inicio <= r.dia <= hoje:
            por_missao.setdefault(r.missao_id, []).append(r)

    saida = []
    for sigla, nome in ATRIBUTOS.items():
        dele = [m for m in do_periodo if m.atributo == sigla]
        cumpridas = [m for m in dele if m.id in por_missao]
        por_maquina = [
            m for m in dele
            if any(r.origem == "sensor" for r in por_missao.get(m.id, []))
        ]
        saida.append({
            "atributo": sigla,
            "nome": nome,
            "missoes": len(dele),
            "cumpridas": len(cumpridas),
            "pct": round(len(cumpridas) / len(dele) * 100, 1) if dele else 0.0,
            "com_evidencia_de_maquina": len(por_maquina),
        })
    return saida


def cobertura_de_evidencia(missoes: list[Missao], registros: list[RegistroDeMissao]) -> dict:
    """Quanto do que o app afirma veio de medida, e quanto é memória.

    É o espelho de `cobertura_da_classificacao` do lado financeiro, e existe
    pelo mesmo motivo: deixar visível o que ainda não se sabe. Aqui tem um
    motivo extra — memória de uso de celular distorce a favor de quem lembra.
    """
    ativas = [m for m in missoes if m.ativa]
    com_sensor = [
        m for m in ativas
        if any(r.missao_id == m.id and r.origem == "sensor" for r in registros)
    ]
    return {
        "missoes_ativas": len(ativas),
        "mensuraveis_por_aparelho": sum(1 for m in ativas if m.sensor_possivel),
        "com_medida_registrada": len(com_sensor),
        "pct_medido": round(len(com_sensor) / len(ativas) * 100, 1) if ativas else 0.0,
        "explicacao": (
            "quanto do que o app afirma veio de medida. O resto é memória, e "
            "memória de tempo de tela distorce a favor de quem lembra"
        ),
    }


# ------------------------------------------- a ponte com a decisão de dinheiro


def _colide(missao: Missao, texto_da_compra: str) -> str | None:
    """A colisão declarada que esta compra toca, se tocar.

    Só casa com o que a pessoa escreveu em `colide_com`. O motor não decide
    que tablet é vício: se a palavra não está lá, não há colisão.
    """
    for termo in missao.colide_com:
        if termo and norm(termo) in texto_da_compra:
            return termo
    return None


def contexto_de_compra(
    vida: Vida,
    *,
    item: str,
    preco: Decimal,
    categoria: str = "",
    tags: list[str] | None = None,
    hoje: date | None = None,
) -> dict:
    """O que as seis frentes dizem sobre esta compra.

    Devolve quatro coisas, nesta ordem de força:

    1. `regra_declarada` — a regra que a pessoa assinou, aplicada. **A única
       coisa daqui que pode mexer no veredito**, e vai nomeada, com o `porque`
       dela, para a conversa ser "a sua regra diz" e nunca "o app acha".
    2. `missoes_em_jogo` — qual sequência esta compra põe em risco, com o
       `porque` que a pessoa escreveu na missão.
    3. `custo_em_aportes` — o preço convertido em meses da missão de aporte.
       Aritmética, e a tradução mais útil que existe: "este item custa 7
       meses do que você guarda".
    4. `frentes_no_momento` — as seis barras de hoje, para que a conversa saiba
       se a compra cai numa frente que já está fraca.
    """
    hoje = hoje or date.today()
    tags = tags or []
    texto = norm(f"{item} {categoria} {' '.join(tags)}")

    # 1. a regra que ela mesma declarou
    regra_aplicada = None
    for r in vida.regras:
        if r.tipo != "espera_antes_de_comprar":
            continue
        aplica = preco > r.acima_de
        regra_aplicada = {
            "id": r.id,
            "tipo": r.tipo,
            "acima_de": float(r.acima_de),
            "dias": r.dias,
            "porque_ela_escreveu": r.porque,
            "aplica": aplica,
            "liberada_em": (hoje + timedelta(days=r.dias)).isoformat() if aplica else None,
            "nota": (
                "regra da pessoa, aplicada pelo motor — não é opinião do app. "
                "Cite a regra dela, não um conselho seu"
            ),
        }
        break

    # 2. as sequências em jogo
    em_jogo = []
    for m in vida.missoes:
        if not m.ativa:
            continue
        termo = _colide(m, texto)
        # Missão de dinheiro entra sempre: qualquer compra disputa com ela.
        if termo is None and m.atributo != "OURO":
            continue
        estado = estado_diario(m, vida.registros, hoje) if m.cadencia == "diaria" else None
        em_jogo.append({
            "missao": m.id,
            "titulo": m.titulo,
            "atributo": m.atributo,
            "cadencia": m.cadencia,
            "por_que_entra_aqui": (
                f"a pessoa declarou que '{termo}' colide com esta missão"
                if termo else "missão de dinheiro — toda compra disputa com ela"
            ),
            "colisao_declarada": termo,
            "porque_da_missao": m.porque,
            "sequencia_em_risco": estado["sequencia"] if estado else None,
            "recorde": estado["recorde"] if estado else None,
        })

    # 3. preço em meses de aporte
    aporte = next(
        (m for m in vida.missoes
         if m.ativa and m.atributo == "OURO" and m.valor_mensal and m.valor_mensal > 0),
        None,
    )
    custo_em_aportes = None
    if aporte:
        custo_em_aportes = {
            "missao": aporte.id,
            "aporte_mensal": float(aporte.valor_mensal),
            "meses_de_aporte": float(round(preco / aporte.valor_mensal, 2)),
            "nota": (
                "preço traduzido no que ela guarda por mês — não é o mesmo que "
                "a sobra do extrato, é o compromisso que ela assinou"
            ),
        }

    return {
        "regra_declarada": regra_aplicada,
        "missoes_em_jogo": em_jogo,
        "custo_em_aportes": custo_em_aportes,
        "frentes_no_momento": forca_dos_atributos(vida.missoes, vida.registros, hoje),
        "cobertura_de_evidencia": cobertura_de_evidencia(vida.missoes, vida.registros),
        "sem_missoes_cadastradas": vida.vazia,
        "nota": (
            "só a `regra_declarada` pode mexer no veredito, porque é regra da "
            "própria pessoa. O resto diz o que trazer para a conversa — a "
            "interpretação é sua"
        ),
    }


def contexto_de_planos(vida: Vida, resultados_de_planos: list[dict]) -> dict:
    """Como a missão de aporte conversa com os planos cadastrados.

    O plano diz quanto o plano precisa por mês; a missão de aporte diz quanto
    a pessoa se comprometeu a guardar. Quando os dois não fecham, o motor
    mostra a diferença em vez de escolher um dos dois — a escolha é dela.
    """
    aporte = next(
        (m for m in vida.missoes
         if m.ativa and m.atributo == "OURO" and m.valor_mensal and m.valor_mensal > 0),
        None,
    )
    if not aporte:
        return {
            "missao_de_aporte": None,
            "nota": (
                "nenhuma missão de aporte com `valor_mensal` no catálogo — sem "
                "isso não há compromisso declarado para comparar com os planos"
            ),
        }

    exigido = sum(
        Decimal(str(r.get("aporte_necessario_mes") or 0))
        for r in resultados_de_planos
        if r.get("status") != "concluido"
    )
    folga = aporte.valor_mensal - exigido
    return {
        "missao_de_aporte": {
            "missao": aporte.id,
            "titulo": aporte.titulo,
            "aporte_mensal": float(aporte.valor_mensal),
            "como_medir": aporte.como_medir,
        },
        "exigido_pelos_planos_mes": float(exigido),
        "folga_mensal": float(folga),
        "planos_cabem_no_aporte": folga >= 0,
        "nota": (
            "o aporte declarado é compromisso, não previsão. Se os planos "
            "exigem mais do que ele, a pessoa escolhe: subir o aporte, esticar "
            "o prazo ou cortar plano. O motor não escolhe por ela"
        ),
    }


# ----------------------------------------- o catálogo viajando para o aparelho

DEVICE_SCHEMA = 1


def exportar_para_aparelho(vida: Vida) -> dict:
    """O catálogo no formato que o app Android lê.

    **Por que existe um segundo formato.** O workspace guarda `missoes.yaml`
    porque é arquivo que a pessoa edita à mão, e YAML existe para isso. O
    aparelho não edita nada à mão e, sobretudo, **o celular é outra máquina**:
    ele não lê `~/Documents/FinTips/data/` e nunca vai ler. O que chega ao
    aparelho chega por transporte, e formato de transporte não precisa ser
    formato de edição.

    Isso tem uma consequência que não era óbvia e vale para quem planeja o
    porte: **a leitura de YAML em Kotlin não bloqueia o app**. O aparelho
    precisa ler o que ele mesmo grava, e isso é JSON.

    Dinheiro vai como string com duas casas, nunca como float: `4300.00`, não
    `4300.0`. É a mesma regra que atravessa o projeto — valor que passa por
    `float` volta diferente, e aqui ele atravessa a fronteira entre dois
    motores.
    """
    def reais(v: Decimal) -> str:
        return f"{v.quantize(Decimal('0.01'))}"

    return {
        "schema_version": DEVICE_SCHEMA,
        "missoes": [
            {
                "id": m.id,
                "titulo": m.titulo,
                "atributo": m.atributo,
                "cadencia": m.cadencia,
                "como_medir": m.como_medir,
                "sensor_possivel": m.sensor_possivel,
                "porque": m.porque,
                "ativa": m.ativa,
                "valor_mensal": reais(m.valor_mensal) if m.valor_mensal is not None else None,
                "colide_com": list(m.colide_com),
            }
            for m in vida.missoes
        ],
        "regras": [
            {
                "id": r.id,
                "tipo": r.tipo,
                "acima_de": reais(r.acima_de),
                "dias": r.dias,
                "porque": r.porque,
            }
            for r in vida.regras
        ],
    }


def importar_do_aparelho(
    registros_jsonl: str,
    missoes_conhecidas: set[str] | None = None,
) -> list[RegistroDeMissao]:
    """Lê o histórico que voltou do aparelho.

    O mesmo JSONL que o app grava, para o workspace poder absorver o que foi
    marcado no celular. Registro de missão fora do catálogo é recusado em vez
    de guardado: ele não enche barra nenhuma e sairia dos relatórios — erro que
    não aparece é o pior tipo.
    """
    saida = []
    for n, linha in enumerate(registros_jsonl.splitlines(), 1):
        linha = linha.strip()
        if not linha:
            continue
        r = RegistroDeMissao.from_dict(json.loads(linha))
        if missoes_conhecidas and r.missao_id not in missoes_conhecidas:
            raise ValueError(
                f"linha {n}: registro da missão '{r.missao_id}', que não está no catálogo"
            )
        saida.append(r)
    return saida
