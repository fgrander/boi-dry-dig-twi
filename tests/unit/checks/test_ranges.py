"""RangeWarning detection (T064; FR-012)."""

import math

import numpy as np
import pandas as pd
import pytest

from boidrytwin.checks.ranges import RangeWarning, detect_periods, range_warnings
from boidrytwin.dryer.config import DryerConfiguration

T0 = pd.Timestamp("2026-01-01T00:00:00Z")
CFG = DryerConfiguration(
    length=20.0,
    diameter=4.0,
    slope=math.radians(2),
    shell_mass=60_000.0,
    rotation_speed=4 * 2 * math.pi / 60,
)


def _index(n: int) -> pd.DatetimeIndex:
    return pd.DatetimeIndex([T0 + pd.Timedelta(minutes=m) for m in range(n)])


def test_contiguous_periods_are_merged() -> None:
    values = np.array([1, 5, 6, 1, 1, 7, 8, 9, 1], dtype=float)
    warnings = detect_periods(_index(9), values, limit=4.0, limit_type="max", quantity="q")
    assert len(warnings) == 2
    first, second = warnings
    assert isinstance(first, RangeWarning)
    assert (first.period_start, first.period_end) == (
        T0 + pd.Timedelta(minutes=1),
        T0 + pd.Timedelta(minutes=2),
    )
    assert first.observed_extreme == 6.0 and first.limit == 4.0 and first.limit_type == "max"
    assert second.observed_extreme == 9.0
    assert second.period_end == T0 + pd.Timedelta(minutes=7)


def test_min_limit() -> None:
    values = np.array([10, 3, 2, 10], dtype=float)
    (w,) = detect_periods(_index(4), values, limit=5.0, limit_type="min", quantity="margin")
    assert w.observed_extreme == 2.0 and w.limit_type == "min"


def test_nan_values_are_not_violations() -> None:
    values = np.array([np.nan, 1.0, np.nan], dtype=float)
    assert detect_periods(_index(3), values, limit=0.5, limit_type="max", quantity="q") != []
    assert (
        detect_periods(_index(3), np.full(3, np.nan), limit=0.5, limit_type="max", quantity="q")
        == []
    )


def _results(n: int, inlet: float, exhaust: float, dew: float, solids: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "drum_inlet_gas_temperature": np.full(n, inlet),
            "exhaust_temperature": np.full(n, exhaust),
            "exhaust_dew_point": np.full(n, dew),
            "_max_solids_temperature": np.full(n, solids),
        },
        index=_index(n),
    )


def test_drum_inlet_temperature_above_validated_range() -> None:
    res = _results(5, 900.0, 400.0, 330.0, 350.0)
    res.iloc[0, 0] = 800.0
    (w,) = range_warnings(res, CFG, [])
    assert w.quantity == "drum_inlet_gas_temperature"
    assert w.limit == CFG.max_drum_inlet_gas_temperature
    assert w.period_start == T0 + pd.Timedelta(minutes=1)


def test_dew_point_margin_below_minimum() -> None:
    (w,) = range_warnings(_results(3, 800.0, 335.0, 330.0, 350.0), CFG, [])
    assert w.quantity == "exhaust_dew_point_margin"
    assert w.limit_type == "min" and w.limit == CFG.min_dew_point_margin
    assert w.observed_extreme == pytest.approx(5.0)


def test_emc_extrapolation() -> None:
    (w,) = range_warnings(_results(3, 800.0, 400.0, 330.0, 420.0), CFG, [])
    assert w.quantity == "solids_temperature"
    assert w.limit == CFG.emc_data_limit


def test_configuration_outside_validated_range_covers_the_whole_run() -> None:
    cfg = CFG.model_copy(update={"diameter": 8.0})
    res = _results(4, 800.0, 400.0, 330.0, 350.0)
    (w,) = range_warnings(res, cfg, cfg.validated_range_violations())
    assert w.quantity == "dryer.diameter"
    assert w.observed_extreme == 8.0 and w.limit_type == "max"
    assert (w.period_start, w.period_end) == (res.index[0], res.index[-1])


def test_inside_all_ranges_gives_no_warnings() -> None:
    assert range_warnings(_results(3, 800.0, 400.0, 330.0, 350.0), CFG, []) == []
