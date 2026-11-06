# Feature Specification: Single-Page Interface

**Feature Branch**: `005-single-page-ui`

**Created**: 2026-11-06

**Status**: Implemented

**Input**: User description: "Mir gefällt die Bedienung der Website nicht. Kannst du es so
machen wie bei dem Zwilling der Contiroll. Auch die Seite mit den Results und dem Report."
Later: "Wenn du fertig bist update die README, push to main und mach ein neues Release."

## Context

The web app of feature 003 is a set of pages: a start page that asks for a view (engineer or
operator), a run list, a page per run, a scenario list, a scenario editor that saves under a
new name and sends the user to a queue page, what-if cases, test scenarios and formulas. A
simple task (change an input, compute, look at the result) crosses four pages.

The press line twin (`con-pre-dig-twi`, feature 009 there) works on one page: a header, tabs
for the parameter set, the results, the process data, the formulas and the report, the line
drawing always visible below the tabs, a Run button, key figures, limits with margins,
messages, charts with their values, CSV and picture, pinned results for comparison, and a
report that prints as PDF. This feature gives the boiler house and dryer twin the same
operation.

## Clarifications

### Session 2026-11-06

- Q: What happens to the pages of feature 003? → A: They stay as they are, reachable from the
  header as "Previous interface" (`/classic`), until the user decides which of their functions
  (what-if cases for operators, test scenario pages, the queue) move into the new page.
- Q: Is there still a view choice? → A: Not on the new page. It works in the engineer view; the
  permission table and the operator view of the older pages are unchanged.
- Q: May code of the press line twin be used? → A: Its layout and its way of working are
  followed, and the same open-source browser libraries are bundled. Its models, data and texts
  are not used. This repository already bundles Temml by way of that repository.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Change inputs and compute on one page (Priority: P1)

An engineer begins with an example, changes inputs, sees at each input whether the twin accepts
it, presses Run and sees the results on the next tab, without saving first and without leaving
the page.

**Independent Test**: New from an example, change the end time and one input, Run, and compare
the key figures with a command-line run of the same scenario.

**Acceptance Scenarios**:

1. **Given** an example, **When** it is opened with "New", **Then** its inputs are shown by
   section with value and unit, and the header says that it is an example.
2. **Given** an edited input, **When** about a second passes, **Then** the twin's own check has
   run and each problem is shown at its input; with problems, Save and Run are disabled.
3. **Given** valid inputs, **When** Run is pressed, **Then** a progress bar shows the simulated
   time, and afterwards the key figures, limits, messages and charts of the new run.
4. **Given** results, **When** an input is changed, **Then** the results are marked outdated.
5. **Given** a saved scenario, **When** it is edited, **Then** Save writes it in place; Save as,
   Rename, Delete, Download and Upload work on saved scenarios; examples stay read-only.
6. **Given** an input that accepts a time series, **When** "as step sequence" is chosen,
   **Then** a start value and steps at times can be entered, as in feature 003.

### User Story 2 - Results and report as in the press line twin (Priority: P1)

The results show key figures, limits and checks with value, limit and margin, messages, the
courses over time, the profiles along the drum and the heater table. Every chart gives its
values as a table, a CSV file and a picture. Up to four results can be pinned and are drawn
together and compared in a table. The report states what was computed with what, lists only the
changed inputs, and prints as PDF.

**Acceptance Scenarios**:

1. **Given** a run, **When** the time slider below the plant drawing is moved, **Then** the
   drawing, the key figures and the drum profiles show that time.
2. **Given** a pinned run and a new run, **Then** the charts show both and a table compares
   their key figures.
3. **Given** a run made from the open scenario, **When** the report is opened, **Then** it
   lists the inputs that differ from the file the scenario was opened from, and prints on a few
   A4 pages without navigation.
4. **Given** an earlier run, **When** it is opened from the run list, **Then** results and
   report show it; the report then says that its inputs are in the run folder.

