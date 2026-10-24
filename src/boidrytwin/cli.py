"""Command-line interface (contracts/cli.md).

Exit codes: 0 success, 1 input rejected, 2 run completed but checks failed, 3 internal or
solver failure. Logs go to stderr; command results go to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from boidrytwin.errors import ScenarioValidationError
from boidrytwin.logging import configure_logging
from boidrytwin.scenario.loader import load_scenario

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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _use_utf8_streams()
    args = _parser().parse_args(argv)
    configure_logging(level=args.log_level, fmt=args.log_format)
    if args.command == "validate":
        return _validate(args.scenario, as_json=args.json)
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
