"""Right-hand side of the drum dryer model (T040)."""

import math
from datetime import UTC, datetime

import numpy as np
import pytest

from boidrytwin.dryer.config import DryerConfiguration
from boidrytwin.dryer.model import DrumDryerModel, ModelInputs
from boidrytwin.interface.composition import GasComposition
from boidrytwin.interface.flue_gas import FlueGasState
from boidrytwin.interface.sources import ConstantFlueGasSupply
from boidrytwin.properties import gas, water
from boidrytwin.scenario.timeseries import Signal

T0 = datetime(2026, 1, 1, tzinfo=UTC)
COMP = GasComposition.from_input(
    {"x_N2": 0.705, "x_O2": 0.06, "x_CO2": 0.105, "x_H2O": 0.12, "x_other": 0.01}
)


def _model(**cfg: float) -> DrumDryerModel:
    config = DryerConfiguration(
        length=20.0,
        diameter=4.0,
        slope=math.radians(2),
        shell_mass=60_000.0,
        rotation_speed=4 * 2 * math.pi / 60,
        n_cells=10,
        **cfg,
    )
    state = FlueGasState(
        time=T0, mass_flow=8.0, temperature=923.15, pressure=101_000.0, composition=COMP
    )
    inputs = ModelInputs(
        flue_gas=ConstantFlueGasSupply(state, start=T0),
        dilution_air=Signal("dilution", constant=2.0),
        feed_mass_flow_wet=Signal("feed", constant=10_000 / 3600),
        feed_moisture_wet=Signal("w", constant=0.5),
        feed_temperature=Signal("Tf", constant=283.15),
        ambient_temperature=Signal("Ta", constant=283.15),
        ambient_relative_humidity=Signal("rh", constant=0.7),
        ambient_pressure=Signal("pa", constant=101_300.0),
    )
    return DrumDryerModel(config, inputs)


def test_dilution_air_mixing_conserves_mass_and_enthalpy() -> None:
    model = _model()
    inlet = model.inlet(0.0)
    y = COMP.mass_fractions()
    w_fg = y[gas.I_H2O]
    p_w = 0.7 * water.p_sat(283.15)
    Y_air = water.humidity_from_partial_pressure(p_w, 101_300.0, 0.028965)
    dry_air = 2.0 / (1 + Y_air)
    assert inlet.dry_gas_flow == pytest.approx(8.0 * (1 - w_fg) + dry_air, rel=1e-4)
    water_in = 8.0 * w_fg + dry_air * Y_air
    assert inlet.humidity == pytest.approx(water_in / inlet.dry_gas_flow, rel=1e-4)
    h_fg = 8.0 * gas.h_sensible_mass(923.15, y)
    assert inlet.heat_supplied == pytest.approx(
        h_fg + inlet.dilution_heat, rel=1e-9
    )  # flue gas + dilution air, relative to 298.15 K
    assert 773.15 < inlet.temperature < 923.15  # dilution cools the gas


def test_without_heat_transfer_solids_are_only_transported() -> None:
    model = _model(heat_transfer_multiplier=0.0, shell_contact_htc=0.0)
    y = model.initial_cold_empty(0.0)
    from scipy.integrate import solve_ivp

    sol = solve_ivp(model.rhs, (0.0, 4 * 3600.0), y, method="BDF", rtol=1e-6, atol=1e-8)
    out = model.diagnostics(sol.t[-1], sol.y[:, -1])
    assert out["product_moisture_wet_basis"] == pytest.approx(0.5, abs=1e-4)
    assert out["evaporation_rate"] == pytest.approx(0.0, abs=1e-9)
    assert out["exhaust_humidity"] == pytest.approx(model.inlet(0.0).humidity, rel=1e-6)


def test_jacobian_sparsity_covers_all_nonzeros() -> None:
    model = _model()
    y0 = model.initial_cold_empty(0.0)
    from scipy.integrate import solve_ivp

    y = solve_ivp(model.rhs, (0.0, 1800.0), y0, method="BDF").y[:, -1]
    pattern = model.jac_sparsity().toarray() != 0
    f0 = model.rhs(0.0, y)
    for j in range(len(y)):
        dy = np.zeros_like(y)
        dy[j] = 1e-6 * max(abs(y[j]), 1.0)
        changed = np.abs(model.rhs(0.0, y + dy) - f0) > 1e-12 * (np.abs(f0) + 1.0)
        assert not np.any(changed & ~pattern[:, j]), f"column {j} has entries outside the pattern"


def test_rhs_is_vectorised_shape() -> None:
    for n in (10, 40):
        model = _model() if n == 10 else _model_n(n)
        y = model.initial_cold_empty(0.0)
        assert model.rhs(0.0, y).shape == y.shape == (8 * n,)


def _model_n(n: int) -> DrumDryerModel:
    m = _model()
    return DrumDryerModel(m.config.model_copy(update={"n_cells": n}), m.inputs)
