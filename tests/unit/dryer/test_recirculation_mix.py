"""Mixing the returned exhaust into the drum inlet gas (T010; FR-002, FR-003, research R4)."""

from pathlib import Path

import numpy as np
import pytest

from boidrytwin import load_scenario
from boidrytwin.dryer.model import (
    I_HG,
    I_YG,
    DrumDryerModel,
    gas_temperature,
    humid_cp,
    humid_enthalpy,
)
from boidrytwin.dryer.simulate import build_model
from boidrytwin.properties import gas
from tests.recirculation import with_recirculation


def hot_state(model: DrumDryerModel, t: float = 0.0) -> np.ndarray:
    """Cold empty drum, but the last cell's gas hot and humid like a dryer outlet."""
    y = model.initial_cold_empty(t).copy()
    cells = y[: model.cells_size].reshape(model.n, -1)
    y_dry = model.inlet(t).y_dry
    cells[-1, I_YG] = 0.14
    cells[-1, I_HG] = model.gas_holdup * float(
        humid_enthalpy(np.asarray(568.0), np.asarray(0.14), y_dry)
    )
    return y


@pytest.fixture
def models(tmp_path: Path) -> tuple[DrumDryerModel, DrumDryerModel]:
    with_loop = build_model(load_scenario(with_recirculation(tmp_path)))
    (tmp_path / "plain").mkdir()
    without = build_model(load_scenario(with_recirculation(tmp_path / "plain", block="")))
    return with_loop, without


def test_mix_is_mass_and_energy_weighted(models: tuple[DrumDryerModel, DrumDryerModel]) -> None:
    model, plain = models
    assert model.recirculation is not None and plain.recirculation is None
    y = hot_state(model)
    inlet = model.inlet(0.0, y)
    fresh = plain.inlet(0.0)
    gp = inlet.gas_path
    assert gp is not None
    G_in, G_rec = fresh.dry_gas_flow, gp.recirculated_dry_gas
    assert inlet.fresh_dry_gas_flow == fresh.dry_gas_flow
    assert G_rec > 0.0
    cells = y[: model.cells_size].reshape(model.n, -1)
    Y_out = cells[-1, I_YG]
    H_out = cells[-1, I_HG] / model.gas_holdup
    G = G_in + G_rec
    assert inlet.dry_gas_flow == pytest.approx(G, rel=1e-12)
    assert inlet.humidity == pytest.approx((G_in * fresh.humidity + G_rec * Y_out) / G, rel=1e-12)
    assert inlet.enthalpy == pytest.approx((G_in * fresh.enthalpy + G_rec * H_out) / G, rel=1e-12)
    T = float(gas_temperature(np.asarray(inlet.enthalpy), np.asarray(inlet.humidity), inlet.y_dry))
    assert inlet.temperature == pytest.approx(T, abs=1e-9)
    np.testing.assert_allclose(inlet.y_dry, fresh.y_dry, rtol=1e-14)
    assert inlet.humidity > fresh.humidity
    assert inlet.temperature < fresh.temperature
    assert inlet.heat_supplied == fresh.heat_supplied


def test_lower_oxygen_at_the_drum_inlet(models: tuple[DrumDryerModel, DrumDryerModel]) -> None:
    model, plain = models
    y = hot_state(model)
    row = model.diagnostics(0.0, y)

    def x_o2(Y: float, y_dry: np.ndarray) -> float:
        moles = y_dry / gas.MOLAR_MASS
        moles[gas.I_H2O] += Y / gas.MOLAR_MASS[gas.I_H2O]
        return float(moles[gas.I_O2] / moles.sum())

    fresh = plain.inlet(0.0)
    assert row["drum_inlet_x_O2"] == pytest.approx(
        x_o2(row["drum_inlet_humidity"], fresh.y_dry), rel=1e-12
    )
    assert row["drum_inlet_x_O2"] < x_o2(fresh.humidity, fresh.y_dry)


def test_duct_heat_loss(tmp_path: Path) -> None:
    path = with_recirculation(
        tmp_path, replace={'duct_heat_loss = "0 W/K"': 'duct_heat_loss = "500 W/K"'}
    )
    model = build_model(load_scenario(path))
    y = hot_state(model)
    inlet = model.inlet(0.0, y)
    gp = inlet.gas_path
    assert gp is not None
    T_a = inlet.ambient_temperature
    # the duct cools the returned gas towards ambient: q = C (T - T_a) (1 - exp(-UA / C))
    C = gp.recirculated_dry_gas * float(humid_cp(np.asarray(568.0), np.asarray(0.14), inlet.y_dry))
    q = C * (568.0 - T_a) * (1.0 - np.exp(-500.0 / C))
    assert inlet.duct_heat_loss == pytest.approx(q, rel=1e-6)
    assert q == pytest.approx(500.0 * (568.0 - T_a), rel=0.1)  # close to UA dT for a short duct
    # same damper flow as without the loss (the loss acts after the fan), lower inlet enthalpy
    (tmp_path / "lossless").mkdir()
    lossless = build_model(load_scenario(with_recirculation(tmp_path / "lossless")))
    ref = lossless.inlet(0.0, hot_state(lossless))
    assert ref.gas_path is not None
    assert gp.recirculated_dry_gas == pytest.approx(ref.gas_path.recirculated_dry_gas, rel=1e-12)
    assert inlet.enthalpy == pytest.approx(ref.enthalpy - q / inlet.dry_gas_flow, rel=1e-12)


def test_without_state_no_return(models: tuple[DrumDryerModel, DrumDryerModel]) -> None:
    model, plain = models
    assert model.inlet(0.0).dry_gas_flow == plain.inlet(0.0).dry_gas_flow
    assert model.inlet(0.0).gas_path is None
