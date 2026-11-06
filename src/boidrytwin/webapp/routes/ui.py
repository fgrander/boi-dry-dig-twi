"""The single-page interface and what it needs beyond features 003/004 (feature 005).

The page itself is static (``webapp/ui``): header, tabs for the scenario, the results, the
formulas and the report. It works on the JSON interface. This module adds the calls that the
older pages did not need: overwrite, rename, delete, download and upload of a saved scenario,
a run of the scenario as it is in the editor (without saving it first), the run record for
the report, and the formula register as JSON.
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from boidrytwin.errors import ScenarioValidationError
from boidrytwin.scenario.loader import load_scenario, require_runnable
from boidrytwin.webapp import about
from boidrytwin.webapp.app import ctx
from boidrytwin.webapp.routes.runs import get_run
from boidrytwin.webapp.routes.scenarios import NAME, issues_json, scenario_path
from boidrytwin.webapp.scenario_form import ScenarioForm, materialize, validate_form
from boidrytwin.webapp.steps import meta_path, read_meta, steps_dir

router = APIRouter()
UI_DIR = Path(__file__).parents[1] / "ui"
MAX_SCENARIO_BYTES = 1_000_000
NAME_RULE = "name: letters, digits, '-' and '_' only, at most 60"


class UpdateBody(BaseModel):
    form: dict[str, Any]


class RenameBody(BaseModel):
    name: str


class DraftBody(BaseModel):
    form: dict[str, Any]
    derived_from: str = ""
    label: str = ""


def _target(request: Request, name: str) -> Path:
    if not NAME.match(name):
        raise HTTPException(422, NAME_RULE)
    return ctx(request).settings.scenarios_dir / f"{name}.toml"


@router.get("/api/ui/about", name="api_ui_about")
def api_ui_about() -> dict[str, Any]:
    """How the app was made, for the note below the header."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        installed = version("boidrytwin")
    except PackageNotFoundError:  # run from a source tree that is not installed
        installed = ""
    return {
        "guided_by": about.GUIDED_BY,
        "ai_work_hours": about.AI_WORK_HOURS,
        "as_of": about.AS_OF,
        "version": installed,
    }


# --- saved scenarios ----------------------------------------------------------------------


@router.put("/api/scenarios/{name}", name="api_scenario_update", response_model=None)
def api_scenario_update(
    request: Request, name: str, body: UpdateBody
) -> dict[str, Any] | JSONResponse:
    """Write the edited form over the saved scenario it was read from."""
    path = scenario_path(request, name, "saved")
    form = ScenarioForm.model_validate(body.form)
    on_disk = path.read_text(encoding="utf-8").split("\n")
    if on_disk and on_disk[-1] == "":
        on_disk = on_disk[:-1]
    if on_disk != form.lines:
        raise HTTPException(409, f"{name} was changed elsewhere since it was opened")
    issues = validate_form(form)
    if issues:
        return issues_json(issues, form)
    form.read_only = False
    form.source = str(path)
    materialize(form, path, derived_from=read_meta(path).derived_from)
    ctx(request).actions.log("engineer", "scenario_saved", name, {"overwritten": True})
    return {"name": name}


@router.delete("/api/scenarios/{name}", name="api_scenario_delete", status_code=204)
def api_scenario_delete(request: Request, name: str) -> Response:
    path = scenario_path(request, name, "saved")
    path.unlink()
    meta_path(path).unlink(missing_ok=True)
    shutil.rmtree(steps_dir(path), ignore_errors=True)
    ctx(request).actions.log("engineer", "scenario_deleted", name, {})
    return Response(status_code=204)


@router.post("/api/scenarios/{name}/rename", name="api_scenario_rename")
def api_scenario_rename(request: Request, name: str, body: RenameBody) -> dict[str, Any]:
    path = scenario_path(request, name, "saved")
    target = _target(request, body.name)
    if target.exists():
        raise HTTPException(409, f"a scenario named {body.name} exists")
    # step files are referenced by the scenario's own name
    text = path.read_text(encoding="utf-8").replace(f'"{name}.steps/', f'"{body.name}.steps/')
    target.write_text(text, encoding="utf-8", newline="\n")
    if steps_dir(path).is_dir():
        steps_dir(path).rename(steps_dir(target))
    if meta_path(path).is_file():
        meta_path(path).rename(meta_path(target))
    path.unlink()
    ctx(request).actions.log("engineer", "scenario_renamed", body.name, {"from": name})
    return {"name": body.name}


