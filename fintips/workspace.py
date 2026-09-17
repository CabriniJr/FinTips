"""Workspace local: onde os dados moram e como são lidos.

Layout (tudo na sua máquina, nada sincronizado por padrão):

    FinTips/
      config.yaml          perfil, nomes próprios, apelidos de PF
      data/
        extratos/          .ofx originais (entrada)
        canonico/          .yaml gerado pelo parser (fonte de verdade)
        planos.yaml        seus planos financeiros
        patrimonio.yaml    saldos e posições que o extrato não vê
        compras.yaml       intenções de compra em avaliação
      relatorios/          saídas geradas (dashboard, análises)
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

DEFAULT_CONFIG = {
    "moeda": "BRL",
    "reserva_alvo_meses": 6,
    "meus_nomes": [],          # nomes que aparecem como você mesmo em Pix
    "apelidos": {},            # {"NOME COMPLETO": "pai"} — só local
    "incluir_memo_bruto": False,  # true = YAML guarda o texto original do banco
}


@dataclass
class Workspace:
    root: Path

    @classmethod
    def open(cls, root: str | Path) -> "Workspace":
        ws = cls(Path(root).expanduser())
        ws.ensure()
        return ws

    # ------------------------------------------------------------- estrutura
    def ensure(self) -> None:
        for p in (self.extratos, self.canonico, self.relatorios):
            p.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self.config_path.write_text(
                yaml.safe_dump(DEFAULT_CONFIG, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        if not self.salt_path.exists():
            self.salt_path.write_text(secrets.token_hex(16), encoding="utf-8")
            try:
                os.chmod(self.salt_path, 0o600)
            except OSError:
                pass  # Windows

    @property
    def data(self) -> Path: return self.root / "data"
    @property
    def extratos(self) -> Path: return self.data / "extratos"
    @property
    def canonico(self) -> Path: return self.data / "canonico"
    @property
    def relatorios(self) -> Path: return self.root / "relatorios"
    @property
    def config_path(self) -> Path: return self.root / "config.yaml"
    @property
    def salt_path(self) -> Path: return self.root / ".fintips-salt"
    @property
    def planos_path(self) -> Path: return self.data / "planos.yaml"
    @property
    def patrimonio_path(self) -> Path: return self.data / "patrimonio.yaml"
    @property
    def compras_path(self) -> Path: return self.data / "compras.yaml"
    @property
    def perfil_path(self) -> Path: return self.data / "perfil.yaml"   # legado (v0.2)
    @property
    def taxonomia_path(self) -> Path: return self.data / "taxonomia.yaml"
    @property
    def regras_path(self) -> Path: return self.data / "regras.yaml"
    @property
    def contexto_path(self) -> Path: return self.data / "contexto.yaml"
    @property
    def custos_fixos_path(self) -> Path: return self.data / "custos-fixos.yaml"
    @property
    def triagem_path(self) -> Path: return self.data / "triagem.yaml"
    @property
    def contrapartes_path(self) -> Path: return self.data / "contrapartes.yaml"
    @property
    def regras_locais_path(self) -> Path:
        """Estabelecimentos do seu dia a dia. Fica em data/ — fora do Git."""
        return self.data / "regras-locais.yaml"

    # ---------------------------------------------------------------- leitura
    @property
    def config(self) -> dict:
        cfg = dict(DEFAULT_CONFIG)
        if self.config_path.exists():
            cfg.update(yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {})
        return cfg

    @property
    def salt(self) -> str:
        return self.salt_path.read_text(encoding="utf-8").strip()

    def load_patrimonio(self) -> dict:
        if not self.patrimonio_path.exists():
            return {"posicoes": [], "total": 0.0, "atualizado_em": None}
        d = yaml.safe_load(self.patrimonio_path.read_text(encoding="utf-8")) or {}
        total = sum(Decimal(str(p.get("valor", 0))) for p in d.get("posicoes", []))
        d["total"] = float(total)
        return d

    def save_patrimonio(self, posicoes: list[dict], *, quando: date | None = None) -> dict:
        payload = {
            "atualizado_em": (quando or date.today()).isoformat(),
            "posicoes": posicoes,
        }
        self.patrimonio_path.parent.mkdir(parents=True, exist_ok=True)
        self.patrimonio_path.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        return self.load_patrimonio()

    def latest_canonical(self) -> Path | None:
        files = sorted(self.canonico.glob("*.yaml"))
        return files[-1] if files else None
