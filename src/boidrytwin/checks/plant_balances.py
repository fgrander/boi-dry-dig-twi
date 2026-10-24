"""Balances per subsystem, at interfaces and for the whole plant (feature 002, FR-013).

Each entry holds feature-001 ``QuantityBalance`` records: residual = inflow − outflow −
change in storage, relative to the total inflow. Mass and element balances use the mass
tolerance, energy balances the energy tolerance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from boidrytwin.checks.balances import QuantityBalance
from boidrytwin.scenario.schema import BalanceTolerances

ENERGY_QUANTITIES = ("energy", "oil_energy")


def quantity_balance(
    inflow: float, outflow: float, start: float, end: float, tolerance: float
) -> QuantityBalance:
    change = end - start
    residual = inflow - outflow - change
    reference = abs(inflow) if inflow != 0 else max(abs(start), abs(end))
    relative = residual / reference if reference > 0 else 0.0
    return QuantityBalance(
        inflow=inflow,
        outflow=outflow,
        storage_change=change,
        residual=residual,
        relative_residual=relative,
        tolerance=tolerance,
        passed=abs(relative) <= tolerance,
    )


class PlantBalanceReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    entries: dict[str, dict[str, QuantityBalance]]

    @property
    def passed(self) -> bool:
        return all(q.passed for entry in self.entries.values() for q in entry.values())

    def failed(self) -> list[str]:
        return [
            f"{name}.{q}"
            for name, entry in self.entries.items()
            for q, b in entry.items()
            if not b.passed
        ]

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            name: {q: b.model_dump() for q, b in entry.items()}
            for name, entry in self.entries.items()
        }
        out["passed"] = self.passed
        return out


def subsystem_entry(
    flows: Mapping[str, tuple[float, float]],
    start: Mapping[str, float],
    end: Mapping[str, float],
    quantities: Sequence[str],
    tolerances: BalanceTolerances,
    rename: Mapping[str, str] | None = None,
) -> dict[str, QuantityBalance]:
    entry: dict[str, QuantityBalance] = {}
    for q in quantities:
        tol = tolerances.energy if q in ENERGY_QUANTITIES else tolerances.mass
        inflow, outflow = flows[q]
        name = (rename or {}).get(q, q)
        entry[name] = quantity_balance(inflow, outflow, start[q], end[q], tol)
    return entry
