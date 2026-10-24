"""BalanceReport (T063; FR-013, SC-002)."""

import pytest

from boidrytwin.checks.balances import QUANTITIES, BalanceReport, balance_report
from boidrytwin.scenario.schema import BalanceTolerances

TOL = BalanceTolerances()  # 0.1 % mass, 1 % energy


def _store(dry: float, water: float, gas: float, energy: float) -> dict[str, float]:
    return {"dry_solids": dry, "water": water, "gas": gas, "energy": energy}


def test_closed_balances_pass() -> None:
    flows = {
        "dry_solids": (1000.0, 900.0),
        "water": (5000.0, 4950.0),
        "gas": (20_000.0, 20_000.0),
        "energy": (8.0e9, 7.9e9),
    }
    start = _store(0.0, 0.0, 100.0, 1.0e6)
    end = _store(100.0, 50.0, 100.0, 1.0e6 + 1.0e8)
    report = balance_report(flows, start, end, TOL)
    assert isinstance(report, BalanceReport)
    assert report.passed
    for q in QUANTITIES:
        b = getattr(report, q)
        assert b.residual == pytest.approx(0.0, abs=1e-6)
        assert b.passed


def test_residual_definition_and_relative_value() -> None:
    flows = {q: (1000.0, 990.0) for q in QUANTITIES}
    start = _store(0.0, 0.0, 0.0, 0.0)
    end = _store(9.5, 9.5, 9.5, 9.5)
    report = balance_report(flows, start, end, TOL)
    b = report.water
    assert b.inflow == 1000.0 and b.outflow == 990.0 and b.storage_change == 9.5
    assert b.residual == pytest.approx(0.5)  # in - out - change in storage
    assert b.relative_residual == pytest.approx(0.5 / 1000.0)
    assert b.tolerance == TOL.mass
    assert b.passed  # 0.05 % < 0.1 %
    assert report.energy.tolerance == TOL.energy


def test_leaky_result_fails() -> None:
    flows = {q: (1000.0, 990.0) for q in QUANTITIES}
    start = _store(0.0, 0.0, 0.0, 0.0)
    end = _store(5.0, 9.99, 10.0, -5.0)  # 5 kg dry solids and 1.5 % of the energy vanish
    report = balance_report(flows, start, end, TOL)
    assert not report.dry_solids.passed
    assert report.water.passed and report.gas.passed
    assert report.energy.relative_residual == pytest.approx(0.015)
    assert not report.energy.passed
    assert not report.passed


def test_zero_inflow_uses_stored_amount_as_reference() -> None:
    flows = {q: (0.0, 0.0) for q in QUANTITIES}
    start = _store(0.0, 0.0, 50.0, 1.0e6)
    end = _store(0.0, 0.0, 50.0, 1.0e6)
    report = balance_report(flows, start, end, TOL)
    assert report.passed
    assert report.dry_solids.relative_residual == 0.0