@router.get("/api/scenarios/{name}/file", name="api_scenario_file")
def api_scenario_file(request: Request, name: str, source: str = "saved") -> Response:
    path = scenario_path(request, name, source)
    return FileResponse(path, media_type="application/toml", filename=path.name)


@router.post(
    "/api/scenarios/upload", name="api_scenario_upload", status_code=201, response_model=None
)
async def api_scenario_upload(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008 - FastAPI's way to declare a file
    name: str = Form(""),
) -> dict[str, Any] | JSONResponse:
    """Keep an uploaded scenario file as a saved scenario, if the twin can load it."""
    stem = name or Path(file.filename or "").stem
    target = _target(request, stem)
    if target.exists():
        raise HTTPException(409, f"a scenario named {stem} exists")
    data = await file.read(MAX_SCENARIO_BYTES + 1)
    if len(data) > MAX_SCENARIO_BYTES:
        raise HTTPException(413, "a scenario file has at most 1 MB")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(422, "the file is not UTF-8 text") from None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    try:
        load_scenario(target)
    except ScenarioValidationError as exc:
        target.unlink()
        return JSONResponse({"issues": [i.model_dump() for i in exc.issues]}, status_code=422)
    ctx(request).actions.log("engineer", "scenario_uploaded", stem, {})
    return JSONResponse({"name": stem}, status_code=201)


# --- running the scenario in the editor -----------------------------------------------------


@router.post("/api/jobs/draft", name="api_jobs_draft", status_code=202, response_model=None)
def api_jobs_draft(request: Request, body: DraftBody) -> dict[str, Any] | JSONResponse:
    """Queue a run of the form as it is, saved or not. The job keeps its own frozen copy."""
    form = ScenarioForm.model_validate(body.form)
    issues = validate_form(form)
    if issues:
        return issues_json(issues, form)
    settings = ctx(request).settings
    folder = settings.app_dir / "drafts" / uuid.uuid4().hex[:12]
    target = folder / Path(form.source).name
    try:
        form.read_only = False
        materialize(form, target, derived_from=body.derived_from)
        loaded = load_scenario(target)  # 422 with the loader's issues if it does not load
        require_runnable(loaded)
        job = (
            ctx(request)
            .queue()
            .enqueue(
                "run", target, view="engineer", label=body.label or loaded.spec.name, profiles=True
            )
        )
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    ctx(request).actions.log(
        "engineer", "run_started", job.job_id, {"derived_from": body.derived_from, "draft": True}
    )
    return JSONResponse({"job_id": job.job_id}, status_code=202)


# --- report and formulas --------------------------------------------------------------------


@router.get("/api/runs/{run_id}/record", name="api_run_record")
def api_run_record(request: Request, run_id: str) -> dict[str, Any]:
    """What a report states about a run: who computed it, with what, from which inputs."""
    record = get_run(request, run_id).record

    def table(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    scenario = table(record.get("scenario"))
    time = table(scenario.get("time"))
    return {
        "run_id": run_id,
        "scenario_name": scenario.get("name"),
        "scenario_file": record.get("scenario_file"),
        "scenario_sha256": record.get("scenario_sha256"),
        "model_version": record.get("model_version"),
        "created_at": record.get("created_at"),
        "status": record.get("status"),
        "message": record.get("message"),
        "start": time.get("start"),
        "end": time.get("end"),
        "python": table(record.get("environment")).get("python"),
        "has_profiles": bool(record.get("profiles_file")),
    }


@router.get("/api/formulas", name="api_formulas")
def api_formulas() -> dict[str, Any]:
    """Every formula of the models with its symbols, code and numbered sources."""
    from boidrytwin.webapp.formulas import SOURCES, by_section, numbered_sources

    numbers = numbered_sources()
    return {
        "sections": [
            {"key": key, "title": title, "formulas": [asdict(f) for f in items]}
            for key, title, items in by_section()
        ],
        "sources": {
            key: {**asdict(SOURCES[key]), "number": number} for key, number in numbers.items()
        },
    }


# --- the page -------------------------------------------------------------------------------


def page(request: Request) -> Response:
    """The single page. It needs no view choice: it works in the engineer view."""
    response = FileResponse(UI_DIR / "index.html", media_type="text/html; charset=utf-8")
    response.headers["Cache-Control"] = "no-cache"
    if request.cookies.get("view") != "engineer":
        response.set_cookie("view", "engineer", httponly=True, samesite="strict")
    return response
