"""Plant balances close (T045; SC-003)."""

from pathlib import Path

import pytest

from boidrytwin import load_scenario
from boidrytwin.plant.simulate import simulate_plant

from .conftest import make_variant

ENTRIES = {
    "boiler_house": {"mass", "C", "H", "O", "N", "S", "energy"},
    "oil_circuit": {"energy"},
    "dryer": {"dry_solids", "water", "gas", "energy"},
    "interface": {"mass", "energy"},
    "plant": {"mass", "energy"},
}


@pytest.mark.parametrize(
    ("base", "end"),
    [
        ("plant_reference.toml", "2026-01-01T02:00:00Z"),
        ("plant_oil_step.toml", "2026-01-01T08:00:00Z"),
    ],
)
def test_all_entries_pass(tmp_path: Path, base: str, end: str) -> None:
    sim = simulate_plant(load_scenario(make_variant(tmp_path, base=base, end=end)))
    report = sim.balance
    assert set(report.entries) == set(ENTRIES)
    for name, quantities in ENTRIES.items():
        assert set(report.entries[name]) == quantities, name
    assert report.passed, report.failed()
    for name, entry in report.entries.items():
        for q, b in entry.items():
            limit = 1e-3 if q not in ("energy",) else 1e-2
            assert abs(b.relative_residual) < limit, (name, q)
