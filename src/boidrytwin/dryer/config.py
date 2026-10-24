"""Dryer configuration with physical and validated ranges (data-model.md §2).

Every field has a ``physical`` range (outside: impossible, rejected) and a ``validated``
range (outside: accepted, reported as a RangeWarning, FR-012). Defaults marked VERIFY come
from correlations whose coefficients still need checking against the original sources
(research.md Open item 1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

RPM = 2 * math.pi / 60


@dataclass(frozen=True)
class FieldSpec:
    dimension: str
    default: float | None
    physical: tuple[float, float]
    validated: tuple[float, float]
    doc: str
    group: str
    lower_inclusive: bool = True


FIELDS: dict[str, FieldSpec] = {
    # geometry
    "length": FieldSpec("length", None, (0.0, 200.0), (5.0, 60.0), "drum length", "geometry", False),
    "diameter": FieldSpec("length", None, (0.0, 15.0), (1.0, 6.0), "drum inner diameter", "geometry", False),
    "slope": FieldSpec("angle", None, (0.0, math.radians(20)), (0.0, math.radians(5)), "drum slope towards the outlet", "geometry"),
    "n_flights": FieldSpec("dimensionless", 24.0, (0.0, 200.0), (8.0, 60.0), "number of flights (documentation; not used by the transport law yet)", "geometry"),
    "flight_lip_length": FieldSpec("length", 0.3, (0.0, 2.0), (0.05, 1.0), "flight lip length (documentation; not used yet)", "geometry"),
    "shell_thickness": FieldSpec("length", 0.016, (0.0, 0.2), (0.006, 0.04), "steel shell thickness", "geometry", False),
    "shell_mass": FieldSpec("mass", None, (0.0, 1e7), (1e3, 5e5), "shell mass including flights", "geometry", False),
    "insulation_thickness": FieldSpec("length", 0.0, (0.0, 1.0), (0.0, 0.3), "external insulation thickness", "geometry"),
    "insulation_conductivity": FieldSpec("thermal_conductivity", 0.04, (1e-3, 10.0), (0.02, 0.2), "insulation conductivity", "geometry"),
    # operation
    "rotation_speed": FieldSpec("angular_velocity", None, (0.0, 30 * RPM), (1 * RPM, 10 * RPM), "drum rotation speed", "operation", False),
    # discretisation
    "n_cells": FieldSpec("dimensionless", 20.0, (10.0, 40.0), (10.0, 40.0), "number of axial cells", "discretisation"),
    # product
    "chip_equivalent_diameter": FieldSpec("length", 0.015, (1e-4, 0.2), (0.002, 0.05), "equivalent sphere diameter of the chips", "product"),
    "particle_density": FieldSpec("density", 450.0, (50.0, 1500.0), (300.0, 700.0), "dry particle density (kg dry wood per m³ of chip)", "product"),
    "bulk_density": FieldSpec("density", 160.0, (20.0, 1000.0), (100.0, 400.0), "dry bulk density of chips", "product"),
    "fibre_saturation_moisture": FieldSpec("fraction", 0.30, (0.1, 0.6), (0.25, 0.35), "fibre saturation point, dry basis", "product"),
    "critical_moisture_dry_basis": FieldSpec("fraction", 0.8, (0.01, 5.0), (0.3, 1.5), "end of the constant-rate period, dry basis", "product"),
    "falling_rate_exponent": FieldSpec("dimensionless", 1.0, (0.01, 10.0), (0.5, 3.0), "exponent n of the falling-rate curve", "product"),
    # shell
    "shell_emissivity": FieldSpec("fraction", 0.8, (0.0, 1.0), (0.5, 0.95), "emissivity of the outer shell", "shell"),
    "shell_specific_heat": FieldSpec("specific_heat", 500.0, (1.0, 5000.0), (450.0, 550.0), "shell specific heat", "shell"),
    # calibration
    "drag_coefficient": FieldSpec("dimensionless", 0.1, (0.0, 100.0), (0.01, 1.0), "curtain drag relative to single-sphere drag (Baker 1992). VERIFY", "calibration"),
    "kilning_coefficient": FieldSpec("dimensionless", 1.0, (0.0, 100.0), (0.2, 5.0), "kilning/bouncing advance relative to Saeman-Mitchell f = π. VERIFY", "calibration"),
    "flight_capacity_factor": FieldSpec("dimensionless", 1.0, (1e-3, 10.0), (0.3, 3.0), "flight unloading rate relative to one cascade per revolution", "calibration"),
    "heat_transfer_multiplier": FieldSpec("dimensionless", 1.0, (0.0, 100.0), (0.3, 3.0), "C_a: multiplier on gas-solids heat and mass transfer", "calibration"),
    "shell_contact_htc": FieldSpec("heat_transfer_coefficient", 100.0, (0.0, 2000.0), (50.0, 150.0), "shell-solids contact coefficient. VERIFY", "calibration"),
    # limits of the valid operating range
    "max_drum_inlet_gas_temperature": FieldSpec("temperature", 873.15, (300.0, 1500.0), (300.0, 1500.0), "highest validated drum inlet gas temperature", "limits"),
    "min_dew_point_margin": FieldSpec("temperature_difference", 10.0, (0.0, 100.0), (0.0, 100.0), "minimum exhaust temperature above dew point", "limits"),
    "emc_data_limit": FieldSpec("temperature", 403.15, (300.0, 500.0), (300.0, 500.0), "upper temperature of the EMC data", "limits"),
}  # fmt: skip

GROUPS = ("geometry", "operation", "discretisation", "product", "shell", "calibration", "limits")


@dataclass(frozen=True)
class RangeViolation:
    field: str
    value: float
    limit_type: Literal["min", "max"]
    limit: float


class DryerConfiguration(BaseModel):
    """Design, operating and material parameters of the drum, SI units."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    length: float
    diameter: float
    slope: float
    n_flights: float = 24.0
    flight_lip_length: float = 0.3
    shell_thickness: float = 0.016
    shell_mass: float
    insulation_thickness: float = 0.0
    insulation_conductivity: float = 0.04
    rotation_speed: float
    gas_flow_direction: Literal["co-current"] = "co-current"
    n_cells: int = 20
    chip_equivalent_diameter: float = 0.015
    particle_density: float = 450.0
    bulk_density: float = 160.0
    fibre_saturation_moisture: float = 0.30
    critical_moisture_dry_basis: float = 0.8
    falling_rate_exponent: float = 1.0
    shell_emissivity: float = 0.8
    shell_specific_heat: float = 500.0
    drag_coefficient: float = 0.1
    kilning_coefficient: float = 1.0
    flight_capacity_factor: float = 1.0
    heat_transfer_multiplier: float = 1.0
    shell_contact_htc: float = 100.0
    max_drum_inlet_gas_temperature: float = 873.15
    min_dew_point_margin: float = 10.0
    emc_data_limit: float = 403.15

    @model_validator(mode="after")
    def _physical_ranges(self) -> DryerConfiguration:
        problems = []
        for name, spec in FIELDS.items():
            value = float(getattr(self, name))
            lo, hi = spec.physical
            low_ok = value >= lo if spec.lower_inclusive else value > lo
            if not (low_ok and value <= hi):
                bracket = "[" if spec.lower_inclusive else "("
                problems.append(
                    f"{name} = {value:g} outside physical range {bracket}{lo:g}, {hi:g}]"
                )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def validated_range_violations(self) -> list[RangeViolation]:
        """Fields outside the range the model is validated for (accepted, but warned)."""
        out: list[RangeViolation] = []
        for name, spec in FIELDS.items():
            value = float(getattr(self, name))
            lo, hi = spec.validated
            if value < lo:
                out.append(RangeViolation(name, value, "min", lo))
            elif value > hi:
                out.append(RangeViolation(name, value, "max", hi))
        return out

    @property
    def cell_length(self) -> float:
        return self.length / self.n_cells

    @property
    def cross_section(self) -> float:
        return math.pi * self.diameter**2 / 4.0

    @property
    def cell_volume(self) -> float:
        return self.cross_section * self.cell_length

    def summary(self) -> dict[str, Any]:
        return self.model_dump()
