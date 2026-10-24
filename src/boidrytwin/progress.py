"""Read-only progress reporting of simulation runs (feature 003, research R2).

A simulator that is given a ``progress`` callback reports its phase (``initialising`` for a
steady-state start, ``simulating``, ``writing``) and the furthest simulated time evaluated so
far. The reporter only observes the times at which the solver evaluates the right-hand side.
It never adds breakpoints or changes steps, so results are identical with or without it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

MIN_INTERVAL = 1.0  # s of wall time between reports within one phase


class Progress(Protocol):
    def __call__(self, phase: str, simulated_s: float, duration_s: float) -> None: ...


class ProgressReporter:
    def __init__(self, callback: Progress | None, duration: float) -> None:
        self.callback = callback
        self.duration = duration
        self.current = "initialising"
        self.simulated = 0.0
        self._last = -float("inf")

    def phase(self, name: str, simulated_s: float | None = None) -> None:
        self.current = name
        if simulated_s is not None:
            self.simulated = simulated_s
        self._emit()

    def seen(self, t: float, force: bool = False) -> None:
        self.simulated = max(self.simulated, min(float(t), self.duration))
        if force or time.perf_counter() - self._last >= MIN_INTERVAL:
            self._emit()

    def wrap(self, rhs: Callable[..., Any]) -> Callable[..., Any]:
        """``rhs`` that also reports the evaluation time (unchanged values)."""
        if self.callback is None:
            return rhs

        def observed(t: float, z: Any) -> Any:
            self.seen(t)
            return rhs(t, z)

        return observed

    def _emit(self) -> None:
        if self.callback is not None:
            self._last = time.perf_counter()
            self.callback(self.current, self.simulated, self.duration)
