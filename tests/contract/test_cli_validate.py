"""CLI contract: ``boidrytwin validate`` (T024; contracts/cli.md)."""

import json

import pytest

from boidrytwin.cli import main

from .conftest import CONSTANT_FLUE_GAS, ScenarioWriter


def test_valid_scenario(write_scenario: ScenarioWriter, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["validate", str(write_scenario())])
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("OK")
    assert "923.15" in out  # normalised SI summary


def test_invalid_scenario(
    write_scenario: ScenarioWriter, capsys: pytest.CaptureFixture[str]
) -> None:
    flue = CONSTANT_FLUE_GAS.replace('"8.0 kg/s"', '"-1 kg/s"')
    code = main(["validate", str(write_scenario(flue_gas=flue))])
    out = capsys.readouterr().out
    assert code == 1
    assert "flue_gas.mass_flow" in out and "must be ≥ 0" in out


def test_json_output_schema(
    write_scenario: ScenarioWriter, capsys: pytest.CaptureFixture[str]
) -> None:
    flue = CONSTANT_FLUE_GAS.replace('"8.0 kg/s"', '"-1 kg/s"')
    code = main(["validate", "--json", str(write_scenario(flue_gas=flue))])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["valid"] is False
    assert set(payload["issues"][0]) == {"field", "value", "reason", "allowed", "location"}

    code = main(["validate", "--json", str(write_scenario())])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload == {"valid": True, "issues": []}


def test_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", "does-not-exist.toml"]) == 1
    assert "file not found" in capsys.readouterr().out


def test_logs_go_to_stderr(
    write_scenario: ScenarioWriter, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["validate", "--log-level", "INFO", str(write_scenario())])
    captured = capsys.readouterr()
    assert "scenario_validated" in captured.err
    assert "scenario_validated" not in captured.out
