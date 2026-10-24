"""Boiler house valid operating range (T018; research.md R9)."""

import numpy as np
import pandas as pd
import pytest

from boidrytwin.boiler_house.ranges import LIMITS, boiler_range_warnings, flags

T0 = pd.Timestamp("2026-01-01T00:00:00Z")
C = 273.15


def _frame(**cols: float) -> pd.DataFrame:
    base = {
        "fuel_moisture_wet_basis": 0.45,
        "excess_air_ratio": 1.5,
        "furnace_temperature": 950 + C,
        "load_fraction": 0.8,
        "oil_outlet_temperature": 282 + C,
        "max_film_temperature": 300 + C,
        "min_oil_velocity": 2.5,
        "min_oil_reynolds": 1e5,
    }
    base.update(cols)
    idx = pd.DatetimeIndex([T0 + pd.Timedelta(minutes=i) for i in range(3)])
    return pd.DataFrame({k: np.full(3, v) for k, v in base.items()}, index=idx)


def _quantities(frame: pd.DataFrame) -> set[str]:
    return {w.quantity for w in boiler_range_warnings(frame, max_bulk=573.15, max_film=593.15)}


def test_inside_range_no_warnings() -> None:
    assert _quantities(_frame()) == set()


@pytest.mark.parametrize(
    ("column", "value", "quantity"),
    [
        ("fuel_moisture_wet_basis", 0.58, "fuel_moisture_wet_basis"),
        ("fuel_moisture_wet_basis", 0.05, "fuel_moisture_wet_basis"),
        ("excess_air_ratio", 1.1, "excess_air_ratio"),
        ("furnace_temperature", 820 + C, "furnace_temperature"),
        ("furnace_temperature", 1200 + C, "furnace_temperature"),
        ("load_fraction", 0.25, "load_fraction"),
        ("oil_outlet_temperature", 305 + C, "oil_bulk_temperature"),
        ("max_film_temperature", 325 + C, "oil_film_temperature"),
        ("min_oil_velocity", 1.5, "oil_velocity"),
        ("min_oil_reynolds", 5e3, "oil_reynolds"),
    ],
)
def test_out_of_range(column: str, value: float, quantity: str) -> None:
    assert quantity in _quantities(_frame(**{column: value}))


def test_limits_table() -> None:
    assert LIMITS["fuel_moisture_wet_basis"] == (0.10, 0.55)
    assert LIMITS["excess_air_ratio"][0] == 1.2
    assert LIMITS["furnace_temperature"] == (850 + C, 1150 + C)
    assert LIMITS["load_fraction"][0] == 0.30


def test_flags() -> None:
    f = flags(_frame(load_fraction=0.4, furnace_temperature=830 + C, max_film_temperature=315 + C),
              max_bulk=573.15, max_film=593.15)  # fmt: skip
    assert f["load_out_of_range"].all()  # warning below 50 %
    assert f["combustion_out_of_range"].all()  # 800-850 °C warning band
    # film rise above 80 % of the margin is a pre-warning (282 + 0.8*38 = 312.4 °C)
    assert f["oil_limit"].all()
