"""Boiler house valid operating range (research.md R9, FR-011).

Range warnings (periods) and per-sample flags from the boiler results. Limits are the
validated range; see research.md R9 for sources (Nussbaumer 2024, VTT 272, Shell TDS).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from boidrytwin.range_warnings import LimitType, RangeWarning, detect_periods

C = 273.15
INF = float("inf")

LIMITS: dict[str, tuple[float, float]] = {
    "fuel_moisture_wet_basis": (0.10, 0.55),
    "excess_air_ratio": (1.2, INF),
    "furnace_temperature": (850 + C, 1150 + C),
    "load_fraction": (0.30, 1.0),
    "oil_velocity": (2.0, INF),  # VERIFY practice value
    "oil_reynolds": (1e4, INF),
}
LOAD_WARNING = 0.5
FILM_PREWARNING = 0.8


def boiler_range_warnings(
    results: pd.DataFrame, *, max_bulk: float, max_film: float
) -> list[RangeWarning]:
    index = pd.DatetimeIndex(results.index)
    checks: list[tuple[str, str, float, LimitType]] = []  # (column, quantity, limit, type)
    for column, quantity in (
        ("fuel_moisture_wet_basis", "fuel_moisture_wet_basis"),
        ("excess_air_ratio", "excess_air_ratio"),
        ("furnace_temperature", "furnace_temperature"),
        ("load_fraction", "load_fraction"),
        ("min_oil_velocity", "oil_velocity"),
        ("min_oil_reynolds", "oil_reynolds"),
    ):
        lo, hi = LIMITS[quantity]
        checks.append((column, quantity, lo, "min"))
        if hi < INF:
            checks.append((column, quantity, hi, "max"))
    checks.append(("oil_outlet_temperature", "oil_bulk_temperature", max_bulk, "max"))
    checks.append(("max_film_temperature", "oil_film_temperature", max_film, "max"))
    out: list[RangeWarning] = []
    for column, quantity, limit, kind in checks:
        if column in results:
            out += detect_periods(
                index, results[column].to_numpy(), limit=limit, limit_type=kind, quantity=quantity
            )
    return out


def flags(results: pd.DataFrame, *, max_bulk: float, max_film: float) -> pd.DataFrame:
    def col(name: str) -> np.ndarray:
        return (
            results[name].to_numpy(dtype=float)
            if name in results
            else np.full(len(results), np.nan)
        )

    with np.errstate(invalid="ignore"):
        T_f = col("furnace_temperature")
        moisture = col("fuel_moisture_wet_basis")
        combustion = (
            (T_f < LIMITS["furnace_temperature"][0])
            | (T_f > LIMITS["furnace_temperature"][1])
            | (col("excess_air_ratio") < LIMITS["excess_air_ratio"][0])
            | (moisture < LIMITS["fuel_moisture_wet_basis"][0])
            | (moisture > LIMITS["fuel_moisture_wet_basis"][1])
        )
        load = col("load_fraction") < LOAD_WARNING
        bulk = col("oil_outlet_temperature")
        film = col("max_film_temperature")
        oil = (
            (bulk > max_bulk)
            | (film > max_film)
            | (film - bulk > FILM_PREWARNING * (max_film - bulk))
        )
    return pd.DataFrame(
        {"combustion_out_of_range": combustion, "load_out_of_range": load, "oil_limit": oil},
        index=results.index,
    )
