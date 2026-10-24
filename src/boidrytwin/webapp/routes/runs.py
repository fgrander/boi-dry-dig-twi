"""US1: run list, run view, plots, CSV export, profiles (FR-001–FR-006, FR-018a)."""

from __future__ import annotations

import shutil
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from starlette.exceptions import HTTPException

from boidrytwin.webapp.app import ctx, view_of
from boidrytwin.webapp.display_units import display_unit, to_display
from boidrytwin.webapp.plot_data import build_plot, default_columns, plot_csv
from boidrytwin.webapp.run_index import RunSummary
from boidrytwin.webapp.run_view import RunData, load_run

router = APIRouter()


def origins(request: Request) -> dict[str, str]:
    """run id → how the run was made (app runs from the queue; CLI otherwise)."""
    out: dict[str, str] = {}
    for job in ctx(request).queue().jobs():
        if job.run_id:
            out[job.run_id] = {"run": "app"}.get(job.kind, job.kind)
    return out


def summaries(request: Request, **filters: Any) -> list[RunSummary]:
    runs = ctx(request).index.list(**filters)
    kinds = origins(request)
    return [r.model_copy(update={"origin": kinds.get(r.run_id, "cli")}) for r in runs]


def get_run(request: Request, run_id: str) -> RunData:
    folder = ctx(request).index.folder(run_id)
    if folder is None:
        raise HTTPException(404, f"no run {run_id}")
    return load_run(folder)


def columns_param(run: RunData, columns: str | None) -> list[str]:
    if not columns:
        return default_columns(run)
    return [c for c in columns.split(",") if c]


def plot_or_422(runs: list[RunData], cols: list[str], *, reduce: bool = True) -> Any:
    try:
        return build_plot(runs, cols, reduce=reduce)
    except KeyError as exc:
        raise HTTPException(422, f"unknown column {exc.args[0]}") from None


# --- pages ------------------------------------------------------------------------------


@router.get("/runs", name="runs_page", response_class=HTMLResponse)
def runs_page(
    request: Request, q: str | None = None, status: str | None = None, kind: str | None = None
) -> Response:
    runs = summaries(request, q=q, status=status, kind=kind)
    return ctx(request).templates.TemplateResponse(
        request,
        "runs.html",
        {"runs": runs, "q": q or "", "status": status or "", "kind": kind or ""},
    )


@router.get("/runs/{run_id}", name="run_page", response_class=HTMLResponse)
def run_page(request: Request, run_id: str) -> Response:
    run = get_run(request, run_id)
    return ctx(request).templates.TemplateResponse(
        request,
        "run.html",
        {
            "run": run,
            "summary": run.summary,
            "balances": run.balances(),
            "warnings": run.warnings(),
            "columns": run.columns(),
            "defaults": default_columns(run),
            "has_profiles": run.profiles() is not None,
            "is_engineer": view_of(request) == "engineer",
            "comparison": (run.folder / "validation_report.json").is_file(),
        },
    )


@router.get("/compare", name="compare_page", response_class=HTMLResponse)
def compare_page(request: Request, runs: str = "") -> Response:
    ids = [r for r in runs.split(",") if r]
    loaded = [get_run(request, r) for r in ids]
    common = sorted(set.intersection(*(set(r.columns()) for r in loaded))) if loaded else []
    defaults = [c for c in default_columns(loaded[0]) if c in common] if loaded else []
    return ctx(request).templates.TemplateResponse(
        request,
        "compare.html",
        {"runs": loaded, "ids": ids, "columns": common, "defaults": defaults},
    )


# --- API ----------------------------------------------------------------------------------


@router.get("/api/runs", name="api_runs")
def api_runs(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    kind: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    runs = summaries(request, q=q, status=status, kind=kind)
    page = runs[offset : offset + limit]
    return {"runs": [r.model_dump(mode="json") for r in page], "total": len(runs)}


@router.get("/api/runs/{run_id}", name="api_run")
def api_run(request: Request, run_id: str) -> dict[str, Any]:
    run = get_run(request, run_id)
    flags = [
        {"table": p.table, "flag": p.flag, "start": p.start.isoformat(), "end": p.end.isoformat()}
        for p in run.flag_periods()
    ]
    return {
        "summary": run.summary.model_dump(mode="json"),
        "balances": run.balances(),
        "warnings": run.warnings(),
        "flag_periods": flags,
        "files": run.files(),
        "columns": run.columns(),
    }


@router.get("/api/runs/{run_id}/plot", name="api_run_plot")
def api_run_plot(request: Request, run_id: str, columns: str | None = None) -> dict[str, Any]:
    run = get_run(request, run_id)
    return plot_or_422([run], columns_param(run, columns)).model_dump()  # type: ignore[no-any-return]


@router.get("/api/plot", name="api_plot")
def api_plot(request: Request, runs: str, columns: str) -> dict[str, Any]:
    loaded = [get_run(request, r) for r in runs.split(",") if r]
    cols = [c for c in columns.split(",") if c]
    return plot_or_422(loaded, cols).model_dump()  # type: ignore[no-any-return]


@router.get("/api/runs/{run_id}/plot.csv", name="api_run_plot_csv")
def api_run_plot_csv(request: Request, run_id: str, columns: str | None = None) -> Response:
    run = get_run(request, run_id)
    plot = plot_or_422([run], columns_param(run, columns), reduce=False)
    return Response(
        plot_csv(plot),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{run_id}_plot.csv"'},
    )


@router.get("/api/runs/{run_id}/profiles", name="api_run_profiles")
def api_run_profiles(request: Request, run_id: str, time: str | None = None) -> dict[str, Any]:
    run = get_run(request, run_id)
    table = run.profiles()
    if table is None:
        raise HTTPException(404, "this run has no profiles")
    frame = table.frame
    times = pd.DatetimeIndex(frame.index.unique())
    if time:
        target = pd.Timestamp(time)
        target = target.tz_localize("UTC") if target.tzinfo is None else target.tz_convert("UTC")
        at = times[int(np.argmin(np.abs((times - target).total_seconds())))]
    else:
        at = times[-1]
    rows = frame.loc[[at]]
    cols = [c for c in rows.columns if c != "cell"]
    return {
        "time": at.isoformat(),
        "times": [t.isoformat() for t in times],
        "cells": [int(c) for c in rows["cell"]],
        "columns": {
            c: [
                None if np.isnan(v) else float(v)
                for v in to_display(c, table.units.get(c, ""), rows[c].to_numpy(dtype=float))
            ]
            for c in cols
        },
        "units": {c: display_unit(c, table.units.get(c, "")) for c in cols},
    }


@router.delete("/api/runs/{run_id}", name="api_run_delete", status_code=204)
def api_run_delete(request: Request, run_id: str, confirm: bool = False) -> Response:
    run = get_run(request, run_id)
    if not confirm:
        raise HTTPException(400, "deleting a run needs confirm=true")
    shutil.rmtree(run.folder)
    ctx(request).actions.log(
        "engineer", "run_deleted", run_id, {"scenario": run.summary.scenario_name}
    )
    return Response(status_code=204)
