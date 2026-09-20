from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from urllib.parse import urljoin

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry
from referencing.jsonschema import DRAFT202012


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def registry() -> Registry:
    """Every schema resolvable by its own $id and by the URL a sibling-relative
    ref resolves to. A ref like "signal.schema.json" is resolved against the
    referrer's $id with its last segment dropped (base URI of ".../brief/v1"
    is ".../brief/"), so each schema is registered under that key for every
    possible referrer base."""
    schemas = [(path.name, load(path)) for path in sorted(CONTRACTS.glob("*.schema.json"))]
    bases = [schema["$id"] for _, schema in schemas]
    resources = []
    for file_name, schema in schemas:
        keys = [schema["$id"], *(urljoin(base, file_name) for base in bases)]
        for key in keys:
            resources.append((key, DRAFT202012.create_resource(schema)))
    return Registry().with_resources(resources)


REGISTRY = registry()


def validator(name: str) -> Draft202012Validator:
    schema = load(CONTRACTS / f"{name}.schema.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker(), registry=REGISTRY)


def must_reject(checker: Draft202012Validator, value: dict, label: str) -> None:
    try:
        checker.validate(value)
    except ValidationError:
        return
    raise ValueError(f"negative contract fixture unexpectedly passed: {label}")


def error_path(error: ValidationError) -> str:
    path = "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)
    return path or "$"


def validate_fixture(checker: Draft202012Validator, value: dict, label: str) -> None:
    try:
        checker.validate(value)
    except ValidationError as exc:
        raise ValueError(f"fixture invalid: {label}; path={error_path(exc)}; reason={exc.message}") from exc


def verify_diagnosis_refs(value: dict, label: str) -> None:
    expected = 1 + len(value["alternatives"]) + len(value["unknowns"])
    actual = len(value["source_refs"])
    if actual != expected:
        raise ValueError(
            f"diagnosis source_refs invariant failed: {label}; path=.source_refs; expected length {expected}, got {actual}"
        )


def verify() -> None:
    schemas = sorted(CONTRACTS.glob("*.schema.json"))
    if not schemas:
        raise ValueError("no contract schemas discovered")
    examples = CONTRACTS / "examples"
    values: dict[str, dict] = {}
    for schema_path in schemas:
        name = schema_path.name.removesuffix(".schema.json")
        checker = validator(name)
        positive_path = examples / f"{name}.synthetic.json"
        if not positive_path.is_file():
            raise ValueError(f"missing positive fixture: schema={name}; expected={positive_path.name}")
        value = load(positive_path)
        validate_fixture(checker, value, f"schema={name}; fixture={positive_path.name}")
        values[name] = value
        if name == "diagnosis":
            verify_diagnosis_refs(value, positive_path.name)

    artifact = copy.deepcopy(values["source-artifact"])
    del artifact["content_sha256"]
    must_reject(validator("source-artifact"), artifact, "artifact without checksum")
    artifact = copy.deepcopy(values["source-artifact"])
    del artifact["content_size"]
    must_reject(validator("source-artifact"), artifact, "artifact without content size")
    attempt = copy.deepcopy(values["acquisition-attempt"])
    attempt["pagination"]["complete"] = False
    must_reject(validator("acquisition-attempt"), attempt, "successful incomplete pagination")
    release = copy.deepcopy(values["domain-release"])
    release["atomic"] = False
    must_reject(validator("domain-release"), release, "non-atomic published release")
    for field, invalid in (
        ("attempt_ids", ["not an id with spaces"]),
        ("artifact_ids", ["%%%"]),
        ("previous_release_id", "***"),
    ):
        release = copy.deepcopy(values["domain-release"])
        release[field] = invalid
        must_reject(validator("domain-release"), release, f"invalid {field}")

    passport = copy.deepcopy(values["client-passport"])
    del passport["cogs_status"]
    must_reject(validator("client-passport"), passport, "passport without cogs_status")
    passport = copy.deepcopy(values["client-passport"])
    passport["sales_drop_threshold_pct"] = 0
    must_reject(validator("client-passport"), passport, "passport with zero sales drop threshold")
    passport = copy.deepcopy(values["client-passport"])
    passport["weekend_days"] = ["monday"]
    must_reject(validator("client-passport"), passport, "passport with invalid weekday")

    supply = copy.deepcopy(values["supply-plan"])
    supply["status"] = "принято"
    must_reject(validator("supply-plan"), supply, "supply with non-ascii status")
    supply = copy.deepcopy(values["supply-plan"])
    supply["quantity"] = 0
    must_reject(validator("supply-plan"), supply, "supply with zero quantity")
    supply = copy.deepcopy(values["supply-plan"])
    del supply["entered_by"]
    must_reject(validator("supply-plan"), supply, "supply without actor")

    negative_paths = sorted(examples.glob("*-bad-*.synthetic.json"))
    for fixture_path in negative_paths:
        name = fixture_path.name.split("-bad-", 1)[0]
        schema_path = CONTRACTS / f"{name}.schema.json"
        if not schema_path.is_file():
            raise ValueError(f"negative fixture has no matching schema: fixture={fixture_path.name}; schema={name}")
        value = load(fixture_path)
        try:
            validator(name).validate(value)
        except ValidationError as exc:
            print(f"negative rejected: fixture={fixture_path.name}; schema={name}; path={error_path(exc)}")
        else:
            try:
                if name == "diagnosis":
                    verify_diagnosis_refs(value, fixture_path.name)
            except ValueError as exc:
                print(f"negative rejected: fixture={fixture_path.name}; schema={name}; {exc}")
            else:
                raise ValueError(f"negative fixture unexpectedly passed: fixture={fixture_path.name}; schema={name}; path=$")


if __name__ == "__main__":
    try:
        verify()
    except SchemaError as exc:
        location = "/".join(str(part) for part in exc.absolute_path) or "$"
        print(f"contract verification failed: invalid schema; path={location}; reason={exc.message}", file=sys.stderr)
        raise SystemExit(1) from exc
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"contract verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("contract verification passed")
