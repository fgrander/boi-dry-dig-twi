"""The single-page interface in a real browser, used like a person would (feature 005).

Not part of the usual run, as it needs a browser and takes some minutes:

    uv run --extra web --with playwright pytest -m ui

It runs ``scripts/make_ui_screenshots.py`` (new scenario, run, pin, step sequence, second run,
report, formulas, save as, comparison with measurements) against a real ``boidrytwin serve``
and checks what the script saw. It is skipped without Playwright, and fails with a clear
message without Microsoft Edge or Google Chrome.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("playwright")

ROOT = Path(__file__).parents[2]
pytestmark = pytest.mark.ui


@pytest.fixture(scope="module")
def flow(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, Path]:
    out = tmp_path_factory.mktemp("ui_pictures")
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_ui_screenshots.py"), "--out", str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1200,
        check=False,
    )
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]
    return done.stdout, out


def _number(text: str, label: str) -> int:
    match = re.search(rf"{re.escape(label)}\s*(\d+)", text)
    assert match, f"{label!r} not in the output:\n{text}"
    return int(match.group(1))


def test_the_page_reports_no_errors(flow: tuple[str, Path]) -> None:
    assert _number(flow[0], "problems:") == 0


def test_a_step_sequence_is_valid_and_both_runs_are_shown(flow: tuple[str, Path]) -> None:
    text = flow[0]
    assert "check: All inputs are valid." in text
    runs = re.search(r"runs: (\S+) (\S+)", text)
    assert runs and runs.group(1) != runs.group(2)
    assert _number(text, "key figures:") >= 10
    assert _number(text, "charts:") >= 10
    assert _number(text, "pinned table:") == 1


def test_the_report_lists_the_changed_inputs_and_fits_a_few_pages(flow: tuple[str, Path]) -> None:
    text = flow[0]
    assert _number(text, "changed inputs in the report:") == 2  # the end time and the feed moisture
    assert 1 <= _number(text, "report pages:") <= 6


def test_every_formula_is_typeset_and_the_search_filters(flow: tuple[str, Path]) -> None:
    text = flow[0]
    assert _number(text, "formulas:") >= 40
    assert _number(text, "not typeset:") == 0
    assert 1 <= _number(text, "formulas for 'saeman':") < 10


def test_save_as_and_the_comparison_with_measurements(flow: tuple[str, Path]) -> None:
    text = flow[0]
    assert "saved as: feed_step" in text
    assert _number(text, "compared outputs:") == 2


def test_a_picture_of_every_view_is_written(flow: tuple[str, Path]) -> None:
    for name in ("set", "results", "data", "formulas", "report"):
        picture = flow[1] / f"ui-{name}.png"
        assert picture.is_file() and picture.stat().st_size > 20_000, name
