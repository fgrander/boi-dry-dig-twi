"""Plant coupling contract (T042; contracts/plant-coupling.md, SC-006)."""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import simulate
from boidrytwin.interface.flue_gas import FlueGasSupply
from boidrytwin.plant.coupled_supply import ControlledSignal, CoupledFlueGasSupply
from boidrytwin.plant.simulate import simulate_plant
from boidrytwin.scenario.timeseries import Signal
from tests.integration.conftest import EXAMPLES, dryer_only_from_interface, make_variant, run_cli

COMPARED = [
    "product_dry_mass_flow", "product_moisture_wet_basis", "product_temperature",
    "evaporation_rate", "exhaust_mass_flow", "exhaust_temperature", "exhaust_humidity",
    "drum_inlet_gas_temperature", "heat_supplied",
]  # fmt: skip


def test_coupled_supply_and_signal_satisfy_the_feature_001_interfaces() -> None:
    supply = CoupledFlueGasSupply(start=datetime(2026, 1, 1, tzinfo=UTC))
    assert isinstance(supply, FlueGasSupply)
    assert supply.covers(0.0, 1e9)
    sig = ControlledSignal(name="dilution_air.mass_flow")
    assert isinstance(sig, Signal)
    sig.set(2.5)
    assert sig.value_at(123.0) == 2.5 and sig.covers(0.0, 1e9) and len(sig.breakpoints()) == 0


def test_boiler_outlet_equals_dryer_inlet(tmp_path: Path) -> None:
    sim = simulate_plant(
        load_scenario(
            make_variant(tmp_path, base="plant_reference.toml", end="2026-01-01T02:00:00Z")
        )
    )
    iface = sim.balance.entries["interface"]
    for q in ("mass", "energy"):
        assert iface[q].residual == 0.0, q
    flue, boiler = sim.flue_gas_to_dryer, sim.results
    assert np.array_equal(
        flue["mass_flow"].to_numpy(), boiler["flue_gas_to_dryer_mass_flow"].to_numpy()
    )
    assert np.array_equal(
        flue["temperature"].to_numpy(), boiler["flue_gas_to_dryer_temperature"].to_numpy()
    )


def test_dryer_configuration_unchanged() -> None:
    plant = load_scenario(EXAMPLES / "plant_reference.toml")
    dryer = load_scenario(EXAMPLES / "reference_constant.toml")
    assert plant.spec.dryer == dryer.spec.dryer
    assert plant.spec.product_feed == dryer.spec.product_feed
    assert plant.spec.ambient == dryer.spec.ambient


def test_swap_boiler_for_timeseries(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    end = "2026-01-01T08:00:00Z"  # the oil demand step at 06:00 changes the flue gas
    coupled = make_variant(tmp_path, base="plant_oil_step.toml", end=end)
    code, folder = run_cli(coupled, tmp_path / "runs", capsys)
    assert code == 0
    import pandas as pd

    plant = pd.read_csv(folder / "results.csv", skiprows=[1])
    alone = simulate(load_scenario(dryer_only_from_interface(tmp_path, folder, end))).results
    assert len(alone) == len(plant)
    for col in COMPARED:
        a, b = alone[col].to_numpy(dtype=float), plant[col].to_numpy(dtype=float)
        assert np.allclose(a, b, rtol=1e-3, atol=1e-9), (
            col,
            float(np.max(np.abs(a - b) / np.abs(b))),
        )
