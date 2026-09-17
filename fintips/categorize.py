"""Classificação determinística das transações.

Determinística de propósito: o mesmo extrato sempre produz o mesmo YAML.
O Claude entra depois, em cima de dados estáveis — não é o LLM que decide
se o CDB é despesa.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import yaml

from .models import Transaction
from .privacy import person_label, scrub

RULES_PATH = Path(__file__).parent / "rules" / "categories.yaml"

# "MERCADO CENTRAL          SAO PAULO    BR" -> nome + cidade
_CARD_TAIL = re.compile(r"^(.*?)\s{2,}([A-Z][A-Za-z ]+?)\s*(BR|US|[A-Z]{2})?$")


def norm(s: object) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().upper()


class Categorizer:
    def __init__(
        self,
        rules_path: str | Path = RULES_PATH,
        *,
        aliases: dict[str, str] | None = None,
        my_names: Iterable[str] = (),
        salt: str = "",
        local_rules_path: str | Path | None = None,
    ) -> None:
        self.rules = yaml.safe_load(Path(rules_path).read_text(encoding="utf-8"))
        if local_rules_path and Path(local_rules_path).exists():
            self._merge_local(yaml.safe_load(Path(local_rules_path).read_text(encoding="utf-8")) or {})
        self.aliases = aliases or {}
        self.my_names = {norm(n) for n in my_names}
        self.salt = salt
        self._merchants = [
            (cat, [norm(k) for k in keys])
            for cat, keys in (self.rules.get("merchants") or {}).items()
        ]

    def _merge_local(self, local: dict) -> None:
        """Funde regras locais (não versionadas) por cima das públicas."""
        for cat, keys in (local.get("merchants") or {}).items():
            base = self.rules.setdefault("merchants", {}).setdefault(cat, [])
            # locais primeiro: em caso de empate, o estabelecimento seu vence
            self.rules["merchants"][cat] = list(keys) + [k for k in base if k not in keys]
        if local.get("canais"):
            self.rules["canais"] = list(local["canais"]) + self.rules.get("canais", [])
        if local.get("pessoa_fisica_hint"):
            self.rules["pessoa_fisica_hint"].update(local["pessoa_fisica_hint"])

    # ---------------------------------------------------------------- public
    def apply(self, tx: Transaction) -> Transaction:
        memo = scrub(tx.memo_raw)
        rule = self._match_channel(memo)
        if rule:
            tx.channel = rule.get("canal", tx.channel)
            tx.flow = rule.get("fluxo", tx.flow)
            tx.category = rule.get("categoria", tx.category)
            for tag in rule.get("tags", []) or []:
                if tag not in tx.tags:
                    tx.tags.append(tag)

        raw_party = memo.split(" - ", 1)[1].strip() if " - " in memo else ""
        if rule and rule.get("contraparte"):
            tx.counterparty = rule["contraparte"]
            tx.counterparty_kind = "institution"
        elif raw_party:
            self._set_counterparty(tx, raw_party)

        if tx.category in ("outros", "") and tx.counterparty:
            tx.category = self._category_for(tx.counterparty)

        self._post(tx)
        self._marca_origem(tx)
        return tx

    def apply_all(self, txs: Iterable[Transaction]) -> list[Transaction]:
        return [self.apply(t) for t in txs]

    # --------------------------------------------------------------- helpers
    def _match_channel(self, memo: str) -> dict | None:
        target = norm(memo)
        for rule in self.rules.get("canais", []):
            if target.startswith(norm(rule["match"])):
                return rule
        return None

    def _set_counterparty(self, tx: Transaction, raw: str) -> None:
        name, city = raw, ""
        m = _CARD_TAIL.match(raw)
        if m and tx.channel == "debit_card":
            name, city = m.group(1).strip(), m.group(2).strip()
        name = re.sub(r"\s{2,}", " ", name).strip(" .-")

        if self._is_person(name, tx.channel):
            if norm(name) in self.my_names:
                tx.counterparty = "eu (outra conta)"
                tx.counterparty_kind = "self"
                tx.flow = "transfer"
                tx.category = "outros"
            else:
                tx.counterparty = person_label(name, self.aliases, self.salt)
                tx.counterparty_kind = "person"
                tx.category = "pessoas"
        else:
            tx.counterparty = name
            tx.counterparty_kind = "merchant"
        tx.city = city

    def _is_person(self, name: str, channel: str = "") -> bool:
        # Cartão de débito, tarifa e recarga são sempre estabelecimento:
        # um nome comprido num cartão é loja, não pessoa.
        if channel not in ("pix", "pix_auto", "pix_qr"):
            return False
        hint = self.rules.get("pessoa_fisica_hint", {})
        n = norm(name)
        # Comparação por token: "ME" não pode casar dentro de "MENDES".
        tokens = {re.sub(r"[^A-Z]", "", w) for w in n.split()}
        sufixos = {re.sub(r"[^A-Z]", "", norm(s)) for s in (hint.get("sufixos_empresa") or [])}
        if tokens & sufixos:
            return False
        if any(ch.isdigit() or ch in "*/#" for ch in n):
            return False
        return len(n.split()) >= int(hint.get("min_palavras", 2))

    def _category_for(self, party: str) -> str:
        n = norm(party)
        for cat, keys in self._merchants:
            if any(k in n for k in keys):
                return cat
        return self.rules.get("fallback", "outros")

    def _marca_origem(self, tx: Transaction) -> None:
        """Toda saída daqui é palpite do pacote, nunca conhecimento sobre a pessoa."""
        tx.category_source = "heuristica"
        # canal e fluxo vêm do formato do extrato (confiável); a CATEGORIA é que
        # é chute — por isso a confiança fica baixa de propósito.
        tx.category_confidence = 0.55 if tx.category != "outros" else 0.1

    def _post(self, tx: Transaction) -> None:
        """Ajustes que dependem do conjunto canal+categoria+valor."""
        # Pix/transferência entre pessoas não é consumo: é repasse.
        if tx.counterparty_kind == "person" and tx.flow in ("expense", "income"):
            tx.flow = "transfer" if tx.flow == "expense" else "transfer"
            tx.category = "pessoas"
            if "repasse" not in tx.tags:
                tx.tags.append("repasse")
        # Micro-gasto: alvo do detector de gasto invisível.
        if tx.flow == "expense" and abs(tx.amount) <= Decimal("30"):
            if "micro" not in tx.tags:
                tx.tags.append("micro")
