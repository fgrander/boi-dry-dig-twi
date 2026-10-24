"""Plant model: subsystems and control loops in one state vector (contracts/plant-coupling.md).

State: ``[x_boiler, controller integrals, (drum inlet measurement, x_dryer)]``.

- Boiler-house-only plants (User Story 1): the boiler house with the oil-temperature loop
  (fuel feed) and the O2 loop (excess air ratio, fed forward on the current burnout). The
  bypass position is prescribed.
- Coupled plants (User Story 2) add the dryer and the drum inlet split-range loop, which
  sets the bypass position and the dilution air. The loop measures the mixed drum inlet
  temperature through a first-order sensor lag; without it the controller output would
  depend algebraically on its own measurement.

The plant is the only place that knows both subsystems. On every evaluation it evaluates
the boiler house, hands its outlet and the dilution air to the dryer through the
feature-001 interfaces (``CoupledFlueGasSupply``, ``ControlledSignal``), then evaluates the
dryer. The dryer itself is not changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix, lil_matrix

from boidrytwin.boiler_house.model import BoilerHouseModel, BoilerInputs, BoilerOutputs
from boidrytwin.control.pi import PIController
from boidrytwin.control.split_range import split
from boidrytwin.dryer.model import DrumDryerModel, ModelInputs
from boidrytwin.plant.coupled_supply import ControlledSignal, CoupledFlueGasSupply
from boidrytwin.properties import fuel as fp
from boidrytwin.properties import water
from boidrytwin.properties.gas import FloatArray
from boidrytwin.scenario.loader import LoadedScenario
from boidrytwin.scenario.schema import BoilerHouseSpec, ControllerSpec
from boidrytwin.scenario.timeseries import Signal

LOOPS = ("oil_temperature", "oxygen")
DRUM_LOOP = "drum_inlet_temperature"
BOILER_QUANTITIES = ("mass", "C", "H", "O", "N", "S", "energy", "oil_energy")
DRYER_QUANTITIES = ("dry_solids", "water", "gas", "energy")
INTERFACE_QUANTITIES = ("mass", "energy")
DRUM_SENSOR_TIME_CONSTANT = 20.0  # s, drum inlet thermocouple (VERIFY)


@dataclass
class Loop:
    name: str
    spec: ControllerSpec
    pi: PIController
    setpoint: Signal
    manual: Signal | None

    def manual_value(self, t: float) -> float | None:
        if self.spec.mode != "manual":
            return None
        if self.manual is not None:
            return self.manual.value_at(t)
        # O2 loop in manual with a prescribed air mass flow: the output is not used
        return (
            self.spec.manual_output if self.spec.manual_output is not None else loop_mid(self.spec)
        )


@dataclass
class PlantEvaluation:
    dz: FloatArray
    boiler: BoilerOutputs
    flows: dict[str, tuple[float, float]]
    controller: dict[str, dict[str, float]]
    bypass_position: float
    dilution_air: float
    drum_inlet_temperature: float | None


class Plant:
    def __init__(self, loaded: LoadedScenario) -> None:
        spec = loaded.spec.boiler_house
        assert spec is not None
        self.spec: BoilerHouseSpec = spec
        self.loaded = loaded
        self.boiler = BoilerHouseModel(spec.config, spec.oil)
        self.boiler.set_fuel(spec.fuel)
        sig = loaded.signals
        self.signals = sig
        self.coupled = loaded.spec.dryer is not None
        names = (*LOOPS, DRUM_LOOP) if self.coupled else LOOPS
        self.loops = {
            name: Loop(
                name,
                getattr(spec.controllers, name),
                PIController(getattr(spec.controllers, name)),
                sig[f"boiler_house.controllers.{name}.setpoint"],
                sig.get(f"boiler_house.controllers.{name}.manual_output"),
            )
            for name in names
        }
        self.nb = self.boiler.layout.size
        self.index = {name: self.nb + i for i, name in enumerate(names)}
        n = self.nb + len(names)
        self.supply: CoupledFlueGasSupply | None = None
        self.dilution: ControlledSignal | None = None
        self.dryer: DrumDryerModel | None = None
        self.i_drum_meas = -1
        self.dryer_slice = slice(n, n)
        if self.coupled:
            assert loaded.spec.dryer is not None
            start = loaded.spec.time.start if loaded.spec.time else datetime(2000, 1, 1, tzinfo=UTC)
            self.supply = CoupledFlueGasSupply(start=start)
            self.supply.input_breakpoints = self.breakpoints()
            self.dilution = ControlledSignal(name="dilution_air.mass_flow")
            self.dryer = DrumDryerModel(
                loaded.spec.dryer,
                ModelInputs(
                    flue_gas=self.supply,
                    dilution_air=self.dilution,
                    feed_mass_flow_wet=sig["product_feed.mass_flow_wet"],
                    feed_moisture_wet=sig["product_feed.moisture_wet_basis"],
                    feed_temperature=sig["product_feed.temperature"],
                    ambient_temperature=sig["ambient.temperature"],
                    ambient_relative_humidity=sig["ambient.relative_humidity"],
                    ambient_pressure=sig["ambient.pressure"],
                ),
            )
            self.i_drum_meas = n
            self.dryer_slice = slice(n + 1, n + 1 + self.dryer.size)
            n += 1 + self.dryer.size
        self.size = n

    @property
    def n_upstream(self) -> int:
        """Boiler house and controller states: everything the dryer does not feed back to."""
        return self.dryer_slice.start if self.coupled else self.size

    @property
    def flow_keys(self) -> tuple[str, ...]:
        keys: tuple[str, ...] = BOILER_QUANTITIES
        if self.coupled:
            keys = (
                *keys,
                *(f"dryer.{q}" for q in DRYER_QUANTITIES),
                *(f"interface.{q}" for q in INTERFACE_QUANTITIES),
            )
        return keys

    # --- inputs -----------------------------------------------------------------------

    def _value(self, name: str, t: float, default: float | None = None) -> float:
        s = self.signals.get(name)
        if s is None:
            if default is None:
                raise KeyError(name)
            return default
        return s.value_at(t)

    def air_humidity(self, t: float) -> float:
        T_air = self._value("boiler_house.combustion_air.temperature", t)
        rh = self._value(
            "boiler_house.combustion_air.relative_humidity",
            t,
            self._value("ambient.relative_humidity", t),
        )
        p = self._value("ambient.pressure", t)
        p_w = rh * float(water.p_sat(T_air))
        return float(water.humidity_from_partial_pressure(p_w, p, fp.M_DRY_AIR))

    def oil_outlet_temperature(self, z: FloatArray) -> float:
        lay = self.boiler.layout
        return float(self.boiler.oil.temperature_from_enthalpy(z[lay.oil][0]))

    def measurements(self, z: FloatArray) -> dict[str, float]:
        meas = {
            "oil_temperature": self.oil_outlet_temperature(z),
            "oxygen": float(z[self.boiler.layout.o2]),
        }
        if self.coupled:
            meas[DRUM_LOOP] = float(z[self.i_drum_meas])
        return meas

    def actuators(self, t: float, u: dict[str, float]) -> tuple[float, float]:
        """(bypass position, dilution air kg/s) from the drum inlet loop, or prescribed."""
        if not self.coupled:
            return self._value("boiler_house.bypass.position", t, 0.0), 0.0
        spec = self.loops[DRUM_LOOP].spec
        assert spec.max_dilution_air is not None
        return split(u[DRUM_LOOP], spec.split_value, spec.max_dilution_air)

    def boiler_inputs(
        self, t: float, z: FloatArray, u: dict[str, float], bypass: float | None = None
    ) -> BoilerInputs:
        air_mass = self.signals.get("boiler_house.combustion_air.mass_flow")
        if bypass is None:
            bypass = self.actuators(t, u)[0]
        return BoilerInputs(
            fuel=self.spec.fuel,
            fuel_command=u["oil_temperature"],
            moisture_wet=self._value("boiler_house.fuel.moisture_wet_basis", t),
            fuel_temperature=self._value("boiler_house.fuel.temperature", t),
            excess_air=u["oxygen"],
            air_mass_flow=air_mass.value_at(t)
            if air_mass is not None and self.loops["oxygen"].spec.mode == "manual"
            else None,
            air_temperature=self._value("boiler_house.combustion_air.temperature", t),
            air_humidity=self.air_humidity(t),
            oil_mass_flow=self._value("boiler_house.thermal_oil.mass_flow", t),
            oil_return_temperature=self._value("boiler_house.thermal_oil.return_temperature", t),
            ambient_temperature=self._value("ambient.temperature", t),
            bypass_position=bypass,
        )

    # --- evaluation ---------------------------------------------------------------------

    def controllers(
        self, t: float, z: FloatArray
    ) -> tuple[dict[str, float], dict[str, float], dict[str, dict[str, float]]]:
        """(outputs, integral rates, info per loop)."""
        meas = self.measurements(z)
        u: dict[str, float] = {}
        rates: dict[str, float] = {}
        info: dict[str, dict[str, float]] = {}
        for name, loop in self.loops.items():
            sp = loop.setpoint.value_at(t)
            integral = float(z[self.index[name]])
            manual = loop.manual_value(t)
            v, out = loop.pi.output(sp, meas[name], integral, manual)
            u[name] = float(out)
            rates[name] = float(loop.pi.integral_rate(sp, meas[name], integral, manual))
            info[name] = {
                "setpoint": sp,
                "measurement": meas[name],
                "output": float(out),
                "unsaturated": float(v),
            }
        return u, rates, info

    def couple(self, out_b: BoilerOutputs, dilution: float) -> None:
        """Hand the boiler outlet and the dilution air to the dryer's interfaces."""
        assert self.supply is not None and self.dilution is not None
        self.supply.current = out_b.flue_gas_to_dryer
        self.dilution.set(dilution)

    def evaluate(self, t: float, z: FloatArray, *, with_dryer: bool = True) -> PlantEvaluation:
        """One plant evaluation. ``with_dryer=False`` skips the dryer's right-hand side (its
        derivatives are returned as 0); nothing upstream depends on the dryer states."""
        u, rates, info = self.controllers(t, z)
        bypass, dilution = self.actuators(t, u)
        inputs = self.boiler_inputs(t, z, u, bypass)
        dxb, out_b = self.boiler.rhs(t, z[: self.nb], inputs)
        dz = np.empty(self.size)
        dz[: self.nb] = dxb
        for name in self.loops:
            dz[self.index[name]] = rates[name]
        flows = dict(out_b.boundary_flows)
        T_in = None
        if self.coupled:
            assert self.dryer is not None
            self.couple(out_b, dilution)
            inlet = self.dryer.inlet(t)
            T_in = inlet.temperature
            dz[self.i_drum_meas] = (T_in - z[self.i_drum_meas]) / DRUM_SENSOR_TIME_CONSTANT
            if with_dryer:
                dxd, flows_d = self.dryer.rhs_and_flows(t, z[self.dryer_slice])
                dz[self.dryer_slice] = dxd
            else:
                dz[self.dryer_slice] = 0.0
                flows_d = dict.fromkeys(DRYER_QUANTITIES, (0.0, 0.0))
            for q in DRYER_QUANTITIES:
                flows[f"dryer.{q}"] = flows_d[q]
            assert self.supply is not None
            flows["interface.mass"] = (
                out_b.flue_gas_to_dryer.mass_flow,
                self.supply.conditions_at(t).mass_flow,
            )
            flows["interface.energy"] = (
                out_b.results["flue_gas_to_dryer_enthalpy_flow"],
                inlet.flue_heat,
            )
        return PlantEvaluation(
            dz=dz,
            boiler=out_b,
            flows=flows,
            controller=info,
            bypass_position=bypass,
            dilution_air=dilution,
            drum_inlet_temperature=T_in,
        )

    def rhs_and_flows(
        self, t: float, z: FloatArray
    ) -> tuple[FloatArray, dict[str, tuple[float, float]]]:
        ev = self.evaluate(t, z)
        return ev.dz, ev.flows

    def storage(self, z: FloatArray) -> dict[str, float]:
        out = self.boiler.storage(z[: self.nb], self.spec.fuel)
        if self.coupled:
            assert self.dryer is not None
            for q, v in self.dryer.storage(z[self.dryer_slice]).items():
                out[f"dryer.{q}"] = v
        return out

    # --- initial states and solver support ----------------------------------------------

    def initial_outputs(self) -> dict[str, float]:
        """Controller outputs at a cold start: minimum fuel feed, mid-range excess air,
        both drum inlet actuators closed."""
        u = {}
        for name, loop in self.loops.items():
            s = loop.spec
            if s.manual_output is not None:
                u[name] = s.manual_output
            elif name == "oil_temperature":
                u[name] = s.output_min
            elif name == DRUM_LOOP:
                u[name] = s.output_min + s.split_value * (s.output_max - s.output_min)
            else:
                u[name] = loop_mid(s)
        return u

    def with_integrals(self, t: float, z: FloatArray, u: dict[str, float]) -> FloatArray:
        """Set the loop integrals so that the controllers output ``u`` at state ``z``."""
        meas = self.measurements(z)
        for name, loop in self.loops.items():
            z[self.index[name]] = loop.pi.initial_integral(
                u[name], loop.setpoint.value_at(t), meas[name]
            )
        return z

    def prepare_dryer(self, t: float, z: FloatArray, u: dict[str, float]) -> None:
        """Evaluate the boiler house once so the dryer's interfaces hold valid values."""
        bypass, dilution = self.actuators(t, u)
        _, out_b = self.boiler.rhs(t, z[: self.nb], self.boiler_inputs(t, z, u, bypass))
        self.couple(out_b, dilution)

    def initial_cold(self, t: float) -> FloatArray:
        u0 = self.initial_outputs()
        z = np.zeros(self.size)
        z[: self.nb] = self.boiler.initial_cold(self.boiler_inputs(t, z, u0, 0.0))
        if self.coupled:
            assert self.dryer is not None
            self.prepare_dryer(t, z, u0)
            z[self.dryer_slice] = self.dryer.initial_cold_empty(t)
            z[self.i_drum_meas] = self.dryer.inlet(t).temperature
        return self.with_integrals(t, z, u0)

    def scales(self, t: float = 0.0) -> FloatArray:
        s = np.ones(self.size)
        s[: self.nb] = self.boiler.scales()
        for name, loop in self.loops.items():
            s[self.index[name]] = max(abs(loop.spec.output_max), 1.0)
        if self.coupled:
            assert self.dryer is not None
            s[self.i_drum_meas] = 500.0
            s[self.dryer_slice] = self.dryer.scales(t)
        return s

    def jac_sparsity(self) -> csr_matrix:
        """Boiler house and controllers dense; the dryer depends on them (through its inlet)
        and on itself (banded); nothing upstream depends on the dryer."""
        n_up = self.dryer_slice.start
        if not self.coupled:
            return csr_matrix(np.ones((self.size, self.size), dtype=np.int8))
        assert self.dryer is not None
        pattern = lil_matrix((self.size, self.size), dtype=np.int8)
        pattern[:n_up, :n_up] = 1
        pattern[self.dryer_slice, :n_up] = 1
        core = self.dryer.jac_sparsity().tocoo()
        for i, j in zip(core.row, core.col, strict=True):
            pattern[n_up + i, n_up + j] = 1
        return csr_matrix(pattern)

    def breakpoints(self) -> FloatArray:
        prefixes: tuple[str, ...] = ("boiler_house.", "ambient.")
        if self.coupled:
            prefixes = (*prefixes, "product_feed.")
        points = [s.breakpoints() for name, s in self.signals.items() if name.startswith(prefixes)]
        return np.unique(np.concatenate(points)) if points else np.empty(0)

    def controller_settings(self) -> dict[str, Any]:
        return {name: loop.spec.model_dump(mode="json") for name, loop in self.loops.items()}


def loop_mid(spec: ControllerSpec) -> float:
    return 0.5 * (spec.output_min + spec.output_max)
