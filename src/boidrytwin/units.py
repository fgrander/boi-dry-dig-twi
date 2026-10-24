"""Unit parsing at the system boundary; everything inside is SI.

Physical values are given as ``"<number> <unit>"`` strings (e.g. ``"450 degC"``,
``"12.5 t/h"``) and converted here to plain SI floats. Values without a unit are rejected
for every physical dimension; only fractions and dimensionless counts accept bare numbers.
pint is used only here, never inside the model core (research.md R7).
"""

from __future__ import annotations

import math
from typing import Any

import pint

_UREG = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)

# target SI unit per dimension name used in schemas
SI_UNITS: dict[str, str] = {
    "temperature": "K",
    "temperature_difference": "K",
    "pressure": "Pa",
    "mass_flow": "kg/s",
    "mass": "kg",
    "length": "m",
    "area": "m^2",
    "volume": "m^3",
    "time": "s",
    "angle": "rad",
    "angular_velocity": "rad/s",
    "velocity": "m/s",
    "density": "kg/m^3",
    "power": "W",
    "thermal_conductance": "W/K",
    "mass_flow_per_temperature": "kg/(s*K)",
    "per_temperature": "1/K",
    "specific_energy": "J/kg",
    "specific_heat": "J/(kg*K)",
    "thermal_conductivity": "W/(m*K)",
    "heat_transfer_coefficient": "W/(m^2*K)",
    "fraction": "dimensionless",
    "dimensionless": "dimensionless",
}

# dimensions where a bare number is acceptable
_UNITLESS_OK = frozenset({"fraction", "dimensionless"})


class QuantityError(ValueError):
    """A value could not be converted to the requested dimension."""

    def __init__(self, reason: str, value: object, dimension: str) -> None:
        self.reason = reason
        self.value = value
        self.dimension = dimension
        super().__init__(f"{reason}: {value!r} (expected {dimension}, e.g. {SI_UNITS[dimension]})")

    @property
    def allowed(self) -> str:
        if self.dimension in _UNITLESS_OK:
            return "number or value with a dimensionless unit (e.g. %)"
        return f"value with a unit compatible with {SI_UNITS[self.dimension]}"


def parse_quantity(
    value: object,
    dimension: str,
    *,
    gauge_reference: float | None = None,
) -> float:
    """Convert ``value`` to an SI float of the given ``dimension``.

    ``gauge_reference`` (Pa) turns a gauge pressure into an absolute one.
    Raises :class:`QuantityError` with reason ``unit missing``, ``incompatible unit`` or
    ``cannot parse``. An unknown ``dimension`` raises ``KeyError`` (programming error).
    """
    target = SI_UNITS[dimension]

    if isinstance(value, bool):
        raise QuantityError("cannot parse", value, dimension)
    if isinstance(value, int | float):
        if dimension not in _UNITLESS_OK:
            raise QuantityError("unit missing", value, dimension)
        return _finite(float(value), value, dimension)
    if not isinstance(value, str):
        raise QuantityError("cannot parse", value, dimension)

    text = value.strip().replace("%", " percent")
    try:
        quantity = _UREG.Quantity(text)
    except (pint.UndefinedUnitError, pint.errors.DefinitionSyntaxError, ValueError, TypeError):
        raise QuantityError("cannot parse", value, dimension) from None
    except Exception:  # pint raises various tokenizer errors on malformed input
        raise QuantityError("cannot parse", value, dimension) from None

    if not isinstance(quantity, pint.Quantity):
        # a bare number parses to int/float
        if dimension not in _UNITLESS_OK:
            raise QuantityError("unit missing", value, dimension)
        return _finite(float(quantity), value, dimension)
    if quantity.unitless and dimension not in _UNITLESS_OK:
        raise QuantityError("unit missing", value, dimension)

    try:
        si = float(quantity.to(target).magnitude)
    except pint.DimensionalityError:
        raise QuantityError("incompatible unit", value, dimension) from None

    if gauge_reference is not None:
        si += gauge_reference
    return _finite(si, value, dimension)


def convert_array(values: list[float], unit: str, dimension: str) -> list[float]:
    """Convert numbers given in ``unit`` to SI with the same arithmetic as
    :func:`parse_quantity` (so a CSV value and the same value in TOML give identical floats).
    NaN stays NaN. Raises :class:`QuantityError` for a missing or incompatible unit."""
    parse_quantity(f"1 {unit}", dimension)  # validates the unit
    target = SI_UNITS[dimension]
    text_unit = unit.strip().replace("%", "percent")
    out: list[float] = []
    for v in values:
        if math.isnan(v):
            out.append(math.nan)
            continue
        quantity = _UREG.Quantity(v, text_unit)
        out.append(float(quantity.to(target).magnitude))
    return out


def _finite(number: float, value: object, dimension: str) -> float:
    if not math.isfinite(number):
        raise QuantityError("cannot parse", value, dimension)
    return number


def _pint_unit(unit: str) -> str:
    return {"°C": "degC", "%": "percent", "": "dimensionless"}.get(
        unit, unit.replace("%", "percent")
    )


def convert_values(values: Any, from_unit: str, to_unit: str) -> Any:
    """Convert an array of numbers between two units of the same dimension (display only;
    the twin itself always works in SI). Offsets (K ↔ °C) are handled."""
    import numpy as np

    arr = np.asarray(values, dtype=float)
    if from_unit == to_unit:
        return arr
    quantity = _UREG.Quantity(arr, _pint_unit(from_unit))
    return np.asarray(quantity.to(_pint_unit(to_unit)).magnitude, dtype=float)
