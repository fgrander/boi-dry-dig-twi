"""Which view may call which route (FR-016; contracts/http-api.md).

Every route of the app has a name, and this table says which views may call it:

- ``public``: no view needed (the view choice itself, static files);
- ``both``: engineer and operator;
- ``engineer``: engineer only;
- ``own``: both views, but an operator only on the what-if jobs it queued (checked in the
  handler, where the job is known).

The check runs on the server for every request. The view is not a security boundary yet
(no sign-in); this table is where a later sign-in feature attaches.
"""

from __future__ import annotations

from typing import Literal

Access = Literal["public", "both", "engineer", "own"]
VIEWS = ("engineer", "operator")

PERMISSIONS: dict[str, Access] = {
    # core
    "index": "public",
    "set_view": "public",
    "plotly_js": "public",
    # US1: runs
    "runs_page": "both",
    "run_page": "both",
    "compare_page": "both",
    "formulas_page": "both",
    "api_runs": "both",
    "api_run": "both",
    "api_run_plot": "both",
    "api_plot": "both",
    "api_run_plot_csv": "both",
    "api_run_profiles": "both",
    "api_run_delete": "engineer",
    # US2: scenarios and jobs
    "scenarios_page": "engineer",
    "scenario_page": "engineer",
    "queue_page": "both",
    "api_scenarios": "engineer",
    "api_scenario": "engineer",
    "api_scenario_validate": "engineer",
    "api_scenario_save": "engineer",
    "api_jobs_create": "engineer",
    "api_jobs": "both",
    "api_job": "both",
    "api_job_start": "own",
    "api_job_drop": "own",
    # US3: operator scenarios
    "operator_list_page": "both",
    "operator_page": "both",
    "whatif_page": "both",
    "api_operator_list": "both",
    "api_operator": "both",
    "api_operator_version": "engineer",
    "api_operator_whatif": "both",
    "api_whatif": "both",
    "api_whatif_csv": "both",
    # US4: comparisons
    "api_comparisons": "engineer",
    "api_run_comparison": "both",
}


def allowed(route: str, view: str | None) -> bool:
    access = PERMISSIONS.get(route)
    if access is None:
        return False  # a route without an entry is never served
    if access == "public":
        return True
    if view not in VIEWS:
        return False
    return access != "engineer" or view == "engineer"
