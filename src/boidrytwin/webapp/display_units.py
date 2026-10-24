"""The one place where the web app converts SI values to display units (FR-003, research R7).

Result files carry SI units in their unit row. The views show engineering units: °C instead
of K, MW instead of W, % instead of fractions, kPa instead of Pa, and t/h for fuel and product
flows. Columns with an unknown unit are shown unchanged.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from boidrytwin.units import convert_values

BY_UNIT: dict[str, str] = {
    "K": "°C",
    "W": "MW",
    "kg/kg": "%",
    "mol/mol": "%",
    "Pa": "kPa",
    "J/kg": "MJ/kg",
}
# flows of solids are read in t/h in the plant
TONNES_PER_HOUR = frozenset(
    {
        "fuel_feed",
        "fuel_delivered",
        "fuel_burnout_dry",
        "controller_output_oil_temperature",
        "product_dry_mass_flow",
        "evaporation_rate",
    }
)
# fractions shown in % (most fractions without a unit are shown unchanged)
PERCENT = frozenset({"recirculation_damper_position", "recirculation_share"})
# small pressures read in Pa (the mixing chamber draft, feature 004)
PASCAL = frozenset(
    {
        "mixing_chamber_pressure",
        "mixing_chamber_pressure_setpoint",
        "mixing_chamber_pressure_measured",
    }
)
# columns whose "K" is a temperature difference (no offset)
DIFFERENCES = frozenset({"exhaust_dew_point_margin"})


def display_unit(column: str, unit: str) -> str:
    if unit == "kg/s" and column in TONNES_PER_HOUR:
        return "t/h"
    if unit == "K" and column in DIFFERENCES:
        return "K"
    if unit == "" and column in PERCENT:
        return "%"
    if unit == "Pa" and column in PASCAL:
        return "Pa"
    return BY_UNIT.get(unit, unit)


def to_display(column: str, unit: str, values: Any) -> np.ndarray:
    shown = display_unit(column, unit)
    return np.asarray(
        convert_values(values, unit, shown) if shown != unit else np.asarray(values, dtype=float)
    )


def to_si(column: str, unit: str, values: Any) -> np.ndarray:
    shown = display_unit(column, unit)
    return np.asarray(
        convert_values(values, shown, unit) if shown != unit else np.asarray(values, dtype=float)
    )
