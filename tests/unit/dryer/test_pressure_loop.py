"""Pressure transmitter and damper controller states of the dryer (T011; FR-007 - FR-009)."""

from pathlib import Path

import numpy as np
import pytest

from boidrytwin import load_scenario
from boidrytwin.dryer.model import N_FIELDS, DrumDryerModel
from boidrytwin.dryer.simulate import build_model
from tests.recirculation import with_recirculation
from tests.unit.dryer.test_recirculation_mix import hot_state


def model_for(tmp_path: Path, replace: dict[str, str] | None = None) -> DrumDryerModel:
    return build_model(load_scenario(with_recirculation(tmp_path, replace=replace)))


def test_two_extra_states(tmp_path: Path) -> None:
    model = model_for(tmp_path)
    assert model.size == model.n * N_FIELDS + 2
    assert len(model.initial_cold_empty(0.0)) == model.size
    assert len(model.scales(0.0)) == model.size


def test_transmitter_lag_and_reverse_action(tmp_path: Path) -> None:
    model = model_for(tmp_path)
    loop = model.recirculation
    assert loop is not None
    y = hot_state(model)
    for p_meas in (-400.0, -200.0, 0.0):
        y[model.cells_size] = p_meas
        p_mc = model.inlet(0.0, y).gas_path.mixing_chamber_pressure  # type: ignore[union-attr]
        d = model.rhs(0.0, y)[model.cells_size :]
        assert d[0] == pytest.approx((p_mc - p_meas) / 2.0, rel=1e-9)
    # measured below the set point (draft too strong) -> the damper opens
    y[model.cells_size] = -400.0
    assert model.rhs(0.0, y)[model.cells_size + 1] > 0.0
    y[model.cells_size] = 0.0
    assert model.rhs(0.0, y)[model.cells_size + 1] < 0.0


def test_output_limits_and_anti_windup(tmp_path: Path) -> None:
    model = model_for(tmp_path)
    loop = model.recirculation
    assert loop is not None
    extra = np.array([-200.0, 5.0])  # integral far above output_max
    v, u = loop.position(0.0, extra)
    assert v > 1.0 and u == pytest.approx(1.0, abs=1e-6)
    rates = loop.derivatives(0.0, extra, p_mc=-200.0)
    assert rates[1] < 0.0  # back-calculation pulls the integral back
    extra = np.array([-200.0, -3.0])
    assert loop.position(0.0, extra)[1] == pytest.approx(0.0, abs=1e-6)


def test_manual_mode_constant_and_steps(tmp_path: Path) -> None:
    model = model_for(tmp_path, {'mode = "automatic"': 'mode = "manual"\nmanual_output = "35 %"'})
    loop = model.recirculation
    assert loop is not None
    assert loop.position(0.0, np.array([-900.0, 0.2]))[1] == pytest.approx(0.35)
    (tmp_path / "s").mkdir()
    csv = (
        "time,position\nunit,%\n2026-01-01T00:00:00Z,40\n"
        "2026-01-01T01:00:00Z,60\n2026-01-03T00:00:00Z,60\n"
    )
    (tmp_path / "s" / "pos.csv").write_text(csv, encoding="utf-8")
    manual = 'mode = "manual"\nmanual_output = { file = "pos.csv", column = "position" }'
    model = model_for(tmp_path / "s", {'mode = "automatic"': manual})
    loop = model.recirculation
    assert loop is not None
    assert loop.position(0.0, np.array([0.0, 0.0]))[1] == pytest.approx(0.4)
    assert loop.position(1800.0, np.array([0.0, 0.0]))[1] == pytest.approx(0.5)
    assert 3600.0 in set(loop.breakpoints())


def test_initial_state_starts_at_the_initial_position(tmp_path: Path) -> None:
    model = model_for(tmp_path)
    loop = model.recirculation
    assert loop is not None
    y = model.initial_cold_empty(0.0)
    extra = y[model.cells_size :]
    assert loop.position(0.0, extra)[1] == pytest.approx(0.5, abs=1e-9)
    p_mc = model.inlet(0.0, y).gas_path.mixing_chamber_pressure  # type: ignore[union-attr]
    assert extra[0] == pytest.approx(p_mc)
    (tmp_path / "m").mkdir()
    manual = model_for(
        tmp_path / "m", {'mode = "automatic"': 'mode = "manual"\nmanual_output = "35 %"'}
    )
    y = manual.initial_cold_empty(0.0)
    assert manual.recirculation is not None
    assert manual.recirculation.position(0.0, y[manual.cells_size :])[1] == pytest.approx(0.35)


def test_sparsity_marks_the_return(tmp_path: Path) -> None:
    model = model_for(tmp_path)
    pattern = model.jac_sparsity().toarray()
    last = slice((model.n - 1) * N_FIELDS, model.n * N_FIELDS)
    extras = slice(model.cells_size, model.size)
    assert pattern[:, last].all()  # every row depends on the last cell (G_drum and the mix)
    assert pattern[: model.cells_size, extras].all()
    assert pattern[extras, extras].all()
