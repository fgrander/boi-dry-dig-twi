"""Fuel feed delay and fuel bed (T013; research.md R3)."""

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from boidrytwin.boiler_house import fuel_bed


def test_feed_delay_gain_and_mean_delay() -> None:
    theta = 120.0
    rate = fuel_bed.feed_stage_rates(np.array([0.0, 0.0]), command=1.0, dead_time=theta)
    assert rate[0] == pytest.approx(1.0 / (theta / 2))
    sol = solve_ivp(
        lambda t, y: fuel_bed.feed_stage_rates(y, 1.0, theta),
        (0, 3000),
        [0.0, 0.0],
        rtol=1e-10,
        atol=1e-12,
    )
    assert sol.y[1, -1] == pytest.approx(1.0, rel=1e-6)  # steady-state gain 1
    # mean delay of two equal lags = theta
    t = np.linspace(0, 3000, 30001)
    resp = solve_ivp(lambda t, y: fuel_bed.feed_stage_rates(y, 1.0, theta), (0, 3000), [0.0, 0.0],
                     t_eval=t, rtol=1e-10, atol=1e-12).y[1]  # fmt: skip
    mean_delay = np.trapezoid(1.0 - resp, t)
    assert mean_delay == pytest.approx(theta, rel=1e-3)


def test_bed_balances_and_steady_inventories() -> None:
    feed, w = 1.5, 0.45
    rates = fuel_bed.bed_rates(
        m_water=0.0, m_dry=0.0, feed=feed, moisture_wet=w, tau_bed=900, tau_water=600
    )
    assert rates.d_water == pytest.approx(w * feed) and rates.d_dry == pytest.approx((1 - w) * feed)
    steady = fuel_bed.steady_inventory(feed, w, tau_bed=900, tau_water=600)
    r = fuel_bed.bed_rates(steady[0], steady[1], feed, w, 900, 600)
    assert r.d_water == pytest.approx(0, abs=1e-12) and r.d_dry == pytest.approx(0, abs=1e-12)
    assert steady == pytest.approx((w * feed * 600, (1 - w) * feed * 900))


def test_mass_conservation() -> None:
    r = fuel_bed.bed_rates(
        m_water=30.0, m_dry=500.0, feed=1.2, moisture_wet=0.5, tau_bed=900, tau_water=600
    )
    assert r.d_water + r.d_dry == pytest.approx(1.2 - r.evaporation - r.burnout, rel=1e-12)