### User Story 3 - Measurements, formulas, language (Priority: P2)

A measurement file is uploaded and compared with a run of the saved scenario, with the
deviation per output and a chart of model against measurement. All formulas are shown with
their symbols, code and sources, and can be searched and printed. German and English switch
without losing the edits.

### Edge Cases

- The service stops: a banner says so, the page keeps trying and goes on afterwards.
- A saved scenario was changed elsewhere since it was opened: Save is refused with a message.
- A run fails or is interrupted: the message of the job is shown; the last results stay.
- The page is reloaded: the scenario and the run that were open are opened again; unsaved edits
  are lost (stated limit).
- An example whose inputs refer to a file next to it (`[flue_gas] file = …`) is checked and run
  from another folder: the reference is followed (a fault of feature 003 found here).

## Requirements *(mandatory)*

- **FR-001**: `/` MUST serve one page with the tabs Scenario, Results, Measurements &
  comparison, Formulas & sources and Report; the tab is part of the address (`#results`).
- **FR-002**: The page MUST compute nothing itself: every value comes from the service, in the
  display units of feature 003.
- **FR-003**: Scenarios MUST be opened from the examples (read-only) and the saved scenarios,
  and saved scenarios MUST be saved in place, saved as, renamed, deleted, downloaded and
  uploaded. An upload that the twin cannot load MUST be refused and leave nothing behind.
- **FR-004**: Every edit MUST be checked by the twin's loader, with each issue at its input.
- **FR-005**: Run MUST compute the scenario as it is in the editor, saved or not, through the
  same queue and the same `records.run` as before, with the profiles along the drum.
- **FR-006**: Results MUST show key figures at the chosen time, the checks (flags as share of
  the run time; balances as relative error against tolerance, with margin and pass mark), the
  range warnings, charts over time, drum profiles and the heater table.
- **FR-007**: Every chart MUST offer its values as a table, a CSV file in the page's language
  (decimal comma and `;` in German) and a PNG picture.
- **FR-008**: Up to four runs MUST be pinned, kept on this computer, drawn together and
  compared.
- **FR-009**: The report MUST state scenario name, run id, fingerprint (SHA-256 of the
  scenario), software version, time of computation and simulated period, the changed inputs,
  key figures, checks, charts and messages, and MUST print without navigation.
- **FR-010**: The plant drawing of feature 003 MUST be shown below the tabs for the shown run,
  with a slider for the output time; it can be hidden.
- **FR-011**: A comparison with measurements MUST be started from the page and shown per output
  with bias, RMSE, largest deviation, tolerance, share within tolerance and verdict.
- **FR-012**: The formulas MUST be listed from the formula register with search and print.
- **FR-013**: All texts of the page MUST exist in German and English; German is the default.
- **FR-014**: The pages of feature 003 MUST keep working at their addresses; their start page
  moves to `/classic`.
- **FR-015**: The page MUST work offline: all scripts, styles and fonts are bundled, and the
  bundled libraries MUST be unchanged copies with their licences and checked hashes.
- **FR-016**: Every new call MUST be in the permission table and write an action log entry if
  it changes something.

## Success Criteria *(mandatory)*

- **SC-001**: From an open example to the results of a changed input in one page and at most
  three actions (edit, Results tab, Run).
- **SC-002**: A run from the page gives the same result files as `boidrytwin run` of the same
  scenario (same functions, as in feature 003).
- **SC-003**: The whole flow runs in a browser test without a console error.
- **SC-004**: A run report prints on at most six A4 pages.

## Assumptions

- One user on this computer, as in feature 003; no sign-in.
- Labels of sections and inputs are translated for the keys of the examples; an unknown key is
  shown by its name in the scenario file, which is always shown next to the label.
- Plausible ranges per input (as the press line twin's catalogue has) are not part of this
  feature: the scenario files carry units, and the loader's messages say what is allowed.
