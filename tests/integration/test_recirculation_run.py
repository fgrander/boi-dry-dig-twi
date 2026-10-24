"""Dryer-only runs with a recirculation (T015; US1, edge cases)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import simulate
from tests.integration.conftest import EXAMPLES
from tests.recirculation import with_recirculation

END = "2026-01-01T06:00:00Z"


def test_example_runs_from_steady_state() -> None:
    sim = simulate(load_scenario(EXAMPLES / "dryer_recirculation.toml"))
    last = sim.results.iloc[-1]
    assert last["mixing_chamber_pressure"] == pytest.approx(-200.0, abs=50.0)
    assert 0.2 < last["recirculation_damper_position"] < 0.8
    assert not sim.results["setpoint_not_reached"].any()
    assert sim.balance.passed


def test_cold_empty_start(tmp_path: Path) -> None:
    sim = simulate(load_scenario(with_recirculation(tmp_path, end=END)))
    assert sim.results["mixing_chamber_pressure"].iloc[-1] == pytest.approx(-200.0, abs=50.0)


def test_closed_damper_without_leakage_equals_no_recirculation(tmp_path: Path) -> None:
    closed = with_recirculation(
        tmp_path,
        replace={
            'mode = "automatic"': 'mode = "manual"\nmanual_output = "0 %"',
            'design_temperature = "290 degC"': 'design_temperature = "290 degC"\nleakage = "0 %"',
        },
        end=END,
    )
    (tmp_path / "plain").mkdir()
    plain = with_recirculation(tmp_path / "plain", block="", end=END)
    a = simulate(load_scenario(closed)).results
    b = simulate(load_scenario(plain)).results
    assert (a["recirculation_mass_flow"] == 0.0).all()
    # equal within the global solver error (the loop states change the solver steps), once
    # product leaves the empty drum (before that the moisture is a ratio of near-zeros)
    flowing = b["product_dry_mass_flow"] > 1e-3
    for col in b.columns:
        if b[col].dtype.kind == "f":
            np.testing.assert_allclose(
                a.loc[flowing, col], b.loc[flowing, col], rtol=1e-4, atol=1e-6, err_msg=col
            )


def test_with_a_time_series_flue_gas(tmp_path: Path) -> None:
    sim = simulate(
        load_scenario(with_recirculation(tmp_path, base="reference_timeseries.toml", end=END))
    )
    assert sim.balance.passed
    assert isinstance(sim.results.index, pd.DatetimeIndex)
    assert sim.results["recirculation_mass_flow"].iloc[-1] > 0.0
