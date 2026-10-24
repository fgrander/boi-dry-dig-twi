"""Boiler house configuration with physical and validated ranges (data-model.md §2).

Defaults marked VERIFY are typical values from research.md that are still to be checked
against primary sources or calibrated on plant data (Open items).
"""

from __future__ import annotations

import math
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from boidrytwin.fields import FieldSpec, RangeViolation, physical_problems, validated_violations

STEEL_SPECIFIC_HEAT = 500.0  # J/(kg K)

FURNACE_FIELDS: dict[str, FieldSpec] = {
    "rated_fuel_power": FieldSpec("power", 15e6, (1e5, 1e9), (1e6, 1e8), "rated fuel power (as-received LHV basis)"),
    "min_load_fraction": FieldSpec("fraction", 0.3, (0.0, 1.0), (0.2, 0.6), "minimum load as fraction of rated power (VERIFY 30 %)"),
    "gas_holdup_volume": FieldSpec("volume", 50.0, (0.1, 1e4), (5.0, 500.0), "furnace gas volume"),
    "refractory_mass_hot_face": FieldSpec("mass", 22_000.0, (1.0, 1e7), (1e3, 1e6), "refractory hot-face mass"),
    "refractory_mass_bulk": FieldSpec("mass", 44_000.0, (1.0, 1e7), (1e3, 1e6), "refractory bulk mass"),
    "refractory_specific_heat": FieldSpec("specific_heat", 1000.0, (100.0, 3000.0), (800.0, 1200.0), "refractory specific heat"),
    "refractory_area": FieldSpec("area", 100.0, (1.0, 1e5), (10.0, 1e4), "refractory area exposed to the gas"),
    "refractory_gas_htc": FieldSpec("heat_transfer_coefficient", 30.0, (0.0, 1000.0), (5.0, 200.0), "gas to refractory coefficient (VERIFY)"),
    "refractory_conductance": FieldSpec("thermal_conductance", 800.0, (0.0, 1e6), (50.0, 1e5), "hot face to bulk conductance"),
    "loss_ua": FieldSpec("thermal_conductance", 260.0, (0.0, 1e6), (10.0, 1e5), "refractory bulk to ambient (≈ 1 % of rated power)"),
    "ash_discharge_temperature": FieldSpec("temperature", 773.15, (273.15, 1773.15), (473.15, 1273.15), "ash discharge temperature (VERIFY)"),
    "ash_specific_heat": FieldSpec("specific_heat", 800.0, (100.0, 3000.0), (600.0, 1200.0), "ash specific heat (VERIFY)"),
    "min_combustion_air": FieldSpec("mass_flow", 1.0, (0.0, 1000.0), (0.1, 100.0), "minimum combustion air of the fans (VERIFY)"),
    "outlet_pressure": FieldSpec("pressure", 101_000.0, (50_000.0, 200_000.0), (90_000.0, 110_000.0), "flue gas pressure at the outlet to the dryer"),
    "bed_time_constant": FieldSpec("time", 900.0, (1.0, 1e5), (300.0, 3600.0), "fuel bed burnout time constant (VERIFY)"),
    "water_time_constant": FieldSpec("time", 600.0, (1.0, 1e5), (120.0, 3600.0), "fuel bed drying time constant (VERIFY)"),
    "feed_dead_time": FieldSpec("time", 120.0, (0.1, 3600.0), (10.0, 600.0), "fuel feed transport delay (VERIFY)"),
    "o2_sensor_time_constant": FieldSpec("time", 30.0, (0.1, 3600.0), (5.0, 120.0), "O2 measurement lag (VERIFY)"),
}  # fmt: skip


