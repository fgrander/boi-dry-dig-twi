"""Solid biofuel composition, heating value and complete-combustion stoichiometry (R2).

Sources:
- Default compositions: Alakangas et al. (2016), *Properties of indigenous fuels in Finland*,
  VTT Technology 272, Tables 4.3 and 4.7 (dry-basis wt%; O by difference).
- HHV: Channiwala & Parikh (2002), Fuel 81, 1051-1063.
- LHV: ISO 18125 form. LHV_d = HHV_d - 0.2122 H - 0.0008 (O + N) MJ/kg (VERIFY coefficients
  against the ISO text); LHV_ar = LHV_d (1 - M/100) - 0.02443 M (verified).

Stoichiometry is per kg of dry fuel and conserves every element exactly. Product species
follow :data:`boidrytwin.properties.gas.SPECIES`; SO2 is carried in "other" (represented by
argon) with its *mass* preserved, so mass balances stay exact, and is accounted separately in
the sulphur balance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from boidrytwin.errors import ScenarioValidationError, ValidationIssue
from boidrytwin.properties import gas, wood
from boidrytwin.properties.gas import FloatArray

FuelKind = Literal["wood_chips", "bark", "custom"]

M_C, M_H2, M_O2, M_N2, M_S = 0.012011, 0.002016, 0.031998, 0.028014, 0.03206  # kg/mol
M_SO2 = M_S + M_O2
M_WATER = float(gas.MOLAR_MASS[gas.I_H2O])
DRY_AIR_X: FloatArray = np.array([0.7808, 0.2095, 0.0004, 0.0, 0.0093])  # gas.SPECIES order
M_DRY_AIR = float(gas.molar_mass_mixture(DRY_AIR_X))
SUM_TOLERANCE = 0.005
VAPORISATION_ISO = 0.02443e6  # J/kg per wt% moisture (ISO 18125)

DEFAULTS: dict[str, dict[str, float]] = {
    "wood_chips": {"C": 0.513, "H": 0.061, "N": 0.004, "S": 0.0002, "ash": 0.013},  # forest residue
    "bark": {"C": 0.499, "H": 0.059, "N": 0.004, "S": 0.0003, "ash": 0.025},  # spruce bark
}  # fmt: skip


class FuelComposition(BaseModel):
    """Dry-basis mass fractions of a solid fuel, plus an optional measured heating value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    C: float
    H: float
    N: float
    S: float
    ash: float
    O: float
    hhv_measured: float | None = None
    lhv_measured: float | None = None

    @classmethod
    def default(cls, kind: Literal["wood_chips", "bark"]) -> FuelComposition:
        return cls.from_input(kind=kind)

    @classmethod
    def from_input(
        cls,
        *,
        kind: FuelKind = "custom",
        C: float | None = None,
        H: float | None = None,
        N: float | None = None,
        S: float | None = None,
        ash: float | None = None,
        O: float | None = None,
        hhv_dry: float | None = None,
        lhv_dry: float | None = None,
        field_prefix: str = "boiler_house.fuel",
        location: str | None = None,
    ) -> FuelComposition:
        issues: list[ValidationIssue] = []

        def issue(fieldname: str, value: object, reason: str, allowed: str) -> None:
            issues.append(
                ValidationIssue(
                    field=f"{field_prefix}.{fieldname}",
                    value=str(value),
                    reason=reason,
                    allowed=allowed,
                    location=location,
                )
            )

        given = {"C": C, "H": H, "N": N, "S": S, "ash": ash}
        if kind != "custom":
            values = dict(DEFAULTS[kind])
            values.update({k: v for k, v in given.items() if v is not None})
        else:
            values = {}
            for key, v in given.items():
                if v is None:
                    issue(key, "", "required", "a dry-basis mass fraction")
                else:
                    values[key] = float(v)
        for key, v in values.items():
            if not 0.0 <= v <= 1.0:
                issue(key, v, "out of range", "0 ≤ x ≤ 1")
        if hhv_dry is not None and lhv_dry is not None:
            issue(
                "hhv_dry", hhv_dry, "at most one heating value may be given", "hhv_dry or lhv_dry"
            )
        if not issues:
            partial = sum(values.values())
            if O is not None:
                total = partial + O
                if abs(total - 1.0) > SUM_TOLERANCE:
                    issue("O", O, f"composition sum is {total:.4f}", "sum = 1 ± 0.005")
                o_value = float(O)
            else:
                o_value = 1.0 - partial
                if o_value < 0.0:
                    issue("O", f"{o_value:.4f}", "composition sum without O exceeds 1", "sum ≤ 1")
        if issues:
            raise ScenarioValidationError(issues)
        return cls(O=o_value, hhv_measured=hhv_dry, lhv_measured=lhv_dry, **values)

    def _percent(self) -> tuple[float, float, float, float, float, float]:
        return (
            100 * self.C,
            100 * self.H,
            100 * self.O,
            100 * self.N,
            100 * self.S,
            100 * self.ash,
        )

    def hhv_dry(self) -> float:
        """Higher heating value, J/kg dry fuel (measured, else Channiwala-Parikh)."""
        if self.hhv_measured is not None:
            return self.hhv_measured
        if self.lhv_measured is not None:
            _, h, o, n, _, _ = self._percent()
            return self.lhv_measured + (0.2122 * h + 0.0008 * (o + n)) * 1e6
        c, h, o, n, s, a = self._percent()
        mj = 0.3491 * c + 1.1783 * h + 0.1005 * s - 0.1034 * o - 0.0151 * n - 0.0211 * a
        return mj * 1e6

    def lhv_dry(self) -> float:
        """Lower heating value, J/kg dry fuel. VERIFY(ISO 18125 coefficients)."""
        if self.lhv_measured is not None:
            return self.lhv_measured
        _, h, o, n, _, _ = self._percent()
        return self.hhv_dry() - (0.2122 * h + 0.0008 * (o + n)) * 1e6

    def lhv_as_received(self, moisture_wet: float) -> float:
        """LHV of the as-received (moist) fuel, J/kg (ISO 18125)."""
        return self.lhv_dry() * (1.0 - moisture_wet) - VAPORISATION_ISO * 100.0 * moisture_wet


