"""BoilerHouseConfiguration (T011; data-model.md §2)."""

import pytest
from pydantic import ValidationError

from boidrytwin.boiler_house.config import (
    FURNACE_FIELDS,
    BoilerHouseConfiguration,
    ConvectiveHeater,
    RadiantHeater,
    reference_configuration,
)


def test_reference_defaults() -> None:
    cfg = reference_configuration()
    f = cfg.furnace
    assert f.rated_fuel_power == 15e6
    assert f.min_load_fraction == 0.3
    assert (f.bed_time_constant, f.water_time_constant, f.feed_dead_time) == (900.0, 600.0, 120.0)
    assert f.o2_sensor_time_constant == 30.0
    assert len(cfg.heaters) == 3
    radiant, conv = cfg.heaters[0], cfg.heaters[1]
    assert isinstance(radiant, RadiantHeater) and radiant.flame_emissivity == 0.5
    assert radiant.convective_htc == 11.0
    assert isinstance(conv, ConvectiveHeater)
    assert (conv.n_cells, conv.gas_emissivity, conv.fouling_resistance) == (5, 0.1, 0.008)
    assert cfg.bypass.starts_after_heater == 1


def test_every_field_has_two_ranges_and_a_doc() -> None:
    for spec_table in (FURNACE_FIELDS, RadiantHeater.FIELDS, ConvectiveHeater.FIELDS):
        for name, spec in spec_table.items():
            lo, hi = spec.physical
            vlo, vhi = spec.validated
            assert lo <= vlo <= vhi <= hi, name
            assert spec.doc, name


def test_first_heater_must_be_radiant_and_others_convective() -> None:
    cfg = reference_configuration()
    with pytest.raises(ValidationError, match="radiant"):
        BoilerHouseConfiguration(
            furnace=cfg.furnace, heaters=[cfg.heaters[1], cfg.heaters[1]], bypass=cfg.bypass
        )
    with pytest.raises(ValidationError, match="convective"):
        BoilerHouseConfiguration(
            furnace=cfg.furnace, heaters=[cfg.heaters[0], cfg.heaters[0]], bypass=cfg.bypass
        )


def test_bypass_must_start_before_the_last_heater() -> None:
    cfg = reference_configuration()
    with pytest.raises(ValidationError, match="starts_after_heater"):
        BoilerHouseConfiguration(
            furnace=cfg.furnace,
            heaters=cfg.heaters,
            bypass=cfg.bypass.model_copy(update={"starts_after_heater": 3}),
        )


def test_physical_range_rejected_and_validated_range_reported() -> None:
    cfg = reference_configuration()
    with pytest.raises(ValidationError, match="flame_emissivity"):
        RadiantHeater(**{**cfg.heaters[0].model_dump(), "flame_emissivity": 1.5})
    odd = cfg.model_copy(
        update={
            "heaters": [
                cfg.heaters[0].model_copy(update={"flame_emissivity": 0.95}),
                *cfg.heaters[1:],
            ]
        }
    )
    assert any(v.field == "heaters[0].flame_emissivity" for v in odd.validated_range_violations())


def test_sizing_notes_are_documented() -> None:
    # the reference geometry is sized by documented rules of thumb (analysis finding U3)
    assert "kW/m²" in reference_configuration.__doc__  # type: ignore[operator]
