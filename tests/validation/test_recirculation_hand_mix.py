"""Hand mix of the returned exhaust at the drum inlet (T012; SC-002, recirculation_case.md)."""

import math

import numpy as np
import pandas as pd
import pytest

from boidrytwin import load_scenario
from boidrytwin.dryer.gas_path import M_WATER, GasPath, air_density
from boidrytwin.dryer.simulate import simulate
from boidrytwin.properties import gas, water
from tests.integration.conftest import EXAMPLES

M_AIR = 0.0289647
AIR_X = np.array([0.7808, 0.2095, 0.0004, 0.0, 0.0093])  # N2, O2, CO2, H2O, other (Ar)


@pytest.fixture(scope="module")
def last() -> pd.Series:
    sim = simulate(load_scenario(EXAMPLES / "dryer_recirculation.toml"))
    return sim.results.iloc[-1]


def h_species(T: float) -> np.ndarray:
    return np.asarray(gas.h_sensible_species_mass(np.asarray(T)))


def hand_mix(r: pd.Series) -> dict[str, float]:
    # flue gas
    x_fg = np.array([0.705, 0.06, 0.105, 0.12, 0.01])
    y_fg = np.asarray(gas.mass_fractions(x_fg))
    w = y_fg[gas.I_H2O]
    dry_fg, water_fg = 8.0 * (1 - w), 8.0 * w
    y_fg_dry = y_fg.copy()
    y_fg_dry[gas.I_H2O] = 0.0
    y_fg_dry /= y_fg_dry.sum()
    H_fg = 8.0 * float(h_species(923.15) @ y_fg)
    # dilution air at ambient
    T_a, p = 283.15, 101_300.0
    p_w = 0.7 * float(water.p_sat(T_a))
    Y_air = M_WATER / M_AIR * p_w / (p - p_w)
    y_air = np.asarray(gas.mass_fractions(AIR_X))
    dry_air = 2.0 / (1 + Y_air)
    h_a = h_species(T_a)
    H_air = dry_air * float(h_a @ y_air + Y_air * h_a[gas.I_H2O])
    G_in = dry_fg + dry_air
    y_dry = (dry_fg * y_fg_dry + dry_air * y_air) / G_in
    # returned gas, from the run's results
    Y_out, T_out = float(r["exhaust_humidity"]), float(r["exhaust_temperature"])
    G_rec = float(r["recirculation_mass_flow"]) / (1 + Y_out)
    h_o = h_species(T_out)
    h_rec = float(h_o @ y_dry + Y_out * h_o[gas.I_H2O])
    # mix
    G = G_in + G_rec
    Y = (water_fg + dry_air * Y_air + G_rec * Y_out) / G
    H = (H_fg + H_air + G_rec * h_rec) / G

    def h(T: float) -> float:
        hs = h_species(T)
        return float(hs @ y_dry + Y * hs[gas.I_H2O]) - H

    lo, hi = 300.0, 1200.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if h(mid) < 0 else (lo, mid)
    moles = y_dry / gas.MOLAR_MASS
    moles[gas.I_H2O] += Y / gas.MOLAR_MASS[gas.I_H2O]
    return {"T": 0.5 * (lo + hi), "Y": Y, "x_O2": float(moles[gas.I_O2] / moles.sum()),
            "G_in": G_in, "y_dry": y_dry}  # fmt: skip


def test_drum_inlet_matches_the_hand_mix(last: pd.Series) -> None:
    hand = hand_mix(last)
    assert last["drum_inlet_gas_temperature"] == pytest.approx(hand["T"], abs=0.5)
    assert last["drum_inlet_humidity"] == pytest.approx(hand["Y"], rel=0.01)
    assert last["drum_inlet_x_O2"] == pytest.approx(hand["x_O2"], rel=0.01)


def test_mixing_chamber_pressure_matches_a_hand_gas_path(last: pd.Series) -> None:
    loaded = load_scenario(EXAMPLES / "dryer_recirculation.toml")
    spec = loaded.spec.recirculation
    assert spec is not None
    hand = hand_mix(last)
    Y, T = float(last["exhaust_humidity"]), float(last["exhaust_temperature"])
    M_dry = 1.0 / float((hand["y_dry"] / gas.MOLAR_MASS).sum())
    rho = 101_300.0 * (1 + Y) / (1 / M_dry + Y / M_WATER) / (gas.R_UNIVERSAL * T)
    path = GasPath(spec)
    m_drum = float(last["drum_outlet_mass_flow"])
    stack = 300.0 * (air_density(563.15) / rho) * (float(last["exhaust_mass_flow"]) / 10.7) ** 2
    drum = 1200.0 * (air_density(563.15) / rho) * (m_drum / 15.0) ** 2
    fan = path.fan_pressure_rise(m_drum / rho, float(last["exhaust_fan_speed"]), rho)
    assert last["mixing_chamber_pressure"] == pytest.approx(stack - fan + drum, abs=1.0)
    assert last["mixing_chamber_pressure"] == pytest.approx(-200.0, abs=50.0)
    assert math.isclose(last["exhaust_fan_volume_flow"], m_drum / rho, rel_tol=1e-6)
