"""Combustion hand calculation (T020, SC-001; see combustion_case.md)."""

import numpy as np
import pytest

from boidrytwin import load_scenario
from boidrytwin.plant.simulate import simulate_plant
from boidrytwin.properties import water
from tests.integration.conftest import EXAMPLES


def _hand(w: float, o2_dry_target: float, T_air: float, rh: float, p: float) -> dict[str, float]:
    c, h, n, s = 0.513, 0.061, 0.004, 0.0002
    o = 1 - c - h - n - s - 0.013
    nC, nH2, nO2f, nN2, nS = c / 0.012011, h / 0.002016, o / 0.031998, n / 0.028014, s / 0.03206
    o2min = nC + nH2 / 2 + nS - nO2f
    M_air = 0.7808 * 0.028014 + 0.2095 * 0.031998 + 0.0004 * 0.044009 + 0.0093 * 0.03995
    p_w = rh * float(water.p_sat(T_air))
    Y = 0.018015 / M_air * p_w / (p - p_w)
    X = w / (1 - w)

    def products(lam: float) -> np.ndarray:
        A = lam * o2min / 0.2095
        return np.array([
            0.7808 * A + nN2,
            (lam - 1) * o2min,
            nC + 0.0004 * A,
            nH2 + X / 0.018015 + A * M_air * Y / 0.018015,
            0.0093 * A + nS * (0.03206 + 0.031998) / 0.03995,
        ])  # fmt: skip

    def o2_dry(lam: float) -> float:
        pr = products(lam)
        return pr[1] / (pr.sum() - pr[3])

    lo, hi = 1.0, 3.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if o2_dry(mid) < o2_dry_target else (lo, mid)
    lam = (lo + hi) / 2
    pr = products(lam)
    x = pr / pr.sum()
    M = np.array([0.028014, 0.031998, 0.044009, 0.018015, 0.03995])
    return {"lambda": lam, "x_N2": x[0], "x_O2": x[1], "x_CO2": x[2], "x_H2O": x[3],
            "mass_per_kg_dry": float(np.sum(pr * M))}  # fmt: skip


def test_furnace_flue_gas_matches_hand_calculation() -> None:
    sim = simulate_plant(load_scenario(EXAMPLES / "boiler_house_only.toml"))
    last = sim.results.iloc[-1]
    hand = _hand(0.45, 0.07, 293.15, 0.60, 101_300.0)
    flue = sim.flue_gas_to_dryer.iloc[-1]
    for key in ("x_N2", "x_O2", "x_CO2", "x_H2O"):
        assert flue[key] == pytest.approx(hand[key], abs=0.001), key
    assert last["excess_air_ratio"] == pytest.approx(hand["lambda"], rel=2e-3)
    # the bed water evaporates at the same rate as it is fed at steady state
    expected_flow = last["fuel_burnout_dry"] * hand["mass_per_kg_dry"]
    assert last["flue_gas_to_dryer_mass_flow"] == pytest.approx(expected_flow, rel=1e-3)
