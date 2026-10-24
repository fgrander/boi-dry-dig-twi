"""Operator scenarios: versions, releases, baselines (T034; FR-012, FR-014, data-model §6)."""

import tomllib
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.jobs import JobQueue
from boidrytwin.webapp.operator import (
    DEFAULT_OUTPUTS,
    OperatorStore,
    Release,
    ReleaseError,
    baseline_state,
)

MOIST = Release(
    key="boiler_house.fuel.moisture_wet_basis",
    label="Fuel moisture",
    unit="%",
    minimum=35,
    maximum=55,
    allow_step=True,
)
RETURN = Release(
    key="boiler_house.thermal_oil.return_temperature",
    label="Oil return",
    unit="degC",
    minimum=220,
    maximum=260,
)


@pytest.fixture
def store(web_settings: Any) -> OperatorStore:
    return OperatorStore(web_settings.scenarios_dir, JobQueue(web_settings.app_dir))


def test_create_version(store: OperatorStore, web_settings: Any) -> None:
    v = store.create_version(
        "fuel_and_oil",
        web_settings.examples_dir / "plant_reference.toml",
        [MOIST, RETURN],
        view="engineer",
    )
    folder = web_settings.scenarios_dir / "operator" / "fuel_and_oil" / "v1"
    assert v.version == 1 and (folder / "scenario.toml").is_file()
    doc = tomllib.loads((folder / "operator.toml").read_text(encoding="utf-8"))
    assert doc["version"] == 1 and [r["key"] for r in doc["release"]] == [MOIST.key, RETURN.key]
    assert doc["comparison_outputs"] == list(DEFAULT_OUTPUTS)  # coupled: all defaults
    assert doc["baseline"]["job_id"] == v.baseline_job_id
    job = JobQueue(web_settings.app_dir).get(v.baseline_job_id)
    assert job.kind == "baseline" and job.state == "queued"


def test_versions_increase(store: OperatorStore, web_settings: Any) -> None:
    src = web_settings.examples_dir / "plant_reference.toml"
    a = store.create_version("x", src, [MOIST], view="engineer")
    b = store.create_version("x", src, [MOIST, RETURN], view="engineer")
    assert (a.version, b.version) == (1, 2)
    assert [v.version for v in store.versions("x")] == [1, 2]
    assert store.get("x").version == 2 and store.get("x", 1).releases == [MOIST]


def test_boiler_only_outputs_leave_out_dryer(store: OperatorStore, web_settings: Any) -> None:
    v = store.create_version(
        "b", web_settings.examples_dir / "boiler_house_only.toml", [MOIST], view="engineer"
    )
    assert "product_moisture_wet_basis" not in v.comparison_outputs
    assert "oil_outlet_temperature" in v.comparison_outputs


def test_custom_outputs(store: OperatorStore, web_settings: Any) -> None:
    v = store.create_version(
        "c",
        web_settings.examples_dir / "plant_reference.toml",
        [MOIST],
        comparison_outputs=["fuel_feed", "losses"],
        view="engineer",
    )
    assert v.comparison_outputs == ["fuel_feed", "losses"]


@pytest.mark.parametrize(
    "release",
    [
        Release(key=MOIST.key, label="x", unit="%", minimum=50, maximum=40),  # min ≥ max
        Release(key=MOIST.key, label="x" * 61, unit="%", minimum=35, maximum=55),  # label
        Release(key="boiler_house.fuel.nope", label="x", unit="%", minimum=1, maximum=2),  # key
        Release(key=MOIST.key, label="x", unit="degC", minimum=35, maximum=55),  # dimension
        Release(
            key=MOIST.key, label="x", unit="%", minimum=35, maximum=70
        ),  # outside the twin's range
        Release(
            key="boiler_house.furnace.rated_fuel_power",
            label="x",
            unit="MW",
            minimum=10,
            maximum=20,
            allow_step=True,
        ),  # no time series for this input
    ],
)
def test_release_checks(store: OperatorStore, web_settings: Any, release: Release) -> None:
    with pytest.raises(ReleaseError):
        store.create_version(
            "bad", web_settings.examples_dir / "plant_reference.toml", [release], view="engineer"
        )
    assert not (web_settings.scenarios_dir / "operator" / "bad").exists()


def test_baseline_states(store: OperatorStore, web_settings: Any) -> None:
    q = JobQueue(web_settings.app_dir)
    v = store.create_version(
        "s", web_settings.examples_dir / "plant_reference.toml", [MOIST], view="engineer"
    )
    assert baseline_state(v, q) == ("baseline pending", None)
    q.mark_running(v.baseline_job_id)
    q.mark_finished(v.baseline_job_id, run_id="r-1", failed=False)
    assert baseline_state(v, JobQueue(web_settings.app_dir)) == ("ready", "r-1")
    w = store.create_version(
        "s", web_settings.examples_dir / "plant_reference.toml", [MOIST], view="engineer"
    )
    q = JobQueue(web_settings.app_dir)
    q.mark_running(w.baseline_job_id)
    q.mark_finished(w.baseline_job_id, run_id=None, failed=True, message="x")
    assert baseline_state(w, JobQueue(web_settings.app_dir))[0] == "baseline failed"
