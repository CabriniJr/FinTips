"""Camada de PII.

Regra do projeto: o número da conta, o CPF e nomes completos de pessoas
físicas nunca são gravados em claro no YAML canônico nem saem da máquina.

- Conta/agência/CPF  -> hash truncado (irreversível, estável entre extratos).
- Pessoa física      -> pseudônimo estável ("PF:abc123") + apelido opcional
                        que VOCÊ define no mapa local (nunca inferido).
- Empresa/merchant   -> mantido em claro (não é dado pessoal e é o que dá
                        sentido à análise de gastos).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

SALT_FILE_NAME = ".fintips-salt"

# Padrões brasileiros que nunca devem vazar para um relatório.
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
_PHONE = re.compile(r"\b(?:\+55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}\b")


def digest(value: str, salt: str = "", length: int = 10) -> str:
    h = hashlib.sha256((salt + "|" + value).encode("utf-8")).hexdigest()
    return h[:length]


def hash_account(acct_id: str, salt: str = "") -> str:
    return "acct:" + digest(acct_id, salt)


def pseudonym(name: str, salt: str = "") -> str:
    return "PF:" + digest(_norm(name), salt, length=6)


def scrub(text: str) -> str:
    """Remove identificadores diretos de um texto livre."""
    text = _CPF.sub("[cpf]", text)
    text = _CNPJ.sub("[cnpj]", text)
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub("[fone]", text)
    text = _CARD.sub("[numero]", text)
    return text


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().upper()


def person_label(name: str, aliases: dict[str, str], salt: str = "") -> str:
    """Nome de pessoa física -> apelido do mapa local, ou pseudônimo estável.

    `aliases` é um dicionário que fica só na sua máquina, em
    data/aliases.yaml, no formato {"NOME COMPLETO": "pai"}.
    """
    key = _norm(name)
    for raw, alias in aliases.items():
        if _norm(raw) == key:
            return alias
    return pseudonym(name, salt)
