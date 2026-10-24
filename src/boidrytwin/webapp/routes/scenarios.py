"""US2: scenarios, saving, starting runs, the queue (FR-007–FR-011)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from boidrytwin.errors import ScenarioValidationError
from boidrytwin.scenario.loader import load_scenario, require_runnable
from boidrytwin.webapp.app import ctx, view_of
from boidrytwin.webapp.jobs import Job, JobStateError
from boidrytwin.webapp.scenario_form import (
    ScenarioForm,
    form_dict,
    materialize,
    read_form,
    validate_form,
)
from boidrytwin.webapp.steps import read_meta

router = APIRouter()
NAME = re.compile(r"^[A-Za-z0-9_\-]{1,60}$")


class FormBody(BaseModel):
    form: dict[str, Any]


class SaveBody(BaseModel):
    name: str
    derived_from: str = ""
    form: dict[str, Any]


class JobBody(BaseModel):
    scenario: str
    source: str = "saved"


def scenario_path(request: Request, name: str, source: str) -> Path:
    settings = ctx(request).settings
    if not NAME.match(name) or source not in ("example", "saved"):
        raise HTTPException(404, f"no scenario {name}")
    folder = settings.examples_dir if source == "example" else settings.scenarios_dir
    path = folder / f"{name}.toml"
    if not path.is_file():
        raise HTTPException(404, f"no scenario {name}")
    return path


def title(path: Path) -> str:
    try:
        return str(tomllib.loads(path.read_text(encoding="utf-8")).get("name", path.stem))
    except (OSError, tomllib.TOMLDecodeError):
        return path.stem


def listing(request: Request) -> dict[str, list[dict[str, Any]]]:
    s = ctx(request).settings
    examples = [{"name": p.stem, "title": title(p), "source": "example", "read_only": True}
                for p in sorted(s.examples_dir.glob("*.toml"))]  # fmt: skip
    saved_files = sorted(s.scenarios_dir.glob("*.toml")) if s.scenarios_dir.is_dir() else []
    saved = [
        {"name": p.stem, "title": title(p), "source": "saved", "read_only": False,
         "derived_from": read_meta(p).derived_from}
        for p in saved_files
    ]  # fmt: skip
    return {"examples": examples, "saved": saved}


def series_keys(path: Path) -> set[str]:
    try:
        return set(load_scenario(path).signals)
    except (ScenarioValidationError, OSError):
        return set()


def load_form(path: Path, read_only: bool) -> ScenarioForm:
    return read_form(path, read_only=read_only, series_keys=series_keys(path))


def issues_json(issues: list[Any], form: ScenarioForm) -> JSONResponse:
    return JSONResponse(
        {"issues": [i.model_dump() for i in issues], "form": form_dict(form)}, status_code=422
    )


def job_json(request: Request, job: Job) -> dict[str, Any]:
    data = job.model_dump(mode="json")
    data["progress"] = ctx(request).queue().read_progress(job.job_id)
    return data


def get_job(request: Request, job_id: str) -> Job:
    try:
        return ctx(request).queue().get(job_id)
    except KeyError:
        raise HTTPException(404, f"no job {job_id}") from None


def check_own(request: Request, job: Job) -> str:
    view = view_of(request) or ""
    if view == "operator" and not (job.kind == "what_if" and job.view == "operator"):
        raise HTTPException(403, "not allowed in the operator view")
    return view


# --- pages ------------------------------------------------------------------------------


@router.get("/scenarios", name="scenarios_page", response_class=HTMLResponse)
def scenarios_page(request: Request) -> Response:
    return ctx(request).templates.TemplateResponse(request, "scenarios.html", listing(request))


@router.get("/scenarios/{name}", name="scenario_page", response_class=HTMLResponse)
def scenario_page(request: Request, name: str, source: str = "saved") -> Response:
    path = scenario_path(request, name, source)
    return ctx(request).templates.TemplateResponse(
        request, "scenario.html", {"name": name, "source": source, "title": title(path)}
    )


@router.get("/queue", name="queue_page", response_class=HTMLResponse)
def queue_page(request: Request) -> Response:
    return ctx(request).templates.TemplateResponse(request, "queue.html", {})


# --- scenarios API ----------------------------------------------------------------------


@router.get("/api/scenarios", name="api_scenarios")
def api_scenarios(request: Request) -> dict[str, Any]:
    return listing(request)


@router.get("/api/scenarios/{name}", name="api_scenario")
def api_scenario(request: Request, name: str, source: str = "saved") -> dict[str, Any]:
    path = scenario_path(request, name, source)
    return form_dict(load_form(path, read_only=source == "example"))


@router.post("/api/scenarios/validate", name="api_scenario_validate", response_model=None)
def api_scenario_validate(request: Request, body: FormBody) -> dict[str, Any] | JSONResponse:
    form = ScenarioForm.model_validate(body.form)
    issues = validate_form(form)
    if issues:
        return issues_json(issues, form)
    return {"valid": True}


@router.post("/api/scenarios", name="api_scenario_save", status_code=201, response_model=None)
def api_scenario_save(request: Request, body: SaveBody) -> dict[str, Any] | JSONResponse:
    if not NAME.match(body.name):
        raise HTTPException(422, "name: letters, digits, '-' and '_' only, at most 60")
    target = ctx(request).settings.scenarios_dir / f"{body.name}.toml"
    if target.exists():
        raise HTTPException(409, f"a scenario named {body.name} exists")
    form = ScenarioForm.model_validate(body.form)
    issues = validate_form(form)
    if issues:
        return issues_json(issues, form)
    form.read_only = False
    materialize(form, target, derived_from=body.derived_from)
    ctx(request).actions.log("engineer", "scenario_saved", body.name,
                             {"derived_from": body.derived_from})  # fmt: skip
    return JSONResponse({"name": body.name}, status_code=201)


# --- jobs API -----------------------------------------------------------------------------


@router.post("/api/jobs", name="api_jobs_create", status_code=202)
def api_jobs_create(request: Request, body: JobBody) -> dict[str, Any]:
    path = scenario_path(request, body.scenario, body.source)
    loaded = load_scenario(path)  # 422 with the loader's issues if it does not load
    require_runnable(loaded)
    job = ctx(request).queue().enqueue("run", path, view="engineer", label=loaded.spec.name)
    ctx(request).actions.log("engineer", "run_started", job.job_id,
                             {"scenario": body.scenario, "source": body.source})  # fmt: skip
    return {"job_id": job.job_id}


@router.get("/api/jobs", name="api_jobs")
def api_jobs(request: Request) -> dict[str, Any]:
    return {"jobs": [job_json(request, j) for j in ctx(request).queue().jobs()]}


@router.get("/api/jobs/{job_id}", name="api_job")
def api_job(request: Request, job_id: str) -> dict[str, Any]:
    return job_json(request, get_job(request, job_id))


@router.post("/api/jobs/{job_id}/start", name="api_job_start", status_code=202)
def api_job_start(request: Request, job_id: str) -> dict[str, Any]:
    job = get_job(request, job_id)
    view = check_own(request, job)
    try:
        ctx(request).queue().start(job_id)
    except JobStateError as exc:
        raise HTTPException(409, str(exc)) from None
    ctx(request).actions.log(view, "job_restarted", job_id, {})
    return {"job_id": job_id, "state": "queued"}


@router.post("/api/jobs/{job_id}/drop", name="api_job_drop")
def api_job_drop(request: Request, job_id: str) -> dict[str, Any]:
    job = get_job(request, job_id)
    view = check_own(request, job)
    try:
        ctx(request).queue().drop(job_id)
    except JobStateError as exc:
        raise HTTPException(409, str(exc)) from None
    ctx(request).actions.log(view, "job_dropped", job_id, {})
    return {"job_id": job_id, "state": "dropped"}
