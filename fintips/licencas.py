"""O que de terceiros viaja junto, e sob que licença.

Este módulo existe por dois motivos que parecem distantes e são o mesmo.

O primeiro é legal: a Play Store exige que o app mostre as atribuições de
código aberto, e a maioria das licenças que usamos (MIT, Apache-2.0, OFL)
**obriga** a carregar o aviso junto do binário. Uma tela de licenças errada não
é um detalhe de rodapé; é descumprimento de licença.

O segundo é a disciplina do projeto. Uma lista de atribuições escrita à mão
envelhece em semanas: alguém acrescenta uma dependência, esquece a lista, e o
app passa a afirmar uma coisa que o binário desmente. É exatamente a falha que
`nada é verdade sem proveniência` existe para impedir — só que aqui a
afirmação falsa está numa tela que o usuário lê como declaração oficial.

## Como isso não envelhece

Cada ecossistema entra pela melhor fonte que ele oferece:

- **npm** é derivado de verdade. `web/package-lock.json` (v3) carrega o campo
  `license` de cada pacote, então a lista sai do lockfile e não de ninguém.
- **Gradle e Python** não publicam a licença no manifesto. Ali o manifesto diz
  **quais** dependências existem e `rules/licencas.yaml` declara **qual** é a
  licença de cada uma — e `conferir()` cruza os dois. Dependência nova sem
  declaração **quebra**, em vez de sumir da tela.
- **Fontes** entram pelo arquivo de licença que já viaja ao lado delas.

## O que embarca não é o que se instala

A atribuição que a loja cobra é a do que **vai no binário**, e o APK não leva
FastAPI nem o Vite. Por isso cada componente declara `embarca_em`, e a tela de
licenças de cada superfície pede só a sua. Misturar as duas listas inflaria a
tela do celular com dezenas de ferramentas de build que nunca chegam nele — e
uma tela que ninguém lê deixa de cumprir a função que a licença exige.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

LICENCAS_SCHEMA = 1

# As superfícies que distribuímos. `so_build` existe para que uma ferramenta de
# desenvolvimento possa ser declarada sem poluir a tela de ninguém.
SUPERFICIES = ("apk", "painel_web", "pacote_python", "so_build")

# Licenças que sabemos tratar. O mapa não é enfeite: `exige_aviso` decide se o
# texto precisa viajar junto do binário, e uma licença fora desta lista é
# recusada em vez de assumida — assumir aqui é assumir risco jurídico por
# omissão.
LICENCAS_CONHECIDAS: dict[str, dict] = {
    "MIT": {"nome": "MIT License", "exige_aviso": True, "copyleft": False},
    "Apache-2.0": {"nome": "Apache License 2.0", "exige_aviso": True, "copyleft": False},
    "BSD-2-Clause": {"nome": "BSD 2-Clause", "exige_aviso": True, "copyleft": False},
    "BSD-3-Clause": {"nome": "BSD 3-Clause", "exige_aviso": True, "copyleft": False},
    "ISC": {"nome": "ISC License", "exige_aviso": True, "copyleft": False},
    "MPL-2.0": {"nome": "Mozilla Public License 2.0", "exige_aviso": True, "copyleft": True},
    "OFL-1.1": {"nome": "SIL Open Font License 1.1", "exige_aviso": True, "copyleft": False},
    "Python-2.0": {"nome": "Python Software Foundation License", "exige_aviso": True, "copyleft": False},
    "0BSD": {"nome": "BSD Zero Clause", "exige_aviso": False, "copyleft": False},
    "Unlicense": {"nome": "The Unlicense", "exige_aviso": False, "copyleft": False},
}

# Licenças que, se aparecerem, param tudo. Copyleft forte num app distribuído
# muda o que podemos publicar, e isso é decisão de produto — nunca algo que o
# inventário deva resolver sozinho, em silêncio, enquanto a tela segue bonita.
LICENCAS_QUE_BLOQUEIAM = ("GPL-2.0", "GPL-3.0", "AGPL-3.0", "SSPL-1.0")


@dataclass
class Componente:
    id: str
    nome: str
    licenca: str
    versao: str = ""
    url: str = ""
    embarca_em: list[str] = field(default_factory=list)
    # De onde a informação veio: o lockfile, o manifesto, ou a declaração.
    fonte: str = ""

    @property
    def conhecida(self) -> bool:
        return self.licenca in LICENCAS_CONHECIDAS

    @property
    def bloqueia(self) -> bool:
        return self.licenca in LICENCAS_QUE_BLOQUEIAM

    def to_dict(self) -> dict:
        meta = LICENCAS_CONHECIDAS.get(self.licenca, {})
        return {
            "id": self.id,
            "nome": self.nome,
            "versao": self.versao,
            "licenca": self.licenca,
            "licenca_nome": meta.get("nome", self.licenca),
            "exige_aviso": bool(meta.get("exige_aviso", True)),
            "url": self.url,
            "embarca_em": list(self.embarca_em),
            "fonte": self.fonte,
        }


# ---------------------------------------------------------- as três fontes


def _declarados(raiz: Path) -> dict[str, Componente]:
    """`rules/licencas.yaml`: a licença de quem não a publica no manifesto."""
    p = raiz / "fintips" / "rules" / "licencas.yaml"
    if not p.exists():
        return {}
    d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    saida = {}
    for c in d.get("componentes") or []:
        for s in c.get("embarca_em") or []:
            if s not in SUPERFICIES:
                raise ValueError(
                    f"componente '{c.get('id')}': superfície '{s}' não existe. "
                    f"As quatro são {', '.join(SUPERFICIES)}"
                )
        saida[c["id"]] = Componente(
            id=c["id"], nome=c.get("nome", c["id"]), licenca=c["licenca"],
            versao=str(c.get("versao", "")), url=c.get("url", ""),
            embarca_em=list(c.get("embarca_em") or []), fonte="rules/licencas.yaml",
        )
    return saida


def _npm(raiz: Path) -> list[Componente]:
    """Derivado do lockfile. Só o que o bundle leva — `dev` fica de fora.

    O painel é compilado com Vite: as dependências de desenvolvimento ficam na
    máquina de quem compila e não entram em `fintips/web/assets/`. Listá-las na
    tela seria afirmar que elas viajam.
    """
    p = raiz / "web" / "package-lock.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
    saida = []
    for caminho, info in (d.get("packages") or {}).items():
        if not caminho.startswith("node_modules/") or info.get("dev"):
            continue
        nome = caminho.split("node_modules/")[-1]
        saida.append(Componente(
            id=f"npm:{nome}", nome=nome, licenca=str(info.get("license") or ""),
            versao=str(info.get("version", "")),
            url=f"https://www.npmjs.com/package/{nome}",
            embarca_em=["painel_web", "apk"],   # o APK embarca o painel na WebView
            fonte="web/package-lock.json",
        ))
    return sorted(saida, key=lambda c: c.id)


# Toda configuração que põe código no artefato, não só `implementation`:
# `debugImplementation` foi por onde o `androidx.webkit` entrou no APK, e uma
# varredura que só olha `implementation` o perderia em silêncio.
# Toda configuração que põe código no artefato, não só `implementation`: foi
# por `debugImplementation` que o `androidx.webkit` entrou no APK, e uma
# varredura que olhasse só `implementation` o perderia em silêncio.
_GRADLE = re.compile(
    r'(?:debugImplementation|releaseImplementation|implementation|api)'
    r'\s*\(\s*"([^":]+):([^":]+):([^"]+)"\s*\)'
)


def _gradle(raiz: Path) -> list[tuple[str, str]]:
    """Coordenadas que o build Android/JVM declara. Só os nomes — a licença
    não está no manifesto, e inventá-la aqui seria o oposto do ponto."""
    achados = []
    for f in sorted((raiz / "kotlin").rglob("build.gradle.kts")):
        texto = f.read_text(encoding="utf-8")
        for grupo, artefato, versao in _GRADLE.findall(texto):
            if "$" in versao:   # versão por variável: resolvida na declaração
                versao = ""
            achados.append((f"gradle:{grupo}:{artefato}", versao))
    return sorted(set(achados))


def _python(raiz: Path) -> list[tuple[str, str]]:
    """As dependências de `pyproject.toml`, pelo nome do distribuível.

    Lido com um parser TOML de verdade, e não por expressão regular sobre o
    arquivo: a primeira versão deste código varria qualquer string com um
    operador de comparação dentro e achou uma dependência chamada `motor` — que
    era a seta `->` da descrição do projeto. Varredura que inventa dependência
    é pior que varredura que perde uma, porque a lista fica plausível.
    """
    p = raiz / "pyproject.toml"
    if not p.exists():
        return []
    try:
        import tomllib
    except ModuleNotFoundError:          # Python 3.10
        return []
    d = tomllib.loads(p.read_text(encoding="utf-8"))
    proj = d.get("project", {})
    linhas = list(proj.get("dependencies") or [])
    for extra in (proj.get("optional-dependencies") or {}).values():
        linhas.extend(extra)
    nomes = set()
    for linha in linhas:
        m = re.match(r"^([A-Za-z0-9_.\-]+)", linha.strip())
        if m:
            nomes.add(m.group(1).lower())
    return sorted((f"pypi:{n}", "") for n in nomes)


# ------------------------------------------------------ conferência cruzada


def conferir(raiz: str | Path = ".") -> dict:
    """Os manifestos e a declaração ainda contam a mesma história?

    Três perguntas, e cada uma pega um jeito diferente de a tela de licenças
    começar a mentir:

    - **`nao_declarados`**: alguém acrescentou uma dependência e não disse a
      licença. É o caso comum, e o mais perigoso, porque o app continua
      funcionando e a tela continua bonita.
    - **`declarados_sem_uso`**: a dependência saiu do projeto e a declaração
      ficou. A tela passa a atribuir crédito a código que não viaja mais.
    - **`sem_licenca_conhecida`**: o lockfile trouxe um identificador que não
      sabemos tratar. Assumir que é permissiva seria assumir risco jurídico
      por omissão.

    Qualquer uma delas preenchida significa `ok: False`.
    """
    raiz = Path(raiz)
    declarados = _declarados(raiz)
    nos_manifestos: dict[str, str] = {}
    for ident, versao in _gradle(raiz) + _python(raiz):
        nos_manifestos[ident] = versao

    nao_declarados = sorted(set(nos_manifestos) - set(declarados))
    # Declarações que não vêm de manifesto não podem ser cobradas por ele: o
    # stdlib entra pelo plugin do Kotlin e a fonte viaja como arquivo.
    cobráveis = {
        k for k in declarados
        if k.startswith(("gradle:", "pypi:")) and not k.endswith("kotlin-stdlib")
    }
    declarados_sem_uso = sorted(cobráveis - set(nos_manifestos))

    do_npm = _npm(raiz)
    sem_licenca = sorted(
        c.id for c in do_npm if not c.licenca or c.licenca not in LICENCAS_CONHECIDAS
    ) + sorted(c.id for c in declarados.values() if not c.conhecida)
    bloqueiam = sorted(
        c.id for c in list(declarados.values()) + do_npm if c.bloqueia
    )

    return {
        "ok": not (nao_declarados or declarados_sem_uso or sem_licenca or bloqueiam),
        "nao_declarados": nao_declarados,
        "declarados_sem_uso": declarados_sem_uso,
        "sem_licenca_conhecida": sem_licenca,
        "licenca_que_bloqueia": bloqueiam,
        "conferidos": {
            "gradle": len(_gradle(raiz)),
            "python": len(_python(raiz)),
            "npm_que_embarca": len(do_npm),
            "declarados": len(declarados),
        },
        "como_corrigir": (
            "acrescente o componente em fintips/rules/licencas.yaml com a "
            "licença dele, ou remova a declaração se a dependência saiu"
        ),
    }


def inventario(raiz: str | Path = ".", superficie: str = "apk") -> list[dict]:
    """As atribuições de uma superfície, prontas para a tela.

    Ordenadas pelo nome, com o aviso que cada licença exige. Esta é a lista que
    a Play Store cobra — e é por isso que ela sai daqui, e não de um arquivo de
    texto que alguém mantém à mão.
    """
    if superficie not in SUPERFICIES:
        raise ValueError(
            f"superfície '{superficie}' não existe. "
            f"As quatro são {', '.join(SUPERFICIES)}"
        )
    raiz = Path(raiz)
    versoes = dict(_gradle(raiz))
    saida = []
    for c in _declarados(raiz).values():
        if superficie in c.embarca_em:
            c.versao = c.versao or versoes.get(c.id, "")
            saida.append(c.to_dict())
    for c in _npm(raiz):
        if superficie in c.embarca_em:
            saida.append(c.to_dict())
    return sorted(saida, key=lambda d: d["nome"].lower())


def exportar_para_aparelho(raiz: str | Path = ".") -> dict:
    """O que a aba de configuração do app mostra em "Licenças".

    Só o que embarca no APK. A conferência vai junto, e não como enfeite: se
    ela falhar, a tela precisa poder dizer que a lista pode estar incompleta em
    vez de apresentá-la como completa.
    """
    estado = conferir(raiz)
    itens = inventario(raiz, "apk")
    return {
        "schema_version": LICENCAS_SCHEMA,
        "componentes": itens,
        "quantos": len(itens),
        "conferencia_ok": estado["ok"],
        "nota": (
            "lista derivada dos manifestos do projeto, não escrita à mão. "
            "Se `conferencia_ok` for falso, diga na tela que a lista pode "
            "estar incompleta — não a apresente como completa"
        ),
    }
