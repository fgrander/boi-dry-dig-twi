# Tasks: Single-Page Interface

**Input**: [spec.md](spec.md), [plan.md](plan.md), [contracts/http-api-ui.md](contracts/http-api-ui.md)

## Phase 1: Service

- [x] T001 `routes/ui.py`: the page at `/` (engineer view, no view choice); the older start
      page at `/classic`; `ui/` served at `/ui`
- [x] T002 Save in place, rename, delete, download and upload of saved scenarios
- [x] T003 `POST /api/jobs/draft`: run the form as it is; jobs of the page compute profiles
- [x] T004 `GET /api/runs/{id}/record`, `GET /api/formulas`, `GET /api/ui/about`
- [x] T005 Permission table and action log entries for the new calls
- [x] T006 Contract tests `tests/contract/webapp/test_api_ui.py`; older tests moved to `/classic`
- [x] T007 Fix: a plain `file` key keeps pointing to its file when a scenario is written to
      another folder (two tests first, `scenario_form._relocated`)
- [x] T008 The meta file keeps what a scenario was derived from, with or without steps

## Phase 2: Page (US1)

- [x] T009 Bundled libraries with licences, README and hash test
- [x] T010 Header, tabs, language switch, service status, note on how the app was made
- [x] T011 Scenario view: toolbar, open dialog, inputs by section, step sequences, issues at
      the inputs, changed marks, reset, filter and search
- [x] T012 Labels of sections, inputs, columns, flags and balances in German and English

## Phase 3: Results and report (US2)

- [x] T013 Run with progress, outdated mark, opening an earlier run
- [x] T014 Key figures, checks with margins, messages, heater table
- [x] T015 Charts over time and along the drum with values, CSV and picture
- [x] T016 Plant drawing below the tabs with the time slider; can be hidden
- [x] T017 Pinned runs: overlay and comparison table
- [x] T018 Report and print layout

## Phase 4: Measurements and formulas (US3)

- [x] T019 Measurements & comparison view
- [x] T020 Formulas & sources view with search and print

## Phase 5: Polish

- [x] T021 `scripts/make_ui_screenshots.py` and the browser test `tests/ui/` (`-m ui`)
- [x] T022 `docs/webapp.md`, README with new pictures, contract
- [x] T023 The page in the Windows program (`packaging/BoiDryTwin.spec`), version 0.2.0
- [x] T024 ruff, ruff format, mypy and the full test suite pass

## Follow-up (not done)

- [ ] T030 What-if cases for operators in the new page (or drop them)
- [ ] T031 Test scenario pages in the new page (or drop them)
- [ ] T032 Remove the older pages and Plotly once T030 and T031 are decided
- [ ] T033 Plausible ranges and descriptions per input from the model's field tables
- [ ] T034 Texts of the formula register in German
- [ ] T035 Keep unsaved edits over a reload of the page
