"""Balances per subsystem, at interfaces and for the whole plant (feature 002, FR-013).

Each entry holds feature-001 ``QuantityBalance`` records: residual = inflow − outflow −
change in storage, relative to the total inflow. Mass and element balances use the mass
tolerance, energy balances the energy tolerance.

Entries: ``boiler_house`` (mass, C, H, O, N, S, energy), ``oil_circuit`` (energy) and, for
coupled runs, ``dryer`` (feature-001 quantities), ``interface`` (boiler outlet against dryer
inlet, mass and energy, no storage) and ``plant`` (mass and energy across the whole plant
boundary: internal flows, i.e. the flue gas to the dryer and the heat to the oil, cancel).
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
        tol = tolerances.energy if q.rsplit(".", 1)[-1] in ENERGY_QUANTITIES else tolerances.mass
        inflow, outflow = flows[q]
        name = (rename or {}).get(q, q)
        entry[name] = quantity_balance(inflow, outflow, start[q], end[q], tol)
    return entry


DRYER_MASS = ("dryer.dry_solids", "dryer.water", "dryer.gas")


def plant_entry(
    flows: Mapping[str, tuple[float, float]],
    start: Mapping[str, float],
    end: Mapping[str, float],
    tolerances: BalanceTolerances,
) -> dict[str, QuantityBalance]:
    """Whole-plant mass and energy balance from the subsystem accumulators."""
    iface_m, iface_e = flows["interface.mass"], flows["interface.energy"]
    heat = flows["oil.heat"][0]
    m_in = flows["mass"][0] + sum(flows[q][0] for q in DRYER_MASS) - iface_m[1]
    m_out = flows["mass"][1] - iface_m[0] + sum(flows[q][1] for q in DRYER_MASS)
    e_in = (
        flows["energy"][0] + flows["oil_energy"][0] - heat + flows["dryer.energy"][0] - iface_e[1]
    )
    e_out = (
        flows["energy"][1] - heat - iface_e[0] + flows["oil_energy"][1] + flows["dryer.energy"][1]
    )

    def mass(s: Mapping[str, float]) -> float:
        return s["mass"] + sum(s[q] for q in DRYER_MASS)

    def energy(s: Mapping[str, float]) -> float:
        return s["energy"] + s["oil_energy"] + s["dryer.energy"]

    return {
        "mass": quantity_balance(m_in, m_out, mass(start), mass(end), tolerances.mass),
        "energy": quantity_balance(e_in, e_out, energy(start), energy(end), tolerances.energy),
    }
