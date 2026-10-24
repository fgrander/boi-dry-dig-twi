"""DryerState packing and persistence (T036)."""

from pathlib import Path

import numpy as np
import pytest

from boidrytwin.dryer.state import FIELDS, DryerState


def _state(n: int = 3) -> DryerState:
    rng = np.random.default_rng(0)
    return DryerState(
        dry_mass_passive=rng.uniform(1, 50, n),
        dry_mass_active=rng.uniform(0, 5, n),
        water_mass_passive=rng.uniform(0, 50, n),
        water_mass_active=rng.uniform(0, 5, n),
        solids_temperature=rng.uniform(280, 360, n),
        gas_temperature=rng.uniform(350, 900, n),
        gas_humidity=rng.uniform(0.01, 0.4, n),
        shell_temperature=rng.uniform(300, 500, n),
    )


def test_field_order_matches_data_model() -> None:
    assert FIELDS == (
        "dry_mass_passive",
        "dry_mass_active",
        "water_mass_passive",
        "water_mass_active",
        "solids_temperature",
        "gas_temperature",
        "gas_humidity",
        "shell_temperature",
    )


def test_pack_unpack_round_trip() -> None:
    s = _state()
    v = s.to_vector()
    assert v.shape == (24,)
    # cell-major layout: the 8 values of cell 0 come first
    assert v[:8] == pytest.approx([getattr(s, f)[0] for f in FIELDS])
    back = DryerState.from_vector(v, n_cells=3)
    for f in FIELDS:
        assert np.array_equal(getattr(back, f), getattr(s, f))


@pytest.mark.parametrize(
    ("field", "value"),
    [("dry_mass_passive", -1.0), ("gas_temperature", 0.0), ("gas_humidity", -0.1)],
)
def test_invariants(field: str, value: float) -> None:
    s = _state()
    arr = getattr(s, field).copy()
    arr[1] = value
    with pytest.raises(ValueError, match=field):
        DryerState(**{**{f: getattr(s, f) for f in FIELDS}, field: arr})


def test_all_fields_need_the_same_length() -> None:
    s = _state()
    with pytest.raises(ValueError, match="length"):
        DryerState(**{**{f: getattr(s, f) for f in FIELDS}, "gas_humidity": np.ones(2)})


def test_json_round_trip(tmp_path: Path) -> None:
    s = _state()
    path = tmp_path / "final_state.json"
    s.save(path)
    back = DryerState.load(path)
    assert back.n_cells == 3
    for f in FIELDS:
        assert np.array_equal(getattr(back, f), getattr(s, f))
