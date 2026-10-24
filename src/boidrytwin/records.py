"""Run records: reproducibility and audit trail of simulation runs (FR-014, FR-017).

A run folder ``<out>/<run_id>/`` holds ``run_record.json``, ``results.csv`` (second row:
units), optional ``profiles.csv`` and ``final_state.json``. A boiler-house-only run (feature
002) writes ``boiler_results.csv`` instead of ``results.csv``; its final state holds the
boiler house state plus the controller integrals.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from boidrytwin.dryer.simulate import SimulationResult, simulate
from boidrytwin.errors import ScenarioValidationError, SimulationError, ValidationIssue
from boidrytwin.logging import bind_run_id, get_logger
from boidrytwin.plant.simulate import PlantSimulationResult, simulate_plant
from boidrytwin.scenario.loader import LoadedScenario, load_scenario, require_runnable
from boidrytwin.scenario.timeseries import sha256_of
from boidrytwin.validation.compare import (
    ValidationReport,
    compare_frames,
    load_settings,
    read_measured,
)

log = get_logger("records")

Status = Literal["created", "validated", "running", "completed", "failed", "rejected"]

RESULT_UNITS: dict[str, str] = {
    "product_dry_mass_flow": "kg/s",
    "product_moisture_wet_basis": "kg/kg",
    "product_temperature": "K",
    "evaporation_rate": "kg/s",
    "exhaust_mass_flow": "kg/s",
    "exhaust_temperature": "K",
    "exhaust_humidity": "kg/kg dry gas",
    "exhaust_x_N2": "mol/mol",
    "exhaust_x_O2": "mol/mol",
    "exhaust_x_CO2": "mol/mol",
    "exhaust_x_H2O": "mol/mol",
    "exhaust_x_other": "mol/mol",
    "exhaust_dew_point": "K",
    "drum_inlet_gas_temperature": "K",
    "heat_supplied": "W",
    "heat_used_for_drying": "W",
    "shell_heat_loss": "W",
    "specific_energy": "J/kg",
    "solids_holdup": "kg",
    "heat_limited": "",
    "out_of_range": "",
    "condensation_risk": "",
    "input_quality": "",
}
PROFILE_UNITS: dict[str, str] = {
    "cell": "",
    "solids_temperature": "K",
    "gas_temperature": "K",
    "gas_humidity": "kg/kg dry gas",
    "moisture_wet_basis": "kg/kg",
    "solids_holdup": "kg",
    "shell_temperature": "K",
}
FLAG_COLUMNS = ("heat_limited", "out_of_range", "condensation_risk")
BOILER_FLAG_COLUMNS = (
    "oil_limit",
    "combustion_out_of_range",
    "load_out_of_range",
    "controller_saturated",
    "setpoint_not_reached",
    "out_of_range",
)
BOILER_UNITS: dict[str, str] = {
    "fuel_feed": "kg/s",
    "fuel_delivered": "kg/s",
    "fuel_burnout_dry": "kg/s",
    "fuel_moisture_wet_basis": "kg/kg",
    "heat_released": "W",
    "load_fraction": "",
    "excess_air_ratio": "",
    "o2_dry": "mol/mol",
    "o2_dry_measured": "mol/mol",
    "combustion_air_flow": "kg/s",
    "furnace_temperature": "K",
    "oil_outlet_temperature": "K",
    "heat_to_oil": "W",
    "max_film_temperature": "K",
    "min_oil_velocity": "m/s",
    "min_oil_reynolds": "",
    "losses": "W",
    "bypass_position": "",
    "dilution_air_flow": "kg/s",
    "flue_gas_to_dryer_mass_flow": "kg/s",
    "flue_gas_to_dryer_temperature": "K",
    "controller_output_oil_temperature": "kg/s",
    "controller_output_oxygen": "",
    "controller_output_drum_inlet_temperature": "",
}
BOILER_UNIT_PATTERNS = (
    ("gas_temperature_after_heater_", "K"),
    ("oil_temperature_after_heater_", "K"),
    ("heat_to_oil_", "W"),
)


def boiler_units(columns: list[str]) -> dict[str, str]:
    units = dict(BOILER_UNITS)
    for col in columns:
        for prefix, unit in BOILER_UNIT_PATTERNS:
            if col.startswith(prefix):
                units[col] = unit
    return units


class RunRecord(BaseModel):
    """Everything needed to reproduce and audit a run (data-model.md §4)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    created_at: datetime
    status: Status
    model_version: str
    environment: dict[str, str]
    scenario_file: str
    scenario: dict[str, Any]
    scenario_sha256: str
    input_files: dict[str, str] = Field(default_factory=dict)
    results_file: str | None = None
    profiles_file: str | None = None
    final_state_file: str | None = None
    balance_report: dict[str, Any] | None = None
    plant_balance_report: dict[str, Any] | None = None
    controller_settings: dict[str, Any] = Field(default_factory=dict)
    range_warnings: list[dict[str, Any]] = Field(default_factory=list)
    flags_summary: dict[str, int] = Field(default_factory=dict)
    solver_stats: dict[str, Any] = Field(default_factory=dict)
    rejected_inputs: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None

    def save(self, folder: Path) -> Path:
        path = folder / "run_record.json"
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> RunRecord:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def scenario_hash(spec_json: dict[str, Any]) -> str:
    canonical = json.dumps(spec_json, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def model_version() -> str:
    try:
        pkg = version("boidrytwin")
    except PackageNotFoundError:  # pragma: no cover - running from a source tree
        pkg = "0+unknown"
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            cwd=Path(__file__).parent,
        ).stdout.strip()
    except OSError:  # pragma: no cover - git not installed
        commit = ""
    return f"{pkg}+{commit}" if commit else pkg


