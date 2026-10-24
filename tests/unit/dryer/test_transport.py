"""Two-phase solids transport (T037; research.md R2)."""

import math

import numpy as np
import pytest

from boidrytwin.dryer import transport
from boidrytwin.dryer.config import DryerConfiguration

CFG = DryerConfiguration(
    length=20.0,
    diameter=4.0,
    slope=math.radians(2),
    shell_mass=60_000.0,
    rotation_speed=4 * 2 * math.pi / 60,
)
N = CFG.n_cells


def _rates(u_g: float = 1.0, X: float = 0.5) -> transport.TransportRates:
    return transport.transport_rates(CFG, X_active=np.full(N, X), rho_g=0.8, u_g=np.full(N, u_g))


def test_dry_mass_is_conserved_between_phases_and_cells() -> None:
    rng = np.random.default_rng(3)
    m_p, m_a = rng.uniform(10, 60, N), rng.uniform(0, 6, N)
    flows = transport.solids_flows(CFG, _rates(), m_p, m_a)
    dmp, dma = transport.mass_derivatives(1.4, flows)
    assert np.sum(dmp + dma) == pytest.approx(1.4 - flows.outlet, rel=1e-12)


def test_water_moves_with_dry_mass() -> None:
    rng = np.random.default_rng(4)
    m_p, m_a = rng.uniform(10, 60, N), rng.uniform(0, 6, N)
    X_p, X_a = rng.uniform(0.2, 1.0, N), rng.uniform(0.2, 1.0, N)
    flows = transport.solids_flows(CFG, _rates(), m_p, m_a)
    dwp, dwa = transport.water_derivatives(1.4, flows, X_p, X_a)
    out = flows.passive_out[-1] * X_p[-1] + flows.active_out[-1] * X_a[-1]
    assert np.sum(dwp + dwa) == pytest.approx(1.4 - out, rel=1e-12)
    assert transport.outlet_water(flows, X_p, X_a) == pytest.approx(out)


def test_empty_drum_without_feed_has_no_flows() -> None:
    flows = transport.solids_flows(CFG, _rates(), np.zeros(N), np.zeros(N))
    dmp, dma = transport.mass_derivatives(0.0, flows)
    assert not np.any(dmp) and not np.any(dma) and flows.outlet == 0.0


def test_drag_increases_with_gas_velocity_and_lighter_particles() -> None:
    slow, fast = _rates(u_g=0.5), _rates(u_g=3.0)
    assert np.all(fast.v_active > slow.v_active)
    wet, dry = _rates(X=1.0), _rates(X=0.1)
    assert np.all(dry.v_active > wet.v_active)


def test_without_gas_reproduces_saeman_mitchell_with_f_pi() -> None:
    rates = _rates(u_g=0.0)
    tau = transport.steady_residence_time(CFG, rates)
    assert tau == pytest.approx(transport.saeman_mitchell_residence_time(CFG, f=math.pi), rel=1e-9)


def test_residence_time_within_friedman_marshall_band() -> None:
    tau = transport.steady_residence_time(CFG, _rates(u_g=1.0))
    fm = transport.friedman_marshall_residence_time(CFG)
    assert 0.5 * fm < tau < 2.0 * fm
