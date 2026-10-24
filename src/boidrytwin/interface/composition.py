"""Flue gas composition (data-model.md §1 GasComposition)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from boidrytwin.errors import InterfaceValidationError, ValidationIssue
from boidrytwin.properties import gas
from boidrytwin.properties.gas import FloatArray

KEYS: tuple[str, ...] = ("x_N2", "x_O2", "x_CO2", "x_H2O", "x_other")  # order = gas.SPECIES
DRY_KEYS: tuple[str, ...] = ("x_N2", "x_O2", "x_CO2", "x_other")
SUM_TOLERANCE = 0.005
ALLOWED = "0 ≤ x ≤ 1, sum = 1 ± 0.005"

Basis = Literal["wet", "dry"]
FractionType = Literal["mole", "mass"]


class GasComposition(BaseModel):
    """Wet-basis mole fractions, normalised to sum exactly 1. ``x_other`` is treated as Ar."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x_N2: float = Field(ge=0.0, le=1.0)
    x_O2: float = Field(ge=0.0, le=1.0)
    x_CO2: float = Field(ge=0.0, le=1.0)
    x_H2O: float = Field(ge=0.0, le=1.0)
    x_other: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _sums_to_one(self) -> GasComposition:
        if abs(sum(self.as_tuple()) - 1.0) > 1e-9:
            raise ValueError("mole fractions must sum to 1; build via GasComposition.from_input")
        return self

    @classmethod
    def from_input(
        cls,
        fractions: Mapping[str, float],
        *,
        basis: Basis = "wet",
        fraction_type: FractionType = "mole",
        water_wet: float | None = None,
        field_prefix: str = "flue_gas.composition",
        location: str | None = None,
    ) -> GasComposition:
        """Validate user fractions (already unit-converted) and normalise them.

        ``basis="dry"`` expects N2, O2, CO2 and other on a dry basis plus ``water_wet``, the
        water mole (or mass) fraction of the wet gas.
        """
        issues: list[ValidationIssue] = []

        def issue(key: str, value: object, reason: str, allowed: str = ALLOWED) -> None:
            issues.append(
                ValidationIssue(
                    field=f"{field_prefix}.{key}",
                    value=str(value),
                    reason=reason,
                    allowed=allowed,
                    location=location,
                )
            )

        keys = DRY_KEYS if basis == "dry" else KEYS
        values: dict[str, float] = {}
        for key in keys:
            if key not in fractions:
                issue(key, "", "required")
                continue
            v = float(fractions[key])
            if not 0.0 <= v <= 1.0:
                issue(key, v, "out of range")
            values[key] = v

        if basis == "dry":
            if water_wet is None:
                issue(
                    "x_H2O", "", "water content required for dry basis", "water fraction of wet gas"
                )
            elif not 0.0 <= water_wet < 1.0:
                issue("x_H2O", water_wet, "out of range", "0 ≤ x < 1")

        if not issues:
            total = sum(values.values())
            if abs(total - 1.0) > SUM_TOLERANCE:
                issue("sum", f"{total:.4f}", f"composition sums to {total:.3f}, expected 1 ± 0.005")
        if issues:
            raise InterfaceValidationError(issues)

        arr = np.zeros(gas.N_SPECIES)
        for key, v in values.items():
            arr[KEYS.index(key)] = v
        arr /= arr.sum()
        if basis == "dry":
            assert water_wet is not None
            arr *= 1.0 - water_wet
            arr[gas.I_H2O] = water_wet
        if fraction_type == "mass":
            arr = gas.mole_fractions(arr)
        arr /= arr.sum()
        return cls.from_array(arr)

    @classmethod
    def from_array(cls, x: FloatArray) -> GasComposition:
        """Build from a wet mole-fraction array in species order (normalised here)."""
        arr = np.asarray(x, dtype=float)
        arr = arr / arr.sum()
        return cls(**dict(zip(KEYS, (float(v) for v in arr), strict=True)))

    def as_tuple(self) -> tuple[float, float, float, float, float]:
        return (self.x_N2, self.x_O2, self.x_CO2, self.x_H2O, self.x_other)

    def as_array(self) -> FloatArray:
        """Wet mole fractions in the order of :data:`boidrytwin.properties.gas.SPECIES`."""
        return np.array(self.as_tuple())

    def mass_fractions(self) -> FloatArray:
        return gas.mass_fractions(self.as_array())

    @property
    def molar_mass(self) -> float:
        return float(gas.molar_mass_mixture(self.as_array()))

    @property
    def dry_molar_mass(self) -> float:
        """Mean molar mass of the gas without its water vapour, kg/mol."""
        return dry_molar_mass(self.as_array())


def dry_molar_mass(x: FloatArray) -> float:
    """Mean molar mass of the dry part of a wet mole-fraction array, kg/mol."""
    dry = np.asarray(x, dtype=float).copy()
    dry[gas.I_H2O] = 0.0
    return float(np.sum(dry * gas.MOLAR_MASS) / dry.sum())
