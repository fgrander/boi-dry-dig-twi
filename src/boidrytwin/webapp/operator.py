"""Operator scenarios: frozen versions with released inputs and a baseline each
(FR-012–FR-014a; research R6, data-model §6, contracts/app-state.md).

``scenarios/operator/<name>/v<N>/`` holds a frozen ``scenario.toml`` (plus its step files) and
``operator.toml`` (releases, comparison outputs, baseline job). Saving a version queues its
baseline run. A what-if run is the version's scenario with only the released inputs changed,
each checked against its released range here, before the run is queued.

A release is accepted only if the scenario still loads with the input at the release's
minimum and at its maximum, so the twin's own valid ranges apply (R6).
"""

from __future__ import annotations

import json
import re
import shutil
import tomllib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from boidrytwin.webapp.jobs import Job, JobQueue, write_atomic
from boidrytwin.webapp.scenario_form import (
    Issue,
    ScenarioForm,
    materialize,
    read_form,
    set_field,
    validate_form,
)
from boidrytwin.webapp.steps import Step, StepSequence

NAME = re.compile(r"^[A-Za-z0-9_\-]{1,60}$")
DEFAULT_OUTPUTS = (
    "oil_outlet_temperature",
    "fuel_feed",
    "o2_dry",
    "drum_inlet_gas_temperature",
    "product_moisture_wet_basis",
    "evaporation_rate",
    "heat_to_oil",
)
BOILER_OUTPUTS = frozenset({"oil_outlet_temperature", "fuel_feed", "o2_dry", "heat_to_oil"})
DRYER_OUTPUTS = frozenset(
    {"drum_inlet_gas_temperature", "product_moisture_wet_basis", "evaporation_rate"}
)
MAX_LABEL = 60


class ReleaseError(ValueError):
    def __init__(self, issues: list[Issue]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{i.field}: {i.reason}" for i in issues))


class Release(BaseModel):
    key: str
    label: str
    unit: str
    minimum: float
    maximum: float
    allow_step: bool = False

    @property
    def section_key(self) -> tuple[str, str]:
        section, _, key = self.key.rpartition(".")
        return section, key

    @property
    def allowed(self) -> str:
        return f"{self.minimum:g}–{self.maximum:g} {self.unit}"


class OperatorVersion(BaseModel):
    name: str
    version: int
    title: str = ""
    created_at: datetime
    releases: list[Release]
    comparison_outputs: list[str]
    baseline_job_id: str | None = None
    folder: str = Field(default="", exclude=True)

    @property
    def scenario_path(self) -> Path:
        return Path(self.folder) / "scenario.toml"


def baseline_state(version: OperatorVersion, queue: JobQueue) -> tuple[str, str | None]:
    """(``baseline pending`` | ``ready`` | ``baseline failed``, baseline run id)."""
    if not version.baseline_job_id:
        return "baseline pending", None
    try:
        job = queue.get(version.baseline_job_id)
    except KeyError:
        return "baseline failed", None
    if job.state == "completed":
        return "ready", job.run_id
    if job.state in ("failed", "dropped", "interrupted"):
        return "baseline failed", None
    return "baseline pending", None


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)


def write_operator_toml(path: Path, version: OperatorVersion) -> None:
    lines = [
        "version = 1",
        f"name = {_toml_value(version.name)}",
        f"title = {_toml_value(version.title)}",
        f'created_at = "{version.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")}"',
        f"comparison_outputs = {_toml_value(version.comparison_outputs)}",
        "",
    ]
    for r in version.releases:
        lines += ["[[release]]"]
        lines += [f"{k} = {_toml_value(v)}" for k, v in r.model_dump().items()]
        lines.append("")
    lines += ["[baseline]", f"job_id = {_toml_value(version.baseline_job_id or '')}", ""]
    write_atomic(path, "\n".join(lines))


def read_operator_toml(folder: Path, name: str) -> OperatorVersion:
    doc = tomllib.loads((folder / "operator.toml").read_text(encoding="utf-8"))
    created = datetime.fromisoformat(str(doc["created_at"]).replace("Z", "+00:00"))
    return OperatorVersion(
        name=name,
        version=int(folder.name[1:]),
        title=str(doc.get("title", "")),
        created_at=created,
        releases=[Release(**r) for r in doc.get("release", [])],
        comparison_outputs=list(doc.get("comparison_outputs", [])),
        baseline_job_id=doc.get("baseline", {}).get("job_id") or None,
        folder=str(folder),
    )


def default_outputs(scenario: Path) -> list[str]:
    doc = tomllib.loads(scenario.read_text(encoding="utf-8"))
    has_boiler, has_dryer = "boiler_house" in doc, "dryer" in doc
    return [
        o
        for o in DEFAULT_OUTPUTS
        if (o not in BOILER_OUTPUTS or has_boiler) and (o not in DRYER_OUTPUTS or has_dryer)
    ]


