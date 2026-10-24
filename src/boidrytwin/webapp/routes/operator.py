"""US3: operator scenarios, what-if runs and their comparison (FR-012–FR-015)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from boidrytwin.webapp.app import ctx, view_of
from boidrytwin.webapp.jobs import Job
from boidrytwin.webapp.operator import (
    OperatorStore,
    OperatorVersion,
    Release,
    ReleaseError,
    baseline_state,
)
from boidrytwin.webapp.routes.scenarios import listing, scenario_path
from boidrytwin.webapp.run_view import RunData, load_run
from boidrytwin.webapp.whatif import compare_runs, comparison_csv

router = APIRouter()


class VersionBody(BaseModel):
    scenario: str
    source: str = "saved"
    releases: list[Release]
    comparison_outputs: list[str] | None = None
    title: str = ""
    from_version: int | None = None  # source "operator": the version to start from


class WhatIfBody(BaseModel):
    version: int | None = None
    values: dict[str, Any]


def store(request: Request) -> OperatorStore:
    c = ctx(request)
    return OperatorStore(c.settings.scenarios_dir, c.queue())


def get_version(request: Request, name: str, version: int | None = None) -> OperatorVersion:
    try:
        return store(request).get(name, version)
    except KeyError:
        raise HTTPException(404, f"no operator scenario {name}") from None


def version_json(request: Request, v: OperatorVersion) -> dict[str, Any]:
    state, run_id = baseline_state(v, ctx(request).queue())
    return {
        **v.model_dump(mode="json"),
        "baseline_state": state,
        "baseline_run_id": run_id,
        "versions": [x.version for x in store(request).versions(v.name)],
    }


def release_issues(exc: ReleaseError) -> JSONResponse:
    return JSONResponse({"issues": [i.model_dump() for i in exc.issues]}, status_code=422)


def whatif_job(request: Request, run_id: str) -> Job:
    for job in ctx(request).queue().jobs():
        if job.run_id == run_id and job.kind == "what_if":
            return job
    raise HTTPException(404, f"{run_id} is not a what-if run")


def comparison(request: Request, run_id: str) -> dict[str, Any]:
    job = whatif_job(request, run_id)
    extra = job.model_extra or {}
    version = get_version(request, str(extra.get("operator", "")), int(extra.get("version", 0)))
    folder = ctx(request).index.folder(run_id)
    if folder is None:
        raise HTTPException(409, "the what-if run has no results yet")
    whatif = load_run(folder)
    baseline: RunData | None = None
    baseline_id: str | None = None
    state, run = baseline_state(version, ctx(request).queue())
    if state == "ready" and run:
        base_folder = ctx(request).index.folder(run)
        if base_folder is not None:
            baseline, baseline_id = load_run(base_folder), run
    cmp = compare_runs(baseline, whatif, version.comparison_outputs)
    return {
        "run_id": run_id,
        "job_id": job.job_id,
        "operator": version.name,
        "title": version.title,
        "version": version.version,
        "baseline_run_id": baseline_id,
        "changes": extra.get("changes", {}),
        "status": whatif.summary.status,
        **cmp.model_dump(),
    }


# --- pages ------------------------------------------------------------------------------


@router.get("/operator", name="operator_list_page", response_class=HTMLResponse)
def operator_list_page(request: Request) -> Response:
    s = store(request)
    items = [version_json(request, s.get(n)) for n in s.names()]
    scenarios = (
        listing(request) if view_of(request) == "engineer" else {"examples": [], "saved": []}
    )
    return ctx(request).templates.TemplateResponse(
        request, "operator_list.html", {"items": items, "scenarios": scenarios}
    )


@router.get("/operator/{name}", name="operator_page", response_class=HTMLResponse)
def operator_page(request: Request, name: str, version: int | None = None) -> Response:
    v = version_json(request, get_version(request, name, version))
    return ctx(request).templates.TemplateResponse(
        request, "operator.html", {"v": v, "is_engineer": view_of(request) == "engineer"}
    )


@router.get("/whatif/{run_id}", name="whatif_page", response_class=HTMLResponse)
def whatif_page(request: Request, run_id: str) -> Response:
    return ctx(request).templates.TemplateResponse(
        request, "whatif.html", {"c": comparison(request, run_id)}
    )


# --- API ----------------------------------------------------------------------------------


@router.get("/api/operator", name="api_operator_list")
def api_operator_list(request: Request) -> dict[str, Any]:
    s = store(request)
    return {"operator_scenarios": [version_json(request, s.get(n)) for n in s.names()]}


@router.get("/api/operator/{name}", name="api_operator")
def api_operator(request: Request, name: str, version: int | None = None) -> dict[str, Any]:
    return version_json(request, get_version(request, name, version))


@router.post(
    "/api/operator/{name}/versions",
    name="api_operator_version",
    status_code=201,
    response_model=None,
)
def api_operator_version(request: Request, name: str, body: VersionBody) -> Any:
    if body.source == "operator":  # a new version of this case, from one of its versions
        path = get_version(request, name, body.from_version).scenario_path
    else:
        path = scenario_path(request, body.scenario, body.source)
    try:
        v = store(request).create_version(
            name,
            path,
            body.releases,
            view="engineer",
            comparison_outputs=body.comparison_outputs,
            title=body.title,
        )
    except ReleaseError as exc:
        return release_issues(exc)
    ctx(request).actions.log(
        "engineer",
        "operator_version_saved",
        f"{name} v{v.version}",
        {"scenario": body.scenario, "baseline_job_id": v.baseline_job_id},
    )
    return JSONResponse(
        {"version": v.version, "baseline_job_id": v.baseline_job_id}, status_code=201
    )


@router.post(
    "/api/operator/{name}/whatif", name="api_operator_whatif", status_code=202, response_model=None
)
def api_operator_whatif(request: Request, name: str, body: WhatIfBody) -> Any:
    v = get_version(request, name, body.version)
    view = view_of(request) or "operator"
    try:
        job = store(request).create_whatif(
            v, body.values, view=view, staging=ctx(request).settings.app_dir / "staging"
        )
    except ReleaseError as exc:
        return release_issues(exc)
    ctx(request).actions.log(
        view,
        "what_if_started",
        job.job_id,
        {"operator": name, "version": v.version, "values": body.values},
    )
    return JSONResponse({"job_id": job.job_id}, status_code=202)


@router.get("/api/whatif/{run_id}.csv", name="api_whatif_csv")
def api_whatif_csv(request: Request, run_id: str) -> Response:
    data = comparison(request, run_id)
    from boidrytwin.webapp.whatif import WhatIfComparison

    cmp = WhatIfComparison.model_validate(data)
    return Response(
        comparison_csv(cmp, data["baseline_run_id"], run_id),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{run_id}_whatif.csv"'},
    )


@router.get("/api/whatif/{run_id}", name="api_whatif")
def api_whatif(request: Request, run_id: str) -> dict[str, Any]:
    return comparison(request, run_id)
