"""Boiler house model: right-hand side, outputs and storage (research.md R2-R7).

Internal state (layout from :class:`StateLayout`): feed stages, bed water and dry fuel,
furnace gas enthalpy (J), refractory hot-face and bulk temperatures, heater wall
temperatures and oil *specific enthalpies* (J/kg) per node, and the measured O2.

Energy accounting is exact: the bed stores the chemical energy of the dry fuel (LHV) and its
water at the 298.15 K liquid reference; the fuel's sensible enthalpy enters the gas with the
feed; the furnace gas, refractory, walls and oil store enthalpy; every flow leaving one node
enters the next. The gas in the convective heaters is quasi-static (its heat goes straight
to the walls), the furnace gas has a constant hold-up mass. Element balances (C, H, O, N, S)
close exactly because the products follow from the element flows.

This module must not import boidrytwin.dryer or boidrytwin.plant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix

from boidrytwin.boiler_house import bypass as bypass_mod
from boidrytwin.boiler_house import fuel_bed, furnace, heaters
from boidrytwin.boiler_house.config import (
    STEEL_SPECIFIC_HEAT,
    BoilerHouseConfiguration,
    ConvectiveHeater,
)
from boidrytwin.boiler_house.state import BoilerHouseState, StateLayout
from boidrytwin.interface.flue_gas import FlueGasConditions
from boidrytwin.properties import fuel as fp
from boidrytwin.properties import gas, water, wood
from boidrytwin.properties.gas import FloatArray
from boidrytwin.properties.thermal_oil import ThermalOil, get_oil

T_REF = gas.T_REF
H_LIQ_REF = float(water.h_liquid(T_REF))
AIR_Y = gas.mass_fractions(fp.DRY_AIR_X)
FURNACE_HOLDUP_TEMPERATURE = 1300.0  # K, fixes the constant furnace gas hold-up mass
OIL_INVENTORY_TEMPERATURE = 553.15  # K, density for the constant oil inventory
SMOOTH_AIR = 0.05  # kg/s, width of the smooth maximum on the air flow
MIN_EXCESS_AIR = 1.05  # air never below 1.05 × stoichiometric (keeps O2 ≥ 0)


def _smooth_max(a: float, b: float, width: float) -> float:
    d = (a - b) / width
    return float(b + width * (math.log1p(math.exp(-abs(d))) + max(d, 0.0)))


@dataclass(frozen=True)
class BoilerInputs:
    """Inputs at one time (SI). ``air_mass_flow`` (humid air) overrides ``excess_air``."""

    fuel: fp.FuelComposition
    fuel_command: float  # kg/s wet fuel
    moisture_wet: float
    fuel_temperature: float
    excess_air: float
    air_mass_flow: float | None
    air_temperature: float
    air_humidity: float  # kg/kg dry air
    oil_mass_flow: float
    oil_return_temperature: float
    ambient_temperature: float
    bypass_position: float


@dataclass
class BoilerOutputs:
    flue_gas_to_dryer: FlueGasConditions
    results: dict[str, Any]
    boundary_flows: dict[str, tuple[float, float]]
    o2_dry: float
    burnout: float
    o2_min_per_kg: float
    extra: dict[str, Any] = field(default_factory=dict)


class BoilerHouseModel:
    def __init__(
        self, config: BoilerHouseConfiguration, oil: str | ThermalOil = "shell_s2"
    ) -> None:
        self.config = config
        self.oil = get_oil(oil) if isinstance(oil, str) else oil
        self.layout = StateLayout.for_config(config)
        f = config.furnace
        M_ref = 0.0285
        self.furnace_holdup = (
            101_325.0 * f.gas_holdup_volume * M_ref / (gas.R_UNIVERSAL * FURNACE_HOLDUP_TEMPERATURE)
        )
        rho_oil = float(self.oil.density(OIL_INVENTORY_TEMPERATURE))
        rad = config.radiant
        self.wall_capacity = [rad.tube_mass * STEEL_SPECIFIC_HEAT]
        self.oil_mass = [rad.oil_volume * rho_oil]
        self.cells: list[
            tuple[int, Any]
        ] = []  # (heater number, 1-based, heater) per convective cell
        for j, h in enumerate(config.convective, start=2):
            for _ in range(h.n_cells):
                self.cells.append((j, h))
                self.wall_capacity.append(h.tube_mass * STEEL_SPECIFIC_HEAT / h.n_cells)
                self.oil_mass.append(h.oil_volume * rho_oil / h.n_cells)
        self.wall_capacity_arr = np.array(self.wall_capacity)
        self.oil_mass_arr = np.array(self.oil_mass)

    # --- conversions ------------------------------------------------------------------

    def _flue(self, inputs: BoilerInputs, burnout: float, evaporation: float) -> dict[str, Any]:
        """Air and product flows (mol/s) for the current burnout and evaporation."""
        fuel = inputs.fuel
        n_c, n_h2 = fuel.C / fp.M_C, fuel.H / fp.M_H2
        n_o2f, n_n2, n_s = fuel.O / fp.M_O2, fuel.N / fp.M_N2, fuel.S / fp.M_S
        o2_min = n_c + 0.5 * n_h2 + n_s - n_o2f
        stoich_air_mass = o2_min / fp.DRY_AIR_X[gas.I_O2] * fp.M_DRY_AIR  # kg dry air / kg dry fuel
        Y = inputs.air_humidity
        if inputs.air_mass_flow is not None:
            air_dry_mass = inputs.air_mass_flow / (1.0 + Y)
        else:
            air_dry_mass = inputs.excess_air * stoich_air_mass * burnout
        f = self.config.furnace
        air_dry_mass = _smooth_max(air_dry_mass, f.min_combustion_air / (1.0 + Y), SMOOTH_AIR)
        air_dry_mass = _smooth_max(
            air_dry_mass, MIN_EXCESS_AIR * stoich_air_mass * burnout, SMOOTH_AIR
        )
        air_dry = air_dry_mass / fp.M_DRY_AIR
        moles = air_dry * fp.DRY_AIR_X
        moles[gas.I_H2O] += air_dry_mass * Y / fp.M_WATER
        moles[gas.I_CO2] += burnout * n_c
        moles[gas.I_H2O] += burnout * n_h2 + evaporation / fp.M_WATER
        moles[gas.I_N2] += burnout * n_n2
        moles[gas.I_O2] -= burnout * o2_min
        moles[gas.I_AR] += burnout * n_s * fp.M_SO2 / gas.MOLAR_MASS[gas.I_AR]
        x = moles / moles.sum()
        dry = moles.sum() - moles[gas.I_H2O]
        lam = air_dry * fp.DRY_AIR_X[gas.I_O2] / (burnout * o2_min) if burnout > 1e-9 else math.nan
        return {
            "moles": moles,
            "x": x,
            "y": gas.mass_fractions(x),
            "mass_flow": float(np.sum(moles * gas.MOLAR_MASS)),
            "air_dry_mass": air_dry_mass,
            "air_water_mass": air_dry_mass * Y,
            "o2_dry": float(moles[gas.I_O2] / dry),
            "excess_air": lam,
            "o2_min": o2_min,
            "s_out": burnout * n_s,
        }

    def _bed_elements(
        self, inputs_fuel: fp.FuelComposition, m_dry: float, m_water: float
    ) -> FloatArray:
        c = inputs_fuel
        return np.array(
            [
                m_dry * c.C / fp.M_C,
                m_dry * 2 * c.H / fp.M_H2 + 2 * m_water / fp.M_WATER,
                m_dry * 2 * c.O / fp.M_O2 + m_water / fp.M_WATER,
                m_dry * 2 * c.N / fp.M_N2,
                m_dry * c.S / fp.M_S,
            ]
        )

    @staticmethod
    def _flow_elements(moles: FloatArray, s_moles: float) -> FloatArray:
        return np.array(
            [
                moles[gas.I_CO2],
                2 * moles[gas.I_H2O],
                2 * moles[gas.I_CO2] + moles[gas.I_H2O] + 2 * moles[gas.I_O2] + 2 * s_moles,
                2 * moles[gas.I_N2],
                s_moles,
            ]
        )

    def _air_elements(self, air_dry_mass: float, Y: float) -> FloatArray:
        air = air_dry_mass / fp.M_DRY_AIR * fp.DRY_AIR_X
        w = air_dry_mass * Y / fp.M_WATER
        return np.array(
            [
                air[gas.I_CO2],
                2 * w,
                2 * air[gas.I_O2] + 2 * air[gas.I_CO2] + w,
                2 * air[gas.I_N2],
                0.0,
            ]
        )

    # --- right-hand side --------------------------------------------------------------

    def rhs(
        self, t: float, x: FloatArray, inputs: BoilerInputs
    ) -> tuple[FloatArray, BoilerOutputs]:
        lay, cfg = self.layout, self.config
        f, rad = cfg.furnace, cfg.radiant
        fuel = inputs.fuel
        lhv = fuel.lhv_dry()
        dx = np.zeros_like(x)

        # fuel feed and bed
        stages = x[lay.feed]
        dx[lay.feed] = fuel_bed.feed_stage_rates(stages, inputs.fuel_command, f.feed_dead_time)
        delivered = max(float(stages[1]), 0.0)
        w = inputs.moisture_wet
        bed = fuel_bed.bed_rates(
            x[lay.bed_water],
            x[lay.bed_dry],
            delivered,
            w,
            f.bed_time_constant,
            f.water_time_constant,
        )
        dx[lay.bed_water] = bed.d_water
        dx[lay.bed_dry] = bed.d_dry
        B, E = bed.burnout, bed.evaporation

        # combustion products and furnace gas
        fl = self._flue(inputs, B, E)
        y, m_g = fl["y"], fl["mass_flow"]
        H_f = x[lay.furnace]
        T_f = furnace.gas_temperature(H_f / self.furnace_holdup, y, T_guess=1200.0)
        T_fuel, T_air = inputs.fuel_temperature, inputs.air_temperature
        h_ash = f.ash_specific_heat * (f.ash_discharge_temperature - T_REF)
        air_enthalpy = fl["air_dry_mass"] * float(gas.h_sensible_mass(T_air, AIR_Y)) + fl[
            "air_water_mass"
        ] * float(water.h_vapour(T_air))
        fuel_sensible = delivered * (
            (1 - w) * float(wood.h_dry(T_fuel)) + w * (float(water.h_liquid(T_fuel)) - H_LIQ_REF)
        )
        gas_in = B * lhv + E * H_LIQ_REF + fuel_sensible - B * fuel.ash * h_ash + air_enthalpy

        T_w = x[lay.wall]
        h_oil = x[lay.oil]
        T_oil = self.oil.temperature_from_enthalpy(h_oil)
        q_rad = furnace.radiant_heat(
            T_f,
            float(T_w[0]),
            rad.cold_plane_area,
            rad.flame_emissivity,
            rad.tube_area,
            rad.convective_htc,
        )
        q_rg, q_cond, q_rloss = furnace.refractory_flows(
            T_f, x[lay.refractory_hot], x[lay.refractory_bulk], inputs.ambient_temperature,
            f.refractory_gas_htc, f.refractory_area, f.refractory_conductance, f.loss_ua,
        )  # fmt: skip
        h_f_spec = float(gas.h_sensible_mass(T_f, y))
        dx[lay.furnace] = gas_in - m_g * h_f_spec - q_rad - q_rg
        C_r = f.refractory_specific_heat
        dx[lay.refractory_hot] = (q_rg - q_cond) / (f.refractory_mass_hot_face * C_r)
        dx[lay.refractory_bulk] = (q_cond - q_rloss) / (f.refractory_mass_bulk * C_r)

        # oil side: coefficients per node
        m_oil = inputs.oil_mass_flow
        n_nodes = lay.n_heater_nodes
        q_wo = np.zeros(n_nodes)
        film = np.zeros(n_nodes)
        vel = np.zeros(n_nodes)
        reyn = np.zeros(n_nodes)
        h_i0, vel[0], reyn[0] = heaters.oil_htc(
            m_oil, float(T_oil[0]), self.oil, rad.tube_inner_diameter, rad.n_parallel_passes
        )
        q_wo[0] = h_i0 * rad.inner_area * (T_w[0] - T_oil[0])
        film[0] = heaters.film_temperature(
            float(T_oil[0]), q_wo[0] / rad.inner_area, rad.peak_flux_factor, h_i0
        )

        # gas path through the convective heaters, with the bypass split
        b = cfg.bypass.starts_after_heater
        m_heat, m_byp = m_g, 0.0
        T_byp = T_f
        T_gas = T_f
        gas_after = {1: T_f}
        q_cell_loss = 0.0
        q_gas_wall = np.zeros(n_nodes)
        for k, (j, h) in enumerate(self.cells, start=1):
            first_cell_of_heater = k == 1 or self.cells[k - 2][0] != j
            if j == b + 1 and first_cell_of_heater:  # the bypass starts after heater b
                m_heat, m_byp = bypass_mod.split_flow(m_g, inputs.bypass_position)
                T_byp = T_gas
            if m_heat > 0:
                # casing loss of the cell, exact for a gas cooling towards ambient (stays
                # bounded when nearly all gas bypasses the heater)
                T_amb = inputs.ambient_temperature
                ntu = h.loss_ua / h.n_cells / (m_heat * float(gas.cp_mass(T_gas, y)))
                T_after = T_amb + (T_gas - T_amb) * math.exp(-ntu)
                q_cell_loss += m_heat * float(
                    gas.h_sensible_mass(T_gas, y) - gas.h_sensible_mass(T_after, y)
                )
                T_gas = T_after
            hg = heaters.gas_htc_bank(
                m_heat,
                T_gas,
                float(T_w[k]),
                fl["x"],
                h.tube_outer_diameter,
                h.free_flow_area,
                h.transverse_pitch / h.longitudinal_pitch,
                h.gas_emissivity,
            )
            UA = heaters.overall_gas_side(hg, h.fouling_resistance) * h.outer_area / h.n_cells
            T_gas, q_g = heaters.gas_cell(T_gas, float(T_w[k]), m_heat, y, UA)
            q_gas_wall[k] = q_g
            h_i, vel[k], reyn[k] = heaters.oil_htc(
                m_oil, float(T_oil[k]), self.oil, h.tube_inner_diameter, h.n_parallel_passes
            )
            A_i = h.inner_area / h.n_cells
            q_wo[k] = h_i * A_i * (T_w[k] - T_oil[k])
            film[k] = heaters.film_temperature(
                float(T_oil[k]), q_wo[k] / A_i, h.peak_flux_factor, h_i
            )
            gas_after[j] = T_gas
        q_gas_wall[0] = q_rad

        # bypass duct and mixing
        q_duct = (
            cfg.bypass.duct_loss_ua * inputs.bypass_position * (T_byp - inputs.ambient_temperature)
        )
        if m_byp > 0:
            T_byp = furnace.gas_temperature(
                float(gas.h_sensible_mass(T_byp, y)) - q_duct / m_byp, y, T_guess=T_byp
            )
        else:
            q_duct = 0.0
        m_out, T_out = bypass_mod.mix(m_heat, T_gas, m_byp, T_byp, y)

        # walls and oil (counter-current: oil enters the last cell, leaves heater 1)
        dx[lay.wall] = (q_gas_wall - q_wo) / self.wall_capacity_arr
        h_return = float(self.oil.enthalpy(inputs.oil_return_temperature))
        upstream = np.empty(n_nodes)
        upstream[1:] = heaters.oil_upstream(h_oil[1:], h_return)
        upstream[0] = h_oil[1]
        dx[lay.oil] = (m_oil * (upstream - h_oil) + q_wo) / self.oil_mass_arr

        o2_true = fl["o2_dry"]
        dx[lay.o2] = (o2_true - x[lay.o2]) / f.o2_sensor_time_constant

        # boundary flows (per second) for the balances
        h_out_spec = float(gas.h_sensible_mass(T_out, y))
        fuel_energy_in = delivered * (
            (1 - w) * (lhv + float(wood.h_dry(T_fuel))) + w * float(water.h_liquid(T_fuel))
        )
        losses = q_rloss + q_cell_loss + q_duct
        heat_to_oil = float(q_wo.sum())
        fuel_elements = delivered * (
            (1 - w) * self._bed_elements(fuel, 1.0, 0.0) + w * self._bed_elements(fuel, 0.0, 1.0)
        )
        boundary = {
            "mass": (delivered + fl["air_dry_mass"] + fl["air_water_mass"], m_out + B * fuel.ash),
            "energy": (
                fuel_energy_in + air_enthalpy,
                m_out * h_out_spec + B * fuel.ash * h_ash + losses + heat_to_oil,
            ),
            "oil_energy": (m_oil * h_return + heat_to_oil, m_oil * float(h_oil[0])),
        }
        el_in = fuel_elements + self._air_elements(fl["air_dry_mass"], inputs.air_humidity)
        el_out = self._flow_elements(fl["moles"], fl["s_out"])
        for i, name in enumerate(("C", "H", "O", "N", "S")):
            boundary[name] = (float(el_in[i]), float(el_out[i]))

        fuel_power = delivered * fuel.lhv_as_received(w)
        results: dict[str, Any] = {
            "fuel_feed": inputs.fuel_command,
            "fuel_delivered": delivered,
            "fuel_burnout_dry": B,
            "fuel_moisture_wet_basis": w,
            "heat_released": B * lhv,
            "load_fraction": fuel_power / f.rated_fuel_power,
            "excess_air_ratio": fl["excess_air"],
            "o2_dry": o2_true,
            "o2_dry_measured": float(x[lay.o2]),
            "combustion_air_flow": fl["air_dry_mass"] + fl["air_water_mass"],
            "furnace_temperature": T_f,
        }
        for j in range(1, len(cfg.heaters) + 1):
            results[f"gas_temperature_after_heater_{j}"] = gas_after.get(j, math.nan)
        node = 0
        for j, h in enumerate(cfg.heaters, start=1):
            n = h.n_cells if isinstance(h, ConvectiveHeater) else 1
            idx = slice(node, node + n)
            # oil leaves each heater at its first node (counter-current)
            results[f"oil_temperature_after_heater_{j}"] = float(T_oil[node])
            results[f"heat_to_oil_{j}"] = float(q_wo[idx].sum())
            node += n
        results.update(
            {
                "oil_outlet_temperature": float(T_oil[0]),
                "heat_to_oil": heat_to_oil,
                "max_film_temperature": float(film.max()),
                "min_oil_velocity": float(vel.min()),
                "min_oil_reynolds": float(reyn.min()),
                "losses": losses + B * fuel.ash * h_ash,
                "bypass_position": inputs.bypass_position,
                "flue_gas_to_dryer_mass_flow": m_out,
                "flue_gas_to_dryer_temperature": T_out,
                "flue_gas_to_dryer_enthalpy_flow": m_out * h_out_spec,
            }
        )
        conditions = FlueGasConditions(
            mass_flow=m_out,
            temperature=T_out,
            pressure=f.outlet_pressure,
            x=fl["x"],
            quality="good",
        )
        out = BoilerOutputs(
            flue_gas_to_dryer=conditions,
            results=results,
            boundary_flows=boundary,
            o2_dry=o2_true,
            burnout=B,
            o2_min_per_kg=fl["o2_min"],
        )
        return dx, out

    # --- storage, initial states, solver support --------------------------------------

    def storage(self, x: FloatArray, fuel: fp.FuelComposition | None = None) -> dict[str, float]:
        lay, f = self.layout, self.config.furnace
        fuel = fuel or self._fuel
        m_w, m_d = float(x[lay.bed_water]), float(x[lay.bed_dry])
        elements = self._bed_elements(fuel, m_d, m_w)
        energy = (
            m_d * fuel.lhv_dry()
            + m_w * H_LIQ_REF
            + float(x[lay.furnace])
            + f.refractory_specific_heat
            * (
                f.refractory_mass_hot_face * (x[lay.refractory_hot] - T_REF)
                + f.refractory_mass_bulk * (x[lay.refractory_bulk] - T_REF)
            )
            + float(np.sum(self.wall_capacity_arr * (x[lay.wall] - T_REF)))
        )
        out = {
            "mass": m_w + m_d,
            "energy": float(energy),
            "oil_energy": float(np.sum(self.oil_mass_arr * x[lay.oil])),
        }
        for i, name in enumerate(("C", "H", "O", "N", "S")):
            out[name] = float(elements[i])
        return out

    _fuel: fp.FuelComposition = fp.FuelComposition.default("wood_chips")

    def set_fuel(self, fuel: fp.FuelComposition) -> None:
        """Fuel used by :meth:`storage` when none is given (the scenario's fuel)."""
        self._fuel = fuel

    def initial_cold(self, inputs: BoilerInputs) -> FloatArray:
        lay = self.layout
        T_a = inputs.ambient_temperature
        x = np.zeros(lay.size)
        x[lay.furnace] = self.furnace_holdup * float(gas.h_sensible_mass(T_a, AIR_Y))
        x[lay.refractory_hot] = x[lay.refractory_bulk] = T_a
        x[lay.wall] = T_a
        x[lay.oil] = float(self.oil.enthalpy(T_a))
        x[lay.o2] = float(fp.DRY_AIR_X[gas.I_O2])
        self.set_fuel(inputs.fuel)
        return x

    def to_state(self, x: FloatArray, inputs: BoilerInputs) -> BoilerHouseState:
        lay = self.layout
        _, out = self.rhs(0.0, x, inputs)
        return BoilerHouseState(
            layout=lay,
            feed_stages=np.maximum(x[lay.feed], 0.0),
            bed_water=max(float(x[lay.bed_water]), 0.0),
            bed_dry_fuel=max(float(x[lay.bed_dry]), 0.0),
            furnace_temperature=float(out.results["furnace_temperature"]),
            refractory_hot_face=float(x[lay.refractory_hot]),
            refractory_bulk=float(x[lay.refractory_bulk]),
            heater_wall=x[lay.wall],
            heater_oil=self.oil.temperature_from_enthalpy(x[lay.oil]),
            o2_measured=min(max(float(x[lay.o2]), 0.0), 0.21),
        )

    def to_internal(self, state: BoilerHouseState, inputs: BoilerInputs) -> FloatArray:
        lay = self.layout
        x = state.to_vector()
        f = self.config.furnace
        bed = fuel_bed.bed_rates(
            state.bed_water,
            state.bed_dry_fuel,
            0.0,
            inputs.moisture_wet,
            f.bed_time_constant,
            f.water_time_constant,
        )
        y = self._flue(inputs, bed.burnout, bed.evaporation)["y"]
        x[lay.furnace] = self.furnace_holdup * float(
            gas.h_sensible_mass(state.furnace_temperature, y)
        )
        x[lay.oil] = self.oil.enthalpy(state.heater_oil)
        self.set_fuel(inputs.fuel)
        return x

    def scales(self) -> FloatArray:
        lay = self.layout
        s = np.ones(lay.size)
        s[lay.feed] = 1.0
        s[lay.bed_water] = 500.0
        s[lay.bed_dry] = 800.0
        s[lay.furnace] = self.furnace_holdup * 1.5e6
        s[lay.refractory_hot] = s[lay.refractory_bulk] = 1000.0
        s[lay.wall] = 500.0
        s[lay.oil] = 5e5
        s[lay.o2] = 0.1
        return s

    def jac_sparsity(self) -> csr_matrix:
        return csr_matrix(np.ones((self.layout.size, self.layout.size), dtype=np.int8))
