"""BoilerHouseState (T012; data-model.md §3)."""

from pathlib import Path

import numpy as np
import pytest

from boidrytwin.boiler_house.config import reference_configuration
from boidrytwin.boiler_house.state import BoilerHouseState, StateLayout


def _state() -> BoilerHouseState:
    layout = StateLayout.for_config(reference_configuration())
    rng = np.random.default_rng(2)
    return BoilerHouseState(
        layout=layout,
        feed_stages=rng.uniform(0, 2, 2),
        bed_water=10.0,
        bed_dry_fuel=600.0,
        furnace_temperature=1300.0,
        refractory_hot_face=1200.0,
        refractory_bulk=800.0,
        heater_wall=rng.uniform(500, 700, layout.n_heater_nodes),
        heater_oil=rng.uniform(500, 560, layout.n_heater_nodes),
        o2_measured=0.07,
    )


def test_layout_size_for_reference() -> None:
    layout = StateLayout.for_config(reference_configuration())
    assert layout.n_heater_nodes == 1 + 5 + 5
    assert (
        layout.size == 2 + 2 + 1 + 2 + 2 * 11 + 1
    )  # 30 boiler states; +3 controllers in the plant


def test_pack_unpack_and_json(tmp_path: Path) -> None:
    s = _state()
    back = BoilerHouseState.from_vector(s.layout, s.to_vector())
    assert np.array_equal(back.heater_oil, s.heater_oil) and back.bed_dry_fuel == s.bed_dry_fuel
    s.save(tmp_path / "s.json")
    loaded = BoilerHouseState.load(tmp_path / "s.json")
    assert np.array_equal(loaded.heater_wall, s.heater_wall)
    assert loaded.layout == s.layout


@pytest.mark.parametrize(
    ("field", "value"),
    [("bed_water", -1.0), ("furnace_temperature", 0.0), ("o2_measured", 0.3)],
)
def test_invariants(field: str, value: float) -> None:
    s = _state()
    with pytest.raises(ValueError, match=field):
        BoilerHouseState(**{**s.as_dict(), field: value})
