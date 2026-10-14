"""Perfil financeiro: arquétipos casados por número, assinados por gente.

O perfil é a única parte do motor que tenta dizer *quem* é o usuário, e por
isso é a que mais precisa da disciplina de proveniência. O desenho separa duas
coisas que quase todo app de finanças confunde:

- **Sugestão** — o catálogo em `rules/arquetipos.yaml` casado contra os
  indicadores do próprio extrato. Sai com origem `importacao`: é palpite, tem
  evidência anexada, e não é gravado em lugar nenhum.
- **Perfil assinado** — o que o agente concluiu depois de conversar, ou o que a
  pessoa afirmou. Só isso mora em `data/perfil.yaml`, e é só isso que o resto
  do motor pode tratar como verdade.

A consequência prática: rodar `analyze` mil vezes nunca cria perfil. O número
sozinho não assina nada. Um extrato com sobra alta sugere `acumulacao`, mas
quem sabe se aquilo foi um mês de férias sem gastar é a pessoa.

Os eixos são independentes de propósito. Perfil único — "o poupador", "o
gastador" — é horóscopo: descreve todo mundo e não muda conta nenhuma.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from datetime import date

from .contracts import Proveniencia, agora

PROFILE_SCHEMA = 2

# Quando o eixo não declara, este é o prazo. Doze meses porque é o período em
# que praticamente tudo que o perfil descreve pode ter mudado sem aviso.
VALIDADE_PADRAO_EM_MESES = 12

_CATALOGO_PATH = Path(__file__).parent / "rules" / "arquetipos.yaml"


# --------------------------------------------------------------------------
# Catálogo
# --------------------------------------------------------------------------
@dataclass
class Sinal:
    indicador: str
    minimo: float | None = None
    maximo: float | None = None
    peso: float = 1.0

    def casa(self, valor: float | None) -> bool:
        if valor is None:
            return False
        if self.minimo is not None and valor < self.minimo:
            return False
        if self.maximo is not None and valor > self.maximo:
            return False
        return True

    def descrever(self, valor: float | None) -> str:
        """Evidência legível: o número observado e a faixa que ele precisava ocupar."""
        obs = "sem dado" if valor is None else f"{valor:g}"
        if self.minimo is not None and self.maximo is not None:
            faixa = f"entre {self.minimo:g} e {self.maximo:g}"
        elif self.minimo is not None:
            faixa = f"≥ {self.minimo:g}"
        elif self.maximo is not None:
            faixa = f"≤ {self.maximo:g}"
        else:
            faixa = "qualquer valor"
        return f"{self.indicador} = {obs} (esperado {faixa})"


@dataclass
class Arquetipo:
    id: str
    nome: str
    descricao: str
    o_que_muda: str
    eixo: str
    sinais: list[Sinal] = field(default_factory=list)

    def avaliar(self, ind: dict[str, float | None]) -> dict:
        """Casa os sinais contra os indicadores. Devolve aderência e evidência."""
        total = sum(s.peso for s in self.sinais) or 1.0
        casados, evidencia, contra = 0.0, [], []
        for s in self.sinais:
            valor = ind.get(s.indicador)
            if s.casa(valor):
                casados += s.peso
                evidencia.append(s.descrever(valor))
            else:
                contra.append(s.descrever(valor))
        return {
            "id": self.id,
            "nome": self.nome,
            "descricao": self.descricao,
            "o_que_muda": self.o_que_muda,
            "aderencia": round(casados / total, 2),
            "evidencia": evidencia,
            "contra": contra,
        }


@dataclass
class Eixo:
    id: str
    nome: str
    o_que_e: str
    minimo: float
    arquetipos: list[Arquetipo]
    # Por quantos meses a assinatura deste eixo continua dizendo algo. Não é
    # prazo de validade de dado: o traço não some. É quando o app passa a
    # perguntar se ainda é assim, e quando a cobertura para de contá-lo.
    validade_em_meses: int = VALIDADE_PADRAO_EM_MESES


def carregar_catalogo(path: str | Path | None = None) -> list[Eixo]:
    data = yaml.safe_load(Path(path or _CATALOGO_PATH).read_text(encoding="utf-8")) or {}
    eixos = []
    for e in data.get("eixos") or []:
        arqs = [
            Arquetipo(
                id=a["id"],
                nome=a.get("nome", a["id"]),
                descricao=a.get("descricao", ""),
                o_que_muda=a.get("o_que_muda", ""),
                eixo=e["id"],
                sinais=[
                    Sinal(
                        indicador=s["indicador"],
                        minimo=s.get("min"),
                        maximo=s.get("max"),
                        peso=float(s.get("peso", 1)),
                    )
                    for s in a.get("sinais") or []
                ],
            )
            for a in e.get("arquetipos") or []
        ]
        eixos.append(
            Eixo(
                id=e["id"],
                nome=e.get("nome", e["id"]),
                o_que_e=e.get("o_que_e", ""),
                minimo=float(e.get("minimo", 0.6)),
                arquetipos=arqs,
                validade_em_meses=int(
                    e.get("validade_em_meses", VALIDADE_PADRAO_EM_MESES)
                ),
            )
        )
    return eixos


# --------------------------------------------------------------------------
# Indicadores
# --------------------------------------------------------------------------
def indicadores(ctx: dict) -> dict[str, float | None]:
    """Os números que o casamento de arquétipo enxerga.

    Todos saem do contexto único produzido por `report.analyze` — nenhum é
    calculado aqui de um jeito diferente do que o painel mostra. Quando o dado
    não existe, o indicador vem `None` e todo sinal que dependa dele falha, em
    vez de casar por omissão.
    """
    base = ctx.get("baseline") or {}
    score = (ctx.get("score") or {}).get("indicadores") or {}
    estrutura = ctx.get("estrutura_de_custo") or {}
    invis = (ctx.get("gastos_invisiveis") or {}).get("micro_gastos") or {}
    periodo = ctx.get("periodo") or {}

    considerados = set(base.get("meses_considerados") or [])
    meses = [m for m in ctx.get("meses") or [] if not considerados or m["mes"] in considerados]
    rendas = [float(m.get("renda", 0) or 0) for m in meses]
    com_renda = [r for r in rendas if r > 0]

    renda_variacao: float | None = None
    if len(com_renda) > 1:
        media = statistics.fmean(com_renda)
        renda_variacao = round(statistics.pstdev(com_renda) / media, 3) if media else None

    por_cat = ctx.get("por_categoria_total") or {}
    total_cat = sum(por_cat.values())
    top3 = sum(sorted(por_cat.values(), reverse=True)[:3])
    concentracao = round(top3 / total_cat * 100, 1) if total_cat else None

    n_despesas = periodo.get("despesas")
    micro_oc = invis.get("ocorrencias")
    transacoes_micro_pct = (
        round(micro_oc / n_despesas * 100, 1) if n_despesas and micro_oc is not None else None
    )

    return {
        "taxa_poupanca": _num(base.get("taxa_poupanca_media")),
        "meses_de_reserva": _num(score.get("meses_de_reserva")),
        "meses_no_vermelho": _num(base.get("meses_no_vermelho")),
        "volatilidade_despesa": _num(base.get("volatilidade_despesa")),
        "comprometido_pct_renda": _num(estrutura.get("comprometido_pct_renda")),
        "comprometido_pct_despesa": _num(estrutura.get("comprometido_pct_despesa")),
        "despesa_em_micro_pct": _num(invis.get("pct_da_despesa")),
        "transacoes_micro_pct": transacoes_micro_pct,
        "concentracao_top3_categorias": concentracao,
        "renda_variacao": renda_variacao,
        "meses_com_renda_pct": round(len(com_renda) / len(meses), 2) if meses else None,
        "meses_observados": float(len(meses)) if meses else None,
    }


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Casamento
# --------------------------------------------------------------------------
def casar(ctx: dict, catalogo: list[Eixo] | None = None) -> list[dict]:
    """Sugere um arquétipo por eixo, com aderência e evidência.

    O resultado é sempre `importacao` — palpite derivado dos dados. Abaixo do
    `minimo` do eixo, o motor devolve `sugerido: None` em vez de forçar o
    menos ruim: não ter leitura é um estado honesto, e a triagem prefere
    perguntar a chutar.
    """
    catalogo = catalogo or carregar_catalogo()
    ind = indicadores(ctx)
    out = []
    for eixo in catalogo:
        avaliados = sorted(
            (a.avaliar(ind) for a in eixo.arquetipos),
            key=lambda d: d["aderencia"],
            reverse=True,
        )
        melhor = avaliados[0] if avaliados else None
        empate = (
            len(avaliados) > 1
            and melhor is not None
            and avaliados[1]["aderencia"] == melhor["aderencia"]
        )
        sugerido = melhor if melhor and melhor["aderencia"] >= eixo.minimo and not empate else None
        out.append(
            {
                "eixo": eixo.id,
                "nome": eixo.nome,
                "o_que_e": eixo.o_que_e,
                "minimo": eixo.minimo,
                "sugerido": sugerido,
                "candidatos": avaliados,
                "sem_leitura_porque": (
                    None if sugerido
                    else "empate entre arquétipos" if empate
                    else "nenhum arquétipo atingiu a aderência mínima"
                ),
            }
        )
    return out


# --------------------------------------------------------------------------
# Perfil assinado
# --------------------------------------------------------------------------
@dataclass
class TracoDePerfil:
    """Um eixo do perfil, assinado por quem tem autoridade para isso."""

    eixo: str
    arquetipo: str                    # id do catálogo, ou "personalizado"
    nome: str
    descricao: str = ""
    proveniencia: Proveniencia = field(default_factory=Proveniencia)
    substituiu: str | None = None

    def idade_em_meses(self, hoje: date | None = None) -> int | None:
        """Há quantos meses esta assinatura foi dada.

        `None` quando a proveniência não trouxe data legível — perfil antigo,
        escrito antes de `quando` existir. Devolver 0 ali seria afirmar que a
        assinatura é de hoje, que é a mentira mais conveniente possível.
        """
        quando = self.proveniencia.quando
        if not quando:
            return None
        try:
            d = date.fromisoformat(str(quando)[:10])
        except ValueError:
            return None
        hoje = hoje or date.today()
        return max((hoje.year - d.year) * 12 + (hoje.month - d.month), 0)

    def envelhecido(self, validade_em_meses: int, hoje: date | None = None) -> bool:
        idade = self.idade_em_meses(hoje)
        return idade is not None and idade >= validade_em_meses

    def to_dict(self) -> dict:
        return {
            "eixo": self.eixo,
            "arquetipo": self.arquetipo,
            "nome": self.nome,
            "descricao": self.descricao,
            "substituiu": self.substituiu,
            "proveniencia": self.proveniencia.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TracoDePerfil":
        return cls(
            eixo=d["eixo"],
            arquetipo=d.get("arquetipo", "personalizado"),
            nome=d.get("nome", ""),
            descricao=d.get("descricao", ""),
            substituiu=d.get("substituiu"),
            proveniencia=Proveniencia.from_dict(d.get("proveniencia")),
        )


def migrar(data: dict) -> dict:
    """Traz um `perfil.yaml` de qualquer versão anterior para a de hoje.

    Existe antes de ser necessária, e esse é o ponto. O arquivo mora na
    máquina da pessoa e não há como implantar uma correção nele: quando o
    formato mudar e não houver migração, o app vai ler um arquivo que não
    entende e **escolher entre dois erros ruins** — recusar o perfil inteiro,
    ou interpretar errado em silêncio. Ter o degrau pronto desde a versão 1
    custa dez linhas; construí-lo depois do fato custa o perfil de alguém.

    Migração é só para frente: quem abriu o arquivo com uma versão nova do app
    e volta para a antiga não é um caminho que se sustenta, e fingir que sim
    daria uma falsa garantia.
    """
    versao = int(data.get("schema_version", 1) or 1)
    if versao > PROFILE_SCHEMA:
        raise ValueError(
            f"perfil.yaml está no esquema {versao} e este FinTips entende até "
            f"{PROFILE_SCHEMA}. Atualize o app — ler um arquivo de versão "
            "futura é adivinhar o que os campos novos significam"
        )

    if versao < 2:
        # v1 → v2: nada a reescrever. A validade por eixo veio do catálogo e a
        # história passou a viver num arquivo próprio, que nasce vazio para
        # quem já tinha perfil. O passado anterior a esta versão não existe, e
        # inventar linhas de história com data de hoje seria pior que não ter.
        versao = 2

    data["schema_version"] = versao
    return data


class PerfilStore:
    """O perfil que vale — um traço por eixo, cada um com quem assinou.

    Guarda apenas o que foi concluído ou afirmado. A sugestão heurística não
    entra aqui nem por engano: se entrasse, bastaria importar um extrato para
    o app "saber" quem a pessoa é, que é exatamente o erro que o projeto
    inteiro existe para não cometer.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        # A história fica ao lado do estado, e em append. Ver `historico()`.
        self.historico_path = self.path.with_name(
            self.path.stem + "-historico.jsonl"
        )
        self.tracos: dict[str, TracoDePerfil] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        data = migrar(data)
        for d in data.get("tracos") or []:
            self.tracos[d["eixo"]] = TracoDePerfil.from_dict(d)

    def _registrar(self, traco: TracoDePerfil, acao: str) -> None:
        """Acrescenta uma linha à história. Nunca reescreve.

        Sem isto, reassinar um eixo **apaga o passado**: sobrava o nome do
        arquétipo anterior em `substituiu` e nada mais — nem o `porque`, nem a
        data, nem a evidência de quem assinou antes. Num projeto cuja premissa
        é guardar o porquê, o perfil era o único lugar onde ele se perdia.

        E a pergunta que isso impedia de responder é das boas: *por que eu
        mudei?* Ver a travessia de `aperto` para `folga` com os dois `porque`
        lado a lado diz mais sobre a pessoa do que qualquer um dos dois
        sozinho.
        """
        linha = {"acao": acao, "quando": agora(), **traco.to_dict()}
        self.historico_path.parent.mkdir(parents=True, exist_ok=True)
        with self.historico_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")

    def historico(self, eixo: str = "") -> list[dict]:
        """Tudo que já foi assinado, na ordem em que foi. Opcionalmente de um eixo."""
        if not self.historico_path.exists():
            return []
        saida = []
        for linha in self.historico_path.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha:
                continue
            d = json.loads(linha)
            if not eixo or d.get("eixo") == eixo:
                saida.append(d)
        return saida

    def travessias(self, eixo: str = "") -> list[dict]:
        """As mudanças de arquétipo, com o `porque` dos dois lados.

        É a leitura que o agente quer quando a pessoa pergunta "o que mudou em
        mim": não a lista de assinaturas, mas os pontos em que ela deixou de
        ser uma coisa e passou a ser outra, com o motivo de cada ponta.
        """
        saida = []
        por_eixo: dict[str, dict] = {}
        for d in self.historico(eixo):
            anterior = por_eixo.get(d["eixo"])
            if anterior and anterior["arquetipo"] != d["arquetipo"]:
                saida.append({
                    "eixo": d["eixo"],
                    "de": anterior["arquetipo"],
                    "para": d["arquetipo"],
                    "quando": d["quando"],
                    "porque_antes": (anterior.get("proveniencia") or {}).get("porque", ""),
                    "porque_agora": (d.get("proveniencia") or {}).get("porque", ""),
                })
            if d.get("acao") == "esquecer":
                por_eixo.pop(d["eixo"], None)
            else:
                por_eixo[d["eixo"]] = d
        return saida

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": PROFILE_SCHEMA,
                    "atualizado_em": agora(),
                    "tracos": [t.to_dict() for t in sorted(self.tracos.values(), key=lambda x: x.eixo)],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    # -------------------------------------------------------------- escrita
    def assinar(
        self,
        eixo: str,
        arquetipo: str,
        *,
        proveniencia: Proveniencia,
        nome: str = "",
        descricao: str = "",
        catalogo: list[Eixo] | None = None,
    ) -> TracoDePerfil:
        """Grava o traço de um eixo.

        Recusa proveniência sem autoridade: heurística e importação não
        assinam perfil, por definição. Um traço de autoridade menor também não
        derruba um maior — o palpite do agente não apaga o que a pessoa disse.
        """
        prov = proveniencia
        if not prov.e_verdade:
            raise ValueError(
                "perfil só aceita origem 'agente' ou 'usuario': o casamento por "
                "número é sugestão, não assinatura"
            )
        if not prov.porque:
            raise ValueError("assinar um traço de perfil exige `porque`")

        catalogo = catalogo or carregar_catalogo()
        eixos = {e.id: e for e in catalogo}
        if eixo not in eixos:
            raise ValueError(f"eixo desconhecido: {eixo}. Conhecidos: {sorted(eixos)}")
        arqs = {a.id: a for a in eixos[eixo].arquetipos}
        if arquetipo != "personalizado" and arquetipo not in arqs:
            raise ValueError(
                f"arquétipo '{arquetipo}' não existe no eixo '{eixo}'. "
                f"Use um de {sorted(arqs)} ou 'personalizado' com nome e descrição próprios"
            )
        if arquetipo == "personalizado" and not (nome and descricao):
            raise ValueError("arquétipo personalizado exige nome e descrição")

        atual = self.tracos.get(eixo)
        if atual and atual.proveniencia.autoridade > prov.autoridade:
            return atual

        base = arqs.get(arquetipo)
        traco = TracoDePerfil(
            eixo=eixo,
            arquetipo=arquetipo,
            nome=nome or (base.nome if base else arquetipo),
            descricao=descricao or (base.descricao if base else ""),
            proveniencia=prov,
            substituiu=atual.arquetipo if atual and atual.arquetipo != arquetipo else None,
        )
        self.tracos[eixo] = traco
        self._registrar(traco, "assinar")
        self.save()
        return traco

    def esquecer(self, eixo: str) -> bool:
        """Apaga o traço do estado atual — **não** da história.

        Esquecer é dizer "isto não me descreve mais", e não "isto nunca foi
        verdade". A linha fica, marcada como `esquecer`, porque o fato de a
        pessoa ter se descrito assim um dia continua sendo informação sobre
        ela.
        """
        traco = self.tracos.pop(eixo, None)
        if traco is None:
            return False
        self._registrar(traco, "esquecer")
        self.save()
        return True

    # -------------------------------------------------------------- leitura
    def to_dicts(self) -> list[dict]:
        return [t.to_dict() for t in sorted(self.tracos.values(), key=lambda x: x.eixo)]


