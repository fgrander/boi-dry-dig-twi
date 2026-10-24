"""Heat-limited operation (T044; FR-011)."""

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import simulate

from .conftest import EXAMPLES


def test_heat_limited_flag_and_wetter_product() -> None:
    reference = simulate(load_scenario(EXAMPLES / "reference_constant.toml")).results.iloc[-1]
    limited_run = simulate(load_scenario(EXAMPLES / "heat_limited.toml"))
    limited = limited_run.results.iloc[-1]
    assert bool(limited["heat_limited"])
    assert not bool(reference["heat_limited"])
    assert limited["product_moisture_wet_basis"] > reference["product_moisture_wet_basis"]
    # energy is not created: the solids receive less heat than the gas brings in
    assert limited["heat_used_for_drying"] < limited["heat_supplied"]
    assert limited["evaporation_rate"] < reference["evaporation_rate"]
