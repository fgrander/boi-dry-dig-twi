"""Command-line interface (contracts/cli.md).

Exit codes: 0 success, 1 input rejected, 2 run completed but checks failed, 3 internal or
solver failure. Logs go to stderr; command results go to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from boidrytwin.errors import ScenarioValidationError, SimulationError
from boidrytwin.logging import configure_logging
from boidrytwin.scenario.loader import load_scenario, require_runnable

EXIT_OK, EXIT_REJECTED, EXIT_CHECKS_FAILED, EXIT_FAILURE = 0, 1, 2, 3


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--log-level", default=None, help="DEBUG, INFO, WARNING, ERROR")
    common.add_argument("--log-format", choices=("json", "console"), default="json")

    parser = argparse.ArgumentParser(
        prog="boidrytwin", description="Boiler house and drum dryer digital twin"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", parents=[common], help="validate a scenario")
    validate.add_argument("scenario")
    validate.add_argument("--json", action="store_true", help="machine-readable output")

    run = sub.add_parser("run", parents=[common], help="run a simulation")
    run.add_argument("scenario")
    run.add_argument("--out", default="runs", help="folder for run folders (default: runs)")
    run.add_argument("--profiles", action="store_true", help="also write per-cell profiles")

    rerun = sub.add_parser("rerun", parents=[common], help="rerun a recorded run")
    rerun.add_argument("run_record")

    compare = sub.add_parser("compare", parents=[common], help="compare with measurements")
    compare.add_argument("scenario")
    compare.add_argument("measured")
    compare.add_argument("--out", default="runs", help="folder for run folders (default: runs)")
    compare.add_argument("--tolerances", default=None, help="TOML file with tolerances")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _use_utf8_streams()
    args = _parser().parse_args(argv)
    configure_logging(level=args.log_level, fmt=args.log_format)
    if args.command == "validate":
        return _validate(args.scenario, as_json=args.json)
    if args.command == "run":
        return _run(args.scenario, out=args.out, profiles=args.profiles)
    if args.command == "rerun":
        return _rerun(args.run_record)
    if args.command == "compare":
        return _compare(args.scenario, args.measured, out=args.out, tolerances=args.tolerances)
    return EXIT_FAILURE  # pragma: no cover - argparse enforces a command


def _validate(path: str, *, as_json: bool) -> int:
    try:
        loaded = load_scenario(path)
    except ScenarioValidationError as exc:
        _out(exc.to_json() if as_json else str(exc))
        return EXIT_REJECTED
    if as_json:
        _out(json.dumps({"valid": True, "issues": []}))
    else:
        _out("OK\n" + json.dumps(loaded.spec.model_dump(mode="json"), indent=2))
    return EXIT_OK


def _run(path: str, *, out: str, profiles: bool) -> int:
    from boidrytwin.records import checks_passed, run

    try:
        loaded = load_scenario(path)
        require_runnable(loaded)
    except ScenarioValidationError as exc:
        _out(str(exc))
        return EXIT_REJECTED
    try:
        record = run(loaded, out_dir=out, profiles=profiles)
    except SimulationError as exc:
        _out("status   failed")
        _out(f"message  {exc}")
        return EXIT_FAILURE
    _out(f"run_id   {record.run_id}")
    _out(f"status   {record.status}")
    _out(f"folder   {Path(out) / record.run_id}")
    flags = ", ".join(f"{k}={v}" for k, v in record.flags_summary.items())
    _out(f"flags    {flags}")
    _out(f"warnings {len(record.range_warnings)} range warning(s)")
    if not checks_passed(record):
        report = record.balance_report or {}
        quantities = ("dry_solids", "water", "gas", "energy")
        failed = [q for q in quantities if not report.get(q, {}).get("passed", False)]
        _out(f"balances FAILED: {', '.join(failed)}")
        return EXIT_CHECKS_FAILED
    _out("balances passed")
    return EXIT_OK


def _rerun(record_path: str) -> int:
    from boidrytwin.records import rerun

    try:
        record, identical = rerun(record_path)
    except ScenarioValidationError as exc:
        _out(str(exc))
        return EXIT_REJECTED
    except SimulationError as exc:
        _out(f"message  {exc}")
        return EXIT_FAILURE
    _out(f"run_id   {record.run_id}")
    _out(f"identical: {'true' if identical else 'false'}")
    return EXIT_OK if identical else EXIT_CHECKS_FAILED


def _compare(path: str, measured: str, *, out: str, tolerances: str | None) -> int:
    from boidrytwin.records import compare

    try:
        loaded = load_scenario(path)
        require_runnable(loaded)
        record, report = compare(loaded, measured, out_dir=out, tolerances=tolerances)
    except ScenarioValidationError as exc:
        _out(str(exc))
        return EXIT_REJECTED
    except SimulationError as exc:
        _out(f"message  {exc}")
        return EXIT_FAILURE
    _out(f"run_id   {record.run_id}")
    for name, o in report.outputs.items():
        verdict = {True: "passed", False: "FAILED", None: "no tolerance"}[o.passed]
        within = (
            "-" if o.fraction_within_tolerance is None else f"{o.fraction_within_tolerance:.1%}"
        )
        _out(
            f"{name}: {verdict}  bias {o.bias:.4g}  rmse {o.rmse:.4g}  "
            f"within tolerance {within} of {o.n_steady} steady samples, {o.n_excluded} excluded"
        )
    return EXIT_OK if report.passed else EXIT_CHECKS_FAILED


def _use_utf8_streams() -> None:
    """Messages contain ≥, ±, °C; a Windows console defaults to cp1252 and cannot encode them."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _out(text: str) -> None:
    sys.stdout.write(text + "\n")


def entry_point() -> None:  # pragma: no cover
    sys.exit(main())