def environment() -> dict[str, str]:
    env = {"python": sys.version.split()[0], "platform": platform.platform()}
    for pkg in ("numpy", "scipy", "pandas", "pint", "pydantic", "structlog"):
        try:
            env[pkg] = version(pkg)
        except PackageNotFoundError:  # pragma: no cover
            env[pkg] = "missing"
    return env


def write_csv(frame: pd.DataFrame, path: Path, units: dict[str, str], index_label: str) -> None:
    """CSV with a unit row; floats with 17 significant digits so reruns compare exactly."""
    data = frame.reset_index()
    data[index_label] = pd.DatetimeIndex(data[index_label]).strftime("%Y-%m-%dT%H:%M:%SZ")
    unit_row = {col: units.get(col, "") for col in data.columns}
    unit_row[index_label] = "unit"
    out = pd.concat([pd.DataFrame([unit_row]), data], ignore_index=True)
    out.to_csv(path, index=False, float_format="%.17g", lineterminator="\n")


def new_record(loaded: LoadedScenario, run_id: str | None = None) -> RunRecord:
    spec_json = loaded.spec.model_dump(mode="json")
    return RunRecord(
        run_id=run_id or str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        status="validated",
        model_version=model_version(),
        environment=environment(),
        scenario_file=str(loaded.path),
        scenario=spec_json,
        scenario_sha256=scenario_hash(spec_json),
        input_files=dict(loaded.input_files),
    )


def write_outputs(record: RunRecord, sim: SimulationResult, folder: Path) -> None:
    write_csv(sim.results, folder / "results.csv", RESULT_UNITS, "time")
    record.results_file = "results.csv"
    if sim.profiles is not None:
        frame = sim.profiles.reset_index("cell")
        write_csv(frame, folder / "profiles.csv", PROFILE_UNITS, "time")
        record.profiles_file = "profiles.csv"
    sim.final_state.save(folder / "final_state.json")
    record.final_state_file = "final_state.json"
    record.solver_stats = dict(sim.solver_stats)
    record.balance_report = sim.balance.to_dict()
    record.range_warnings = [w.model_dump(mode="json") for w in sim.range_warnings]
    record.flags_summary = {
        flag: int(sim.results[flag].astype(bool).sum()) for flag in FLAG_COLUMNS
    }
    record.flags_summary["input_quality_not_good"] = int(
        (sim.results["input_quality"] != "good").sum()
    )


def write_plant_outputs(record: RunRecord, sim: PlantSimulationResult, folder: Path) -> None:
    columns = list(sim.results.columns)
    write_csv(sim.results, folder / "boiler_results.csv", boiler_units(columns), "time")
    record.results_file = "boiler_results.csv"
    sim.final_state.save(folder / "final_state.json")
    record.final_state_file = "final_state.json"
    record.solver_stats = dict(sim.solver_stats)
    record.plant_balance_report = sim.balance.to_dict()
    record.controller_settings = sim.controller_settings
    record.range_warnings = [w.model_dump(mode="json") for w in sim.range_warnings]
    record.flags_summary = {
        flag: int(sim.results[flag].astype(bool).sum()) for flag in BOILER_FLAG_COLUMNS
    }


