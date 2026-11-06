# Implementation Plan: Single-Page Interface

**Branch**: `005-single-page-ui` | **Date**: 2026-11-06 | **Spec**: [spec.md](spec.md)

## Summary

A static single page (`src/boidrytwin/webapp/ui`) in the layout of the press line twin, built
on the JSON interface of feature 003. The service gets nine small additions for what the older
pages did not need (save in place, rename, delete, download, upload, run without saving, run
record, formulas as JSON, a note on how the app was made). The older pages stay.

## Technical Context

- **Language**: Python 3.12 (service), JavaScript modules in the browser (no build step).
- **Dependencies**: none new in Python. In the browser, bundled unchanged: Preact 10.29.8 with
  hooks (MIT), htm 3.1.1 (Apache-2.0), uPlot 1.6.32 (MIT), and Temml 0.13.5 (MIT, already
  bundled). Justification: the same set as the press line twin, about 160 kB together, no
  build tools, works offline. Plotly stays for the older pages only.
- **Testing**: pytest contract tests for every new call; a browser test of the whole flow
  (`-m ui`, with Playwright through `uv run --with playwright`, not a project dependency, using
  the installed Edge or Chrome); the vendored files are checked against their hashes.
- **Storage**: unchanged (run folders, scenario files, `.app`). Language, pinned runs, the last
  opened scenario and run, and whether the drawing is hidden are kept in the browser.

## Constitution Check

| Principle | How it is met |
| --- | --- |
| I. Test-first | Every new call has contract tests. The fault in file references was reproduced by two failing tests before the fix. **Deviation**: see Complexity Tracking |
| II. Data integrity | The page computes nothing and converts nothing: values and units come from the service. Inputs are checked by the twin's loader only. Save refuses a file changed elsewhere; an upload that does not load is removed again. Runs go through `records.run` as before, so they stay reproducible |
| III. Model fidelity | No model code is touched. The report states model version and scenario fingerprint. The note that the models are not validated stays on the formulas view |
| IV. Observability | New state-changing calls write action log entries (`scenario_renamed`, `scenario_deleted`, `scenario_uploaded`, and the existing `scenario_saved`, `run_started`). The page shows a banner when the service is away |
| Technology | ruff, mypy and the test suite pass. JavaScript is outside ruff and mypy, as in the press line twin |

## Structure

```text
src/boidrytwin/webapp/
  routes/ui.py              the page and the added calls
  ui/index.html, styles.css, print.css
  ui/js/main.js             header, tabs, drawing band
  ui/js/store.js, api.js, session.js, i18n.js, format.js, csv.js, html.js
  ui/js/components/         chart, diagram, field, common
  ui/js/views/              set, results, data, formulas, report
  ui/vendor/                Preact, htm, uPlot with licences and README (hashes)
scripts/make_ui_screenshots.py   drives the page in a browser, writes the README pictures
tests/contract/webapp/test_api_ui.py
tests/ui/test_ui_flow.py         browser test (-m ui)
```

## Decisions

- **R1 A page on the existing interface, not a rewrite of the service.** Scenario form, queue,
  worker, plot data, process state and drawings of features 003/004 are used as they are.
- **R2 Run without saving.** `POST /api/jobs/draft` writes the form into a draft folder, loads
  it with the twin's loader and queues it; the queue freezes its own copy as for every job, and
  the draft folder is removed. Examples can so be varied and run without a name.
- **R3 One job at a time on the page.** The page polls its job every 0.6 s and shows the
  simulated time; the queue page of feature 003 still shows all jobs.
- **R4 Outdated results.** A hash of the inputs is kept with the run; any change marks the
  results as outdated, as in the press line twin.
- **R5 Checks as limits.** The twin has no speed limits like a press. Its "limits" are the
  flags (share of the run time, limit 0) and the balances (relative error against tolerance).
- **R6 Changed inputs in the report** are those that differ from the file the scenario was
  opened from. For a run opened from the list, the page cannot know them and says so.
- **R7 The older pages stay** at their addresses with `/classic` as their start, so no function
  is lost while the new page does not have it.
- **R8 Charts over hours since the start**, not clock time: runs with different start times
  can be drawn together, and tables and CSV stay plain numbers.

## Complexity Tracking

| Deviation | Why | Mitigation |
| --- | --- | --- |
| The page's JavaScript and the contract tests were written together, and the page before its browser test | The layout was given by an existing application and was built against it picture by picture | Contract tests for every call; a browser test of the whole flow; a test that every import of the page exists. The tests found three faults: missing action log entries, a file reference lost when a scenario is checked from another folder, and a missing wait in the first browser script |
| Two user interfaces exist side by side | The functions of the older pages that the new page lacks (what-if cases, test scenario pages, queue) are not lost before the project owner decides | Follow-up tasks T030 to T032; both use the same service |
| No JavaScript unit tests | No JavaScript test runner in the project; adding Node would be a new toolchain | The browser test covers the page; the logic that matters is in the service |