@dataclass(frozen=True)
class Stoichiometry:
    """Complete combustion of 1 kg dry fuel with its moisture and humid air."""

    o2_min: float  # mol O2 per kg dry fuel
    excess_air: float
    air_dry_moles: float  # mol
    air_dry_mass: float  # kg
    air_water_mass: float  # kg
    flue_moles: FloatArray  # mol, gas.SPECIES order ("other" = Ar + SO2 mass-equivalent)
    flue_mass: float  # kg
    sulphur_moles: float  # mol SO2 in "other"
    elements_in: FloatArray  # mol C, H, O, N, S
    elements_out: FloatArray

    def mole_fractions(self) -> FloatArray:
        return np.asarray(self.flue_moles / self.flue_moles.sum())

    @property
    def o2_dry(self) -> float:
        dry = self.flue_moles.sum() - self.flue_moles[gas.I_H2O]
        return float(self.flue_moles[gas.I_O2] / dry)

    def element_balance_residual(self) -> float:
        return float(
            np.max(
                np.abs(self.elements_out - self.elements_in) / np.maximum(self.elements_in, 1e-30)
            )
        )


def stoichiometry(
    fuel: FuelComposition, *, moisture_wet: float, air_humidity: float, excess_air: float
) -> Stoichiometry:
    """Flue gas from 1 kg dry fuel at excess air ratio ``excess_air`` (λ ≥ 1)."""
    n_c = fuel.C / M_C
    n_h2 = fuel.H / M_H2
    n_o2_fuel = fuel.O / M_O2
    n_n2_fuel = fuel.N / M_N2
    n_s = fuel.S / M_S
    o2_min = n_c + 0.5 * n_h2 + n_s - n_o2_fuel
    air_dry = excess_air * o2_min / DRY_AIR_X[gas.I_O2]
    air_dry_mass = air_dry * M_DRY_AIR
    air_water = air_dry_mass * air_humidity
    moisture = moisture_wet / (1.0 - moisture_wet)

    flue = air_dry * DRY_AIR_X
    flue[gas.I_CO2] += n_c
    flue[gas.I_H2O] += n_h2 + moisture / M_WATER + air_water / M_WATER
    flue[gas.I_N2] += n_n2_fuel
    flue[gas.I_O2] -= o2_min
    flue[gas.I_AR] += n_s * M_SO2 / gas.MOLAR_MASS[gas.I_AR]  # mass-preserving SO2 in "other"
    flue_mass = float(np.sum(flue * gas.MOLAR_MASS))

    air_o = 2 * air_dry * (DRY_AIR_X[gas.I_O2] + DRY_AIR_X[gas.I_CO2])
    water_in = moisture / M_WATER + air_water / M_WATER
    elements_in = np.array(
        [
            n_c + air_dry * DRY_AIR_X[gas.I_CO2],
            2 * n_h2 + 2 * water_in,
            2 * n_o2_fuel + air_o + water_in,
            2 * n_n2_fuel + 2 * air_dry * DRY_AIR_X[gas.I_N2],
            n_s,
        ]
    )
    elements_out = np.array(
        [
            flue[gas.I_CO2],
            2 * flue[gas.I_H2O],
            2 * flue[gas.I_CO2] + flue[gas.I_H2O] + 2 * flue[gas.I_O2] + 2 * n_s,
            2 * flue[gas.I_N2],
            n_s,
        ]
    )
    return Stoichiometry(
        o2_min=o2_min,
        excess_air=excess_air,
        air_dry_moles=air_dry,
        air_dry_mass=air_dry_mass,
        air_water_mass=air_water,
        flue_moles=flue,
        flue_mass=flue_mass,
        sulphur_moles=n_s,
        elements_in=elements_in,
        elements_out=elements_out,
    )


def excess_air_from_o2_dry(
    fuel: FuelComposition, o2_dry: float, *, moisture_wet: float, air_humidity: float
) -> float:
    """Excess air ratio λ giving the dry-basis O2 fraction ``o2_dry`` (exact, linear in λ)."""
    s1 = stoichiometry(fuel, moisture_wet=moisture_wet, air_humidity=air_humidity, excess_air=1.0)
    s2 = stoichiometry(fuel, moisture_wet=moisture_wet, air_humidity=air_humidity, excess_air=2.0)

    def dry(s: Stoichiometry) -> float:
        return float(s.flue_moles.sum() - s.flue_moles[gas.I_H2O])

    d1, d2 = dry(s1), dry(s2)
    slope = d2 - d1  # dry moles per unit λ
    base = d1 - slope  # dry moles at λ = 0 (extrapolated)
    o2min = s1.o2_min
    return float((o2_dry * base + o2min) / (o2min - o2_dry * slope))


def fuel_enthalpy_per_kg_dry(fuel: FuelComposition, T: float, moisture_wet: float) -> float:
    """Enthalpy of the moist fuel per kg dry fuel, J/kg, on the product-vapour basis.

    LHV_d (chemical, products with water as vapour at 298.15 K) plus the sensible and moisture
    enthalpy of moist wood from :mod:`boidrytwin.properties.wood` (liquid water reference
    consistent with :mod:`boidrytwin.properties.water`).
    """
    moisture = moisture_wet / (1.0 - moisture_wet)
    return fuel.lhv_dry() + float(wood.enthalpy_per_kg_dry(T, moisture))
