#!/usr/bin/env python3
"""Anonymize WB API JSON fixtures (Story 1.0, AD-4). Fail-closed.

Input: a JSON response of WB Statistics (orders/sales array) or analytics
(sales-funnel v3 history / nm-report downloads). Output: structurally
identical JSON with identifying values replaced. Every key MUST belong to
exactly one disposition set below; an unknown key aborts the run (fail-closed)
so a new/renamed WB field can never leak silently.

- nmId -> deterministic per-run renumbered id (12345001, ...); subjectId -> 9001, ...
- supplierArticle/vendorCode -> sku-<n>; subject/subjectName -> subject-<n>;
  brand/brandName -> brand-<n>; title -> title-<n>; category -> category-<n>
- money fields multiplied by one coefficient 0.8-1.2 per file derived from a
  SECRET salt (--salt-file, never committed), NOT from the public --seed
- timestamps: date part kept, time-of-day remapped by a secret monotonic
  per-file linear map (ordering and equality preserved; exact seconds destroyed);
  the WB null sentinel 0001-01-01T00:00:00 and date-only values pass unchanged
- srid/saleID/gNumber/sticker/barcode/incomeID -> deterministic synthetic
  values preserving uniqueness (saleID keeps its S/R prefix)
- geography (regionName, oblast, oblastOkrugName, countryName,
  warehouseName) -> fixed placeholders
- report ids (key `id`, UUID-shaped) -> synthetic valid v4 UUIDs

Usage:
    python3 tools/anonymize_fixture.py <in.json> <out.json> --seed 42 \
        --salt-file ~/.config/proxima/fixture-salt \
        [--limit-days 14] [--max-bytes 200000]

--limit-days N keeps only the last N days by `date`; --max-bytes thins
rows uniformly (at least one row per day is kept) until the serialized
output fits the byte budget.

Same seed + same salt + same input => identical output. The salt lives
outside git; without it money amounts and timestamps are not reproducible
(and therefore not reversible from the published fixtures).
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

NM_ID_BASE = 12345000
INCOME_ID_BASE = 5000000
SUBJECT_ID_BASE = 9000
NULL_TIMESTAMP = "0001-01-01T00:00:00"

MONEY_KEYS = {
    "totalPrice",
    "priceWithDisc",
    "finishedPrice",
    "forPay",
    "paymentSaleAmount",
    "orderSum",
    "buyoutSum",
    "orders_sum",
    "buyout_sum",
}

TEXT_MAP_KEYS = {
    "supplierArticle": "sku",
    "vendorCode": "sku",
    "subject": "subject",
    "subjectName": "subject",
    "brand": "brand",
    "brandName": "brand",
    "title": "title",
    "category": "category",
}

GEO_PLACEHOLDERS = {
    "regionName": "region-1",
    "oblast": "oblast-1",
    "oblastOkrugName": "oblast-1",
    "countryName": "country-1",
    "warehouseName": "warehouse-1",
}

# date part kept, time-of-day remapped (see Anonymizer._datetime)
DATETIME_KEYS = {"date", "lastChangeDate", "cancelDate", "createdAt"}

# UUID-shaped report ids -> synthetic v4
UUID_KEYS = {"id"}

# verbatim by explicit decision (documented in fixtures README):
# flags/enums carry no identity; counts and conversions without exact
# timestamps, money and categories do not identify the cabinet
PASSTHROUGH_KEYS = {
    "discountPercent",
    "spp",
    "techSize",
    "isSupply",
    "isRealization",
    "isCancel",
    "warehouseType",
    "currency",
    "status",
    "name",
    "size",
    "startDate",
    "endDate",
    "openCount",
    "cartCount",
    "orderCount",
    "buyoutCount",
    "buyoutPercent",
    "addToCartConversion",
    "cartToOrderConversion",
    "addToWishlistCount",
}

# containers we recurse into
STRUCTURAL_KEYS = {"data", "history", "product"}

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
SALE_ID_PREFIX_RE = re.compile(r"^([A-Za-z]*)")
DATETIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})([T ])(\d{2}):(\d{2}):(\d{2})$")
DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DAY_SECONDS = 86399


def _hmac_unit(salt: bytes, label: str) -> float:
    digest = hmac.new(salt, label.encode("utf-8"), hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


class Anonymizer:
    def __init__(self, seed: int, salt: bytes, source_name: str) -> None:
        self.seed = seed
        self.coefficient = round(
            0.8 + 0.4 * _hmac_unit(salt, "money:" + source_name), 6
        )
        self.time_scale = 0.75 + 0.2 * _hmac_unit(salt, "time-scale:" + source_name)
        self.time_offset = _hmac_unit(salt, "time-offset:" + source_name) * (
            DAY_SECONDS - DAY_SECONDS * self.time_scale
        )
        self._maps: dict = {}
        self.unknown_keys: dict = {}

    def _numbered(self, family: str, value, render):
        mapping = self._maps.setdefault(family, {})
        if value not in mapping:
            mapping[value] = render(len(mapping) + 1)
        return mapping[value]

    def _money(self, value):
        scaled = round(value * self.coefficient, 2)
        if isinstance(scaled, float) and scaled.is_integer():
            return int(scaled)
        return scaled

    def _synthetic_uuid(self, value: str) -> str:
        digest = list(
            hashlib.sha256("{}:{}".format(self.seed, value).encode("utf-8")).hexdigest()[:32]
        )
        digest[12] = "4"
        digest[16] = "89ab"[int(digest[16], 16) % 4]
        flat = "".join(digest)
        return "-".join(
            (flat[0:8], flat[8:12], flat[12:16], flat[16:20], flat[20:32])
        )

    def _sale_id(self, value: str) -> str:
        prefix = SALE_ID_PREFIX_RE.match(value).group(1)
        return self._numbered(
            "saleID", value, lambda n: "{}{:011d}".format(prefix, n)
        )

    def _datetime(self, value: str) -> str:
        if value == NULL_TIMESTAMP or DATE_ONLY_RE.match(value):
            return value
        match = DATETIME_RE.match(value)
        if match is None:
            raise SystemExit(
                "anonymize_fixture: unexpected datetime format: {!r}".format(value)
            )
        day, sep = match.group(1), match.group(2)
        seconds = (
            int(match.group(3)) * 3600 + int(match.group(4)) * 60 + int(match.group(5))
        )
        remapped = min(int(seconds * self.time_scale + self.time_offset), DAY_SECONDS)
        return "{}{}{:02d}:{:02d}:{:02d}".format(
            day, sep, remapped // 3600, remapped % 3600 // 60, remapped % 60
        )

    def transform_value(self, key: str, value):
        if key in MONEY_KEYS and isinstance(value, (int, float)) and not isinstance(value, bool):
            return self._money(value)
        if key in ("nmId", "nmID") and isinstance(value, int):
            return self._numbered("nmId", value, lambda n: NM_ID_BASE + n)
        if key == "subjectId" and isinstance(value, int):
            return self._numbered("subjectId", value, lambda n: SUBJECT_ID_BASE + n)
        if key == "incomeID" and isinstance(value, int):
            if value == 0:
                return 0
            return self._numbered("incomeID", value, lambda n: INCOME_ID_BASE + n)
        if key in TEXT_MAP_KEYS and isinstance(value, str):
            family = TEXT_MAP_KEYS[key]
            return self._numbered(family, value, lambda n: "{}-{}".format(family, n))
        if key in GEO_PLACEHOLDERS and isinstance(value, str):
            return GEO_PLACEHOLDERS[key]
        if (
            key in ("srid", "saleID", "gNumber", "sticker", "barcode")
            and isinstance(value, str)
            and not value
        ):
            return value
        if key == "srid" and isinstance(value, str) and value:
            return self._numbered("srid", value, lambda n: "9{:016d}.0.0".format(n))
        if key == "saleID" and isinstance(value, str) and value:
            return self._sale_id(value)
        if key == "gNumber" and isinstance(value, str) and value:
            return self._numbered("gNumber", value, lambda n: "{:020d}".format(n))
        if key == "sticker" and isinstance(value, str) and value:
            return self._numbered("sticker", value, lambda n: "{:011d}".format(n))
        if key == "barcode" and isinstance(value, str) and value:
            return self._numbered("barcode", value, lambda n: "20{:011d}".format(n))
        if key in DATETIME_KEYS and isinstance(value, str):
            return self._datetime(value)
        if key in UUID_KEYS and isinstance(value, str) and UUID_RE.match(value):
            return self._synthetic_uuid(value)
        if isinstance(value, (dict, list)):
            if key in STRUCTURAL_KEYS:
                return self.transform(value)
            self.unknown_keys.setdefault(key, "container")
            return value
        if key in PASSTHROUGH_KEYS:
            return value
        self.unknown_keys.setdefault(key, type(value).__name__)
        return value

    def transform(self, node):
        if isinstance(node, dict):
            return {key: self.transform_value(key, value) for key, value in node.items()}
        if isinstance(node, list):
            return [self.transform(item) for item in node]
        return node


def record_day(record) -> "date | None":
    if not isinstance(record, dict):
        return None
    raw = record.get("date")
    if not isinstance(raw, str) or len(raw) < 10:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def collect_days(node, days: set) -> None:
    if isinstance(node, dict):
        day = record_day(node)
        if day is not None:
            days.add(day)
        for value in node.values():
            collect_days(value, days)
    elif isinstance(node, list):
        for item in node:
            collect_days(item, days)


def limit_days(doc, keep_days: int):
    days: set = set()
    collect_days(doc, days)
    if not days:
        return doc
    cutoff = max(days) - timedelta(days=keep_days - 1)

    def keep(record) -> bool:
        day = record_day(record)
        return day is None or day >= cutoff

    def prune(node):
        if isinstance(node, dict):
            return {key: prune(value) for key, value in node.items()}
        if isinstance(node, list):
            return [prune(item) for item in node if keep(item)]
        return node

    return prune(doc)


def serialize(doc) -> bytes:
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def select_rows(rows, ratio: float):
    groups: dict = {}
    order: list = []
    for index, row in enumerate(rows):
        day = record_day(row)
        if day not in groups:
            groups[day] = []
            order.append(day)
        groups[day].append(index)
    kept: list = []
    for day in order:
        indexes = groups[day]
        target = max(1, int(len(indexes) * ratio))
        if target >= len(indexes):
            kept.extend(indexes)
            continue
        step = (len(indexes) - 1) / (target - 1) if target > 1 else 0.0
        picked = sorted({indexes[round(position * step)] for position in range(target)})
        kept.extend(picked)
    kept.sort()
    return [rows[index] for index in kept]


def thin_to_size(doc, max_bytes: int):
    if len(serialize(doc)) <= max_bytes:
        return doc
    if isinstance(doc, list):
        rows, rebuild = doc, lambda selected: selected
    elif isinstance(doc, dict) and isinstance(doc.get("data"), list):
        rows = doc["data"]
        rebuild = lambda selected: {**doc, "data": selected}
    else:
        raise SystemExit(
            "anonymize_fixture: cannot thin non-array document below --max-bytes"
        )
    ratio = max_bytes / len(serialize(doc))
    for _ in range(64):
        candidate = rebuild(select_rows(rows, ratio))
        if len(serialize(candidate)) <= max_bytes:
            return candidate
        ratio *= 0.9
    raise SystemExit(
        "anonymize_fixture: could not fit document into --max-bytes "
        "(one row per day still too large)"
    )


def anonymize_document(doc, seed: int, salt: bytes, source_name: str, keep_days=None, max_bytes=None):
    if keep_days is not None:
        doc = limit_days(doc, keep_days)
    anonymizer = Anonymizer(seed, salt, source_name)
    doc = anonymizer.transform(doc)
    if anonymizer.unknown_keys:
        listing = ", ".join(
            "{} [{}]".format(key, kind)
            for key, kind in sorted(anonymizer.unknown_keys.items())
        )
        raise SystemExit(
            "anonymize_fixture: unknown keys (fail-closed, add each to a "
            "disposition set consciously): {}".format(listing)
        )
    if max_bytes is not None:
        doc = thin_to_size(doc, max_bytes)
    return doc


def read_salt(path: Path) -> bytes:
    try:
        salt = path.read_bytes().strip()
    except OSError as error:
        raise SystemExit("anonymize_fixture: cannot read --salt-file: {}".format(error))
    if len(salt) < 16:
        raise SystemExit(
            "anonymize_fixture: --salt-file must hold at least 16 bytes of secret"
        )
    return salt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--salt-file",
        type=Path,
        required=True,
        help="file with a secret salt (outside git); drives money and time remapping",
    )
    parser.add_argument("--limit-days", type=int, default=None)
    parser.add_argument("--max-bytes", type=int, default=None)
    args = parser.parse_args(argv)

    salt = read_salt(args.salt_file)
    doc = json.loads(args.input.read_text(encoding="utf-8"))
    doc = anonymize_document(
        doc,
        seed=args.seed,
        salt=salt,
        source_name=args.input.name,
        keep_days=args.limit_days,
        max_bytes=args.max_bytes,
    )
    payload = serialize(doc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(
        "anonymize_fixture: wrote {} ({} bytes, seed {})".format(
            args.output, len(payload), args.seed
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
