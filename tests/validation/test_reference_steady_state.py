"""Hand balance of the reference steady state (T049; see reference_case.md)."""

from pathlib import Path

import numpy as np
import pytest

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import simulate
from boidrytwin.properties import gas, water, wood
from tests.integration.conftest import make_variant

M_AIR = 0.028965
AIR_X = np.array([0.7808, 0.2095, 0.0004, 0.0, 0.0093])


def _humid_enthalpy(T: float, Y: float, y_dry: np.ndarray) -> float:
    hs = gas.h_sensible_species_mass(T)
    return float(hs @ y_dry + Y * hs[gas.I_H2O])


def test_steady_state_matches_hand_balance(tmp_path: Path) -> None:
    path = make_variant(
        tmp_path,
        replace={'kind = "cold_empty"': 'kind = "steady_state"'},
        end="2026-01-01T00:10:00Z",
    )
    res = simulate(load_scenario(path)).results.iloc[-1]
    w_out = float(res["product_moisture_wet_basis"])
    T_p = float(res["product_temperature"])
    Q_loss = float(res["shell_heat_loss"])

    # 1. feed
    F = 10_000 / 3600 * 0.5
    X_in = 1.0
    # 2. flue gas
    x_fg = np.array([0.705, 0.06, 0.105, 0.12, 0.01])
    y_fg = gas.mass_fractions(x_fg)
    w = y_fg[gas.I_H2O]
    G_fg = 8.0 * (1 - w)
    y_fg_dry = y_fg.copy()
    y_fg_dry[gas.I_H2O] = 0
    y_fg_dry /= y_fg_dry.sum()
    # 3. dilution air
    p_w = 0.70 * float(water.p_sat(283.15))
    Y_air = 0.018015 / M_AIR * p_w / (101_300.0 - p_w)
    G_air = 2.0 / (1 + Y_air)
    y_air = gas.mass_fractions(AIR_X)
    # 4. inlet
    G = G_fg + G_air
    Y_in = (8.0 * w + G_air * Y_air) / G
    y_dry = (G_fg * y_fg_dry + G_air * y_air) / G
    Q_in = 8.0 * float(gas.h_sensible_mass(923.15, y_fg)) + G_air * _humid_enthalpy(
        283.15, Y_air, y_air
    )
    # 5.-6. evaporation and humidity
    X_out = w_out / (1 - w_out)
    E = F * (X_in - X_out)
    Y_ex = Y_in + E / G
    # 7. exhaust temperature
    rhs = (
        Q_in
        + F * float(wood.enthalpy_per_kg_dry(283.15, X_in))
        - F * float(wood.enthalpy_per_kg_dry(T_p, X_out))
        - Q_loss
    )
    lo, hi = 280.0, 1200.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if G * _humid_enthalpy(mid, Y_ex, y_dry) > rhs:
            hi = mid
        else:
            lo = mid
    T_ex = 0.5 * (lo + hi)

    assert res["evaporation_rate"] == pytest.approx(E, rel=5e-3)
    assert res["exhaust_humidity"] == pytest.approx(Y_ex, rel=1e-2)
    assert res["exhaust_temperature"] == pytest.approx(T_ex, abs=2.0)
    assert res["specific_energy"] == pytest.approx(Q_in / E, rel=2e-2)
    assert res["heat_supplied"] == pytest.approx(Q_in, rel=1e-6)
