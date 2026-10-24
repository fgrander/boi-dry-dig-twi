"""Generate ``examples/synthetic_measured.csv`` (T077).

The synthetic "measurements" are the model's own prediction for
``examples/reference_timeseries.toml``, sampled every 5 minutes, with known offsets and
Gaussian noise (fixed seed) and some deliberately missing and bad values. The comparison
must reproduce these deviations; see ``examples/README.md``.

With ``--boiler`` (feature 002, T058) it writes ``examples/synthetic_boiler_measured.csv``
instead: boiler house outputs predicted for ``examples/oil_demand_step.toml``, with the
offsets in ``BOILER_OFFSETS``, the same seed, noise and missing/bad samples.

Usage: ``uv run python scripts/make_synthetic_measured.py [--boiler]``
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import simulate
from boidrytwin.logging import configure_logging
from boidrytwin.plant.simulate import simulate_plant

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "examples" / "reference_timeseries.toml"
OUTPUT = ROOT / "examples" / "synthetic_measured.csv"

SEED = 42
SAMPLE_EVERY = 5  # output intervals (5 min)
OFFSET_MOISTURE = 0.004  # wet basis, measured = model + offset + noise
NOISE_MOISTURE = 0.002
OFFSET_EXHAUST = -2.0  # K
NOISE_EXHAUST = 1.0
MISSING = (20, 21, 22, 150)  # sample numbers with empty values
BAD = (60, 61, 200)  # sample numbers flagged bad (values grossly wrong)

BOILER_SCENARIO = ROOT / "examples" / "oil_demand_step.toml"
BOILER_OUTPUT = ROOT / "examples" / "synthetic_boiler_measured.csv"
# column: (offset, noise standard deviation, unit written), SI values
BOILER_OFFSETS: dict[str, tuple[float, float, str]] = {
    "o2_dry": (0.002, 0.0005, "mol/mol"),
    "furnace_temperature": (-8.0, 1.0, "K"),
    "gas_temperature_after_heater_3": (4.0, 1.0, "K"),
    "oil_outlet_temperature": (-1.0, 0.2, "K"),
}


def boiler_main() -> None:
    configure_logging(level="WARNING")
    sim = simulate_plant(load_scenario(BOILER_SCENARIO))
    res = sim.results.iloc[::SAMPLE_EVERY]
    rng = np.random.default_rng(SEED)
    n = len(res)
    columns = list(BOILER_OFFSETS)
    values = {
        c: res[c].to_numpy() + off + rng.normal(0.0, noise, n)
        for c, (off, noise, _) in BOILER_OFFSETS.items()
    }
    lines = [
        "time," + ",".join(columns) + ",quality",
        "unit," + ",".join(BOILER_OFFSETS[c][2] for c in columns) + ",",
    ]
    for i, stamp in enumerate(res.index):
        quality = "bad" if i in BAD else "good"
        cells = []
        for c in columns:
            v = values[c][i] * (1.5 if i in BAD else 1.0)
            cells.append("" if i in MISSING else f"{v:.6g}")
        lines.append(f"{stamp.strftime('%Y-%m-%dT%H:%M:%SZ')},{','.join(cells)},{quality}")
    BOILER_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {BOILER_OUTPUT} ({n} samples)")


def main() -> None:
    configure_logging(level="WARNING")
    sim = simulate(load_scenario(SCENARIO))
    res = sim.results.iloc[::SAMPLE_EVERY]
    rng = np.random.default_rng(SEED)
    n = len(res)
    moisture = (
        res["product_moisture_wet_basis"].to_numpy()
        + OFFSET_MOISTURE
        + rng.normal(0.0, NOISE_MOISTURE, n)
    )
    exhaust = (
        res["exhaust_temperature"].to_numpy() + OFFSET_EXHAUST + rng.normal(0.0, NOISE_EXHAUST, n)
    )
    lines = ["time,product_moisture_wet_basis,exhaust_temperature,quality", "unit,kg/kg,K,"]
    for i, stamp in enumerate(res.index):
        quality = "bad" if i in BAD else "good"
        m, e = moisture[i], exhaust[i]
        if i in BAD:
            m, e = m + 0.2, e + 80.0
        cells = ["", ""] if i in MISSING or not np.isfinite(m) else [f"{m:.5f}", f"{e:.3f}"]
        lines.append(f"{stamp.strftime('%Y-%m-%dT%H:%M:%SZ')},{cells[0]},{cells[1]},{quality}")
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT} ({n} samples)")


if __name__ == "__main__":
    boiler_main() if "--boiler" in sys.argv[1:] else main()
