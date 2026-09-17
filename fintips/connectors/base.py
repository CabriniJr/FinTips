"""Interface de ingestão.

Todo conector (OFX, Pluggy/Open Finance, CSV, futuro banco direto) entrega a
mesma coisa: um `Statement` já normalizado. O resto do motor não sabe nem se
importa de onde veio.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from ..models import Statement


class Connector(ABC):
    """Fonte de dados bancários."""

    name: str = "base"

    @abstractmethod
    def fetch(self, *, since: date | None = None, until: date | None = None) -> list[Statement]:
        """Traz um ou mais extratos normalizados."""

    def healthcheck(self) -> dict:
        return {"conector": self.name, "ok": True}


class CredentialStore(ABC):
    """Onde ficam segredos. Nunca no YAML, nunca no repositório."""

    @abstractmethod
    def get(self, key: str) -> str | None: ...

    @abstractmethod
    def set(self, key: str, value: str) -> None: ...


class EnvCredentials(CredentialStore):
    """Implementação mínima: variáveis de ambiente.

    Para uso diário, troque por keyring (Windows Credential Manager):
        pip install keyring
        keyring.set_password("fintips", "PLUGGY_CLIENT_SECRET", "...")
    """

    def get(self, key: str) -> str | None:
        import os

        return os.environ.get(key)

    def set(self, key: str, value: str) -> None:  # pragma: no cover
        raise NotImplementedError("defina a variável de ambiente no sistema")
