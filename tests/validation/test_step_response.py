"""Step responses (T043; FR-009, qualitative SC-004).

The quantitative SC-004 check (±20 % of a published or measured response time) needs
literature or plant data and is part of T079.
"""

from pathlib import Path

import numpy as np
import pytest

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import simulate
from tests.integration.conftest import make_variant

STEP_AT = 6 * 3600.0
FEED_STEP = (
    "time,{col}\nunit,{unit}\n2026-01-01T00:00:00Z,{a}\n2026-01-01T06:00:00Z,{a}\n"
    "2026-01-01T06:01:00Z,{b}\n2026-01-02T00:00:00Z,{b}\n"
)

CASES = {
    "feed_moisture": {
        'moisture_wet_basis = "50 %"': 'moisture_wet_basis = { file = "step.csv", column = "w" }',
        "_csv": FEED_STEP.format(col="w", unit="%", a=50, b=55),
    },
    "feed_rate": {
        'mass_flow_wet = "10 t/h"': 'mass_flow_wet = { file = "step.csv", column = "m" }',
        "_csv": FEED_STEP.format(col="m", unit="t/h", a=10, b=12),
    },
    "flue_gas_temperature": {
        'source = "constant"\nmass_flow = "8.0 kg/s"\ntemperature = "650 degC"': (
            'source = "constant"\nmass_flow = "8.0 kg/s"\ntemperature = "650 degC"'
        ),
        "_flue": "600",
    },
}


def _flue_step_csv(new_temperature: str) -> str:
    rows = []
    for m in range(0, 24 * 60 + 1):
        temperature = "650" if m <= 360 else new_temperature
        rows.append(
            f"2026-01-{1 + m // 1440:02d}T{(m // 60) % 24:02d}:{m % 60:02d}:00Z,8.0,"
            f"{temperature},101.0,70.5,6.0,10.5,12.0,1.0,good\n"
        )
    return (
        "time,mass_flow,temperature,pressure,x_N2,x_O2,x_CO2,x_H2O,x_other,quality\n"
        "unit,kg/s,degC,kPa,%,%,%,%,%,\n" + "".join(rows)
    )


@pytest.mark.parametrize("case", list(CASES))
def test_step_response(tmp_path: Path, case: str) -> None:
    spec = dict(CASES[case])
    files: dict[str, str] = {}
    replace = {'kind = "cold_empty"': 'kind = "steady_state"'}
    if "_csv" in spec:
        files["step.csv"] = spec.pop("_csv")
        replace.update(spec)
    else:
        files["flue.csv"] = _flue_step_csv(spec.pop("_flue"))
        text_block = (
            'source = "constant"\nmass_flow = "8.0 kg/s"\ntemperature = "650 degC"\n'
            'pressure = "101.0 kPa"\ncomposition_basis = "wet"\ncomposition_type = "mole"\n'
            'x_N2 = "70.5 %"\nx_O2 = "6.0 %"\nx_CO2 = "10.5 %"\n'
            'x_H2O = "12.0 %"\nx_other = "1.0 %"\n'
        )
        replace[text_block] = 'source = "timeseries"\nfile = "flue.csv"\n'
    sim = simulate(load_scenario(make_variant(tmp_path, replace=replace, files=files)))
    res = sim.results
    t = sim.times
    y = res["product_moisture_wet_basis"].to_numpy()

    i_step = int(np.searchsorted(t, STEP_AT))
    before, after = y[i_step], y[-1]
    delta = after - before
    assert abs(delta) > 1e-3, "the step must change the product moisture"

    # gradual: no jump larger than 5 % of the total change within the first output step
    assert abs(y[i_step + 1] - y[i_step]) <= 0.05 * abs(delta)

    # settles: the last 2 hours stay within 2 % of the total change
    tail = y[t >= t[-1] - 2 * 3600]
    assert np.max(np.abs(tail - after)) <= 0.02 * abs(delta)

    # settling time within the plausibility band of the model's own time constants
    outside = np.flatnonzero(np.abs(y - after) > 0.02 * abs(delta))
    t_settle = t[outside[-1]] - STEP_AT
    tau_res, tau_shell = sim.time_constants
    assert tau_res < t_settle < tau_res + 5 * tau_shell
