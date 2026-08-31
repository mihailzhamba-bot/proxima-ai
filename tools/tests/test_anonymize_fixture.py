from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_tool():
    path = ROOT / "tools" / "anonymize_fixture.py"
    spec = importlib.util.spec_from_file_location("anonymize_fixture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["anonymize_fixture"] = module
    spec.loader.exec_module(module)
    return module


tool = load_tool()


def sales_rows() -> list:
    rows = []
    for index in range(6):
        day = index // 2 + 1
        rows.append(
            {
                "date": "2026-08-{:02d}T10:0{}:00".format(20 + day, index),
                "lastChangeDate": "2026-08-{:02d}T12:00:00".format(20 + day),
                "warehouseName": "Тула",
                "countryName": "Россия",
                "oblastOkrugName": "Центральный федеральный округ",
                "regionName": "Московская область",
                "supplierArticle": "real/артикул-{}".format(index % 3),
                "nmId": 45816963 + index % 3,
                "barcode": "201197665402{}".format(index),
                "subject": "Кольца",
                "brand": "Meizel",
                "totalPrice": 6815,
                "priceWithDisc": 1295.5,
                "finishedPrice": 854,
                "forPay": 176.62,
                "saleID": ("S" if index % 2 == 0 else "R") + "2192856226{}".format(index),
                "sticker": "4863956612{}".format(index),
                "gNumber": "9770263086957765485{}".format(index),
                "srid": "2163980212113608{}.0.0".format(index),
                "isRealization": True,
            }
        )
    return rows


def funnel_doc() -> list:
    return [
        {
            "product": {
                "nmId": 686893199,
                "title": "Кольцо черное",
                "vendorCode": "кольцо_свет/черное",
                "brandName": "Meizelme",
                "subjectId": 24,
                "subjectName": "Кольца",
            },
            "history": [
                {"date": "2026-08-24", "openCount": 271, "orderSum": 2884, "buyoutSum": 1442},
                {"date": "2026-08-25", "openCount": 226, "orderSum": 1441, "buyoutSum": 0},
            ],
        }
    ]


def run(doc, seed=42, keep_days=None, max_bytes=None):
    return tool.anonymize_document(
        json.loads(json.dumps(doc)), seed=seed, keep_days=keep_days, max_bytes=max_bytes
    )


def test_structure_preserved() -> None:
    rows = sales_rows()
    result = run(rows)
    assert len(result) == len(rows)
    for source, transformed in zip(rows, result):
        assert list(transformed.keys()) == list(source.keys())
        assert transformed["date"] == source["date"]
        assert transformed["lastChangeDate"] == source["lastChangeDate"]
        assert transformed["isRealization"] is True


def test_identifiers_anonymized_and_unique() -> None:
    rows = sales_rows()
    result = run(rows)
    assert {row["nmId"] for row in result} == {12345001, 12345002, 12345003}
    assert all(row["supplierArticle"].startswith("sku-") for row in result)
    assert all(row["brand"] == "brand-1" for row in result)
    assert all(row["subject"] == "subject-1" for row in result)
    assert all(row["regionName"] == "region-1" for row in result)
    assert all(row["warehouseName"] == "warehouse-1" for row in result)
    for key in ("srid", "saleID", "gNumber", "sticker", "barcode"):
        values = [row[key] for row in result]
        assert len(set(values)) == len(values), key
        assert not (set(values) & {row[key] for row in rows}), key
    for source, transformed in zip(rows, result):
        assert transformed["saleID"][0] == source["saleID"][0]
        assert transformed["saleID"][0] in ("S", "R")


def test_money_scaled_by_single_seeded_coefficient() -> None:
    rows = sales_rows()
    result = run(rows)
    coefficient = result[0]["totalPrice"] / rows[0]["totalPrice"]
    assert 0.8 <= coefficient <= 1.2
    for source, transformed in zip(rows, result):
        for key in ("totalPrice", "priceWithDisc", "finishedPrice", "forPay"):
            expected = round(source[key] * coefficient, 2)
            assert abs(transformed[key] - expected) < 0.02, key


def test_deterministic_by_seed() -> None:
    rows = sales_rows()
    first = json.dumps(run(rows, seed=42), sort_keys=True)
    second = json.dumps(run(rows, seed=42), sort_keys=True)
    other = json.dumps(run(rows, seed=7), sort_keys=True)
    assert first == second
    assert first != other


def test_days_preserved_without_limit() -> None:
    rows = sales_rows()
    result = run(rows)
    assert {row["date"][:10] for row in result} == {row["date"][:10] for row in rows}


def test_limit_days_keeps_last_n_days() -> None:
    rows = sales_rows()
    result = run(rows, keep_days=2)
    assert {row["date"][:10] for row in result} == {"2026-08-22", "2026-08-23"}


def test_max_bytes_thins_but_keeps_every_day() -> None:
    rows = sales_rows() * 40
    full = len(tool.serialize(run(rows)))
    budget = full // 3
    result = run(rows, max_bytes=budget)
    assert len(tool.serialize(result)) <= budget
    assert len(result) < len(rows)
    assert {row["date"][:10] for row in result} == {row["date"][:10] for row in rows}


def test_funnel_structure_and_history_days() -> None:
    doc = funnel_doc()
    result = run(doc)
    product = result[0]["product"]
    assert product["nmId"] == 12345001
    assert product["title"] == "title-1"
    assert product["vendorCode"] == "sku-1"
    assert product["brandName"] == "brand-1"
    assert product["subjectName"] == "subject-1"
    assert product["subjectId"] == 24
    history = result[0]["history"]
    assert [entry["date"] for entry in history] == ["2026-08-24", "2026-08-25"]
    assert history[0]["openCount"] == 271
    assert history[1]["buyoutSum"] == 0


def test_uuid_strings_replaced_deterministically() -> None:
    doc = {"data": [{"id": "b4b7f68b-ffe8-4637-affb-4bbbe269a481", "status": "SUCCESS"}]}
    first = run(doc)
    second = run(doc)
    replaced = first["data"][0]["id"]
    assert replaced != "b4b7f68b-ffe8-4637-affb-4bbbe269a481"
    assert tool.UUID_RE.match(replaced)
    assert first == second
