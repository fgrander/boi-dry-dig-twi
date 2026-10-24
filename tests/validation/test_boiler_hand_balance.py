"""Boiler house hand balance (T021, SC-002; see boiler_balance_case.md)."""

import pytest

from boidrytwin import load_scenario
from boidrytwin.boiler_house.furnace import gas_temperature
from boidrytwin.plant.simulate import simulate_plant
from boidrytwin.properties import fuel, gas, water, wood
from boidrytwin.properties.thermal_oil import get_oil
from tests.integration.conftest import EXAMPLES


@pytest.fixture(scope="module")
def steady():  # type: ignore[no-untyped-def]
    sim = simulate_plant(load_scenario(EXAMPLES / "boiler_house_only.toml"))
    return sim.results.iloc[-1], sim.flue_gas_to_dryer.iloc[-1]


def test_oil_side_duty(steady) -> None:  # type: ignore[no-untyped-def]
    last, _ = steady
    oil = get_oil("shell_s2")
    duty = 60.0 * float(oil.enthalpy(last["oil_outlet_temperature"]) - oil.enthalpy(513.15))
    assert last["heat_to_oil"] == pytest.approx(duty, rel=0.01)


def test_gas_side_temperature(steady) -> None:  # type: ignore[no-untyped-def]
    last, flue = steady
    chips = fuel.FuelComposition.default("wood_chips")
    B, w, T_fuel = last["fuel_burnout_dry"], 0.45, 283.15
    feed = B / (1 - w)  # steady state: delivered = burnout / (1 - w)
    p_w = 0.60 * float(water.p_sat(293.15))
    M_air = float(gas.molar_mass_mixture(fuel.DRY_AIR_X))
    Y = 0.018015 / M_air * p_w / (101_300.0 - p_w)
    air_dry = last["combustion_air_flow"] / (1 + Y)
    air_y = gas.mass_fractions(fuel.DRY_AIR_X)
    H_air = air_dry * float(gas.h_sensible_mass(293.15, air_y)) + air_dry * Y * float(
        water.h_vapour(293.15)
    )
    h_ash = 800.0 * (773.15 - 298.15)
    gas_in = (
        B * chips.lhv_dry()
        + feed * ((1 - w) * float(wood.h_dry(T_fuel)) + w * float(water.h_liquid(T_fuel)))
        + H_air
    )
    flue_enthalpy = gas_in - last["heat_to_oil"] - last["losses"]  # losses include the ash enthalpy
    del h_ash
    x = flue[["x_N2", "x_O2", "x_CO2", "x_H2O", "x_other"]].to_numpy(dtype=float)
    y = gas.mass_fractions(x)
    T_hand = gas_temperature(flue_enthalpy / last["flue_gas_to_dryer_mass_flow"], y, T_guess=800.0)
    assert last["gas_temperature_after_heater_3"] == pytest.approx(T_hand, abs=5.0)
