"""Test scenarios: one page per example with drawing, explanation and time plots."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from starlette.exceptions import HTTPException

from boidrytwin.errors import ScenarioValidationError
from boidrytwin.scenario.loader import load_scenario
from boidrytwin.webapp.app import ctx, view_of
from boidrytwin.webapp.i18n import lang_of
from boidrytwin.webapp.process_state import snapshot
from boidrytwin.webapp.routes.runs import available_diagrams, render_diagram, summaries
from boidrytwin.webapp.routes.scenarios import title
from boidrytwin.webapp.run_index import RunSummary
from boidrytwin.webapp.run_view import load_run
from boidrytwin.webapp.showcase import BY_NAME, CASES, GROUPS, Case

router = APIRouter()


def latest_runs(request: Request) -> dict[str, RunSummary]:
    """Example name → its latest completed run (matched by the scenario name)."""
    examples = ctx(request).settings.examples_dir
    names = {title(examples / f"{c.name}.toml"): c.name for c in CASES}
    out: dict[str, RunSummary] = {}
    for run in summaries(request):  # newest first
        name = names.get(run.scenario_name)
        if name and name not in out and run.status == "completed":
            out[name] = run
    return out


def validation_issues(request: Request, case: Case) -> list[dict[str, Any]]:
    path = ctx(request).settings.examples_dir / f"{case.name}.toml"
    try:
        load_scenario(path)
    except ScenarioValidationError as exc:
        return [i.model_dump() for i in exc.issues]
    return []


@router.get("/test-scenarios", name="showcase_list", response_class=HTMLResponse)
def showcase_list(request: Request) -> Response:
    lang = lang_of(request)
    runs = latest_runs(request)
    groups = [
        (names[0 if lang == "de" else 1],
         [(c, c.text(lang), runs.get(c.name)) for c in CASES if c.group == key])
        for key, names in GROUPS.items()
    ]  # fmt: skip
    return ctx(request).templates.TemplateResponse(request, "showcase_list.html", {
        "groups": groups, "missing": [c.name for c in CASES if c.name not in runs and c.columns],
        "is_engineer": view_of(request) == "engineer",
    })  # fmt: skip


@router.get("/test-scenarios/{name}", name="showcase_page", response_class=HTMLResponse)
def showcase_page(request: Request, name: str) -> Response:
    case = BY_NAME.get(name)
    if case is None:
        raise HTTPException(404, f"no test scenario {name}")
    lang = lang_of(request)
    run = latest_runs(request).get(name)
    state, diagrams, columns = None, [], []
    if run is not None:
        folder = ctx(request).index.folder(run.run_id)
        data = load_run(folder) if folder is not None else None
        if data is not None and data.tables:
            state = snapshot(data, None)
            diagrams = available_diagrams(state)
            have = set(data.columns())
            columns = [c for c in case.columns if c in have]
    first = case.diagram if case.diagram in diagrams else (diagrams[0] if diagrams else "")
    index = [c.name for c in CASES]
    pos = index.index(name)
    return ctx(request).templates.TemplateResponse(request, "showcase.html", {
        "case": case, "text": case.text(lang), "run": run, "state": state,
        "group": GROUPS[case.group][0 if lang == "de" else 1],
        "diagrams": diagrams, "first": first, "times": state.times if state else [],
        "diagram": render_diagram(request, state, first) if state and first else "",
        "columns": columns, "steps": [{"time": t, "label": label} for t, label in case.steps],
        "issues": validation_issues(request, case) if not case.columns else [],
        "file": f"examples/{case.name}.toml",
        "prev": BY_NAME[index[pos - 1]] if pos > 0 else None,
        "next": BY_NAME[index[pos + 1]] if pos + 1 < len(index) else None,
        "is_engineer": view_of(request) == "engineer",
    })  # fmt: skip
