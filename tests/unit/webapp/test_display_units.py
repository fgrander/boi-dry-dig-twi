"""The one SI → display unit conversion of the web app (T005; FR-003)."""

import numpy as np
import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.display_units import display_unit, to_display, to_si


@pytest.mark.parametrize(
    ("column", "unit", "si", "shown", "value"),
    [
        ("oil_outlet_temperature", "K", 555.15, "°C", 282.0),
        ("heat_to_oil", "W", 7.8e6, "MW", 7.8),
        ("product_moisture_wet_basis", "kg/kg", 0.33, "%", 33.0),
        ("o2_dry", "mol/mol", 0.07, "%", 7.0),
        ("exhaust_x_H2O", "mol/mol", 0.2, "%", 20.0),
        ("pressure", "Pa", 101_000.0, "kPa", 101.0),
        ("fuel_feed", "kg/s", 1.0, "t/h", 3.6),
        ("product_dry_mass_flow", "kg/s", 1.0, "t/h", 3.6),
        ("flue_gas_to_dryer_mass_flow", "kg/s", 8.5, "kg/s", 8.5),
    ],
)
def test_display_conversion(column: str, unit: str, si: float, shown: str, value: float) -> None:
    assert display_unit(column, unit) == shown
    out = to_display(column, unit, np.array([si]))
    assert out[0] == pytest.approx(value, rel=1e-12)
    back = to_si(column, unit, out)
    assert back[0] == pytest.approx(si, rel=1e-12, abs=1e-12)


def test_unknown_and_unitless_columns_pass_through() -> None:
    assert display_unit("load_fraction", "") == ""
    assert display_unit("odd", "furlong/fortnight") == "furlong/fortnight"
    v = np.array([0.5, 1.5])
    assert np.array_equal(to_display("load_fraction", "", v), v)
    assert np.array_equal(to_display("odd", "furlong/fortnight", v), v)
