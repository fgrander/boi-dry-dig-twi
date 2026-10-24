"""DryerState: the stored quantities inside the drum (data-model.md §3).

The vector layout is cell-major: the 8 values of cell 0, then cell 1, ... in the order of
:data:`FIELDS`. The model integrates enthalpies instead of temperatures internally
(:mod:`boidrytwin.dryer.model` converts); this class is the user-facing form, also used for
``final_state.json`` and explicit initial states.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from boidrytwin.properties.gas import FloatArray

FIELDS: tuple[str, ...] = (
    "dry_mass_passive",
    "dry_mass_active",
    "water_mass_passive",
    "water_mass_active",
    "solids_temperature",
    "gas_temperature",
    "gas_humidity",
    "shell_temperature",
)
N_FIELDS = len(FIELDS)
_NON_NEGATIVE = (
    "dry_mass_passive",
    "dry_mass_active",
    "water_mass_passive",
    "water_mass_active",
    "gas_humidity",
)
_POSITIVE = ("solids_temperature", "gas_temperature", "shell_temperature")


@dataclass(frozen=True)
class DryerState:
    dry_mass_passive: FloatArray
    dry_mass_active: FloatArray
    water_mass_passive: FloatArray
    water_mass_active: FloatArray
    solids_temperature: FloatArray
    gas_temperature: FloatArray
    gas_humidity: FloatArray
    shell_temperature: FloatArray

    def __post_init__(self) -> None:
        lengths = {len(np.atleast_1d(getattr(self, f))) for f in FIELDS}
        if len(lengths) != 1:
            raise ValueError(f"all fields need the same length, got {sorted(lengths)}")
        for f in FIELDS:
            object.__setattr__(self, f, np.asarray(getattr(self, f), dtype=float).copy())
        for f in _NON_NEGATIVE:
            if np.any(getattr(self, f) < 0):
                raise ValueError(f"{f} must be ≥ 0")
        for f in _POSITIVE:
            if np.any(getattr(self, f) <= 0):
                raise ValueError(f"{f} must be > 0 K")

    @property
    def n_cells(self) -> int:
        return len(self.gas_temperature)

    def to_vector(self) -> FloatArray:
        return np.stack([getattr(self, f) for f in FIELDS], axis=1).reshape(-1)

    @classmethod
    def from_vector(cls, v: FloatArray, n_cells: int) -> DryerState:
        cols = np.asarray(v, dtype=float).reshape(n_cells, N_FIELDS)
        return cls(**{f: cols[:, i] for i, f in enumerate(FIELDS)})

    def save(self, path: Path) -> None:
        payload = {"n_cells": self.n_cells, **{f: getattr(self, f).tolist() for f in FIELDS}}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> DryerState:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{f: np.array(payload[f], dtype=float) for f in FIELDS})
