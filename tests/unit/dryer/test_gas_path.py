"""Quasi-steady gas path: fan, resistances, damper and the recirculated flow (T005).

FR-016, FR-017; research R2, R3. Hand values: quadratic through the curve points, fan laws,
constant loss coefficients, and an inverse case with a linear damper where the recirculated
flow is chosen first and the damper position computed from it by hand.
"""

import itertools
import math

import numpy as np
import pytest

from boidrytwin.dryer.gas_path import GasPath, air_density
from boidrytwin.properties import gas
from boidrytwin.scenario.schema import (
    ControllerSpec,
    DamperSpec,
    ExhaustFanSpec,
    RecirculationSpec,
    ResistancePoint,
    ResistancesSpec,
    SignalSpec,
)

T_D = 563.15
N0 = 990 * 2 * math.pi / 60
P_AMB = 101_325.0
M_W = float(gas.MOLAR_MASS[gas.I_H2O])
M_DRY = 0.0295  # kg/mol, flue gas plus air (dry)


def spec(characteristic: tuple[tuple[float, float], ...] | None = None) -> RecirculationSpec:
    return RecirculationSpec(
        damper=DamperSpec(
            open_mass_flow=18.0,
            design_pressure_drop=500.0,
            design_temperature=T_D,
            characteristic=characteristic,
        ),
        exhaust_fan=ExhaustFanSpec(
            curve=((15.0, 2300.0), (25.0, 2000.0), (35.0, 1400.0)),
            nominal_speed=N0,
            curve_temperature=T_D,
            speed=SignalSpec(constant=N0),
        ),
        resistances=ResistancesSpec(
            drum_path=ResistancePoint(mass_flow=15.0, pressure_drop=1200.0, temperature=T_D),
            stack=ResistancePoint(mass_flow=10.7, pressure_drop=300.0, temperature=T_D),
        ),
        controller=ControllerSpec(
            setpoint=SignalSpec(constant=-200.0),
            gain=1e-4,
            integral_time=5.0,
            output_min=0.0,
            output_max=1.0,
        ),
    )


def humid_density(Y: float, T: float) -> float:
    M_wet = (1.0 + Y) / (1.0 / M_DRY + Y / M_W)
    return P_AMB * M_wet / (gas.R_UNIVERSAL * T)


def test_air_density() -> None:
    assert air_density(293.15) == pytest.approx(1.2041, rel=1e-3)


def test_fan_curve_through_the_points_and_fan_laws() -> None:
    path = GasPath(spec())
    rho = air_density(T_D)
    for v, dp in ((15.0, 2300.0), (25.0, 2000.0), (35.0, 1400.0)):
        assert path.fan_pressure_rise(v, N0, rho) == pytest.approx(dp, abs=1e-9)
    # fan laws: 0.9 speed and 0.9 flow -> 0.81 pressure rise; density scales linearly
    assert path.fan_pressure_rise(0.9 * 25.0, 0.9 * N0, rho) == pytest.approx(0.81 * 2000.0)
    assert path.fan_pressure_rise(25.0, N0, 0.8 * rho) == pytest.approx(0.8 * 2000.0)


def test_rising_curve_is_rejected() -> None:
    bad = spec().exhaust_fan.model_copy(
        update={"curve": ((15.0, 2000.0), (25.0, 2100.0), (35.0, 1400.0))}
    )
    with pytest.raises(ValueError, match="fall"):
        GasPath(spec().model_copy(update={"exhaust_fan": bad}))


def test_resistance_constant_loss_coefficient() -> None:
    path = GasPath(spec())
    point = spec().resistances.drum_path
    rho_d = air_density(T_D)
    assert path.resistance(point, 15.0, rho_d) == pytest.approx(1200.0, rel=1e-12)
    assert path.resistance(point, 30.0, 0.5 * rho_d) == pytest.approx(1200.0 * 4 * 2, rel=1e-12)


