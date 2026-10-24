"""Generate ``examples/synthetic_measured.csv`` (T077).

The synthetic "measurements" are the model's own prediction for
``examples/reference_timeseries.toml``, sampled every 5 minutes, with known offsets and
Gaussian noise (fixed seed) and some deliberately missing and bad values. The comparison
must reproduce these deviations; see ``examples/README.md``.

Usage: ``uv run python scripts/make_synthetic_measured.py``
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import simulate
from boidrytwin.logging import configure_logging

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
    main()
