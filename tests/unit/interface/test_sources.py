"""Constant and time-series flue gas supplies (T020)."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from boidrytwin.errors import InterfaceValidationError, SupplyCoverageError
from boidrytwin.interface.composition import GasComposition
from boidrytwin.interface.flue_gas import FlueGasState
from boidrytwin.interface.sources import ConstantFlueGasSupply, TimeSeriesFlueGasSupply

T0 = datetime(2026, 1, 1, tzinfo=UTC)
X = {"x_N2": 0.705, "x_O2": 0.06, "x_CO2": 0.105, "x_H2O": 0.12, "x_other": 0.01}
COMP = GasComposition.from_input(X)


def _frame(
    minutes: list[float], temps: list[float], quality: list[str] | None = None
) -> pd.DataFrame:
    index = pd.DatetimeIndex([T0 + timedelta(minutes=m) for m in minutes])
    n = len(minutes)
    frame = pd.DataFrame(
        {
            "mass_flow": np.full(n, 8.0),
            "temperature": temps,
            "pressure": np.full(n, 101_000.0),
            **{k: np.full(n, v) for k, v in X.items()},
            "quality": quality or ["good"] * n,
        },
        index=index,
    )
    return frame


def test_constant_supply() -> None:
    state = FlueGasState(
        time=T0, mass_flow=8.0, temperature=923.15, pressure=101_000.0, composition=COMP
    )
    supply = ConstantFlueGasSupply(state, start=T0)
    assert supply.source_id == "constant"
    assert supply.covers(0.0, 1e9)
    later = supply.state_at(3600.0)
    assert later.time == T0 + timedelta(hours=1)
    assert later.temperature == 923.15
    cond = supply.conditions_at(3600.0)
    assert cond.temperature == 923.15 and cond.mass_flow == 8.0
    assert cond.x == pytest.approx(COMP.as_array())


def test_linear_interpolation_and_quality() -> None:
    supply = TimeSeriesFlueGasSupply(_frame([0, 1, 2], [900.0, 960.0, 930.0]), start=T0)
    assert supply.state_at(30.0).temperature == pytest.approx(930.0)
    assert supply.state_at(30.0).quality == "interpolated"
    assert supply.state_at(60.0).quality == "good"
    assert supply.state_at(90.0).temperature == pytest.approx(945.0)
    assert supply.conditions_at(90.0).temperature == pytest.approx(945.0)


def test_start_offset() -> None:
    supply = TimeSeriesFlueGasSupply(
        _frame([0, 10], [900.0, 1000.0]), start=T0 + timedelta(minutes=5), max_gap=900.0
    )
    assert supply.state_at(0.0).temperature == pytest.approx(950.0)


def test_gap_longer_than_max_gap_is_rejected() -> None:
    with pytest.raises(InterfaceValidationError) as err:
        TimeSeriesFlueGasSupply(_frame([0, 1, 10], [900.0] * 3), start=T0)
    issue = err.value.issues[0]
    assert "gap" in issue.reason
    assert "00:01:00" in issue.reason and "00:10:00" in issue.reason


def test_allowed_gap_is_flagged_missing() -> None:
    supply = TimeSeriesFlueGasSupply(_frame([0, 1, 10], [900.0] * 3), start=T0, allow_gaps=True)
    assert supply.state_at(300.0).quality == "missing"
    assert supply.state_at(30.0).quality == "interpolated"


def test_bad_rows_excluded_and_flagged() -> None:
    frame = _frame([0, 1, 2], [900.0, 5000.0, 920.0], quality=["good", "bad", "good"])
    supply = TimeSeriesFlueGasSupply(frame, start=T0)
    s = supply.state_at(60.0)
    assert s.temperature == pytest.approx(910.0)  # bad sample ignored
    assert s.quality == "bad"


def test_invalid_row_values_are_rejected_with_row() -> None:
    frame = _frame([0, 1], [900.0, 2000.0])
    with pytest.raises(InterfaceValidationError) as err:
        TimeSeriesFlueGasSupply(frame, start=T0, file_label="flue.csv")
    issue = err.value.issues[0]
    assert issue.field == "flue_gas.temperature"
    assert issue.reason == "out of range"
    assert issue.location == "flue.csv:line 4"


def test_coverage() -> None:
    supply = TimeSeriesFlueGasSupply(_frame([0, 1, 2], [900.0] * 3), start=T0)
    assert supply.covers(0.0, 120.0)
    assert not supply.covers(0.0, 121.0)
    assert not supply.covers(-1.0, 60.0)
    with pytest.raises(SupplyCoverageError, match="covered period"):
        supply.state_at(200.0)


def test_state_at_is_deterministic() -> None:
    supply = TimeSeriesFlueGasSupply(_frame([0, 1, 2], [900.0, 960.0, 930.0]), start=T0)
    assert supply.state_at(77.7) == supply.state_at(77.7)


def test_interpolated_composition_sums_to_one() -> None:
    frame = _frame([0, 1], [900.0, 900.0])
    frame.loc[frame.index[1], ["x_N2", "x_H2O"]] = [0.725, 0.10]
    supply = TimeSeriesFlueGasSupply(frame, start=T0)
    assert supply.conditions_at(30.0).x.sum() == pytest.approx(1.0, abs=1e-12)
