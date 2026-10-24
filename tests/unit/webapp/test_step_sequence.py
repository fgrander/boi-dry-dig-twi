"""Step sequences stored as time-series CSV (T024; FR-007a, data-model §5)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from boidrytwin import load_scenario
from boidrytwin.webapp.scenario_form import materialize, read_form, set_field
from boidrytwin.webapp.steps import Step, StepError, StepSequence, read_meta, step_csv

EXAMPLE = Path(__file__).parents[3] / "examples" / "plant_reference.toml"
START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 2, tzinfo=UTC)


def _seq() -> StepSequence:
    return StepSequence(
        unit="degC",
        start_value=240.0,
        steps=[
            Step(time=datetime(2026, 1, 1, 6, tzinfo=UTC), value=231.6),
            Step(time=datetime(2026, 1, 1, 12, tzinfo=UTC), value=240.0),
        ],
    )


def test_csv_format() -> None:
    text = step_csv(_seq(), START, END)
    assert text.splitlines() == [
        "time,value",
        "unit,degC",
        "2026-01-01T00:00:00Z,240.0",
        "2026-01-01T06:00:00Z,240.0",
        "2026-01-01T06:00:01Z,231.6",
        "2026-01-01T12:00:00Z,231.6",
        "2026-01-01T12:00:01Z,240.0",
        "2026-01-02T00:00:00Z,240.0",
    ]


@pytest.mark.parametrize(
    "steps",
    [
        [
            Step(time=datetime(2026, 1, 1, 6, tzinfo=UTC), value=1.0),
            Step(time=datetime(2026, 1, 1, 6, tzinfo=UTC), value=2.0),
        ],  # not increasing
        [Step(time=datetime(2025, 12, 31, tzinfo=UTC), value=1.0)],  # before the start
        [Step(time=datetime(2026, 1, 2, tzinfo=UTC), value=1.0)],  # at the end
    ],
)
def test_times_checked(steps: list[Step]) -> None:
    with pytest.raises(StepError):
        step_csv(StepSequence(unit="degC", start_value=1.0, steps=steps), START, END)


def test_saved_scenario_uses_the_steps(tmp_path: Path) -> None:
    form = read_form(EXAMPLE)
    set_field(form, "boiler_house.thermal_oil", "return_temperature", steps=_seq())
    target = tmp_path / "wet.toml"
    materialize(form, target)
    csv = tmp_path / "wet.steps" / "steps_boiler_house.thermal_oil.return_temperature.csv"
    assert csv.is_file()
    ref = "wet.steps/steps_boiler_house.thermal_oil.return_temperature.csv"
    expected = f'return_temperature = {{ file = "{ref}", column = "value" }}'
    assert expected in target.read_text(encoding="utf-8")
    loaded = load_scenario(target)
    sig = loaded.signals["boiler_house.thermal_oil.return_temperature"]
    assert sig.value_at(0.0) == pytest.approx(513.15)
    assert sig.value_at(6 * 3600 + 1) == pytest.approx(504.75)
    meta = read_meta(target)
    assert meta.steps["boiler_house.thermal_oil.return_temperature"] == _seq()
    again = read_form(target)
    field = again.section("boiler_house.thermal_oil").field("return_temperature")
    assert field.kind == "steps" and field.steps == _seq()


def test_out_of_range_step_value_rejected_by_the_loader(tmp_path: Path) -> None:
    from boidrytwin.errors import ScenarioValidationError

    form = read_form(EXAMPLE)
    step = Step(time=datetime(2026, 1, 1, 6, tzinfo=UTC), value=150.0)
    seq = StepSequence(unit="%", start_value=45.0, steps=[step])
    set_field(form, "boiler_house.fuel", "moisture_wet_basis", steps=seq)
    target = tmp_path / "bad.toml"
    materialize(form, target)
    with pytest.raises(ScenarioValidationError):
        load_scenario(target)
