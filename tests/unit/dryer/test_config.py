"""DryerConfiguration with physical and validated ranges (T035)."""

import math

import pytest

from boidrytwin.dryer.config import FIELDS, DryerConfiguration, RangeViolation

REQUIRED = {
    "length": 20.0,
    "diameter": 4.0,
    "slope": math.radians(2),
    "shell_mass": 60_000.0,
    "rotation_speed": 4 * 2 * math.pi / 60,
}


def test_defaults() -> None:
    cfg = DryerConfiguration(**REQUIRED)
    assert cfg.n_cells == 20
    assert cfg.gas_flow_direction == "co-current"
    assert cfg.fibre_saturation_moisture == 0.30
    assert cfg.shell_emissivity == 0.8
    assert cfg.shell_specific_heat == 500.0
    assert cfg.min_dew_point_margin == 10.0
    assert cfg.emc_data_limit == 403.15


def test_every_field_has_two_ranges_and_a_doc() -> None:
    for name, spec in FIELDS.items():
        assert spec.physical[0] <= spec.validated[0] <= spec.validated[1] <= spec.physical[1], name
        assert spec.doc and spec.dimension, name


@pytest.mark.parametrize(
    ("field", "value"),
    [("length", 0.0), ("diameter", -1.0), ("slope", 1.0), ("n_cells", 9), ("n_cells", 41),
     ("shell_emissivity", 1.5), ("fibre_saturation_moisture", 0.9)],
)  # fmt: skip
def test_outside_physical_range_is_rejected(field: str, value: float) -> None:
    with pytest.raises(ValueError, match=field):
        DryerConfiguration(**{**REQUIRED, field: value})


def test_outside_validated_range_is_accepted_and_reported() -> None:
    cfg = DryerConfiguration(**{**REQUIRED, "diameter": 8.0, "drag_coefficient": 5.0})
    violations = cfg.validated_range_violations()
    assert {v.field for v in violations} == {"diameter", "drag_coefficient"}
    v = next(v for v in violations if v.field == "diameter")
    assert isinstance(v, RangeViolation)
    assert v.value == 8.0 and v.limit_type == "max" and v.limit == FIELDS["diameter"].validated[1]


def test_inside_validated_range_reports_nothing() -> None:
    assert DryerConfiguration(**REQUIRED).validated_range_violations() == []


def test_only_co_current_supported() -> None:
    with pytest.raises(ValueError):
        DryerConfiguration(**{**REQUIRED, "gas_flow_direction": "counter-current"})


def test_derived_geometry() -> None:
    cfg = DryerConfiguration(**REQUIRED)
    assert cfg.cell_length == pytest.approx(1.0)
    assert cfg.cross_section == pytest.approx(math.pi * 4.0)
    assert cfg.cell_volume == pytest.approx(math.pi * 4.0)
