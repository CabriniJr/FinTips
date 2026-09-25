"""API local do FinTips.

Escuta só em 127.0.0.1. Sem login, sem nuvem, sem telemetria: quem alcança a
porta já está na máquina onde os dados moram.

Os endpoints de escrita são as **mesmas primitivas** que o agente usa por MCP —
regra, categoria, compromisso, fato, resolução de triagem. O painel não tem um
caminho paralelo de decisão: o que se faz por aqui fica gravado com a mesma
proveniência do que se faz conversando.
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import levers, mapping, plans as plans_mod, projection, purchases, report
from .analysis import baseline
from .categorize import norm
from .contracts import Proveniencia
from .workspace import Workspace

API_VERSION = "0.5.0"
WEB_DIR = Path(__file__).parent / "web"


def _root() -> Path:
    return Path(os.environ.get("FINTIPS_ROOT", Path.home() / "Documents" / "FinTips"))


def _ws() -> Workspace:
    return Workspace.open(_root())


def _prov(origem: str, confianca: float, porque: str, evidencia: list[str] | None = None) -> Proveniencia:
    return Proveniencia(
        origem=origem if origem in ("agente", "usuario") else "usuario",
        confianca=float(confianca), porque=porque or "decidido no painel",
        evidencia=evidencia or [], por_quem="painel",
    )


class _Cache:
    """Recalcula quando qualquer arquivo de dados muda."""

    def __init__(self) -> None:
        self.stamp: tuple | None = None
        self.value: dict | None = None

    def _fingerprint(self, ws: Workspace) -> tuple:
        files = list(ws.data.rglob("*.yaml")) + list(ws.extratos.glob("*.ofx"))
        return tuple(sorted((str(f), f.stat().st_mtime_ns) for f in files))

    def get(self, ws: Workspace) -> dict:
        fp = self._fingerprint(ws)
        if self.stamp != fp or self.value is None:
            self.value = report.analyze(ws)
            self.stamp = fp
        return self.value

    def clear(self) -> None:
        self.stamp = None


cache = _Cache()
app = FastAPI(title="FinTips", version=API_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


# --------------------------------------------------------------------------
# entrada
# --------------------------------------------------------------------------

class RuleIn(BaseModel):
    quando: dict
    entao: dict
    porque: str = ""
    origem: str = "usuario"
    confianca: float = 1.0
    evidencia: list[str] = Field(default_factory=list)
    nota: str = ""


class CategoryIn(BaseModel):
    id: str
    nome: str
    descricao: str = ""
    essencial: bool | None = None
    pai: str = ""
    porque: str = ""
    origem: str = "usuario"
    confianca: float = 1.0


class CommitmentIn(BaseModel):
    rotulo: str
    base_tipo: str
    base_ref: str
    valor_mensal: float | None = None
    metodo: str = "mediana_meses_completos"
    natureza: str = "rotina"
    porque: str = ""
    origem: str = "usuario"
    confianca: float = 1.0
    evidencia: list[str] = Field(default_factory=list)


class FactIn(BaseModel):
    chave: str
    valor: Any
    tipo: str = ""
    porque: str = ""
    origem: str = "usuario"
    confianca: float = 1.0
    evidencia: list[str] = Field(default_factory=list)
    expira_em: str = ""


class ResolveIn(BaseModel):
    o_que_foi_feito: str = ""
    adiar: bool = False


class PlanIn(BaseModel):
    id: str
    nome: str
    custo_alvo: float
    data_alvo: str | None = None
    tipo: str = "outro"
    prioridade: str = "media"
    aporte_mensal: float = 0
    guardado: float = 0
    merchants: list[str] = Field(default_factory=list)
    categorias: list[str] = Field(default_factory=list)
    notas: str = ""


class PurchaseIn(BaseModel):
    item: str
    preco: float
    categoria: str = "compras"
    urgencia: str = "media"
    parcelas_possiveis: int = 1
    juros_parcelamento: float = 0.0
    substitui: str = ""
    palavras_chave: list[str] = Field(default_factory=list)


class ProfileIn(BaseModel):
    """Assinatura de um traço de perfil.

    `origem` só aceita agente ou usuário — o casamento por número é sugestão e
    entra por outro caminho (a leitura de `/api/context`), nunca por aqui.
    """

    arquetipo: str
    nome: str = ""
    descricao: str = ""
    porque: str = ""
    origem: str = "usuario"
    confianca: float = 1.0
    evidencia: list[str] = Field(default_factory=list)


class HoldingsIn(BaseModel):
    posicoes: list[dict]


# --------------------------------------------------------------------------
# leitura
# --------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    ws = _ws()
    return {
        "ok": True, "versao": API_VERSION, "workspace": str(ws.root),
        "tem_extrato": any(ws.extratos.glob("*.ofx")),
    }


@app.get("/api/context")
def context() -> dict:
    ws = _ws()
    if not any(ws.extratos.glob("*.ofx")):
        raise HTTPException(404, "nenhum extrato importado ainda")
    return cache.get(ws)


@app.get("/api/transactions")
def transactions(mes: str = "", categoria: str = "", fluxo: str = "", q: str = "",
                 valor_minimo: float = 0, limite: int = 200) -> dict:
    ws = _ws()
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    report.enrich(ws, stmt, st)
    alvo = norm(q) if q else ""
    linhas = []
    for t in stmt.transactions:
        if mes and t.month != mes:
            continue
        if categoria and t.category != categoria:
            continue
        if fluxo and t.flow != fluxo:
            continue
        if alvo and alvo not in norm(t.counterparty):
            continue
        if abs(float(t.amount)) < valor_minimo:
            continue
        linhas.append(t.to_yaml_dict())
    linhas.sort(key=lambda d: (d["data"], abs(d["valor"])), reverse=True)
    return {"total": len(linhas), "transacoes": linhas[:limite]}


@app.get("/api/projection")
def projecao(cenario: str = "base", meses: int = 12) -> dict:
    ws = _ws()
    ctx = cache.get(ws)
    return projection.project(
        baseline=ctx["baseline"],
        fixed_monthly=ctx["estrutura_de_custo"]["comprometido_mes"],
        saldo_conta=ctx["saldo_conta"],
        patrimonio=ctx["patrimonio"].get("total", 0),
        planos=ctx["planos"], meses=meses, cenario=cenario,
    )


@app.get("/api/profile")
def perfil() -> dict:
    """Sugestão por número e assinatura, eixo a eixo. Ler nunca grava perfil."""
    ws = _ws()
    return cache.get(ws)["perfil"]


@app.get("/api/levers")
def alavancas() -> dict:
    ws = _ws()
    return levers.calcular(cache.get(ws))


# --------------------------------------------------------------------------
# escrita: as mesmas primitivas do MCP
# --------------------------------------------------------------------------

@app.post("/api/rules")
def definir_regra(body: RuleIn) -> dict:
    ws = _ws()
    st = report.stores(ws)
    cat = (body.entao or {}).get("categoria")
    if cat and not st["taxonomia"].existe(cat):
        raise HTTPException(400, f"categoria '{cat}' não existe")
    try:
        regra = st["regras"].criar(
            body.quando, body.entao,
            proveniencia=_prov(body.origem, body.confianca, body.porque, body.evidencia),
            nota=body.nota,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    stmt = report.load_statement(ws, st)
    efeito = mapping.aplicar(st["regras"], stmt)
    cache.clear()
    return {"regra": regra.to_dict(), "efeito": efeito}


@app.delete("/api/rules/{regra_id}")
def remover_regra(regra_id: str) -> dict:
    st = report.stores(_ws())
    ok = st["regras"].remover(regra_id)
    cache.clear()
    return {"removida": ok}


@app.post("/api/categories")
def criar_categoria(body: CategoryIn) -> dict:
    st = report.stores(_ws())
    try:
        cat = st["taxonomia"].criar(
            body.id, body.nome, descricao=body.descricao, essencial=body.essencial,
            pai=body.pai or None,
            proveniencia=_prov(body.origem, body.confianca, body.porque),
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    cache.clear()
    return cat.to_dict()


@app.post("/api/commitments")
def definir_custo_fixo(body: CommitmentIn) -> dict:
    ws = _ws()
    st = report.stores(ws)
    stmt = report.load_statement(ws, st)
    try:
        item = st["compromissos"].definir(
            body.rotulo, body.base_tipo, body.base_ref,
            valor_mensal=body.valor_mensal, metodo=body.metodo, natureza=body.natureza,
            proveniencia=_prov(body.origem, body.confianca, body.porque, body.evidencia),
            stmt=stmt, meses_completos=baseline(stmt).get("meses_considerados"),
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    cache.clear()
    return {"custo_fixo": item.to_dict(), "total": st["compromissos"].total_mensal()}


@app.delete("/api/commitments/{custo_id}")
def remover_custo_fixo(custo_id: str) -> dict:
    st = report.stores(_ws())
    ok = st["compromissos"].remover(custo_id)
    cache.clear()
    return {"removido": ok}


@app.post("/api/facts")
def gravar_fato(body: FactIn) -> dict:
    st = report.stores(_ws())
    try:
        fato = st["contexto"].gravar(
            body.chave, body.valor, tipo=body.tipo,
            proveniencia=_prov(body.origem, body.confianca, body.porque, body.evidencia),
            expira_em=body.expira_em or None,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    cache.clear()
    return {"fato": fato.to_dict(), "cobertura": st["contexto"].cobertura()}


@app.delete("/api/facts/{chave}")
def esquecer_fato(chave: str) -> dict:
    st = report.stores(_ws())
    ok = st["contexto"].esquecer(chave)
    cache.clear()
    return {"esquecido": ok}


@app.post("/api/profile/{eixo}")
def assinar_perfil(eixo: str, body: ProfileIn) -> dict:
    # aqui o `porque` não ganha texto padrão: dizer quem a pessoa é sem dizer
    # com base em quê é exatamente o que o perfil existe para impedir
    if not body.porque.strip():
        raise HTTPException(400, "assinar um traço de perfil exige `porque`")
    st = report.stores(_ws())
    try:
        traco = st["perfil"].assinar(
            eixo, body.arquetipo,
            nome=body.nome, descricao=body.descricao,
            proveniencia=_prov(body.origem, body.confianca, body.porque, body.evidencia),
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    cache.clear()
    return {"traco": traco.to_dict()}


@app.delete("/api/profile/{eixo}")
def esquecer_perfil(eixo: str) -> dict:
    st = report.stores(_ws())
    ok = st["perfil"].esquecer(eixo)
    cache.clear()
    return {"esquecido": ok}


@app.post("/api/triage/{item_id}/resolve")
def resolver_item(item_id: str, body: ResolveIn) -> dict:
    st = report.stores(_ws())
    loja = st["triagem"]
    reg = (loja.adiar(item_id, body.o_que_foi_feito) if body.adiar
           else loja.resolver(item_id, {"o_que_foi_feito": body.o_que_foi_feito}))
    cache.clear()
    return {"item": item_id, "registro": reg}


@app.post("/api/plans")
def salvar_plano(body: PlanIn) -> dict:
    from datetime import date

    ws = _ws()
    items = [p for p in plans_mod.load_plans(ws.planos_path) if p.id != body.id]
    novo = plans_mod.Plan(
        id=body.id, nome=body.nome, tipo=body.tipo,
        custo_alvo=Decimal(str(body.custo_alvo)),
        data_alvo=date.fromisoformat(body.data_alvo) if body.data_alvo else None,
        prioridade=body.prioridade, aporte_mensal=Decimal(str(body.aporte_mensal)),
        guardado=Decimal(str(body.guardado)), merchants=body.merchants,
        categorias=body.categorias, notas=body.notas,
    )
    items.append(novo)
    plans_mod.save_plans(ws.planos_path, items)
    cache.clear()
    return {"ok": True, "plano": novo.to_dict()}


@app.delete("/api/plans/{plan_id}")
def remover_plano(plan_id: str) -> dict:
    ws = _ws()
    plans_mod.save_plans(
        ws.planos_path, [p for p in plans_mod.load_plans(ws.planos_path) if p.id != plan_id]
    )
    cache.clear()
    return {"ok": True}


@app.post("/api/purchase")
def avaliar_compra(body: PurchaseIn) -> dict:
    ws = _ws()
    st = report.stores(ws)
    ctx = cache.get(ws)
    stmt = report.load_statement(ws, st)
    report.enrich(ws, stmt, st)
    intent = purchases.PurchaseIntent(
        item=body.item, preco=Decimal(str(body.preco)), categoria=body.categoria,
        urgencia=body.urgencia, parcelas_possiveis=body.parcelas_possiveis,
        juros_parcelamento=body.juros_parcelamento, substitui=body.substitui,
        tags=body.palavras_chave,
    )
    return purchases.evaluate(
        intent, stmt, ctx["baseline"], ctx["planos"],
        saldo_conta=ctx["saldo_conta"],
        patrimonio=ctx["patrimonio"].get("total", 0),
        reserva_alvo_meses=float(ctx["baseline"].get("reserva_alvo_meses", 6)),
        perfil=ctx.get("perfil"),
        causas=(ctx.get("causas") or {}).get("itens"),
        precedentes=st["decisoes"].semelhantes(
            f"{intent.item} {intent.categoria}", tipo="compra",
            ligacoes=[f"categoria:{intent.categoria}"],
        ),
        aprendizados=(ctx.get("decisoes") or {}).get("aprendizados"),
    )


@app.post("/api/holdings")
def salvar_patrimonio(body: HoldingsIn) -> dict:
    out = _ws().save_patrimonio(body.posicoes)
    cache.clear()
    return out


@app.post("/api/import")
async def importar(arquivo: UploadFile = File(...)) -> dict:
    ws = _ws()
    nome = Path(arquivo.filename or "extrato.ofx").name
    if not nome.lower().endswith((".ofx", ".qfx")):
        raise HTTPException(400, "envie um arquivo .ofx")
    destino = ws.extratos / nome
    destino.write_bytes(await arquivo.read())
    stmt, canonico = report.ingest(ws, destino)
    ok, diff = stmt.reconciles()
    cache.clear()
    ctx = cache.get(ws)
    return {
        "ok": True, "arquivo": nome, "transacoes": len(stmt.transactions),
        "periodo": [str(stmt.period_start), str(stmt.period_end)],
        "conciliacao_ok": ok, "diferenca": float(diff), "canonico": str(canonico),
        "triagem": ctx["triagem"]["resumo"],
    }


# --------------------------------------------------------------------------
# frontend
# --------------------------------------------------------------------------

if (WEB_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidato = WEB_DIR / full_path
        if full_path and candidato.is_file():
            return FileResponse(candidato)
        return FileResponse(WEB_DIR / "index.html")
else:
    @app.get("/")
    def sem_front():
        return JSONResponse({
            "aviso": "frontend não compilado",
            "como": "cd web && npm install && npm run build",
            "api": "/api/context",
        })


def serve(host: str = "127.0.0.1", port: int = 8420, root: str | None = None) -> None:
    import uvicorn

    if root:
        os.environ["FINTIPS_ROOT"] = str(Path(root).expanduser())
    Workspace.open(_root())
    uvicorn.run(app, host=host, port=port, log_level="warning")
