"""Mass and energy balances over a run (FR-013, SC-002).

residual = inflow - outflow - (stored at end - stored at start), relative to the total
inflow of that quantity over the run (or, without inflow, to the stored amount). Inflows
and outflows are integrated by the solver alongside the model, so the residual measures
the solver error, not a post-processing approximation.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from boidrytwin.scenario.schema import BalanceTolerances

QUANTITIES = ("dry_solids", "water", "gas", "energy")


class QuantityBalance(BaseModel):
    model_config = ConfigDict(frozen=True)

    inflow: float
    outflow: float
    storage_change: float
    residual: float
    relative_residual: float
    tolerance: float
    passed: bool


class BalanceReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    dry_solids: QuantityBalance
    water: QuantityBalance
    gas: QuantityBalance
    energy: QuantityBalance

    @property
    def passed(self) -> bool:
        return all(getattr(self, q).passed for q in QUANTITIES)

    def to_dict(self) -> dict[str, object]:
        return {**self.model_dump(), "passed": self.passed}


def balance_report(
    flows: Mapping[str, tuple[float, float]],
    storage_start: Mapping[str, float],
    storage_end: Mapping[str, float],
    tolerances: BalanceTolerances,
) -> BalanceReport:
    parts: dict[str, QuantityBalance] = {}
    for q in QUANTITIES:
        inflow, outflow = flows[q]
        change = storage_end[q] - storage_start[q]
        residual = inflow - outflow - change
        reference = abs(inflow) if inflow != 0 else max(abs(storage_start[q]), abs(storage_end[q]))
        relative = residual / reference if reference > 0 else 0.0
        tolerance = tolerances.energy if q == "energy" else tolerances.mass
        parts[q] = QuantityBalance(
            inflow=inflow,
            outflow=outflow,
            storage_change=change,
            residual=residual,
            relative_residual=relative,
            tolerance=tolerance,
            passed=abs(relative) <= tolerance,
        )
    return BalanceReport(**parts)