class OperatorStore:
    def __init__(self, scenarios_dir: Path, queue: JobQueue) -> None:
        self.root = scenarios_dir / "operator"
        self.queue = queue

    # --- reading ------------------------------------------------------------------------

    def names(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and self.versions(p.name))

    def versions(self, name: str) -> list[OperatorVersion]:
        folder = self.root / name
        if not NAME.match(name) or not folder.is_dir():
            return []
        dirs = [
            p
            for p in folder.iterdir()
            if re.fullmatch(r"v\d+", p.name) and (p / "operator.toml").is_file()
        ]
        return [read_operator_toml(p, name) for p in sorted(dirs, key=lambda p: int(p.name[1:]))]

    def get(self, name: str, version: int | None = None) -> OperatorVersion:
        versions = self.versions(name)
        if not versions:
            raise KeyError(name)
        if version is None:
            return versions[-1]
        for v in versions:
            if v.version == version:
                return v
        raise KeyError(f"{name} v{version}")

    # --- releases -----------------------------------------------------------------------

    def check_releases(self, scenario: Path, releases: list[Release]) -> list[Issue]:
        from boidrytwin.scenario.loader import load_scenario

        issues: list[Issue] = []
        try:
            signals = set(load_scenario(scenario).signals)
        except Exception:  # the scenario itself must load
            return [Issue(field="scenario", reason="the scenario does not load")]
        if not releases:
            issues.append(Issue(field="releases", reason="at least one input must be released"))
        for r in releases:
            section, key = r.section_key
            if not r.label or len(r.label) > MAX_LABEL:
                issues.append(
                    Issue(field=r.key, reason=f"label must have 1–{MAX_LABEL} characters")
                )
            if not r.minimum < r.maximum:
                issues.append(
                    Issue(field=r.key, reason="minimum must be below maximum", allowed=r.allowed)
                )
                continue
            if r.allow_step and r.key not in signals:
                issues.append(Issue(field=r.key, reason="this input does not accept a time series"))
            for bound in (r.minimum, r.maximum):
                form = read_form(scenario)
                try:
                    set_field(form, section, key, value=f"{bound:g}", unit=r.unit)
                except KeyError:
                    issues.append(Issue(field=r.key, reason="no such input in the scenario"))
                    break
                found = validate_form(form)
                if found:
                    issues += [
                        Issue(
                            field=r.key,
                            value=f"{bound:g} {r.unit}",
                            reason=i.reason,
                            allowed=i.allowed or r.allowed,
                        )
                        for i in found
                    ]
                    break
        return issues

    # --- changes ------------------------------------------------------------------------

    def create_version(
        self,
        name: str,
        scenario: Path,
        releases: list[Release],
        *,
        view: str,
        comparison_outputs: list[str] | None = None,
        title: str = "",
    ) -> OperatorVersion:
        if not NAME.match(name):
            raise ReleaseError([Issue(field="name", reason="letters, digits, '-' and '_' only")])
        issues = self.check_releases(scenario, releases)
        if issues:
            raise ReleaseError(issues)
        existing = self.versions(name)
        number = existing[-1].version + 1 if existing else 1
        folder = self.root / name / f"v{number}"
        folder.mkdir(parents=True)
        materialize(read_form(scenario), folder / "scenario.toml", derived_from=str(scenario))
        doc = tomllib.loads((folder / "scenario.toml").read_text(encoding="utf-8"))
        version = OperatorVersion(
            name=name,
            version=number,
            title=title or str(doc.get("name", name)),
            created_at=datetime.now(UTC),
            releases=releases,
            comparison_outputs=comparison_outputs or default_outputs(folder / "scenario.toml"),
            folder=str(folder),
        )
        job = self.queue.enqueue(
            "baseline",
            version.scenario_path,
            view=view,
            label=f"{version.title} (baseline v{number})",
            operator=name,
            version=number,
        )
        version.baseline_job_id = job.job_id
        write_operator_toml(folder / "operator.toml", version)
        return version

    def check_values(self, version: OperatorVersion, values: dict[str, Any]) -> list[Issue]:
        issues: list[Issue] = []
        released = {r.key: r for r in version.releases}
        for key, value in values.items():
            r = released.get(key)
            if r is None:
                issues.append(
                    Issue(
                        field=key,
                        reason="this input is not released for operators",
                        allowed=", ".join(released),
                    )
                )
                continue
            if isinstance(value, dict):
                if not r.allow_step:
                    issues.append(
                        Issue(
                            field=key,
                            reason="a step is not allowed for this input",
                            allowed=r.allowed,
                        )
                    )
                    continue
                numbers = [value.get("start_value")] + [
                    s.get("value") for s in value.get("steps", [])
                ]
            else:
                numbers = [value]
            for n in numbers:
                if not isinstance(n, int | float) or not r.minimum <= float(n) <= r.maximum:
                    issues.append(
                        Issue(
                            field=key,
                            value=str(n),
                            reason="outside the released range",
                            allowed=r.allowed,
                        )
                    )
                    break
        return issues

    def create_whatif(
        self, version: OperatorVersion, values: dict[str, Any], *, view: str, staging: Path
    ) -> Job:
        issues = self.check_values(version, values)
        if issues:
            raise ReleaseError(issues)
        form: ScenarioForm = read_form(version.scenario_path)
        released = {r.key: r for r in version.releases}
        for key, value in values.items():
            r = released[key]
            section, field = r.section_key
            if isinstance(value, dict):
                seq = StepSequence(
                    unit=r.unit,
                    start_value=float(value["start_value"]),
                    steps=[Step(**s) for s in value.get("steps", [])],
                )
                set_field(form, section, field, steps=seq)
            else:
                set_field(form, section, field, value=f"{float(value):g}", unit=r.unit)
        folder = staging / uuid.uuid4().hex
        try:
            target = folder / "scenario.toml"
            materialize(form, target)
            label = f"{version.title} (what-if on v{version.version})"
            job = self.queue.enqueue(
                "what_if",
                target,
                view=view,
                label=label,
                operator=version.name,
                version=version.version,
                baseline_job_id=version.baseline_job_id,
                changes=values,
            )
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        self._index(job, version, values)
        return job

    def _index(self, job: Job, version: OperatorVersion, values: dict[str, Any]) -> None:
        path = self.queue.app_dir / "whatif.json"
        doc: dict[str, Any] = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.is_file()
            else {"version": 1, "runs": {}}
        )
        doc["runs"][job.job_id] = {
            "operator_scenario": version.name,
            "version": version.version,
            "baseline_job_id": version.baseline_job_id,
            "changes": values,
        }
        write_atomic(path, json.dumps(doc, indent=2))
