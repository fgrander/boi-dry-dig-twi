"""Boiler house state: layout, packing and persistence (data-model.md §3).

User-facing form with temperatures; the model integrates the furnace gas enthalpy and the
oil enthalpies internally (:mod:`boidrytwin.boiler_house.model` converts).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from boidrytwin.boiler_house.config import BoilerHouseConfiguration
from boidrytwin.properties.gas import FloatArray


@dataclass(frozen=True)
class StateLayout:
    convective_cells: tuple[int, ...]

    @classmethod
    def for_config(cls, cfg: BoilerHouseConfiguration) -> StateLayout:
        return cls(tuple(h.n_cells for h in cfg.convective))

    @property
    def n_heater_nodes(self) -> int:
        """Radiant heater node plus all convective cells."""
        return 1 + sum(self.convective_cells)

    # index map of the state vector
    feed = slice(0, 2)
    bed_water = 2
    bed_dry = 3
    furnace = 4
    refractory_hot = 5
    refractory_bulk = 6

    @property
    def wall(self) -> slice:
        return slice(7, 7 + self.n_heater_nodes)

    @property
    def oil(self) -> slice:
        n = self.n_heater_nodes
        return slice(7 + n, 7 + 2 * n)

    @property
    def o2(self) -> int:
        return 7 + 2 * self.n_heater_nodes

    @property
    def size(self) -> int:
        return 8 + 2 * self.n_heater_nodes


@dataclass(frozen=True)
class BoilerHouseState:
    layout: StateLayout
    feed_stages: FloatArray
    bed_water: float
    bed_dry_fuel: float
    furnace_temperature: float
    refractory_hot_face: float
    refractory_bulk: float
    heater_wall: FloatArray
    heater_oil: FloatArray
    o2_measured: float
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("feed_stages", "heater_wall", "heater_oil"):
            object.__setattr__(self, name, np.asarray(getattr(self, name), dtype=float).copy())
        if (
            len(self.heater_wall) != self.layout.n_heater_nodes
            or len(self.heater_oil) != self.layout.n_heater_nodes
        ):
            raise ValueError("heater_wall/heater_oil length does not match the layout")
        for name in ("bed_water", "bed_dry_fuel"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be ≥ 0")
        if np.any(self.feed_stages < 0):
            raise ValueError("feed_stages must be ≥ 0")
        for name in ("furnace_temperature", "refractory_hot_face", "refractory_bulk"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be > 0 K")
        if np.any(self.heater_wall <= 0) or np.any(self.heater_oil <= 0):
            raise ValueError("heater temperatures must be > 0 K")
        if not 0.0 <= self.o2_measured <= 0.21:
            raise ValueError("o2_measured must be in [0, 0.21]")

    def as_dict(self) -> dict[str, Any]:
        return {
            "layout": self.layout,
            "feed_stages": self.feed_stages,
            "bed_water": self.bed_water,
            "bed_dry_fuel": self.bed_dry_fuel,
            "furnace_temperature": self.furnace_temperature,
            "refractory_hot_face": self.refractory_hot_face,
            "refractory_bulk": self.refractory_bulk,
            "heater_wall": self.heater_wall,
            "heater_oil": self.heater_oil,
            "o2_measured": self.o2_measured,
        }

    def to_vector(self) -> FloatArray:
        lay = self.layout
        v = np.empty(lay.size)
        v[lay.feed] = self.feed_stages
        v[lay.bed_water] = self.bed_water
        v[lay.bed_dry] = self.bed_dry_fuel
        v[lay.furnace] = self.furnace_temperature
        v[lay.refractory_hot] = self.refractory_hot_face
        v[lay.refractory_bulk] = self.refractory_bulk
        v[lay.wall] = self.heater_wall
        v[lay.oil] = self.heater_oil
        v[lay.o2] = self.o2_measured
        return v

    @classmethod
    def from_vector(cls, layout: StateLayout, v: FloatArray) -> BoilerHouseState:
        return cls(
            layout=layout,
            feed_stages=v[layout.feed],
            bed_water=float(v[layout.bed_water]),
            bed_dry_fuel=float(v[layout.bed_dry]),
            furnace_temperature=float(v[layout.furnace]),
            refractory_hot_face=float(v[layout.refractory_hot]),
            refractory_bulk=float(v[layout.refractory_bulk]),
            heater_wall=v[layout.wall],
            heater_oil=v[layout.oil],
            o2_measured=float(v[layout.o2]),
        )

    def save(self, path: Path) -> None:
        payload = {
            k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in self.as_dict().items()
        }
        payload["layout"] = asdict(self.layout)
        payload["extra"] = self.extra
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> BoilerHouseState:
        payload = json.loads(path.read_text(encoding="utf-8"))
        layout = StateLayout(tuple(payload.pop("layout")["convective_cells"]))
        extra = payload.pop("extra", {})
        return cls(layout=layout, extra=extra, **payload)