# --------------------------------------------------------------------------
# A visão que as três interfaces consomem
# --------------------------------------------------------------------------
def montar(
    ctx: dict,
    store: PerfilStore,
    catalogo: list[Eixo] | None = None,
    hoje: date | None = None,
) -> dict:
    """Junta sugestão e assinatura, eixo a eixo, e mede quanto do perfil é decisão.

    `cobertura` responde à mesma pergunta que `cobertura_da_classificacao`
    responde para o dinheiro: quanto disso aqui alguém decidiu, e quanto ainda
    é o app achando coisa. Começa em 0%.
    """
    catalogo = catalogo or carregar_catalogo()
    por_id = {e.id: e for e in catalogo}
    leituras = casar(ctx, catalogo)
    eixos = []
    for leitura in leituras:
        traco = store.tracos.get(leitura["eixo"])
        sugerido = leitura["sugerido"]
        diverge = bool(
            traco and sugerido and traco.arquetipo not in (sugerido["id"], "personalizado")
        )
        validade = por_id[leitura["eixo"]].validade_em_meses
        idade = traco.idade_em_meses(hoje) if traco else None
        velho = bool(traco and traco.envelhecido(validade, hoje))
        eixos.append(
            {
                **leitura,
                "assinado": traco.to_dict() if traco else None,
                "diverge_da_sugestao": diverge,
                "validade_em_meses": validade,
                "idade_em_meses": idade,
                "envelhecido": velho,
                "precisa_reconfirmar": velho,
            }
        )

    assinados = sum(1 for e in eixos if e["assinado"])
    validos = sum(1 for e in eixos if e["assinado"] and not e["envelhecido"])
    return {
        "schema_version": PROFILE_SCHEMA,
        "indicadores": indicadores(ctx),
        "eixos": eixos,
        "cobertura": {
            "eixos": len(eixos),
            "assinados": assinados,
            "pct": round(assinados / len(eixos) * 100, 1) if eixos else 0.0,
            # A métrica que vale é esta. Um eixo assinado há três anos continua
            # assinado, mas parou de descrever alguém — contá-lo como decisão
            # atual devolve 100% de cobertura para uma conversa de outra vida.
            "validos": validos,
            "pct_valido": round(validos / len(eixos) * 100, 1) if eixos else 0.0,
            "envelhecidos": [e["eixo"] for e in eixos if e["envelhecido"]],
            "explicacao": (
                "percentual dos eixos do perfil que alguém decidiu. O resto é "
                "sugestão do catálogo contra os seus números — palpite, não perfil"
            ),
            "explicacao_validos": (
                "quanto do perfil foi decidido E ainda está dentro da validade "
                "do eixo. Um traço envelhecido não some nem deixa de valer: o "
                "app só passa a perguntar se ainda é assim"
            ),
        },
        "divergencias": [e["eixo"] for e in eixos if e["diverge_da_sugestao"]],
        "a_reconfirmar": [
            {
                "eixo": e["eixo"],
                "arquetipo": e["assinado"]["arquetipo"],
                "assinado_ha_meses": e["idade_em_meses"],
                "validade_em_meses": e["validade_em_meses"],
                "porque_na_epoca": (e["assinado"].get("proveniencia") or {}).get("porque", ""),
            }
            for e in eixos if e["envelhecido"]
        ],
    }