def run(
    loaded: LoadedScenario, out_dir: str | Path = "runs", *, profiles: bool = False
) -> RunRecord:
    """Simulate a validated scenario and write its run folder. Returns the run record.

    A solver failure is recorded with status ``failed`` and re-raised as
    :class:`SimulationError`.
    """
    return run_with_result(loaded, out_dir, profiles=profiles)[0]


def run_with_result(
    loaded: LoadedScenario, out_dir: str | Path = "runs", *, profiles: bool = False
) -> tuple[RunRecord, SimulationResult | PlantSimulationResult]:
    """As :func:`run`, also returning the in-memory simulation result."""
    record = new_record(loaded)
    folder = Path(out_dir) / record.run_id
    folder.mkdir(parents=True, exist_ok=False)
    bind_run_id(record.run_id)
    log.info("run_started", scenario=str(loaded.path), simulated_s=loaded.spec.time.duration)
    record.status = "running"
    sim: SimulationResult | PlantSimulationResult
    try:
        if loaded.spec.boiler_house is not None:
            sim = simulate_plant(loaded)
        else:
            sim = simulate(loaded, profiles=profiles)
    except SimulationError as exc:
        record.status = "failed"
        record.message = str(exc)
        record.save(folder)
        log.error("run_failed", error=str(exc))
        raise
    if isinstance(sim, PlantSimulationResult):
        write_plant_outputs(record, sim, folder)
    else:
        write_outputs(record, sim, folder)
    record.status = "completed"
    record.save(folder)
    log.info(
        "run_completed",
        status=record.status,
        wall_time_s=round(float(sim.solver_stats["wall_time_s"]), 3),
        nfev=sim.solver_stats["nfev"],
        flags=record.flags_summary,
    )
    return record, sim


def checks_passed(record: RunRecord) -> bool:
    """True if the balances closed within their tolerances."""
    report = record.plant_balance_report or record.balance_report
    return bool(report and report.get("passed"))


def rerun(record_path: str | Path) -> tuple[RunRecord, bool]:
    """Rerun a recorded run from its scenario file and compare results bit for bit.

    The new run folder is created next to the original one. Raises
    :class:`ScenarioValidationError` if the scenario or an input file changed since the
    recorded run (their hashes no longer match).
    """
    path = Path(record_path)
    old = RunRecord.load(path)
    issues: list[ValidationIssue] = []
    for file, sha in old.input_files.items():
        current = sha256_of(Path(file)) if Path(file).is_file() else "missing"
        if current != sha:
            issues.append(
                ValidationIssue(
                    field="input_files",
                    value=file,
                    reason="input file changed since the recorded run",
                    allowed=f"sha256 {sha[:12]}",
                    location=Path(file).name,
                )
            )
    if issues:
        raise ScenarioValidationError(issues)
    loaded = load_scenario(old.scenario_file)
    require_runnable(loaded)
    if scenario_hash(loaded.spec.model_dump(mode="json")) != old.scenario_sha256:
        raise ScenarioValidationError(
            [
                ValidationIssue(
                    field="scenario",
                    value=old.scenario_file,
                    reason="scenario changed since the recorded run",
                    allowed=f"sha256 {old.scenario_sha256[:12]}",
                    location=Path(old.scenario_file).name,
                )
            ]
        )
    out_dir = path.parent.parent
    new = run(loaded, out_dir=out_dir, profiles=old.profiles_file is not None)
    old_results = (path.parent / str(old.results_file)).read_bytes()
    new_results = (out_dir / new.run_id / str(new.results_file)).read_bytes()
    identical = old_results == new_results
    log.info("rerun_compared", original=old.run_id, rerun=new.run_id, identical=identical)
    return new, identical


def compare(
    loaded: LoadedScenario,
    measured: str | Path,
    out_dir: str | Path = "runs",
    *,
    tolerances: str | Path | None = None,
) -> tuple[RunRecord, ValidationReport]:
    """Run the scenario and compare it with measured time series (User Story 4).

    Writes ``validation_report.json`` and ``comparison.csv`` into the run folder.
    """
    settings = load_settings(tolerances)
    measured_frame = read_measured(measured)
    record, sim = run_with_result(loaded, out_dir)
    folder = Path(out_dir) / record.run_id
    report, table = compare_frames(sim.results, measured_frame, settings, record.run_id)
    (folder / "validation_report.json").write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    units = {"predicted": "SI", "measured": "SI", "deviation": "SI"}
    write_csv(table.set_index("time"), folder / "comparison.csv", units, "time")
    log.info(
        "comparison_completed",
        passed=report.passed,
        outputs={k: v.passed for k, v in report.outputs.items()},
        excluded=len(report.excluded),
    )
    return record, report
