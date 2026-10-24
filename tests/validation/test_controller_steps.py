"""Controller step responses (T023, SC-004).

The settling criterion is relative to the loop's own dynamics: 4 × (τ_c + θ) from the tuning
record written by scripts/tune_controllers.py (examples/data/controller_tuning.json). The
30-minute plant target is reported, not asserted (dependency on plant data).
"""

import json
from pathlib import Path

import numpy as np
import pytest

from boidrytwin import load_scenario
from boidrytwin.plant.simulate import simulate_plant
from tests.integration.conftest import EXAMPLES, make_variant

SETPOINT = 555.15
STEP_AT = 6 * 3600.0
TUNING = EXAMPLES / "data" / "controller_tuning.json"


def _settling(t: np.ndarray, y: np.ndarray, band: float, after: float) -> float:
    outside = np.flatnonzero((np.abs(y - SETPOINT) > band) & (t >= after))
    return float(t[outside[-1]] - after) if len(outside) else 0.0


def test_oil_demand_step(capsys: pytest.CaptureFixture[str]) -> None:
    tuning = json.loads(TUNING.read_text(encoding="utf-8"))["oil_temperature"]
    sim = simulate_plant(load_scenario(EXAMPLES / "oil_demand_step.toml"))
    t, y = sim.times, sim.results["oil_outlet_temperature"].to_numpy()
    before = t < STEP_AT
    assert np.max(np.abs(y[before] - SETPOINT)) <= 0.5  # steady within ±0.5 K
    settle = _settling(t, y, 2.0, STEP_AT)
    limit = 4.0 * (tuning["tau_c"] + tuning["theta"])
    assert settle <= limit, f"settling {settle:.0f} s > {limit:.0f} s"
    # more demand pulls the oil down first (the oil passes the heaters in about a minute, the
    # fuel acts only after the feed dead time); overshoot is the swing past the set point
    after = y[t >= STEP_AT] - SETPOINT
    dip = -float(np.min(after))
    overshoot = max(float(np.max(after)), 0.0)
    assert overshoot <= 5.0
    last_hour = y[t >= t[-1] - 3600]
    assert np.ptp(last_hour) < 0.2  # no sustained oscillation
    with capsys.disabled():
        print(
            f"\noil step: settling {settle / 60:.1f} min (plant target 30 min, not asserted),"
            f" peak dip {dip:.1f} K, overshoot {overshoot:.1f} K"
        )


def test_oxygen_returns_after_moisture_step(tmp_path: Path) -> None:
    csv = (
        "time,w\nunit,%\n2026-01-01T00:00:00Z,45\n2026-01-01T03:00:00Z,45\n"
        "2026-01-01T03:01:00Z,50\n2026-01-01T12:00:00Z,50\n"
    )
    path = make_variant(
        tmp_path,
        base="boiler_house_only.toml",
        replace={
            'moisture_wet_basis = "45 %"': 'moisture_wet_basis = { file = "w.csv", column = "w" }'
        },
        end="2026-01-01T12:00:00Z",
        files={"w.csv": csv},
    )
    sim = simulate_plant(load_scenario(path))
    o2 = sim.results["o2_dry_measured"].to_numpy()
    assert abs(o2[-1] - 0.07) < 0.002
    oil = sim.results["oil_outlet_temperature"].to_numpy()
    assert abs(oil[-1] - SETPOINT) < 0.5  # the oil loop compensates the wetter fuel