# --------------------------------------------------------------------------
# O retrato: o perfil inteiro, não só o financeiro
# --------------------------------------------------------------------------

def retrato(ctx: dict) -> dict:
    """Quem é esta pessoa, para quem vai responder uma pergunta dela.

    Os cinco eixos financeiros descrevem a relação dela com dinheiro. Isso era
    o perfil inteiro enquanto o app era de finanças, e deixou de ser quando ele
    passou a ter seis frentes e objetivos com prazo. Um agente que lê só os
    eixos responde "pode comprar, cabe na sobra" para alguém cuja prova é em
    três semanas e que está cortando vídeo curto há quarenta dias.

    Este é o bloco curto que o agente lê **antes** de qualquer conselho. Ele
    junta as três camadas e, em cada uma, diz a mesma coisa sobre si: o quanto
    ali foi decidido e o quanto ainda é palpite do app.

    Não há número agregado, e isso é escolha. Um "índice de perfil" único seria
    exatamente o horóscopo que o catálogo de arquétipos existe para não ser.
    """
    perfil = ctx.get("perfil") or {}
    objetivos = (ctx.get("objetivos") or {}).get("perfil") or {}
    cobertura = perfil.get("cobertura") or {}

    eixos = []
    for e in perfil.get("eixos") or []:
        assinado = e.get("assinado")
        eixos.append({
            "eixo": e["eixo"],
            "nome": e.get("nome", e["eixo"]),
            "arquetipo": assinado["arquetipo"] if assinado else None,
            "como_se_sabe": "assinado" if assinado else "sugestão do catálogo",
            "sugerido": (e.get("sugerido") or {}).get("id"),
            "envelhecido": e.get("envelhecido", False),
            "porque": (assinado.get("proveniencia") or {}).get("porque", "") if assinado else "",
        })

    frentes = (ctx.get("objetivos") or {}).get("gauges", {}).get("frentes") or []
    fracas = [f["chave"] for f in frentes if not f.get("sem_base") and f.get("valor", 0) < 50]

    return {
        "schema_version": PROFILE_SCHEMA,
        "dinheiro": {
            "eixos": eixos,
            "decidido_pct": cobertura.get("pct", 0.0),
            "ainda_valido_pct": cobertura.get("pct_valido", 0.0),
            "a_reconfirmar": perfil.get("a_reconfirmar") or [],
        },
        "vida": {
            "frentes_fracas_hoje": fracas,
            "nota": (
                "frente fraca é o que ela não cumpriu na janela de hoje, não "
                "um traço de personalidade. Não transforme um dia ruim em "
                "diagnóstico"
            ),
        },
        "compromissos": {
            "objetivos": objetivos.get("objetivos") or [],
            "etapas_atrasadas": len(objetivos.get("etapas_atrasadas") or []),
            "restante_a_pagar": objetivos.get("compromisso_total_restante", 0.0),
            "rascunhos_esperando": len(
                objetivos.get("rascunhos_aguardando_assinatura") or []
            ),
        },
        "como_usar": (
            "cite o arquétipo pelo nome e o `porque` que ela escreveu, nunca o "
            "sugerido pelo catálogo como se fosse dela. Eixo em "
            "`a_reconfirmar` foi assinado há tempo demais para o ritmo daquele "
            "eixo: pergunte se ainda é assim antes de usar. E rascunho não é "
            "compromisso — ele está esperando a assinatura dela"
        ),
        "o_que_este_bloco_nao_e": (
            "não há número agregado de perfil, de propósito. Um índice único "
            "descreveria todo mundo e não mudaria conta nenhuma"
        ),
    }
