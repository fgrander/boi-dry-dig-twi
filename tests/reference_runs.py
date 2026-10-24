"""Shortened runs of the example scenarios and what they produce (feature 004 guard, T002).

``scripts/store_reference_results.py`` stores them before the recirculation changes;
``tests/integration/test_recirculation_off.py`` checks that runs without a recirculation
still give exactly these files (FR-005, SC-001).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from boidrytwin import load_scenario, run
from boidrytwin.errors import ScenarioValidationError
from boidrytwin.scenario.loader import require_runnable

ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"
STORE = ROOT / "tests" / "data" / "reference_results"
HOURS = 4.0


def shortened(example: Path, tmp: Path) -> Path:
    """The example ending ``HOURS`` after its start, with absolute data file paths."""
    text = example.read_text(encoding="utf-8")
    start = re.search(r'start = "([^"]+)"', text)
    assert start is not None
    t0 = datetime.fromisoformat(start.group(1).replace("Z", "+00:00"))
    end = (t0 + timedelta(hours=HOURS)).isoformat().replace("+00:00", "Z")
    text = re.sub(r'end = "[^"]+"', f'end = "{end}"', text, count=1)

    def absolute(match: re.Match[str]) -> str:
        return f'file = "{(example.parent / match.group(1)).resolve().as_posix()}"'

    text = re.sub(r'file = "([^"]+)"', absolute, text)
    path = tmp / example.name
    path.write_text(text, encoding="utf-8")
    return path


def runnable_examples() -> list[Path]:
    out = []
    for path in sorted(EXAMPLES.glob("*.toml")):
        try:
            require_runnable(load_scenario(path))
        except ScenarioValidationError:
            continue
        out.append(path)
    return out


def produce(example: Path, tmp: Path) -> dict[str, Any]:
    """Run the shortened example; returns its CSV files (text) and record summary."""
    record = run(load_scenario(shortened(example, tmp)), out_dir=tmp / "runs")
    folder = tmp / "runs" / record.run_id
    csvs = {p.name: p.read_text(encoding="utf-8") for p in sorted(folder.glob("*.csv"))}
    summary = {
        "balance_report": record.balance_report,
        "plant_balance_report": record.plant_balance_report,
        "flags_summary": record.flags_summary,
        "range_warnings": record.range_warnings,
    }
    return {"csv": csvs, "summary": json.loads(json.dumps(summary, default=str))}
