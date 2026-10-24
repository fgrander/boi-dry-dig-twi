"""Dynamic cells-in-series model of a directly heated, co-current rotary drum dryer.

Research.md R1-R5. Per cell i (N cells along the drum) the integrated (internal) state is

    m_dp, m_da   dry solids, passive / active phase                  kg
    m_wp, m_wa   water in the solids, passive / active phase         kg
    U_s          enthalpy of the solids (both phases)                J
    H_g          enthalpy of the humid gas in the cell               J
    Y_g          gas humidity                                        kg water / kg dry gas
    T_sh         shell temperature                                   K

Enthalpies (rather than temperatures) are integrated so that mass and energy are conserved
by construction: every balance is written in flux form, and what leaves one cell enters the
next. Temperatures are recovered from the enthalpies (analytically for the solids, by
Newton iteration for the gas). The dry-gas hold-up of each cell is constant (the gas stays
about a second in a cell), so the dry-gas balance is quasi-steady.

The dryer reads its heat source only through :class:`FlueGasSupply` (constitution III).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix, lil_matrix

from boidrytwin.dryer import drying, transport
from boidrytwin.dryer import heat_transfer as ht
from boidrytwin.dryer.config import DryerConfiguration
from boidrytwin.dryer.state import N_FIELDS, DryerState
from boidrytwin.interface.flue_gas import FlueGasSupply, Quality
from boidrytwin.properties import gas, water, wood
from boidrytwin.properties.gas import FloatArray
from boidrytwin.scenario.timeseries import Signal

AIR_X = ht.AIR  # dry air mole fractions
AIR_Y = gas.mass_fractions(AIR_X)
M_AIR = float(gas.molar_mass_mixture(AIR_X))
T_REF = gas.T_REF

EPS_MASS = 1e-9  # kg, regularises moisture content of (nearly) empty cells
C_EPS = 1_000.0  # J/K, tiny heat capacity per cell so empty cells keep a temperature
X_MAX = 10.0
GAS_HOLDUP_TEMPERATURE = 450.0  # K, fixes the constant dry-gas hold-up mass per cell
PASSIVE_EXPOSURE = 0.1  # fraction of passive chip surface exposed to the gas. VERIFY
WALL_CONTACT_FRACTION = 0.25  # fraction of shell area under the bed when well filled
BED_FILL_REFERENCE = 0.05  # bed volume fraction at which the wall contact is complete
HEAT_LIMITED_UTILISATION = 0.9  # gas has given up this share of its usable temperature drop
NEWTON_ITERATIONS = 6

# internal state indices within a cell
I_MDP, I_MDA, I_MWP, I_MWA, I_US, I_HG, I_YG, I_TSH = range(N_FIELDS)


@dataclass(frozen=True)
class ModelInputs:
    """Everything the dryer needs from outside, as time functions (SI)."""

    flue_gas: FlueGasSupply
    dilution_air: Signal
    feed_mass_flow_wet: Signal
    feed_moisture_wet: Signal
    feed_temperature: Signal
    ambient_temperature: Signal
    ambient_relative_humidity: Signal
    ambient_pressure: Signal


@dataclass(frozen=True)
class Inlet:
    """Conditions at the drum inlet after mixing flue gas and dilution air."""

    dry_gas_flow: float  # kg/s
    humidity: float  # kg/kg dry gas
    enthalpy: float  # J per kg dry gas, relative to 298.15 K
    y_dry: FloatArray  # mass fractions of the dry gas (H2O = 0)
    M_dry: float  # kg/mol
    pressure: float  # Pa
    temperature: float  # K, mixed drum inlet temperature
    flue_heat: float  # W
    dilution_heat: float  # W
    flue_quality: Quality
    feed_dry: float  # kg/s
    feed_water: float  # kg/s
    feed_temperature: float  # K
    feed_enthalpy: float  # W
    ambient_temperature: float
    ambient_humidity: float

    @property
    def heat_supplied(self) -> float:
        """Heat content of flue gas plus dilution air relative to 298.15 K, W."""
        return self.flue_heat + self.dilution_heat


def humid_enthalpy(T: FloatArray, Y: FloatArray, y_dry: FloatArray) -> FloatArray:
    """Enthalpy of humid gas per kg dry gas, J/kg, relative to 298.15 K."""
    hs = gas.h_sensible_species_mass(T)
    return np.asarray(hs @ y_dry + Y * hs[..., gas.I_H2O])


def humid_cp(T: FloatArray, Y: FloatArray, y_dry: FloatArray) -> FloatArray:
    """Heat capacity of humid gas per kg dry gas, J/(kg K)."""
    cs = gas.cp_species_mass(T)
    return np.asarray(cs @ y_dry + Y * cs[..., gas.I_H2O])


def gas_temperature(H: FloatArray, Y: FloatArray, y_dry: FloatArray) -> FloatArray:
    """Invert :func:`humid_enthalpy` for T by Newton iteration (vectorised)."""
    T = T_REF + H / (1050.0 + 1900.0 * Y)
    T = np.clip(T, 200.0, 3000.0)
    for _ in range(NEWTON_ITERATIONS):
        T = T - (humid_enthalpy(T, Y, y_dry) - H) / humid_cp(T, Y, y_dry)
    return np.asarray(T)


class DrumDryerModel:
    """Right-hand side, diagnostics and balances of the drum dryer."""

    def __init__(self, config: DryerConfiguration, inputs: ModelInputs) -> None:
        self.config = config
        self.inputs = inputs
        self.n = config.n_cells
        c = config
        self.dz = c.cell_length
        self.gas_holdup = (
            101_325.0 * c.cell_volume * M_AIR / (gas.R_UNIVERSAL * GAS_HOLDUP_TEMPERATURE)
        )  # kg dry gas per cell
        self.shell_mass_cell = c.shell_mass / self.n
        self.shell_capacity = self.shell_mass_cell * c.shell_specific_heat  # J/K per cell
        self.area_inner = math.pi * c.diameter * self.dz
        self.area_outer = math.pi * (c.diameter + 2 * c.shell_thickness) * self.dz
        self.t_fall = transport.fall_time(c)
        self.chip_area_per_kg = 6.0 / (c.chip_equivalent_diameter * c.particle_density)

    # --- inputs ---------------------------------------------------------------------

    def inlet(self, t: float) -> Inlet:
        inp = self.inputs
        fg = inp.flue_gas.conditions_at(t)
        T_a = inp.ambient_temperature.value_at(t)
        p_a = inp.ambient_pressure.value_at(t)
        rh = inp.ambient_relative_humidity.value_at(t)
        Y_air = float(water.humidity_from_partial_pressure(rh * water.p_sat(T_a), p_a, M_AIR))

        y_fg = gas.mass_fractions(fg.x)
        w_fg = float(y_fg[gas.I_H2O])
        dry_fg = fg.mass_flow * (1.0 - w_fg)
        y_fg_dry = y_fg.copy()
        y_fg_dry[gas.I_H2O] = 0.0
        y_fg_dry /= y_fg_dry.sum()

        m_air = inp.dilution_air.value_at(t)
        dry_air = m_air / (1.0 + Y_air)
        G = dry_fg + dry_air
        if G > 0:
            y_dry = (dry_fg * y_fg_dry + dry_air * AIR_Y) / G
            Y_in = (fg.mass_flow * w_fg + dry_air * Y_air) / G
        else:
            y_dry, Y_in = y_fg_dry, w_fg / (1.0 - w_fg)

        flue_heat = fg.mass_flow * float(gas.h_sensible_mass(fg.temperature, y_fg))
        dilution_heat = dry_air * float(humid_enthalpy(np.asarray(T_a), np.asarray(Y_air), AIR_Y))
        H_in = (flue_heat + dilution_heat) / G if G > 0 else 0.0
        T_in = float(gas_temperature(np.asarray(H_in), np.asarray(Y_in), y_dry)) if G > 0 else T_a

        m_feed = inp.feed_mass_flow_wet.value_at(t)
        w_feed = inp.feed_moisture_wet.value_at(t)
        T_feed = inp.feed_temperature.value_at(t)
        feed_dry = m_feed * (1.0 - w_feed)
        X_feed = w_feed / (1.0 - w_feed)
        feed_enthalpy = feed_dry * float(
            wood.enthalpy_per_kg_dry(T_feed, X_feed, self.config.fibre_saturation_moisture)
        )
        mole_dry = gas.mole_fractions(np.where(y_dry > 0, y_dry, 0.0))
        return Inlet(
            dry_gas_flow=G,
            humidity=Y_in,
            enthalpy=H_in,
            y_dry=y_dry,
            M_dry=float(gas.molar_mass_mixture(mole_dry)),
            pressure=fg.pressure,
            temperature=T_in,
            flue_heat=flue_heat,
            dilution_heat=dilution_heat,
            flue_quality=fg.quality,
            feed_dry=feed_dry,
            feed_water=feed_dry * X_feed,
            feed_temperature=T_feed,
            feed_enthalpy=feed_enthalpy,
            ambient_temperature=T_a,
            ambient_humidity=Y_air,
        )

    # --- state helpers -----------------------------------------------------------------

    def _cells(self, y: FloatArray) -> FloatArray:
        return np.asarray(y, dtype=float).reshape(self.n, N_FIELDS)

    def _moisture(self, m_w: FloatArray, m_d: FloatArray) -> FloatArray:
        return np.clip(m_w / np.maximum(m_d, EPS_MASS), 0.0, X_MAX)

    def solids_temperature(
        self, U: FloatArray, m_dp: FloatArray, m_da: FloatArray, X_p: FloatArray, X_a: FloatArray
    ) -> FloatArray:
        fsp = self.config.fibre_saturation_moisture
        p2, p1, p0 = wood.enthalpy_coefficients(X_p, fsp)
        q2, q1, q0 = wood.enthalpy_coefficients(X_a, fsp)
        a2 = m_dp * p2 + m_da * q2
        a1 = m_dp * p1 + m_da * q1 + C_EPS
        a0 = m_dp * p0 + m_da * q0 - C_EPS * T_REF
        r = U - a0
        disc = np.maximum(a1**2 + 4.0 * a2 * r, 0.0)
        return np.asarray(2.0 * r / (a1 + np.sqrt(disc)))

    def solids_enthalpy(
        self, T: FloatArray, m_dp: FloatArray, m_da: FloatArray, X_p: FloatArray, X_a: FloatArray
    ) -> FloatArray:
        fsp = self.config.fibre_saturation_moisture
        return np.asarray(
            m_dp * wood.enthalpy_per_kg_dry(T, X_p, fsp)
            + m_da * wood.enthalpy_per_kg_dry(T, X_a, fsp)
            + C_EPS * (T - T_REF)
        )

    def to_internal(self, state: DryerState, t: float) -> FloatArray:
        if state.n_cells != self.n:
            raise ValueError(f"state has {state.n_cells} cells, model has {self.n}")
        y_dry = self.inlet(t).y_dry
        X_p = self._moisture(state.water_mass_passive, state.dry_mass_passive)
        X_a = self._moisture(state.water_mass_active, state.dry_mass_active)
        cols = np.empty((self.n, N_FIELDS))
        cols[:, I_MDP] = state.dry_mass_passive
        cols[:, I_MDA] = state.dry_mass_active
        cols[:, I_MWP] = state.water_mass_passive
        cols[:, I_MWA] = state.water_mass_active
        cols[:, I_US] = self.solids_enthalpy(
            state.solids_temperature, state.dry_mass_passive, state.dry_mass_active, X_p, X_a
        )
        cols[:, I_HG] = self.gas_holdup * humid_enthalpy(
            state.gas_temperature, state.gas_humidity, y_dry
        )
        cols[:, I_YG] = state.gas_humidity
        cols[:, I_TSH] = state.shell_temperature
        return cols.reshape(-1)

    def to_state(self, y: FloatArray, t: float) -> DryerState:
        c = self._cells(y)
        y_dry = self.inlet(t).y_dry
        m_dp, m_da = np.maximum(c[:, I_MDP], 0.0), np.maximum(c[:, I_MDA], 0.0)
        m_wp, m_wa = np.maximum(c[:, I_MWP], 0.0), np.maximum(c[:, I_MWA], 0.0)
        X_p, X_a = self._moisture(m_wp, m_dp), self._moisture(m_wa, m_da)
        Y = np.maximum(c[:, I_YG], 0.0)
        return DryerState(
            dry_mass_passive=m_dp,
            dry_mass_active=m_da,
            water_mass_passive=m_wp,
            water_mass_active=m_wa,
            solids_temperature=self.solids_temperature(c[:, I_US], m_dp, m_da, X_p, X_a),
            gas_temperature=gas_temperature(c[:, I_HG] / self.gas_holdup, Y, y_dry),
            gas_humidity=Y,
            shell_temperature=c[:, I_TSH],
        )

    def initial_cold_empty(self, t: float) -> FloatArray:
        """No solids; gas, solids and shell at ambient temperature (gas at ambient humidity)."""
        inlet = self.inlet(t)
        T_a = np.full(self.n, inlet.ambient_temperature)
        zeros = np.zeros(self.n)
        state = DryerState(
            dry_mass_passive=zeros,
            dry_mass_active=zeros,
            water_mass_passive=zeros,
            water_mass_active=zeros,
            solids_temperature=T_a,
            gas_temperature=T_a,
            gas_humidity=np.full(self.n, inlet.ambient_humidity),
            shell_temperature=T_a,
        )
        return self.to_internal(state, t)

    def scales(self, t: float) -> FloatArray:
        """Typical magnitude of each internal state, for solver tolerances."""
        inlet = self.inlet(t)
        tau = transport.saeman_mitchell_residence_time(self.config)
        m_ref = max(inlet.feed_dry * tau / self.n, 1.0)
        w_ref = max(inlet.feed_water * tau / self.n, 1.0)
        u_ref = (m_ref * 1500.0 + w_ref * 4180.0) * 100.0
        h_ref = self.gas_holdup * 1100.0 * 500.0
        cell = np.array([m_ref, 0.1 * m_ref, w_ref, 0.1 * w_ref, u_ref, h_ref, 0.1, 500.0])
        return np.tile(cell, self.n)

    def jac_sparsity(self) -> csr_matrix:
        """Cell i depends only on cells i and i-1 (co-current flow)."""
        size = self.n * N_FIELDS
        pattern = lil_matrix((size, size), dtype=np.int8)
        for i in range(self.n):
            rows = slice(i * N_FIELDS, (i + 1) * N_FIELDS)
            first = max(i - 1, 0) * N_FIELDS
            pattern[rows, first : (i + 1) * N_FIELDS] = 1
        return csr_matrix(pattern)

    # --- physics ---------------------------------------------------------------------

    def _evaluate(self, t: float, y: FloatArray) -> dict[str, Any]:
        c = self.config
        inlet = self.inlet(t)
        cells = self._cells(y)
        m_dp, m_da = np.maximum(cells[:, I_MDP], 0.0), np.maximum(cells[:, I_MDA], 0.0)
        m_wp, m_wa = np.maximum(cells[:, I_MWP], 0.0), np.maximum(cells[:, I_MWA], 0.0)
        U_s, H_g = cells[:, I_US], cells[:, I_HG]
        Y = np.maximum(cells[:, I_YG], 0.0)
        T_sh = cells[:, I_TSH]
        X_p, X_a = self._moisture(m_wp, m_dp), self._moisture(m_wa, m_da)
        y_dry = inlet.y_dry
        p = inlet.pressure
        G = inlet.dry_gas_flow

        T_s = self.solids_temperature(U_s, m_dp, m_da, X_p, X_a)
        Hs = H_g / self.gas_holdup
        T_g = gas_temperature(Hs, Y, y_dry)

        # gas properties per cell
        n_dry = y_dry / gas.MOLAR_MASS
        n_w = Y / gas.MOLAR_MASS[gas.I_H2O]
        moles = np.tile(n_dry, (self.n, 1))
        moles[:, gas.I_H2O] += n_w
        x = moles / moles.sum(axis=1, keepdims=True)
        M_wet = (1.0 + Y) / moles.sum(axis=1)
        rho = p * M_wet / (gas.R_UNIVERSAL * T_g)
        mu = gas.viscosity(T_g, x)
        k_g = gas.conductivity(T_g, x)
        cp_hum = humid_cp(T_g, Y, y_dry)
        pr = cp_hum / (1.0 + Y) * mu / k_g
        u_g = G * (1.0 + Y) / (rho * c.cross_section)

        # solids transport
        rates = transport.transport_rates(c, X_a, rho, u_g)
        flows = transport.solids_flows(c, rates, m_dp, m_da)
        dmp, dma = transport.mass_derivatives(inlet.feed_dry, flows)
        dwp, dwa = transport.water_derivatives(inlet.feed_water, flows, X_p, X_a)

        # gas -> solids heat and mass transfer
        d = c.chip_equivalent_diameter
        u_fall = 0.5 * transport.G_ACCEL * self.t_fall
        re_a = rho * np.sqrt(u_g**2 + u_fall**2) * d / mu
        re_p = rho * np.maximum(u_g, 0.1) * d / mu
        h_a = ht.nu_sphere_gnielinski(re_a, pr) * k_g / d
        h_p = ht.nu_sphere_gnielinski(re_p, pr) * k_g / d
        A_a = self.chip_area_per_kg * m_da
        A_p = PASSIVE_EXPOSURE * self.chip_area_per_kg * m_dp
        C_a = c.heat_transfer_multiplier
        Q_a = ht.gas_solid_heat(C_a, h_a * A_a, T_g, T_s)
        Q_p = ht.gas_solid_heat(C_a, h_p * A_p, T_g, T_s)

        M_dry = inlet.M_dry
        Y_sat = drying.saturation_humidity(T_s, p, M_dry)
        p_w = water.partial_pressure_from_humidity(Y, p, M_dry)
        rh_s = np.clip(p_w / water.p_sat(np.minimum(T_s, 640.0)), 0.0, 0.999)
        X_e = wood.emc(np.minimum(T_s, c.emc_data_limit), rh_s)
        X_cr, n_exp = c.critical_moisture_dry_basis, c.falling_rate_exponent
        f_a = drying.rate_factor(X_a, X_e, X_cr, n_exp)
        f_p = drying.rate_factor(X_p, X_e, X_cr, n_exp)
        E_a, cond_a = drying.evaporation(
            C_a * ht.mass_transfer_coefficient(h_a, cp_hum) * A_a, Y_sat, Y, f_a
        )
        E_p, cond_p = drying.evaporation(
            C_a * ht.mass_transfer_coefficient(h_p, cp_hum) * A_p, Y_sat, Y, f_p
        )
        E = E_a + E_p
        h_v_s = water.h_vapour(T_s)

        # shell
        re_d = rho * u_g * c.diameter / mu
        h_in = ht.nu_pipe(re_d, pr) * k_g / c.diameter
        Q_gsh = h_in * self.area_inner * (T_g - T_sh)
        fill = np.minimum(1.0, (m_dp / c.bulk_density) / (BED_FILL_REFERENCE * c.cell_volume))
        A_ws = WALL_CONTACT_FRACTION * self.area_inner * fill
        Q_shs = c.shell_contact_htc * A_ws * (T_sh - T_s)
        Q_loss = ht.shell_loss(
            T_sh,
            inlet.ambient_temperature,
            area=self.area_outer,
            emissivity=c.shell_emissivity,
            diameter=c.diameter + 2 * c.shell_thickness,
            insulation_thickness=c.insulation_thickness,
            insulation_conductivity=c.insulation_conductivity,
        )

        # solids enthalpy fluxes
        fsp = c.fibre_saturation_moisture
        e_p = wood.enthalpy_per_kg_dry(T_s, X_p, fsp)
        e_a = wood.enthalpy_per_kg_dry(T_s, X_a, fsp)
        out_s = flows.passive_out * e_p + flows.active_out * e_a
        in_s = np.empty(self.n)
        in_s[0] = inlet.feed_enthalpy
        in_s[1:] = out_s[:-1]

        # gas fluxes (co-current)
        Y_up = np.concatenate(([inlet.humidity], Y[:-1]))
        H_up = np.concatenate(([inlet.enthalpy], Hs[:-1]))

        deriv = np.empty((self.n, N_FIELDS))
        deriv[:, I_MDP] = dmp
        deriv[:, I_MDA] = dma
        deriv[:, I_MWP] = dwp - E_p
        deriv[:, I_MWA] = dwa - E_a
        deriv[:, I_US] = in_s - out_s + Q_a + Q_p + Q_shs - E * h_v_s
        deriv[:, I_HG] = G * (H_up - Hs) + E * h_v_s - Q_a - Q_p - Q_gsh
        deriv[:, I_YG] = (G * (Y_up - Y) + E) / self.gas_holdup
        deriv[:, I_TSH] = (Q_gsh - Q_shs - Q_loss) / self.shell_capacity

        return {
            "deriv": deriv.reshape(-1),
            "inlet": inlet,
            "T_s": T_s,
            "T_g": T_g,
            "Y": Y,
            "x": x,
            "X_p": X_p,
            "X_a": X_a,
            "T_sh": T_sh,
            "m_dp": m_dp,
            "m_da": m_da,
            "m_wp": m_wp,
            "m_wa": m_wa,
            "flows": flows,
            "rates": rates,
            "E": E,
            "Q_gs": Q_a + Q_p,
            "Q_shs": Q_shs,
            "Q_gsh": Q_gsh,
            "Q_loss": Q_loss,
            "out_s": out_s,
            "Hs": Hs,
            "condensing": cond_a | cond_p,
            "u_g": u_g,
            "UA_gas_shell": h_in * self.area_inner,
            "UA_shell_solids": c.shell_contact_htc * A_ws,
        }

    def rhs(self, t: float, y: FloatArray) -> FloatArray:
        return np.asarray(self._evaluate(t, y)["deriv"])

    def rhs_and_flows(
        self, t: float, y: FloatArray
    ) -> tuple[FloatArray, dict[str, tuple[float, float]]]:
        """Derivatives and boundary flows from one evaluation (for the flow accumulators)."""
        ev = self._evaluate(t, y)
        return np.asarray(ev["deriv"]), self._boundary(ev)

    def time_constants(self, t: float, y: FloatArray) -> tuple[float, float]:
        """(mean solids residence time, shell time constant), s."""
        ev = self._evaluate(t, y)
        inlet: Inlet = ev["inlet"]
        holdup = float((ev["m_dp"] + ev["m_da"]).sum())
        tau_res = holdup / inlet.feed_dry if inlet.feed_dry > 0 else math.inf
        dT = ev["T_sh"] - inlet.ambient_temperature
        loss_conductance = np.where(
            np.abs(dT) > 1e-6, ev["Q_loss"] / np.where(dT == 0, 1.0, dT), 0.0
        )
        conductance = ev["UA_gas_shell"] + ev["UA_shell_solids"] + loss_conductance
        tau_shell = float(self.shell_capacity / np.mean(conductance))
        return tau_res, tau_shell

    def diagnostics(self, t: float, y: FloatArray) -> dict[str, Any]:
        """DryerResults columns (data-model.md §4) at one time."""
        ev = self._evaluate(t, y)
        inlet: Inlet = ev["inlet"]
        flows: transport.SolidsFlows = ev["flows"]
        product_dry = flows.outlet
        product_water = transport.outlet_water(flows, ev["X_p"], ev["X_a"])
        total_out = product_dry + product_water
        evap = float(ev["E"].sum())
        Y_out = float(ev["Y"][-1])
        T_out = float(ev["T_g"][-1])
        dew = float(water.dew_point(Y_out, inlet.pressure, inlet.M_dry))
        x_out = ev["x"][-1]
        result: dict[str, Any] = {
            "product_dry_mass_flow": product_dry,
            "product_moisture_wet_basis": product_water / total_out
            if total_out > 1e-9
            else math.nan,
            "product_temperature": float(ev["T_s"][-1]),
            "evaporation_rate": evap,
            "exhaust_mass_flow": inlet.dry_gas_flow * (1.0 + Y_out),
            "exhaust_temperature": T_out,
            "exhaust_humidity": Y_out,
            **{
                f"exhaust_x_{name}": float(v)
                for name, v in zip(("N2", "O2", "CO2", "H2O", "other"), x_out, strict=True)
            },
            "exhaust_dew_point": dew,
            "drum_inlet_gas_temperature": inlet.temperature,
            "heat_supplied": inlet.heat_supplied,
            "heat_used_for_drying": float((ev["Q_gs"] + ev["Q_shs"]).sum()),
            "shell_heat_loss": float(ev["Q_loss"].sum()),
            "specific_energy": inlet.heat_supplied / evap if evap > 1e-9 else math.nan,
            "solids_holdup": float((ev["m_dp"] + ev["m_da"] + ev["m_wp"] + ev["m_wa"]).sum()),
            "heat_limited": bool(
                product_dry > 1e-6
                and inlet.temperature - T_out
                >= HEAT_LIMITED_UTILISATION * (inlet.temperature - float(ev["T_s"][-1]))
            ),
            "out_of_range": False,
            # exhaust only: cold chips at the inlet below the gas dew point are normal
            "condensation_risk": bool(T_out - dew < self.config.min_dew_point_margin),
            "input_quality": inlet.flue_quality,
            "_max_solids_temperature": float(ev["T_s"].max()),  # range checks only
        }
        return result

    def profiles(self, t: float, y: FloatArray) -> dict[str, FloatArray]:
        """Per-cell profiles for ``profiles.csv``."""
        ev = self._evaluate(t, y)
        m_d = ev["m_dp"] + ev["m_da"]
        m_w = ev["m_wp"] + ev["m_wa"]
        with np.errstate(invalid="ignore", divide="ignore"):
            moisture = np.where(m_d + m_w > 1e-9, m_w / (m_d + m_w), np.nan)
        return {
            "solids_temperature": ev["T_s"],
            "gas_temperature": ev["T_g"],
            "gas_humidity": ev["Y"],
            "moisture_wet_basis": moisture,
            "solids_holdup": m_d + m_w,
            "shell_temperature": ev["T_sh"],
        }

    # --- balances (used by checks.balances, US3) -------------------------------------

    def storage(self, y: FloatArray) -> dict[str, float]:
        """Stored amounts in the drum: kg for masses, J for energy (relative to 298.15 K)."""
        c = self._cells(y)
        return {
            "dry_solids": float((c[:, I_MDP] + c[:, I_MDA]).sum()),
            "water": float((c[:, I_MWP] + c[:, I_MWA]).sum() + self.gas_holdup * c[:, I_YG].sum()),
            "gas": self.gas_holdup * self.n,
            "energy": float(
                c[:, I_US].sum()
                + c[:, I_HG].sum()
                + self.shell_capacity * (c[:, I_TSH] - T_REF).sum()
            ),
        }

    def boundary_flows(self, t: float, y: FloatArray) -> dict[str, tuple[float, float]]:
        """(inflow, outflow) rates across the drum boundary: kg/s and W."""
        return self._boundary(self._evaluate(t, y))

    def _boundary(self, ev: dict[str, Any]) -> dict[str, tuple[float, float]]:
        inlet: Inlet = ev["inlet"]
        flows: transport.SolidsFlows = ev["flows"]
        G = inlet.dry_gas_flow
        product_water = transport.outlet_water(flows, ev["X_p"], ev["X_a"])
        return {
            "dry_solids": (inlet.feed_dry, flows.outlet),
            "water": (
                inlet.feed_water + G * inlet.humidity,
                product_water + G * float(ev["Y"][-1]),
            ),
            "gas": (G, G),
            "energy": (
                inlet.feed_enthalpy + G * inlet.enthalpy,
                float(ev["out_s"][-1]) + G * float(ev["Hs"][-1]) + float(ev["Q_loss"].sum()),
            ),
        }
