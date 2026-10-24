"""Unit parsing at the boundary (T008)."""

import math

import pytest

from boidrytwin.units import QuantityError, parse_quantity


@pytest.mark.parametrize(
    ("text", "dimension", "expected"),
    [
        ("450 degC", "temperature", 723.15),
        ("723.15 K", "temperature", 723.15),
        ("12.5 t/h", "mass_flow", 12.5 * 1000 / 3600),
        ("8.0 kg/s", "mass_flow", 8.0),
        ("101.0 kPa", "pressure", 101_000.0),
        ("70.5 %", "fraction", 0.705),
        ("2 deg", "angle", math.radians(2)),
        ("4 rpm", "angular_velocity", 4 * 2 * math.pi / 60),
        ("16 mm", "length", 0.016),
        ("60 t", "mass", 60_000.0),
        ("1 min", "time", 60.0),
        ("450 kg/m^3", "density", 450.0),
        ("100 W/(m^2*K)", "heat_transfer_coefficient", 100.0),
    ],
)
def test_parse_to_si(text: str, dimension: str, expected: float) -> None:
    assert parse_quantity(text, dimension) == pytest.approx(expected, rel=1e-9)


def test_fraction_accepts_plain_number() -> None:
    assert parse_quantity("0.8", "fraction") == pytest.approx(0.8)
    assert parse_quantity(0.25, "fraction") == pytest.approx(0.25)


def test_dimensionless_accepts_plain_number() -> None:
    assert parse_quantity(24, "dimensionless") == 24.0


@pytest.mark.parametrize("value", ["450", 450, 450.0, "  12.5 "])
def test_missing_unit_is_rejected(value: object) -> None:
    with pytest.raises(QuantityError, match="unit missing"):
        parse_quantity(value, "temperature")


def test_incompatible_unit_is_rejected() -> None:
    with pytest.raises(QuantityError, match="incompatible unit"):
        parse_quantity("5 kg", "temperature")


def test_unparseable_text_is_rejected() -> None:
    with pytest.raises(QuantityError, match="cannot parse"):
        parse_quantity("hot", "temperature")


def test_gauge_pressure_with_reference() -> None:
    assert parse_quantity("-2 mbar", "pressure", gauge_reference=101_325.0) == pytest.approx(
        101_125.0
    )


def test_unknown_dimension_is_a_programming_error() -> None:
    with pytest.raises(KeyError):
        parse_quantity("1 m", "no_such_dimension")