class _Fields(BaseModel):
    """Base: validates FIELDS physical ranges and reports validated-range violations."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    FIELDS: ClassVar[dict[str, FieldSpec]] = {}

    @model_validator(mode="after")
    def _physical(self) -> _Fields:
        problems = physical_problems(self.model_dump(), self.FIELDS)
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def violations(self, prefix: str) -> list[RangeViolation]:
        return validated_violations(self.model_dump(), self.FIELDS, prefix)


class FurnaceConfig(_Fields):
    FIELDS: ClassVar[dict[str, FieldSpec]] = FURNACE_FIELDS

    rated_fuel_power: float = 15e6
    min_load_fraction: float = 0.3
    gas_holdup_volume: float = 50.0
    refractory_mass_hot_face: float = 22_000.0
    refractory_mass_bulk: float = 44_000.0
    refractory_specific_heat: float = 1000.0
    refractory_area: float = 100.0
    refractory_gas_htc: float = 30.0
    refractory_conductance: float = 800.0
    loss_ua: float = 260.0
    ash_discharge_temperature: float = 773.15
    ash_specific_heat: float = 800.0
    min_combustion_air: float = 1.0
    outlet_pressure: float = 101_000.0
    bed_time_constant: float = 900.0
    water_time_constant: float = 600.0
    feed_dead_time: float = 120.0
    o2_sensor_time_constant: float = 30.0


class RadiantHeater(_Fields):
    """Heater 1: tubes on the furnace walls, heated by radiation from the furnace gas."""

    FIELDS: ClassVar[dict[str, FieldSpec]] = {
        "tube_area": FieldSpec("area", 100.0, (0.1, 1e5), (10.0, 5000.0), "outer tube area"),
        "cold_plane_area": FieldSpec("area", 50.0, (0.1, 1e5), (5.0, 2500.0), "effective cold-plane area αA_cp"),
        "flame_emissivity": FieldSpec("fraction", 0.5, (0.0, 1.0), (0.2, 0.9), "effective flame emissivity (VERIFY, calibrate)"),
        "convective_htc": FieldSpec("heat_transfer_coefficient", 11.0, (0.0, 500.0), (2.0, 50.0), "gas to tube convection (VERIFY)"),
        "tube_mass": FieldSpec("mass", 5200.0, (1.0, 1e7), (100.0, 1e6), "steel tube mass"),
        "oil_volume": FieldSpec("volume", 2.2, (1e-3, 1e3), (0.1, 100.0), "oil volume in the tubes"),
        "tube_inner_diameter": FieldSpec("length", 0.1, (1e-3, 1.0), (0.02, 0.3), "tube inner diameter"),
        "tube_outer_diameter": FieldSpec("length", 0.1143, (1e-3, 1.0), (0.025, 0.35), "tube outer diameter"),
        "n_parallel_passes": FieldSpec("dimensionless", 4.0, (1.0, 1000.0), (1.0, 100.0), "parallel oil passes"),
        "peak_flux_factor": FieldSpec("dimensionless", 1.727, (1.0, 5.0), (1.2, 2.5), "F_C·F_L peak to average flux (Pelini 2008)"),
    }  # fmt: skip

    type: Literal["radiant"] = "radiant"
    tube_area: float = 100.0
    cold_plane_area: float = 50.0
    flame_emissivity: float = 0.5
    convective_htc: float = 11.0
    tube_mass: float = 5200.0
    oil_volume: float = 2.2
    tube_inner_diameter: float = 0.1
    tube_outer_diameter: float = 0.1143
    n_parallel_passes: int = 4
    peak_flux_factor: float = 1.727

    @property
    def inner_area(self) -> float:
        return self.tube_area * self.tube_inner_diameter / self.tube_outer_diameter

    @property
    def flow_area(self) -> float:
        return self.n_parallel_passes * math.pi * self.tube_inner_diameter**2 / 4.0


class ConvectiveHeater(_Fields):
    """Heaters 2 … n: bare-tube banks in crossflow, discretised into counter-current cells."""

    FIELDS: ClassVar[dict[str, FieldSpec]] = {
        "n_cells": FieldSpec("dimensionless", 5.0, (1.0, 50.0), (3.0, 20.0), "cells along the gas path"),
        "tube_outer_diameter": FieldSpec("length", 0.0603, (1e-3, 1.0), (0.02, 0.2), "tube outer diameter"),
        "tube_inner_diameter": FieldSpec("length", 0.05, (1e-3, 1.0), (0.015, 0.18), "tube inner diameter"),
        "transverse_pitch": FieldSpec("length", 0.12, (1e-3, 2.0), (0.03, 0.5), "transverse pitch S_t"),
        "longitudinal_pitch": FieldSpec("length", 0.10, (1e-3, 2.0), (0.03, 0.5), "longitudinal pitch S_l"),
        "n_rows": FieldSpec("dimensionless", 8.0, (1.0, 1000.0), (2.0, 100.0), "tube rows in gas direction"),
        "tubes_per_row": FieldSpec("dimensionless", 16.0, (1.0, 1000.0), (2.0, 200.0), "tubes per row"),
        "tube_length": FieldSpec("length", 4.0, (0.01, 100.0), (0.5, 20.0), "tube length"),
        "free_flow_area": FieldSpec("area", 3.82, (1e-3, 1000.0), (0.1, 100.0), "minimum free flow area"),
        "gas_emissivity": FieldSpec("fraction", 0.1, (0.0, 1.0), (0.0, 0.3), "gas emissivity in the pass (VERIFY)"),
        "fouling_resistance": FieldSpec("dimensionless", 0.008, (0.0, 1.0), (0.0, 0.03), "ash fouling, m² K/W (VERIFY, calibrate)"),
        "tube_mass": FieldSpec("mass", 3500.0, (1.0, 1e7), (100.0, 1e6), "steel tube mass"),
        "oil_volume": FieldSpec("volume", 1.0, (1e-3, 1e3), (0.05, 100.0), "oil volume in the tubes"),
        "n_parallel_passes": FieldSpec("dimensionless", 16.0, (1.0, 1000.0), (1.0, 200.0), "parallel oil passes"),
        "loss_ua": FieldSpec("thermal_conductance", 100.0, (0.0, 1e6), (0.0, 1e4), "casing loss"),
        "peak_flux_factor": FieldSpec("dimensionless", 1.0, (1.0, 5.0), (1.0, 2.0), "peak to average flux"),
    }  # fmt: skip

    type: Literal["convective"] = "convective"
    n_cells: int = 5
    tube_outer_diameter: float = 0.0603
    tube_inner_diameter: float = 0.05
    transverse_pitch: float = 0.12
    longitudinal_pitch: float = 0.10
    n_rows: int = 8
    tubes_per_row: int = 16
    tube_length: float = 4.0
    free_flow_area: float = 3.82
    gas_emissivity: float = 0.1
    fouling_resistance: float = 0.008
    tube_mass: float = 3500.0
    oil_volume: float = 1.0
    n_parallel_passes: int = 16
    loss_ua: float = 100.0
    peak_flux_factor: float = 1.0

    @property
    def total_tube_length(self) -> float:
        return self.tube_length * self.tubes_per_row * self.n_rows

    @property
    def outer_area(self) -> float:
        return math.pi * self.tube_outer_diameter * self.total_tube_length

    @property
    def inner_area(self) -> float:
        return math.pi * self.tube_inner_diameter * self.total_tube_length

    @property
    def flow_area(self) -> float:
        return self.n_parallel_passes * math.pi * self.tube_inner_diameter**2 / 4.0


class BypassConfig(_Fields):
    FIELDS: ClassVar[dict[str, FieldSpec]] = {
        "duct_loss_ua": FieldSpec(
            "thermal_conductance", 0.0, (0.0, 1e6), (0.0, 1e4), "bypass duct loss"
        ),
        "position": FieldSpec(
            "fraction", 0.0, (0.0, 1.0), (0.0, 1.0), "bypass position in boiler-only runs (manual)"
        ),
    }

    starts_after_heater: int = Field(default=1, ge=1)
    duct_loss_ua: float = 0.0
    position: float = 0.0


Heater = Annotated[RadiantHeater | ConvectiveHeater, Field(discriminator="type")]


class BoilerHouseConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    furnace: FurnaceConfig = FurnaceConfig()
    heaters: list[Heater]
    bypass: BypassConfig = BypassConfig()

    @model_validator(mode="after")
    def _arrangement(self) -> BoilerHouseConfiguration:
        if not self.heaters or not isinstance(self.heaters[0], RadiantHeater):
            raise ValueError("heater 1 must be radiant")
        if any(not isinstance(h, ConvectiveHeater) for h in self.heaters[1:]):
            raise ValueError("heaters 2 … n must be convective")
        if len(self.heaters) < 2:
            raise ValueError("at least one convective heater is required")
        if self.bypass.starts_after_heater >= len(self.heaters):
            raise ValueError("bypass starts_after_heater must be less than the number of heaters")
        return self

    @property
    def convective(self) -> list[ConvectiveHeater]:
        return [h for h in self.heaters if isinstance(h, ConvectiveHeater)]

    @property
    def radiant(self) -> RadiantHeater:
        heater = self.heaters[0]
        assert isinstance(heater, RadiantHeater)
        return heater

    def validated_range_violations(self) -> list[RangeViolation]:
        out = self.furnace.violations("furnace.")
        for i, h in enumerate(self.heaters):
            out += h.violations(f"heaters[{i}].")
        out += self.bypass.violations("bypass.")
        return out

    def summary(self) -> dict[str, Any]:
        return self.model_dump()


def reference_configuration() -> BoilerHouseConfiguration:
    """Reference 15 MW plant (example values, not measured data).

    Sizing rules of thumb (analysis finding U3), all VERIFY:
    - fuel: wood chips at 45 % moisture, about 1.56 kg/s wet at 15 MW; air at λ 1.5 ≈ 8 kg/s;
      flue gas ≈ 9.6 kg/s;
    - furnace volume from a volumetric heat release of about 0.3 MW/m³ → 50 m³;
    - radiant heater: average heat flux about 30 kW/m² for about 3 MW → 100 m² outer tube area,
      cold-plane area half of it; 4 passes of DN100 give about 2.8 m/s oil at 60 kg/s;
    - convective heaters: about 2 MW each, U ≈ 40 W/(m² K) with fouling, LMTD 370–520 K →
      about 100 and 135 m²; 16 tubes per row at 120 mm pitch give gas velocities near 8 m/s and
      16 passes give about 2.7 m/s oil;
    - refractory: about 100 m² × 0.3 m at 2200 kg/m³; losses about 1 % of rated power.
    """
    return BoilerHouseConfiguration(
        furnace=FurnaceConfig(),
        heaters=[
            RadiantHeater(),
            ConvectiveHeater(n_rows=8, tube_mass=3500.0, oil_volume=1.0),
            ConvectiveHeater(n_rows=11, tube_mass=4800.0, oil_volume=1.38),
        ],
        bypass=BypassConfig(),
    )
