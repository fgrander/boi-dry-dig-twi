"""FlueGasState and derived quantities (T019)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from boidrytwin.interface.composition import GasComposition
from boidrytwin.interface.flue_gas import FlueGasState, check_state_values
from boidrytwin.properties import gas, water

T0 = datetime(2026, 1, 1, tzinfo=UTC)
FLUE = GasComposition.from_input(
    {"x_N2": 0.705, "x_O2": 0.06, "x_CO2": 0.105, "x_H2O": 0.12, "x_other": 0.01}
)
PURE_N2 = GasComposition.from_input(
    {"x_N2": 1.0, "x_O2": 0.0, "x_CO2": 0.0, "x_H2O": 0.0, "x_other": 0.0}
)


def _state(**kw: object) -> FlueGasState:
    base: dict[str, object] = {
        "time": T0,
        "mass_flow": 8.0,
        "temperature": 923.15,
        "pressure": 101_000.0,
        "composition": FLUE,
    }
    base.update(kw)
    return FlueGasState(**base)  # type: ignore[arg-type]


def test_valid_state() -> None:
    s = _state()
    assert s.quality == "good"
    assert s.mass_flow == 8.0


@pytest.mark.parametrize(
    "kw",
    [
        {"mass_flow": -1.0},
        {"temperature": 272.0},
        {"temperature": 1474.0},
        {"pressure": 50_000.0},
        {"pressure": 200_000.0},
        {"time": datetime(2026, 1, 1)},  # naive
        {"quality": "weird"},
    ],
)
def test_invalid_values_rejected(kw: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _state(**kw)


def test_quality_values() -> None:
    for q in ("good", "interpolated", "missing", "stale", "bad"):
        assert _state(quality=q).quality == q


def test_heat_content_flow_hand_calculation() -> None:
    # NIST-JANAF N2: H - H(298.15) = 11.937 kJ/mol at 700 K, 15.046 kJ/mol at 800 K
    dh_molar = 11.937e3 + (723.15 - 700.0) / 100.0 * (15.046e3 - 11.937e3)
    expected = 2.0 * dh_molar / 0.028014
    s = _state(mass_flow=2.0, temperature=723.15, composition=PURE_N2)
    assert s.heat_content_flow() == pytest.approx(expected, rel=5e-3)


def test_heat_content_flow_is_zero_at_reference() -> None:
    assert _state(temperature=298.15).heat_content_flow() == pytest.approx(0.0, abs=1e-6)
    s = _state(temperature=400.0)
    assert s.heat_content_flow(T_ref=400.0) == pytest.approx(0.0, abs=1e-6)


def test_humidity_and_dew_point() -> None:
    s = _state()
    x = FLUE.as_array()
    m_dry = sum(x[i] * gas.MOLAR_MASS[i] for i in range(5) if i != gas.I_H2O)
    assert s.humidity == pytest.approx(0.12 * gas.MOLAR_MASS[gas.I_H2O] / m_dry)
    assert s.dew_point == pytest.approx(
        water.dew_point(s.humidity, s.pressure, FLUE.dry_molar_mass)
    )
    assert 320.0 < s.dew_point < 330.0  # 12 vol-% water ≈ 50 °C dew point


def test_check_state_values_reports_each_problem() -> None:
    issues = check_state_values(mass_flow=-1.0, temperature=2000.0, pressure=10.0)
    fields = {f for f, _, _ in issues}
    assert fields == {"mass_flow", "temperature", "pressure"}
    reasons = {f: r for f, r, _ in issues}
    assert reasons["mass_flow"] == "must be ≥ 0"
    assert reasons["temperature"] == "out of range"
    assert reasons["pressure"] == "out of range"
    assert check_state_values(mass_flow=1.0, temperature=900.0, pressure=101_325.0) == []
