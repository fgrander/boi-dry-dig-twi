"""Normalised scenario models (SI units), produced by :mod:`boidrytwin.scenario.loader`.

These frozen models are what a run record stores; they hold no unit strings.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from boidrytwin.boiler_house.config import BoilerHouseConfiguration
from boidrytwin.control.pi import PISettings
from boidrytwin.dryer.config import DryerConfiguration
from boidrytwin.properties.fuel import FuelComposition

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


class BoilerFlueGasSpec(_Frozen):
    """The dryer is fed by the [boiler_house] section (coupled run, feature 002)."""

    source: Literal["boiler_house"] = "boiler_house"


FlueGasSpec = Annotated[
    ConstantFlueGasSpec | TimeSeriesFlueGasSpec | BoilerFlueGasSpec, Field(discriminator="source")
]


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


class ControllerSpec(PISettings):
    """PI settings plus the loop's set point and manual output signals (feature 002)."""

    setpoint: SignalSpec
    manual_signal: SignalSpec | None = None
    split_value: float = Field(default=0.5, gt=0.0, lt=1.0)
    max_dilution_air: float | None = Field(default=None, gt=0.0)


class ResistancePoint(_Frozen):
    """Design point of a flow resistance with a constant loss coefficient (feature 004)."""

    mass_flow: float = Field(gt=0.0)  # kg/s
    pressure_drop: float = Field(gt=0.0)  # Pa
    temperature: float = Field(gt=250.0, lt=900.0)  # K


class ResistancesSpec(_Frozen):
    drum_path: ResistancePoint  # mixing chamber -> fan inlet (drum, cyclone, ducts)
    stack: ResistancePoint  # fan outlet -> stack exit


class DamperSpec(_Frozen):
    open_mass_flow: float = Field(gt=0.0)  # kg/s, fully open at the design pressure drop
    design_pressure_drop: float = Field(gt=0.0)  # Pa
    design_temperature: float = Field(gt=250.0, lt=900.0)  # K
    characteristic: tuple[tuple[float, float], ...] | None = None  # (position, relative flow)
    leakage: float = Field(default=0.01, ge=0.0, le=0.2)

    @model_validator(mode="after")
    def _table(self) -> DamperSpec:
        if self.characteristic is not None:
            problem = characteristic_problem(self.characteristic)
            if problem:
                raise ValueError(problem)
        return self


def characteristic_problem(table: tuple[tuple[float, float], ...]) -> str | None:
    """Why a damper table is invalid, or None (contracts/scenario-file-recirculation.md)."""
    pos = [p for p, _ in table]
    flow = [f for _, f in table]
    if len(table) < 2 or pos[0] != 0.0 or pos[-1] != 1.0:
        return "positions must run from 0 to 1"
    if any(b <= a for a, b in pairwise(pos)):
        return "positions must increase"
    if flow[0] < 0.0 or any(b < a for a, b in pairwise(flow)) or flow[-1] != 1.0:
        return "relative flows must not decrease, start ≥ 0 and end at 1"
    return None


class ExhaustFanSpec(_Frozen):
    curve: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]  # (m3/s, Pa)
    nominal_speed: float = Field(gt=0.0)  # rad/s
    curve_temperature: float = Field(default=293.15, gt=250.0, lt=900.0)  # K
    speed: SignalSpec  # rad/s


class RecirculationSpec(_Frozen):
    """Exhaust recirculation with mixing chamber pressure control (feature 004)."""

    damper: DamperSpec
    exhaust_fan: ExhaustFanSpec
    resistances: ResistancesSpec
    controller: ControllerSpec  # set point: mixing chamber pressure, output: damper position
    pressure_sensor_time_constant: float = Field(default=2.0, gt=0.0, le=600.0)  # s
    duct_heat_loss: float = Field(default=0.0, ge=0.0)  # W/K
    max_share: float = Field(default=0.7, gt=0.0, lt=1.0)
    dew_point_margin: float = Field(default=10.0, ge=0.0, le=100.0)  # K


class BoilerControllers(_Frozen):
    oil_temperature: ControllerSpec
    oxygen: ControllerSpec
    drum_inlet_temperature: ControllerSpec | None = None


class BoilerInitialStateSpec(_Frozen):
    kind: Literal["cold", "steady_state", "explicit"] = "steady_state"
    file: str | None = None
    sha256: str | None = None


class BoilerHouseSpec(_Frozen):
    config: BoilerHouseConfiguration
    fuel: FuelComposition
    oil: Literal["shell_s2", "therminol_66"] = "shell_s2"
    max_bulk_temperature: float | None = None
    max_film_temperature: float | None = None
    min_velocity: float = 2.0
    signals: dict[str, SignalSpec]
    controllers: BoilerControllers
    initial_state: BoilerInitialStateSpec = BoilerInitialStateSpec()


class ScenarioSpec(_Frozen):
    schema_version: Literal[1] = 1
    name: str
    time: TimeSettings
    flue_gas: FlueGasSpec | None = None
    dilution_air: DilutionAirSpec = DilutionAirSpec()
    product_feed: ProductFeedSpec | None = None
    ambient: AmbientSpec | None = None
    dryer: DryerConfiguration | None = None
    initial_state: InitialStateSpec = InitialStateSpec()
    balance_tolerances: BalanceTolerances = BalanceTolerances()
    boiler_house: BoilerHouseSpec | None = None
    recirculation: RecirculationSpec | None = None
