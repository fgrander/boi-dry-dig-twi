"""Edge cases from spec.md (T045)."""

from pathlib import Path

import numpy as np
import pytest

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import simulate

from .conftest import EXAMPLES, make_variant

SIX_HOURS = "2026-01-01T06:00:00Z"


@pytest.fixture(scope="module")
def reference_evaporation() -> float:
    sim = simulate(load_scenario(EXAMPLES / "reference_constant.toml"))
    return float(sim.results["evaporation_rate"].iloc[-1])


def test_cold_flue_gas_gives_only_evaporative_cooling(
    tmp_path: Path, reference_evaporation: float
) -> None:
    # unsaturated gas colder than the chips cannot heat them; the little evaporation that
    # remains is evaporative cooling of the chips towards the wet-bulb temperature
    path = make_variant(
        tmp_path,
        replace={
            'temperature = "650 degC"': 'temperature = "15 degC"',
            'x_N2 = "70.5 %"': 'x_N2 = "81.5 %"',
            'x_H2O = "12.0 %"': 'x_H2O = "1.0 %"',
            'mass_flow = "2.0 kg/s"': 'mass_flow = "0 kg/s"',
            'temperature = "10 degC"\n\n[ambient]': 'temperature = "20 degC"\n\n[ambient]',
        },
        end=SIX_HOURS,
    )
    res = simulate(load_scenario(path)).results
    last = res.iloc[-1]
    assert last["evaporation_rate"] < 0.05 * reference_evaporation
    assert last["product_temperature"] < 293.15  # chips leave colder than the 20 °C feed
    assert last["heat_used_for_drying"] < 0  # net heat flows from the chips to the gas


def test_boiler_trip_shell_cools_with_inertia(tmp_path: Path) -> None:
    rows = []
    for m in range(0, 12 * 60 + 1):
        flow = "8.0" if m <= 360 else "0.0"
        rows.append(
            f"2026-01-01T{m // 60:02d}:{m % 60:02d}:00Z,{flow},650,101.0,"
            "70.5,6.0,10.5,12.0,1.0,good\n"
        )
    csv = (
        "time,mass_flow,temperature,pressure,x_N2,x_O2,x_CO2,x_H2O,x_other,quality\n"
        "unit,kg/s,degC,kPa,%,%,%,%,%,\n" + "".join(rows)
    )
    block = (
        'source = "constant"\nmass_flow = "8.0 kg/s"\ntemperature = "650 degC"\n'
        'pressure = "101.0 kPa"\ncomposition_basis = "wet"\ncomposition_type = "mole"\n'
        'x_N2 = "70.5 %"\nx_O2 = "6.0 %"\nx_CO2 = "10.5 %"\nx_H2O = "12.0 %"\nx_other = "1.0 %"\n'
    )
    path = make_variant(
        tmp_path,
        replace={
            block: 'source = "timeseries"\nfile = "trip.csv"\n',
            'kind = "cold_empty"': 'kind = "steady_state"',
        },
        end="2026-01-01T12:00:00Z",
        files={"trip.csv": csv},
    )
    sim = simulate(load_scenario(path), profiles=True)
    res = sim.results
    t = sim.times
    after = t > 6 * 3600
    moisture = res["product_moisture_wet_basis"].to_numpy()
    assert moisture[-1] > moisture[int(np.searchsorted(t, 6 * 3600))]  # product leaves wetter
    shell = sim.profiles["shell_temperature"].unstack("cell").to_numpy().mean(axis=1)
    i6 = int(np.searchsorted(t, 6 * 3600))
    i630 = int(np.searchsorted(t, 6.5 * 3600))
    drop_30min = shell[i6] - shell[i630]
    drop_total = shell[i6] - shell[-1]
    assert drop_total > 0  # the shell cools down ...
    assert drop_30min < 0.9 * drop_total  # ... gradually, not instantly
    assert np.all(np.isfinite(res.loc[after, "product_temperature"]))


def test_zero_feed_gives_no_evaporation(tmp_path: Path) -> None:
    path = make_variant(
        tmp_path, replace={'mass_flow_wet = "10 t/h"': 'mass_flow_wet = "0 t/h"'}, end=SIX_HOURS
    )
    res = simulate(load_scenario(path)).results
    assert res["evaporation_rate"].abs().max() < 1e-6
    assert res["solids_holdup"].iloc[-1] < 1e-6


def test_feed_already_dry(tmp_path: Path, reference_evaporation: float) -> None:
    # hot gas dries the chips further towards the equilibrium moisture, but can never
    # evaporate more water than is fed
    path = make_variant(
        tmp_path,
        replace={'moisture_wet_basis = "50 %"': 'moisture_wet_basis = "8 %"'},
        end=SIX_HOURS,
    )
    res = simulate(load_scenario(path)).results
    last = res.iloc[-1]
    feed_water = 10_000 / 3600 * 0.08
    assert last["evaporation_rate"] <= feed_water * (1 + 1e-6)
    assert last["evaporation_rate"] < 0.35 * reference_evaporation
    assert last["product_moisture_wet_basis"] < 0.08


def test_exhaust_near_dew_point_is_flagged(tmp_path: Path) -> None:
    path = make_variant(
        tmp_path,
        replace={
            'mass_flow = "8.0 kg/s"': 'mass_flow = "2.5 kg/s"',
            'x_N2 = "70.5 %"': 'x_N2 = "52.5 %"',
            'x_H2O = "12.0 %"': 'x_H2O = "30.0 %"',
            'mass_flow = "2.0 kg/s"': 'mass_flow = "0 kg/s"',
        },
        end=SIX_HOURS,
    )
    res = simulate(load_scenario(path)).results
    assert bool(res["condensation_risk"].iloc[-1])
