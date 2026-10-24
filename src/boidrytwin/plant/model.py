"""Plant model: subsystems and control loops in one state vector (contracts/plant-coupling.md).

Boiler-house-only plants (User Story 1): the boiler house with the oil-temperature loop
(fuel feed) and the O2 loop (excess air ratio, fed forward on the current burnout). The
bypass position is prescribed. Coupled plants (User Story 2) add the dryer and the drum
inlet split-range loop.

The plant is the only place that knows both subsystems; they exchange data only through
their interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix

from boidrytwin.boiler_house.model import BoilerHouseModel, BoilerInputs, BoilerOutputs
from boidrytwin.control.pi import PIController
from boidrytwin.properties import fuel as fp
from boidrytwin.properties import water
from boidrytwin.properties.gas import FloatArray
from boidrytwin.scenario.loader import LoadedScenario
from boidrytwin.scenario.schema import BoilerHouseSpec, ControllerSpec
from boidrytwin.scenario.timeseries import Signal

LOOPS = ("oil_temperature", "oxygen")
BOILER_QUANTITIES = ("mass", "C", "H", "O", "N", "S", "energy", "oil_energy")


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
        self.loops = {
            name: Loop(
                name,
                getattr(spec.controllers, name),
                PIController(getattr(spec.controllers, name)),
                sig[f"boiler_house.controllers.{name}.setpoint"],
                sig.get(f"boiler_house.controllers.{name}.manual_output"),
            )
            for name in LOOPS
        }
        self.nb = self.boiler.layout.size
        self.index = {name: self.nb + i for i, name in enumerate(LOOPS)}
        self.size = self.nb + len(LOOPS)

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
        return {
            "oil_temperature": self.oil_outlet_temperature(z),
            "oxygen": float(z[self.boiler.layout.o2]),
        }

    def boiler_inputs(self, t: float, z: FloatArray, u: dict[str, float]) -> BoilerInputs:
        air_mass = self.signals.get("boiler_house.combustion_air.mass_flow")
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
            bypass_position=self._value("boiler_house.bypass.position", t, 0.0),
        )

    # --- evaluation ---------------------------------------------------------------------

    def evaluate(self, t: float, z: FloatArray) -> PlantEvaluation:
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
        inputs = self.boiler_inputs(t, z, u)
        dxb, out_b = self.boiler.rhs(t, z[: self.nb], inputs)
        dz = np.empty(self.size)
        dz[: self.nb] = dxb
        for name in LOOPS:
            dz[self.index[name]] = rates[name]
        return PlantEvaluation(dz=dz, boiler=out_b, flows=out_b.boundary_flows, controller=info)

    def rhs_and_flows(
        self, t: float, z: FloatArray
    ) -> tuple[FloatArray, dict[str, tuple[float, float]]]:
        ev = self.evaluate(t, z)
        return ev.dz, ev.flows

    def storage(self, z: FloatArray) -> dict[str, float]:
        return self.boiler.storage(z[: self.nb], self.spec.fuel)

    # --- initial states and solver support ----------------------------------------------

    def initial_outputs(self) -> dict[str, float]:
        """Controller outputs at a cold start: minimum fuel feed, mid-range excess air."""
        oil, o2 = self.loops["oil_temperature"].spec, self.loops["oxygen"].spec
        return {
            "oil_temperature": oil.manual_output
            if oil.manual_output is not None
            else oil.output_min,
            "oxygen": o2.manual_output if o2.manual_output is not None else loop_mid(o2),
        }

    def with_integrals(self, t: float, z: FloatArray, u: dict[str, float]) -> FloatArray:
        """Set the loop integrals so that the controllers output ``u`` at state ``z``."""
        meas = self.measurements(z)
        for name, loop in self.loops.items():
            z[self.index[name]] = loop.pi.initial_integral(
                u[name], loop.setpoint.value_at(t), meas[name]
            )
        return z

    def initial_cold(self, t: float) -> FloatArray:
        u0 = self.initial_outputs()
        z = np.zeros(self.size)
        z[: self.nb] = self.boiler.initial_cold(self.boiler_inputs(t, z, u0))
        return self.with_integrals(t, z, u0)

    def scales(self) -> FloatArray:
        s = np.ones(self.size)
        s[: self.nb] = self.boiler.scales()
        for name, loop in self.loops.items():
            s[self.index[name]] = max(abs(loop.spec.output_max), 1.0)
        return s

    def jac_sparsity(self) -> csr_matrix:
        return csr_matrix(np.ones((self.size, self.size), dtype=np.int8))

    def breakpoints(self) -> FloatArray:
        points = [
            s.breakpoints()
            for name, s in self.signals.items()
            if name.startswith(("boiler_house.", "ambient."))
        ]
        return np.unique(np.concatenate(points)) if points else np.empty(0)

    def controller_settings(self) -> dict[str, Any]:
        return {name: loop.spec.model_dump(mode="json") for name, loop in self.loops.items()}


def loop_mid(spec: ControllerSpec) -> float:
    return 0.5 * (spec.output_min + spec.output_max)
