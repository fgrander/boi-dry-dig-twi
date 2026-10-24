"""Drum inlet split-range control (T043; SC-005, spec US2 scenarios)."""

from pathlib import Path

import numpy as np
import pytest

from boidrytwin import load_scenario
from boidrytwin.plant.simulate import PlantSimulationResult, simulate_plant

from .conftest import make_variant

SP = 'setpoint = "540 degC"'
END = "2026-01-01T03:00:00Z"


def _sim(tmp_path: Path, name: str, replace: dict[str, str] | None = None) -> PlantSimulationResult:
    return simulate_plant(
        load_scenario(
            make_variant(tmp_path, base="plant_reference.toml", replace=replace, end=END, name=name)
        )
    )


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, PlantSimulationResult]:
    tmp = tmp_path_factory.mktemp("drum")
    return {
        "reference": _sim(tmp, "ref.toml"),
        "hot": _sim(tmp, "hot.toml", {SP: 'setpoint = "480 degC"'}),
        "cold": _sim(tmp, "cold.toml", {SP: 'setpoint = "600 degC"'}),
    }


def test_gas_too_hot_opens_dilution(runs: dict[str, PlantSimulationResult]) -> None:
    res = runs["hot"].results
    assert res["dilution_air_flow"].iloc[-1] > 0.1
    assert (res["bypass_position"] == 0.0).all()
    assert abs(runs["hot"].dryer_results["drum_inlet_gas_temperature"].iloc[-1] - 753.15) <= 5.0


def test_gas_too_cold_opens_bypass(runs: dict[str, PlantSimulationResult]) -> None:
    res = runs["cold"].results
    assert res["bypass_position"].iloc[-1] > 0.05
    assert (res["dilution_air_flow"] == 0.0).all()
    assert abs(runs["cold"].dryer_results["drum_inlet_gas_temperature"].iloc[-1] - 873.15) <= 5.0


def test_never_both_open(runs: dict[str, PlantSimulationResult]) -> None:
    for name, sim in runs.items():
        both = (sim.results["bypass_position"] > 0) & (sim.results["dilution_air_flow"] > 0)
        assert not both.any(), name


def test_drum_inlet_on_setpoint_in_steady_operation(runs: dict[str, PlantSimulationResult]) -> None:
    T = runs["reference"].dryer_results["drum_inlet_gas_temperature"].to_numpy()
    assert np.max(np.abs(T - 813.15)) <= 5.0  # SC-005


def test_bypass_raises_fuel_and_holds_oil(runs: dict[str, PlantSimulationResult]) -> None:
    ref, cold = runs["reference"].results, runs["cold"].results
    assert cold["fuel_feed"].iloc[-1] > ref["fuel_feed"].iloc[-1] * 1.02
    assert np.max(np.abs(cold["oil_outlet_temperature"].to_numpy() - 555.15)) <= 2.0
