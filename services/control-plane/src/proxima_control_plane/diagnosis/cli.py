"""CLI: python -m proxima_control_plane.diagnosis run --input signals.json --output diagnoses.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from proxima_control_plane.diagnosis.adapters.factory import create_client
from proxima_control_plane.diagnosis.config import DiagnosisConfig, load_config
from proxima_control_plane.diagnosis.models import BatchItem, BatchResult, parse_signal
from proxima_control_plane.diagnosis.service import run_batch

CONFIG_FILENAME = "diagnosis.toml"


def _discover_config() -> DiagnosisConfig:
    for directory in [Path.cwd(), *Path.cwd().parents]:
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return load_config(candidate)
    return DiagnosisConfig()


def _load_signals(path: Path) -> list[Any]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        data = data.get("signals")
    if not isinstance(data, list) or not data:
        raise ValueError('input must be a non-empty JSON array of signals or {"signals": [...]}')
    return data


def _placeholder_id(raw: Any, index: int) -> str:
    if isinstance(raw, dict):
        candidate = raw.get("signal_id")
        if isinstance(candidate, str) and candidate:
            return candidate
    return f"signal[{index}]"


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config) if args.config else _discover_config()
    except (OSError, ValueError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    try:
        raw_signals = _load_signals(Path(args.input))
    except (OSError, ValueError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2

    signals = []
    rejected: list[tuple[str, str]] = []
    for index, raw in enumerate(raw_signals):
        try:
            signals.append(parse_signal(raw))
        except ValueError as exc:
            rejected.append((_placeholder_id(raw, index), str(exc)))

    result = run_batch(signals, config)
    items = [
        *result.items,
        *[BatchItem(signal_id=signal_id, status="failed", error=reason) for signal_id, reason in rejected],
    ]
    artifact = BatchResult(generated_at=result.generated_at, items=items).batch_to_dict()

    output = Path(args.output)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as handle:
            json.dump(artifact, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except OSError as exc:
        print(f"output error: {exc}", file=sys.stderr)
        return 2
    return 0


def _load_dataset(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        data = {"cases": data}
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list) or not data["cases"]:
        raise ValueError("dataset must be a JSON object with a non-empty 'cases' array")
    return data


def _cmd_eval(args: argparse.Namespace) -> int:
    """Eval the dataset with the configured provider and print the pass-rate.

    eval always diagnoses (provider from config, mock by default): the llm_enabled
    rollback flag is a run-semantics, not an eval-semantics.
    """
    try:
        config = load_config(args.config) if args.config else _discover_config()
    except (OSError, ValueError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    try:
        dataset = _load_dataset(Path(args.dataset))
    except (OSError, ValueError) as exc:
        print(f"dataset error: {exc}", file=sys.stderr)
        return 2

    try:
        client = create_client(config)
    except ValueError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    signals = []
    invalid = 0
    for raw in dataset["cases"]:
        try:
            signals.append(parse_signal(raw["signal"]))
        except (AttributeError, KeyError, TypeError, ValueError):
            invalid += 1

    result = run_batch(signals, config, client=client)
    total = len(dataset["cases"])
    ok = sum(1 for item in result.items if item.status == "ok")
    rate = ok / total if total else 0.0

    print(f"eval dataset {dataset.get('dataset_version', 'unknown')}: {total} cases")
    print(f"pass-rate: {ok}/{total} = {rate:.1%}")
    for item in result.items:
        if item.status != "ok":
            print(f"failed: {item.signal_id}: {item.error}")
    if invalid:
        print(f"invalid cases: {invalid}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proxima_control_plane.diagnosis",
        description="LLM diagnosis of marketplace signals (mock provider by default).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="process a batch of signals into a diagnosis artifact")
    run.add_argument("--input", required=True, help="path to signals JSON file")
    run.add_argument("--output", required=True, help="path to diagnosis JSON artifact")
    run.add_argument("--config", default=None, help="path to diagnosis TOML config")
    run.set_defaults(handler=_cmd_run)
    evaluate = commands.add_parser(
        "eval",
        help="evaluate an eval dataset and print the pass-rate",
    )
    evaluate.add_argument("--dataset", required=True, help="path to eval dataset JSON (cases.json)")
    evaluate.add_argument("--config", default=None, help="path to diagnosis TOML config")
    evaluate.set_defaults(handler=_cmd_eval)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.handler(args)
