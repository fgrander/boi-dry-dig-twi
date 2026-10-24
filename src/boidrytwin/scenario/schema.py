"""Normalised scenario models (SI units), produced by :mod:`boidrytwin.scenario.loader`.

These frozen models are what a run record stores; they hold no unit strings.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from boidrytwin.dryer.config import DryerConfiguration

OUTPUT_INTERVAL_MIN, OUTPUT_INTERVAL_MAX = 1.0, 3600.0  # s


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TimeSettings(_Frozen):
    start: AwareDatetime
    end: AwareDatetime
    output_interval: float = Field(default=60.0, ge=OUTPUT_INTERVAL_MIN, le=OUTPUT_INTERVAL_MAX)
    rtol: float = Field(default=1e-6, gt=0.0)
    atol: float = Field(default=1e-8, gt=0.0)

    @property
    def duration(self) -> float:
        """Simulated period, s."""
        return (self.end - self.start).total_seconds()


class SignalSpec(_Frozen):
    """A scalar input: constant (SI) or a column of a time series file."""

    constant: float | None = None
    file: str | None = None
    column: str | None = None
    sha256: str | None = None


class ConstantFlueGasSpec(_Frozen):
    source: Literal["constant"] = "constant"
    mass_flow: float
    temperature: float
    pressure: float
    composition: tuple[float, float, float, float, float]  # wet mole fractions, gas.SPECIES


class TimeSeriesFlueGasSpec(_Frozen):
    source: Literal["timeseries"] = "timeseries"
    file: str
    sha256: str
    max_gap: float
    allow_gaps: bool
    stale_after: float
    composition_basis: Literal["wet", "dry"]
    composition_type: Literal["mole", "mass"]
    pressure_reference: float | None = None


FlueGasSpec = Annotated[ConstantFlueGasSpec | TimeSeriesFlueGasSpec, Field(discriminator="source")]


class DilutionAirSpec(_Frozen):
    mass_flow: SignalSpec = SignalSpec(constant=0.0)


class ProductFeedSpec(_Frozen):
    mass_flow_wet: SignalSpec
    moisture_wet_basis: SignalSpec
    temperature: SignalSpec


class AmbientSpec(_Frozen):
    temperature: SignalSpec
    relative_humidity: SignalSpec
    pressure: SignalSpec


class InitialStateSpec(_Frozen):
    kind: Literal["cold_empty", "steady_state", "explicit"] = "cold_empty"
    file: str | None = None
    sha256: str | None = None


class BalanceTolerances(_Frozen):
    mass: float = Field(default=0.001, gt=0.0)  # relative to total inflow (SC-002)
    energy: float = Field(default=0.01, gt=0.0)


class ScenarioSpec(_Frozen):
    schema_version: Literal[1] = 1
    name: str
    time: TimeSettings
    flue_gas: FlueGasSpec
    dilution_air: DilutionAirSpec = DilutionAirSpec()
    product_feed: ProductFeedSpec | None = None
    ambient: AmbientSpec | None = None
    dryer: DryerConfiguration | None = None
    initial_state: InitialStateSpec = InitialStateSpec()
    balance_tolerances: BalanceTolerances = BalanceTolerances()
