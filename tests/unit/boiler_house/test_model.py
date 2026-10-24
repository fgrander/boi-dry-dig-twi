"""BoilerHouseModel right-hand side, outputs and balances (T017)."""

import numpy as np
import pytest

from boidrytwin.boiler_house.config import reference_configuration
from boidrytwin.boiler_house.model import BoilerHouseModel, BoilerInputs
from boidrytwin.interface.flue_gas import FlueGasConditions
from boidrytwin.properties import fuel


def _inputs(**kw: float) -> BoilerInputs:
    base: dict[str, object] = {
        "fuel": fuel.FuelComposition.default("wood_chips"),
        "fuel_command": 1.5,
        "moisture_wet": 0.45,
        "fuel_temperature": 283.15,
        "excess_air": 1.5,
        "air_mass_flow": None,
        "air_temperature": 293.15,
        "air_humidity": 0.009,
        "oil_mass_flow": 60.0,
        "oil_return_temperature": 513.15,
        "ambient_temperature": 293.15,
        "bypass_position": 0.0,
    }
    base.update(kw)
    return BoilerInputs(**base)  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def warm_state() -> tuple[BoilerHouseModel, np.ndarray]:
    from scipy.integrate import solve_ivp

    model = BoilerHouseModel(reference_configuration(), oil="shell_s2")
    x0 = model.initial_cold(_inputs())
    sol = solve_ivp(lambda t, x: model.rhs(t, x, _inputs())[0], (0, 3 * 3600), x0, method="BDF",
                    jac_sparsity=model.jac_sparsity())  # fmt: skip
    return model, sol.y[:, -1]


def test_outputs_include_interface_state(warm_state: tuple[BoilerHouseModel, np.ndarray]) -> None:
    model, x = warm_state
    _, out = model.rhs(0.0, x, _inputs())
    fg = out.flue_gas_to_dryer
    assert isinstance(fg, FlueGasConditions)
    assert fg.x.sum() == pytest.approx(1.0)
    assert 9.0 < fg.mass_flow < 12.0  # ≈ 1.5 kg/s wet fuel at λ 1.5
    assert 500.0 < fg.temperature < 1300.0
    for col in ("heat_released", "heat_to_oil", "oil_outlet_temperature", "furnace_temperature"):
        assert col in out.results


@pytest.mark.parametrize("bypass", [0.0, 0.4])
def test_storage_derivative_equals_boundary_flows(
    warm_state: tuple[BoilerHouseModel, np.ndarray], bypass: float
) -> None:
    model, x = warm_state
    u = _inputs(bypass_position=bypass)
    dx, out = model.rhs(0.0, x, u)
    eps = 1e-3
    for quantity, (inflow, outflow) in out.boundary_flows.items():
        rate = (model.storage(x + eps * dx)[quantity] - model.storage(x - eps * dx)[quantity]) / (
            2 * eps
        )
        scale = max(abs(inflow), abs(outflow), 1e-12)
        assert rate == pytest.approx(inflow - outflow, abs=1e-6 * scale), quantity


def test_heater_numbering_and_bypass_position(
    warm_state: tuple[BoilerHouseModel, np.ndarray],
) -> None:
    model, x = warm_state
    r = model.rhs(0.0, x, _inputs())[1].results
    # heater 1 is radiant (its gas temperature is the furnace temperature), 2 and 3 convective
    assert r["gas_temperature_after_heater_1"] == r["furnace_temperature"]
    assert (
        r["gas_temperature_after_heater_1"]
        > r["gas_temperature_after_heater_2"]
        > r["gas_temperature_after_heater_3"]
    )
    assert r["flue_gas_to_dryer_temperature"] == pytest.approx(r["gas_temperature_after_heater_3"])
    # full bypass after heater 1: the convective heaters receive no gas, the dryer gets furnace gas
    dx_full, out_full = model.rhs(0.0, x, _inputs(bypass_position=1.0))
    full = out_full.results
    assert full["flue_gas_to_dryer_temperature"] == pytest.approx(
        full["furnace_temperature"], abs=1e-6
    )
    # no gas reaches the convective walls, so they cool (the oil still takes their stored heat)
    walls = model.layout.wall
    assert np.all(dx_full[walls][1:] < 0)
    assert dx_full[walls][0] == pytest.approx(
        model.rhs(0.0, x, _inputs())[0][walls][0]
    )  # radiant unaffected


def test_jacobian_sparsity_covers_all_nonzeros(
    warm_state: tuple[BoilerHouseModel, np.ndarray],
) -> None:
    model, x = warm_state
    u = _inputs()
    pattern = model.jac_sparsity().toarray() != 0
    f0 = model.rhs(0.0, x, u)[0]
    for j in range(len(x)):
        dx = np.zeros_like(x)
        dx[j] = 1e-6 * max(abs(x[j]), 1.0)
        changed = np.abs(model.rhs(0.0, x + dx, u)[0] - f0) > 1e-10 * (np.abs(f0) + 1.0)
        assert not np.any(changed & ~pattern[:, j]), f"column {j}"
