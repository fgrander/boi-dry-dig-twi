"""Time series CSV reader (T021)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from boidrytwin.errors import ScenarioValidationError
from boidrytwin.scenario.timeseries import read_timeseries_csv

COLUMNS = {"mass_flow": "mass_flow", "temperature": "temperature"}


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "series.csv"
    path.write_text(text, encoding="utf-8")
    return path


def _issues(err: pytest.ExceptionInfo[ScenarioValidationError]) -> list[str]:
    return [f"{i.reason} @ {i.location}" for i in err.value.issues]


def test_units_converted_to_si(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "time,mass_flow,temperature\nunit,t/h,degC\n"
        "2026-01-01T00:00:00Z,36,650\n2026-01-01T00:01:00Z,72,600\n",
    )
    ts = read_timeseries_csv(path, COLUMNS)
    assert ts.frame["mass_flow"].tolist() == pytest.approx([10.0, 20.0])
    assert ts.frame["temperature"].tolist() == pytest.approx([923.15, 873.15])
    assert str(ts.frame.index.tz) == "UTC"
    assert ts.frame["quality"].tolist() == ["good", "good"]
    assert len(ts.sha256) == 64


def test_offset_timestamps_converted_to_utc(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "time,mass_flow,temperature\nunit,kg/s,K\n2026-01-01T01:00:00+01:00,1,300\n"
    )
    ts = read_timeseries_csv(path, COLUMNS)
    assert ts.frame.index[0] == pd.Timestamp("2026-01-01T00:00:00Z")


def test_missing_unit(tmp_path: Path) -> None:
    path = _write(tmp_path, "time,mass_flow,temperature\nunit,,K\n2026-01-01T00:00:00Z,1,300\n")
    with pytest.raises(ScenarioValidationError) as err:
        read_timeseries_csv(path, COLUMNS)
    assert "unit missing @ series.csv:line 2" in _issues(err)


def test_missing_column(tmp_path: Path) -> None:
    path = _write(tmp_path, "time,mass_flow\nunit,kg/s\n2026-01-01T00:00:00Z,1\n")
    with pytest.raises(ScenarioValidationError) as err:
        read_timeseries_csv(path, COLUMNS)
    assert any(i.field.endswith("temperature") and i.reason == "required" for i in err.value.issues)


def test_timezone_required(tmp_path: Path) -> None:
    path = _write(tmp_path, "time,mass_flow,temperature\nunit,kg/s,K\n2026-01-01T00:00:00,1,300\n")
    with pytest.raises(ScenarioValidationError) as err:
        read_timeseries_csv(path, COLUMNS)
    assert "timezone required @ series.csv:line 3" in _issues(err)


@pytest.mark.parametrize("second", ["2026-01-01T00:00:00Z", "2025-12-31T23:59:00Z"])
def test_not_strictly_increasing(tmp_path: Path, second: str) -> None:
    path = _write(
        tmp_path,
        f"time,mass_flow,temperature\nunit,kg/s,K\n2026-01-01T00:00:00Z,1,300\n{second},1,300\n",
    )
    with pytest.raises(ScenarioValidationError) as err:
        read_timeseries_csv(path, COLUMNS)
    issue = err.value.issues[0]
    assert "not strictly increasing" in issue.reason
    assert second.replace("Z", "") in issue.reason
    assert issue.location == "series.csv:line 4"


def test_quality_column_and_empty_cells(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "time,mass_flow,temperature,quality\nunit,kg/s,K,\n"
        "2026-01-01T00:00:00Z,1,300,good\n"
        "2026-01-01T00:01:00Z,1,,good\n"
        "2026-01-01T00:02:00Z,1,300,bad\n",
    )
    ts = read_timeseries_csv(path, COLUMNS)
    assert ts.frame["quality"].tolist() == ["good", "missing", "bad"]
    assert np.isnan(ts.frame["temperature"].iloc[1])


def test_invalid_quality_value(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "time,mass_flow,temperature,quality\nunit,kg/s,K,\n2026-01-01T00:00:00Z,1,300,ok\n",
    )
    with pytest.raises(ScenarioValidationError) as err:
        read_timeseries_csv(path, COLUMNS)
    assert err.value.issues[0].field.endswith("quality")


def test_non_numeric_value(tmp_path: Path) -> None:
    path = _write(tmp_path, "time,mass_flow,temperature\nunit,kg/s,K\n2026-01-01T00:00:00Z,x,300\n")
    with pytest.raises(ScenarioValidationError) as err:
        read_timeseries_csv(path, COLUMNS)
    assert "not a number @ series.csv:line 3" in _issues(err)


def test_stale_values_are_flagged(tmp_path: Path) -> None:
    rows = "".join(f"2026-01-01T00:{m:02d}:00Z,1,{300 + m if m < 2 else 302}\n" for m in range(21))
    path = _write(tmp_path, "time,mass_flow,temperature\nunit,kg/s,K\n" + rows)
    ts = read_timeseries_csv(path, COLUMNS, stale_columns={"temperature"}, stale_after=900.0)
    quality = ts.frame["quality"].tolist()
    # temperature constant from minute 2: stale once unchanged for more than 15 minutes
    assert quality[:18] == ["good"] * 18
    assert quality[18:] == ["stale"] * 3


def test_stale_detection_off_for_unlisted_columns(tmp_path: Path) -> None:
    rows = "".join(f"2026-01-01T00:{m:02d}:00Z,1,{300 + m}\n" for m in range(21))
    path = _write(tmp_path, "time,mass_flow,temperature\nunit,kg/s,K\n" + rows)
    ts = read_timeseries_csv(path, COLUMNS, stale_columns={"temperature"}, stale_after=900.0)
    assert set(ts.frame["quality"]) == {"good"}  # mass_flow constant but not checked
