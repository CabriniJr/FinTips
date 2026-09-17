"""Conector Open Finance via Meu Pluggy (uso pessoal, gratuito).

Por que via agregador: ser receptora direta no Open Finance Brasil exige
organização cadastrada no Diretório, certificados BRCAC e certificação FAPI-BR
na OpenID Foundation — inviável para pessoa física. O Meu Pluggy dá chaves de
API para você ler as SUAS próprias contas, sem custo, para uso não comercial.

Fluxo:
  1. Conectar seus bancos em meu.pluggy.ai (consentimento fica lá).
  2. Criar uma aplicação no dashboard -> clientId + clientSecret.
  3. Exportar PLUGGY_CLIENT_ID / PLUGGY_CLIENT_SECRET / PLUGGY_ITEM_IDS.
  4. `fintips sync --pluggy`.

O apiKey vale 2h e fica só em memória. Nada de segredo em arquivo do projeto.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from ..models import Account, Statement, Transaction
from ..privacy import hash_account
from .base import Connector, CredentialStore, EnvCredentials

BASE_URL = "https://api.pluggy.ai"
TZ = timezone(timedelta(hours=-3))


class PluggyConnector(Connector):
    name = "pluggy"

    def __init__(
        self,
        item_ids: list[str] | None = None,
        creds: CredentialStore | None = None,
        *,
        salt: str = "",
        timeout: int = 30,
    ) -> None:
        self.creds = creds or EnvCredentials()
        self.item_ids = item_ids or [
            i for i in (self.creds.get("PLUGGY_ITEM_IDS") or "").split(",") if i
        ]
        self.salt = salt
        self.timeout = timeout
        self._api_key: str | None = None
        self._key_expires = datetime.min.replace(tzinfo=TZ)

    # ------------------------------------------------------------------ http
    def _request(self, method: str, path: str, *, body: dict | None = None, auth: bool = True) -> dict:
        url = f"{BASE_URL}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if auth:
            req.add_header("X-API-KEY", self._key())
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _key(self) -> str:
        if self._api_key and datetime.now(TZ) < self._key_expires:
            return self._api_key
        cid = self.creds.get("PLUGGY_CLIENT_ID")
        secret = self.creds.get("PLUGGY_CLIENT_SECRET")
        if not cid or not secret:
            raise RuntimeError("defina PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET")
        out = self._request("POST", "/auth", body={"clientId": cid, "clientSecret": secret}, auth=False)
        self._api_key = out["apiKey"]
        self._key_expires = datetime.now(TZ) + timedelta(minutes=110)  # chave vale 2h
        return self._api_key

    # ----------------------------------------------------------------- fetch
    def fetch(self, *, since: date | None = None, until: date | None = None) -> list[Statement]:
        if not self.item_ids:
            raise RuntimeError("nenhum itemId configurado (PLUGGY_ITEM_IDS)")
        out: list[Statement] = []
        for item_id in self.item_ids:
            accounts = self._request("GET", f"/accounts?itemId={item_id}").get("results", [])
            for acc in accounts:
                out.append(self._statement(acc, since, until))
        return out

    def _statement(self, acc: dict, since: date | None, until: date | None) -> Statement:
        params = [f"accountId={acc['id']}", "pageSize=500"]
        if since:
            params.append(f"from={since.isoformat()}")
        if until:
            params.append(f"to={until.isoformat()}")
        txs_raw: list[dict] = []
        page = 1
        while True:
            payload = self._request("GET", "/transactions?" + "&".join(params + [f"page={page}"]))
            txs_raw.extend(payload.get("results", []))
            if page >= int(payload.get("totalPages", 1)):
                break
            page += 1

        txs = [
            Transaction(
                id=t["id"],
                ts=_parse_iso(t["date"]),
                amount=Decimal(str(t["amount"])),
                memo_raw=(t.get("description") or "").strip(),
                account_id=hash_account(acc["id"], self.salt),
            )
            for t in txs_raw
        ]
        txs.sort(key=lambda t: t.ts)
        start = since or (txs[0].day if txs else date.today())
        end = until or (txs[-1].day if txs else date.today())
        return Statement(
            account=Account(
                id_hash=hash_account(acc["id"], self.salt),
                institution=(acc.get("bankData") or {}).get("institution") or acc.get("name", ""),
                bank_id=str(acc.get("itemId", "")),
                type=acc.get("type", "CHECKING"),
                currency=acc.get("currencyCode", "BRL"),
            ),
            period_start=start,
            period_end=end,
            ledger_balance=Decimal(str(acc.get("balance", 0))),
            balance_as_of=end,
            transactions=txs,
            source="pluggy:open-finance",
        )


def _parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.astimezone(TZ) if dt.tzinfo else dt.replace(tzinfo=TZ)
