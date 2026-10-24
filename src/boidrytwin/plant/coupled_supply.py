"""Flue gas supply and signals set by the plant coordinator (contracts/plant-coupling.md).

Both are valid only inside a plant evaluation: the plant evaluates the boiler house, sets
the current outlet conditions and dilution air flow here, then evaluates the dryer, which
reads them through its unchanged feature-001 interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from boidrytwin.interface.flue_gas import FlueGasState
from boidrytwin.interface.sources import ExternallySetFlueGasSupply
from boidrytwin.properties.gas import FloatArray
from boidrytwin.scenario.timeseries import Signal


class CoupledFlueGasSupply(ExternallySetFlueGasSupply):
    """The boiler house outlet as the dryer's ``FlueGasSupply``.

    ``state_at`` validates the current conditions (raises if they leave the interface
    ranges); the dryer itself reads ``conditions_at``, so a run is never stopped by it.
    """

    def state_at(self, t: float) -> FlueGasState:
        return super().state_at(t)


@dataclass(frozen=True)
class ControlledSignal(Signal):
    """A ``Signal`` whose value is set by a controller on every plant evaluation."""

    source: str = "controller"
    _box: list[float] = field(default_factory=lambda: [0.0], repr=False, compare=False)

    @property
    def current(self) -> float:
        return self._box[0]

    def set(self, value: float) -> None:
        # frozen like every Signal; the value lives in a mutable box
        self._box[0] = float(value)

    def value_at(self, t: float) -> float:
        return self._box[0]

    def values_at(self, t: FloatArray) -> FloatArray:
        return np.full(np.shape(t), self._box[0])

    def covers(self, t_start: float, t_end: float) -> bool:
        return True

    def breakpoints(self) -> FloatArray:
        return np.empty(0)

    def all_values(self) -> FloatArray:
        return np.array([self._box[0]])
