"""Flue gas state and the supply interface (contracts/flue-gas-interface.md).

The dryer obtains its heat only through :class:`FlueGasSupply`; it never accesses the
internals of a source (constitution principle III). This module must not import from
:mod:`boidrytwin.dryer`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, NamedTuple, Protocol, runtime_checkable

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from boidrytwin.interface.composition import GasComposition
from boidrytwin.properties import gas, water
from boidrytwin.properties.gas import FloatArray

Quality = Literal["good", "interpolated", "missing", "stale", "bad"]

# data-model.md §1 FlueGasState
T_MIN, T_MAX = 273.15, 1473.15  # K (0-1200 °C)
P_MIN, P_MAX = 50_000.0, 200_000.0  # Pa absolute, exclusive bounds
T_REF = gas.T_REF

ALLOWED = {
    "mass_flow": "≥ 0 kg/s",
    "temperature": "0-1200 °C (273.15-1473.15 K)",
    "pressure": "0.5-2 bar absolute (50-200 kPa, exclusive)",
}


def check_state_values(
    *, mass_flow: float, temperature: float, pressure: float
) -> list[tuple[str, str, str]]:
    """Return ``(field, reason, allowed)`` for every invalid value (empty if all valid)."""
    problems: list[tuple[str, str, str]] = []
    if not mass_flow >= 0.0:
        problems.append(("mass_flow", "must be ≥ 0", ALLOWED["mass_flow"]))
    if not T_MIN <= temperature <= T_MAX:
        problems.append(("temperature", "out of range", ALLOWED["temperature"]))
    if not P_MIN < pressure < P_MAX:
        problems.append(("pressure", "out of range", ALLOWED["pressure"]))
    return problems


class FlueGasState(BaseModel):
    """State of the flue gas crossing the interface at one time, SI units."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    time: AwareDatetime
    mass_flow: float = Field(ge=0.0)
    temperature: float = Field(ge=T_MIN, le=T_MAX)
    pressure: float = Field(gt=P_MIN, lt=P_MAX)
    composition: GasComposition
    quality: Quality = "good"

    def heat_content_flow(self, T_ref: float = T_REF) -> float:
        """Heat content flow relative to ``T_ref``, W (FR-002)."""
        y = self.composition.mass_fractions()
        dh = gas.h_sensible_mass(self.temperature, y) - gas.h_sensible_mass(T_ref, y)
        return float(self.mass_flow * dh)

    @property
    def humidity(self) -> float:
        """kg water vapour per kg dry gas."""
        return humidity_of(self.composition.as_array())

    @property
    def dew_point(self) -> float:
        """Water dew point, K."""
        return float(water.dew_point(self.humidity, self.pressure, self.composition.dry_molar_mass))


def humidity_of(x: FloatArray) -> float:
    """Humidity (kg H2O / kg dry gas) of a wet mole-fraction array."""
    m = x * gas.MOLAR_MASS
    m_water = float(m[gas.I_H2O])
    return m_water / (float(m.sum()) - m_water)


class FlueGasConditions(NamedTuple):
    """Fast, unvalidated view of a flue gas state for use inside the ODE right-hand side."""

    mass_flow: float
    temperature: float
    pressure: float
    x: FloatArray
    quality: Quality


@runtime_checkable
class FlueGasSupply(Protocol):
    """The only way a dryer obtains its flue gas (FR-005)."""

    source_id: str

    def state_at(self, t: float) -> FlueGasState:
        """Flue gas state at simulation time ``t`` (s since scenario start)."""
        ...

    def conditions_at(self, t: float) -> FlueGasConditions:
        """Same data as :meth:`state_at` as plain floats (no model construction)."""
        ...

    def covers(self, t_start: float, t_end: float) -> bool:
        """True if the source has data for the whole period."""
        ...

    def breakpoints(self) -> FloatArray:
        """Times (s) where the supplied conditions change slope (solver restart points)."""
        ...


def make_state(time: datetime, conditions: FlueGasConditions) -> FlueGasState:
    """Build a validated :class:`FlueGasState` from fast conditions."""
    return FlueGasState(
        time=time,
        mass_flow=conditions.mass_flow,
        temperature=conditions.temperature,
        pressure=conditions.pressure,
        composition=GasComposition.from_array(conditions.x),
        quality=conditions.quality,
    )
