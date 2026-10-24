"""Store shortened runs of every runnable example as the feature-004 guard baseline (T002).

Run on the branch start, before any model change:  uv run python scripts/store_reference_results.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from tests.reference_runs import STORE, produce, runnable_examples  # noqa: E402


def main() -> None:
    STORE.mkdir(parents=True, exist_ok=True)
    for example in runnable_examples():
        with tempfile.TemporaryDirectory() as tmp:
            out = produce(example, Path(tmp))
        folder = STORE / example.stem
        folder.mkdir(exist_ok=True)
        for name, text in out["csv"].items():
            (folder / name).write_text(text, encoding="utf-8", newline="")
        (folder / "summary.json").write_text(
            json.dumps(out["summary"], indent=1, sort_keys=True), encoding="utf-8"
        )
        sys.stdout.write(f"stored {example.stem}: {', '.join(out['csv'])}\n")


if __name__ == "__main__":
    main()
