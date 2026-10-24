"""Configuration fields with physical and validated ranges (shared by subsystems).

A value outside its *physical* range is impossible and rejected; a value outside its
*validated* range is accepted and reported as a range warning (FR-012 of feature 001,
FR-011 of feature 002). Kept outside the subsystem packages so that subsystems do not
depend on each other.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class FieldSpec:
    dimension: str
    default: float | None
    physical: tuple[float, float]
    validated: tuple[float, float]
    doc: str
    lower_inclusive: bool = True


@dataclass(frozen=True)
class RangeViolation:
    field: str
    value: float
    limit_type: Literal["min", "max"]
    limit: float


def physical_problems(values: Mapping[str, Any], fields: Mapping[str, FieldSpec]) -> list[str]:
    problems = []
    for name, spec in fields.items():
        if name not in values or values[name] is None:
            continue
        value = float(values[name])
        lo, hi = spec.physical
        low_ok = value >= lo if spec.lower_inclusive else value > lo
        if not (low_ok and value <= hi):
            bracket = "[" if spec.lower_inclusive else "("
            problems.append(f"{name} = {value:g} outside physical range {bracket}{lo:g}, {hi:g}]")
    return problems


def validated_violations(
    values: Mapping[str, Any], fields: Mapping[str, FieldSpec], prefix: str = ""
) -> list[RangeViolation]:
    out: list[RangeViolation] = []
    for name, spec in fields.items():
        if name not in values or values[name] is None:
            continue
        value = float(values[name])
        lo, hi = spec.validated
        if value < lo:
            out.append(RangeViolation(f"{prefix}{name}", value, "min", lo))
        elif value > hi:
            out.append(RangeViolation(f"{prefix}{name}", value, "max", hi))
    return out
