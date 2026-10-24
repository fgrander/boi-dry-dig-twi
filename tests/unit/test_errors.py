"""Validation issue and error types (T009)."""

import json

import pytest

from boidrytwin.errors import (
    InterfaceValidationError,
    ScenarioValidationError,
    ValidationIssue,
)


def _issue(field: str = "flue_gas.mass_flow") -> ValidationIssue:
    return ValidationIssue(
        field=field,
        value="-1 kg/s",
        reason="must be ≥ 0",
        allowed="≥ 0 kg/s",
        location="scenario.toml:12",
    )


def test_issue_fields_and_immutability() -> None:
    issue = _issue()
    assert issue.field == "flue_gas.mass_flow"
    assert issue.location == "scenario.toml:12"
    with pytest.raises(Exception):  # noqa: B017 - pydantic raises ValidationError on frozen models
        issue.field = "other"  # type: ignore[misc]


def test_location_is_optional() -> None:
    issue = ValidationIssue(field="x", value="1", reason="r", allowed="a")
    assert issue.location is None


@pytest.mark.parametrize("error_type", [ScenarioValidationError, InterfaceValidationError])
def test_errors_collect_issues(error_type: type[ScenarioValidationError]) -> None:
    err = error_type([_issue("a"), _issue("b")])
    assert [i.field for i in err.issues] == ["a", "b"]
    text = str(err)
    assert "a" in text and "b" in text and "must be ≥ 0" in text


def test_error_renders_json() -> None:
    err = ScenarioValidationError([_issue()])
    payload = json.loads(err.to_json())
    assert payload["valid"] is False
    assert payload["issues"][0] == {
        "field": "flue_gas.mass_flow",
        "value": "-1 kg/s",
        "reason": "must be ≥ 0",
        "allowed": "≥ 0 kg/s",
        "location": "scenario.toml:12",
    }


def test_interface_error_is_a_scenario_error() -> None:
    # interface problems found while loading a scenario are scenario problems too
    assert issubclass(InterfaceValidationError, ScenarioValidationError)
