from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validator(name: str) -> Draft202012Validator:
    schema = load(CONTRACTS / f"{name}.schema.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def must_reject(checker: Draft202012Validator, value: dict, label: str) -> None:
    try:
        checker.validate(value)
    except ValidationError:
        return
    raise ValueError(f"negative contract fixture unexpectedly passed: {label}")


def verify() -> None:
    names = ("source-artifact", "acquisition-attempt", "domain-release")
    values: dict[str, dict] = {}
    for name in names:
        value = load(CONTRACTS / "examples" / f"{name}.synthetic.json")
        validator(name).validate(value)
        values[name] = value

    artifact = copy.deepcopy(values["source-artifact"])
    del artifact["content_sha256"]
    must_reject(validator("source-artifact"), artifact, "artifact without checksum")

    attempt = copy.deepcopy(values["acquisition-attempt"])
    attempt["pagination"]["complete"] = False
    must_reject(validator("acquisition-attempt"), attempt, "successful incomplete pagination")

    release = copy.deepcopy(values["domain-release"])
    release["atomic"] = False
    must_reject(validator("domain-release"), release, "non-atomic published release")


if __name__ == "__main__":
    verify()
    print("contract verification passed")
