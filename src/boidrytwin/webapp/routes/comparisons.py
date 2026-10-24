"""US4: compare a scenario's run with uploaded measurements (FR-017, FR-018)."""

from __future__ import annotations

import json
import shutil
from typing import Annotated, Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from boidrytwin.scenario.loader import load_scenario, require_runnable
from boidrytwin.webapp.app import ctx
from boidrytwin.webapp.display_units import display_unit, to_display
from boidrytwin.webapp.routes.runs import get_run
from boidrytwin.webapp.routes.scenarios import scenario_path
from boidrytwin.webapp.run_view import read_table
from boidrytwin.webapp.uploads import MAX_BYTES, UploadError, store_upload

router = APIRouter()


@router.post("/api/comparisons", name="api_comparisons", status_code=202)
async def api_comparisons(
    request: Request,
    scenario: Annotated[str, Form()],
    measured: Annotated[UploadFile, File()],
    source: Annotated[str, Form()] = "saved",
) -> JSONResponse:
    path = scenario_path(request, scenario, source)
    content = await measured.read(MAX_BYTES + 1)
    staging = ctx(request).settings.app_dir / "staging"
    try:
        stored, sha = store_upload(content, measured.filename or "", staging)
    except UploadError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    try:
        loaded = load_scenario(path)
        require_runnable(loaded)
        job = (
            ctx(request)
            .queue()
            .enqueue(
                "comparison",
                path,
                view="engineer",
                measured=stored,
                label=f"{loaded.spec.name} vs {stored.name}",
                measured_sha256=sha,
            )
        )
    finally:
        shutil.rmtree(stored.parent, ignore_errors=True)
    details = {"scenario": scenario, "measured": stored.name, "sha256": sha}
    ctx(request).actions.log("engineer", "comparison_started", job.job_id, details)
    return JSONResponse({"job_id": job.job_id}, status_code=202)


@router.get("/api/runs/{run_id}/comparison", name="api_run_comparison")
def api_run_comparison(request: Request, run_id: str) -> dict[str, Any]:
    run = get_run(request, run_id)
    report_path = run.folder / "validation_report.json"
    table = read_table(run.folder / "comparison.csv")
    if not report_path.is_file() or table is None:
        raise HTTPException(404, "this run has no comparison with measurements")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    frame = table.frame
    series: dict[str, Any] = {}
    for output, rows in frame.groupby("output", sort=False):
        try:
            si_unit = run.column_table(str(output)).units.get(str(output), "")
        except KeyError:
            si_unit = ""
        pred = to_display(str(output), si_unit, pd.to_numeric(rows["predicted"], errors="coerce"))
        meas = to_display(str(output), si_unit, pd.to_numeric(rows["measured"], errors="coerce"))
        series[str(output)] = {
            "unit": display_unit(str(output), si_unit),
            "times": [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in rows.index],
            "predicted": [None if np.isnan(v) else float(v) for v in pred],
            "measured": [None if np.isnan(v) else float(v) for v in meas],
            "included": [str(x).lower() == "true" for x in rows["included"]],
            "reason": [str(x) if str(x) != "nan" else "" for x in rows["reason"]],
        }
    return {"report": report, "series": series}