def test_damper_flow() -> None:
    path = GasPath(spec())
    rho_d = air_density(T_D)
    assert path.damper_flow(1.0, 500.0, rho_d) == pytest.approx(18.0, rel=1e-12)
    assert path.damper_flow(1.0, 2000.0, rho_d) == pytest.approx(36.0, rel=1e-12)
    assert path.damper_flow(0.0, 500.0, rho_d) == pytest.approx(0.01 * 18.0, rel=1e-12)
    assert path.damper_flow(0.6, 0.0, rho_d) == 0.0
    assert path.damper_flow(0.6, -50.0, rho_d) == 0.0
    # default table points and monotone in between
    for s, phi in ((0.2, 0.05), (0.4, 0.15), (0.6, 0.35), (0.8, 0.65)):
        assert path.damper_flow(s, 500.0, rho_d) == pytest.approx(phi * 18.0, rel=1e-12)
    flows = [path.damper_flow(s, 500.0, rho_d) for s in np.linspace(0, 1, 101)]
    assert all(b >= a for a, b in itertools.pairwise(flows))


def test_solve_matches_the_inverse_hand_case() -> None:
    """Choose G_rec, compute the damper position by hand (linear damper), solve back."""
    path = GasPath(spec(characteristic=((0.0, 0.0), (1.0, 1.0))))
    G_in, Y, T = 9.4, 0.14, 568.0
    G_rec = 4.0
    rho = humid_density(Y, T)
    rho_d = air_density(T_D)
    m_drum = (G_in + G_rec) * (1 + Y)
    V = m_drum / rho
    # quadratic through the points by hand: 2000 - 45 (V - 25) - 1.5 (V - 25)^2 at curve density
    dp_fan = (2000.0 - 45.0 * (V - 25.0) - 1.5 * (V - 25.0) ** 2) * rho / rho_d
    dp_path = 1200.0 * (rho_d / rho) * (m_drum / 15.0) ** 2
    dp_stack = 300.0 * (rho_d / rho) * (G_in * (1 + Y) / 10.7) ** 2
    dp_damper = dp_fan - dp_path
    s = G_rec * (1 + Y) / (18.0 * math.sqrt(rho * dp_damper / (rho_d * 500.0)))
    assert 0.0 < s < 1.0
    state = path.solve(G_in, Y, T, M_DRY, s, N0, P_AMB)
    assert state.recirculated_dry_gas == pytest.approx(G_rec, abs=1e-8)
    assert state.drum_dry_gas == state.recirculated_dry_gas + G_in
    assert state.fan_outlet_pressure == pytest.approx(dp_stack, abs=1e-6)
    assert state.mixing_chamber_pressure == pytest.approx(dp_stack - dp_damper, abs=1e-3)
    assert state.fan_volume_flow == pytest.approx(V, rel=1e-9)
    assert state.fan_pressure_rise == pytest.approx(dp_fan, abs=1e-3)
    assert not state.backflow and not state.fan_out_of_curve


def test_more_damper_less_draft_more_speed_more_draft() -> None:
    path = GasPath(spec())
    args = (9.4, 0.14, 568.0, M_DRY)
    p = [path.solve(*args, s, N0, P_AMB).mixing_chamber_pressure for s in (0.3, 0.5, 0.7)]
    assert p[0] < p[1] < p[2]
    fast = path.solve(*args, 0.5, 1.05 * N0, P_AMB).mixing_chamber_pressure
    assert fast < p[1]


def test_fan_too_weak_gives_backflow_and_no_return() -> None:
    path = GasPath(spec())
    state = path.solve(9.4, 0.14, 568.0, M_DRY, 0.6, 0.4 * N0, P_AMB)
    assert state.backflow and state.recirculated_dry_gas == 0.0
    assert state.mixing_chamber_pressure > 0.0


def test_fan_out_of_curve() -> None:
    path = GasPath(spec())
    state = path.solve(25.0, 0.14, 568.0, M_DRY, 0.0, N0, P_AMB)
    assert state.fan_out_of_curve
