"""Parser de OFX (SGML 1.x e XML 2.x) tolerante às variações brasileiras.

Particularidades tratadas:
- SGML sem tags de fechamento nos campos de valor (<TRNAMT>-23.21).
- Datas com timezone no formato OFX: 20260504191415[-3:BRT].
- PagBank escreve <BALAMT> em pt-BR e com símbolo: "R$ 1.234,56".
- <DTASOF> às vezes vem como dd/mm/aaaa em vez de aaaammdd.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ..models import Account, Statement, Transaction
from ..privacy import hash_account

_TAG = re.compile(r"<([A-Z0-9.]+)>([^<\r\n]*)", re.I)
_STMTTRN = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.S | re.I)
_OFX_DT = re.compile(r"^(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?")
_TZ = re.compile(r"\[([+-]?\d+(?:\.\d+)?):?([A-Z]*)\]")


class OFXParseError(ValueError):
    pass


def parse_amount(raw: str) -> Decimal:
    """Aceita '-23.21', 'R$ 1.234,56' e '1,234.56'."""
    s = raw.strip().replace("R$", "").replace("\xa0", " ").strip()
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("()-+ ")
    if "," in s and "." in s:
        # o separador decimal é o que aparece por último
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        value = Decimal(s or "0")
    except InvalidOperation as exc:  # pragma: no cover - entrada corrompida
        raise OFXParseError(f"valor não numérico no OFX: {raw!r}") from exc
    return -value if neg else value


def parse_datetime(raw: str) -> datetime:
    s = raw.strip()
    tz = timezone(timedelta(hours=-3))  # padrão Brasil quando o OFX omite
    m = _TZ.search(s)
    if m:
        tz = timezone(timedelta(hours=float(m.group(1))))
        s = s[: m.start()]
    if "/" in s:  # dd/mm/aaaa
        d, mth, y = s.split("/")[:3]
        return datetime(int(y), int(mth), int(d), tzinfo=tz)
    m = _OFX_DT.match(s)
    if not m:
        raise OFXParseError(f"data OFX inválida: {raw!r}")
    y, mo, d, hh, mm, ss = m.groups()
    return datetime(
        int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0), tzinfo=tz
    )


def _fields(block: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tag, value in _TAG.findall(block):
        tag = tag.upper()
        value = value.strip()
        if value and tag not in out:
            out[tag] = value
    return out


def parse_ofx(path: str | Path, *, salt: str = "") -> Statement:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    body = text.split("<OFX>", 1)[-1]

    head = _fields(body.split("<BANKTRANLIST>", 1)[0])
    acct_raw = head.get("ACCTID", "desconhecida")
    account = Account(
        id_hash=hash_account(acct_raw, salt),
        institution=head.get("ORG", ""),
        bank_id=head.get("BANKID", ""),
        type=head.get("ACCTTYPE", "CHECKING"),
        currency=head.get("CURDEF", "BRL"),
    )

    txs: list[Transaction] = []
    seen: set[tuple[str, str, str]] = set()
    used_ids: set[str] = set()
    for block in _STMTTRN.findall(body):
        f = _fields(block)
        fitid = f.get("FITID") or ""
        if not fitid:
            continue
        # O PagBank reaproveita o FITID no estorno da mesma compra, então a
        # chave de deduplicação é (fitid, valor, data) — senão o estorno some.
        key = (fitid, f.get("TRNAMT", ""), f.get("DTPOSTED", ""))
        if key in seen:
            continue
        seen.add(key)
        uid = fitid
        n = 1
        while uid in used_ids:
            n += 1
            uid = f"{fitid}#{n}"
        used_ids.add(uid)
        txs.append(
            Transaction(
                id=uid,
                ts=parse_datetime(f["DTPOSTED"]),
                amount=parse_amount(f["TRNAMT"]),
                memo_raw=(f.get("MEMO") or f.get("NAME") or "").strip(),
                account_id=account.id_hash,
            )
        )
    txs.sort(key=lambda t: t.ts)
    if not txs:
        raise OFXParseError("nenhuma transação encontrada no arquivo")

    tail = _fields(body.split("</BANKTRANLIST>", 1)[-1])
    start = _safe_date(head.get("DTSTART"), txs[0].ts.date())
    end = _safe_date(head.get("DTEND"), txs[-1].ts.date())
    balance = parse_amount(tail.get("BALAMT", "0"))
    as_of = _safe_date(tail.get("DTASOF"), end)

    return Statement(
        account=account,
        period_start=start,
        period_end=end,
        ledger_balance=balance,
        balance_as_of=as_of,
        transactions=txs,
        source=f"ofx:{account.institution or 'desconhecido'}",
    )


def _safe_date(raw: str | None, fallback: date) -> date:
    if not raw:
        return fallback
    try:
        return parse_datetime(raw).date()
    except OFXParseError:
        return fallback
