"""CLI contract: ``boidrytwin compare`` (T074; contracts/cli.md)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from boidrytwin.cli import main
from tests.integration.conftest import EXAMPLES


def _run_id(out: str) -> str:
    return next(line.split()[-1] for line in out.splitlines() if line.startswith("run_id"))


@pytest.fixture(scope="module")
def synthetic_comparison(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[int, Path]:
    out = tmp_path_factory.mktemp("runs")
    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(
            [
                "compare",
                str(EXAMPLES / "reference_timeseries.toml"),
                str(EXAMPLES / "synthetic_measured.csv"),
                "--out",
                str(out),
            ]
        )
    return code, out / _run_id(buffer.getvalue())


def test_compare_outputs(synthetic_comparison: tuple[int, Path]) -> None:
    code, folder = synthetic_comparison
    assert code == 0
    report = json.loads((folder / "validation_report.json").read_text(encoding="utf-8"))
    assert report["run_id"] == folder.name
    assert report["passed"] is True
    table = pd.read_csv(folder / "comparison.csv", skiprows=[1])
    assert {"time", "output", "predicted", "measured", "deviation", "included"} <= set(
        table.columns
    )


def test_compare_reproduces_known_synthetic_deviations(
    synthetic_comparison: tuple[int, Path],
) -> None:
    _, folder = synthetic_comparison
    report = json.loads((folder / "validation_report.json").read_text(encoding="utf-8"))
    moisture = report["outputs"]["product_moisture_wet_basis"]
    exhaust = report["outputs"]["exhaust_temperature"]
    # examples/README.md: measured = model + offset + noise with offsets +0.004 and -2 K,
    # so the bias (predicted - measured) is -0.004 and +2 K
    assert moisture["bias"] == pytest.approx(-0.004, abs=0.0005)
    assert exhaust["bias"] == pytest.approx(2.0, abs=0.2)
    assert moisture["n_excluded"] > 0 and exhaust["n_excluded"] > 0
    excluded_reasons = {e["reason"] for e in report["excluded"]}
    assert {"missing", "bad"} <= excluded_reasons


def test_tighter_tolerances_fail_with_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tol = tmp_path / "tol.toml"
    tol.write_text('[tolerances]\nexhaust_temperature = "0.5 K"\n', encoding="utf-8")
    code = main(
        [
            "compare",
            str(EXAMPLES / "reference_timeseries.toml"),
            str(EXAMPLES / "synthetic_measured.csv"),
            "--out",
            str(tmp_path / "runs"),
            "--tolerances",
            str(tol),
        ]
    )
    out = capsys.readouterr().out
    assert code == 2
    assert "exhaust_temperature" in out and "FAILED" in out
