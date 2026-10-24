# Feature Specification: Local Web App for the Plant Twin

**Feature Branch**: `003-web-frontend`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "Website for the frontend and simulation: a local web app (started on
the user's own machine) to configure, run and view boiler house and dryer simulations, used
by both engineers and plant operators."

## Context

Features 001 and 002 provide the drum dryer model, the boiler house model and the coupled
plant. Today they are used only from the command line and through files: scenarios are
written as text files with units, and results arrive as tables in run folders. That works for
the engineers who built the models. It does not work for plant operators, who want to try
"what if" cases (a wetter fuel, a higher oil demand, a different drum inlet set point) and
see the effect without editing files or reading tables.

This feature adds a web app, opened in a browser, that sits on top of the existing twin. It
does not change the models. It is a new way to choose scenarios, start runs and look at
results. Everything it does can still be repeated from the command line: every run started
from the app is a normal, reproducible run with its run record.

Two kinds of users:
- **Engineers** prepare scenarios (all inputs, configuration and controller settings),
  decide which inputs operators may change, and inspect results in detail (balances, range
  warnings, profiles, comparisons with measurements).
- **Operators** start what-if runs from a scenario prepared by an engineer, changing only
  the inputs released for them, and compare the result with the baseline.

## Clarifications

### Session 2026-10-24

- Q: Do operators use the app on the same computer as the engineer, or from other computers
  in the plant network? → A: Same computer for now, without sign-in; the engineer and
  operator views are checked on every action so that network access and sign-in can follow
  in a later feature (FR-016).
- Q: When users edit a scenario, may they also change inputs that vary over time, or only
  fixed values? → A: Fixed values, plus a step editor (a value that changes to other values at
  given times, one or more steps); time-series files already used by a scenario are shown
  but not edited, and uploading new input files is out of scope (FR-007a).
- Q: Should users be able to take results out of the app? → A: Yes, as downloads of what is
  shown: each plot as an image and the plotted data or comparison table as a CSV file with
  units; a formatted report is out of scope (FR-018a).
- Q: When an engineer changes an operator scenario after its baseline run exists, what
  happens to the baseline? → A: Each saved version gets its own baseline, run automatically
  when the version is saved; what-if runs are compared with the baseline of the version they
  used (FR-014).
- Q: Who decides which outputs an operator sees in the what-if comparison? → A: A default
  set for all operator scenarios, which the engineer can extend or reduce per operator
  scenario; the plain-language summary is always shown (FR-014a, FR-015).
- Q: If the app is closed while runs wait in the queue, what happens to them on restart?
  → A: They are kept and shown as "not started"; the user can start or drop them, and the
  interrupted run can be restarted the same way. Nothing starts automatically (FR-011).
- Q (added after implementation): Should the app show the models' formulas? → A: Yes, one page
  with all formulas linked to the literature (FR-023).
- Q (added after implementation): Should everything run from one program that opens the
  browser by itself? → A: Yes, `BoiDryTwin.exe` (FR-024).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View the results of a run (Priority: P1)

An engineer opens the app and sees the list of runs in the run folder, newest first, with
scenario name, date, status and whether the checks passed. They open a run and see its key
outputs as time-series plots: for the boiler house the oil outlet temperature, fuel feed,
O₂, furnace temperature and heat to the oil; for the dryer the drum inlet temperature,
product moisture, exhaust temperature and evaporation; the controller outputs. They also see
the balance report, the range warnings and the flagged periods marked on the plots.

**Why this priority**: Reading results is what both user groups need first, and it is useful
even with runs started from the command line. It is the smallest independently useful
slice and the base for all other stories.

**Independent Test**: Run the reference examples from the command line, open the app, and
check that every run is listed and that its plots, balances and warnings match the run
folder's files.

**Acceptance Scenarios**:

1. **Given** a run folder with boiler-only, coupled and dryer-only runs, **When** the user
   opens the app, **Then** all runs are listed with name, start time, status and a
   passed/failed indicator for the checks.
2. **Given** a coupled run, **When** the user opens it, **Then** plots of the key boiler house,
   dryer and controller outputs are shown in display units (°C, t/h, %, MW), with the time
   axis in the scenario's time.
3. **Given** a run with range warnings or controller flags (saturated, set point not
   reached), **When** the user opens it, **Then** those periods are marked on the affected
   plots and listed with their quantity, limit and extreme value.
4. **Given** a run whose balances failed, **When** it is listed or opened, **Then** the failure
   is clearly visible, and the failing entries and quantities are shown.
5. **Given** two runs, **When** the user selects both, **Then** their outputs are plotted
   together for comparison.

---

### User Story 2 - Start a simulation from the browser (Priority: P1)

An engineer chooses a scenario (one of the examples or a saved scenario), changes inputs in a
form (each value with its unit), and starts the run. The form checks the values against the
same rules as the command line and explains any rejected value. While the run is going the
user sees its progress; when it is done it opens in the results view of User Story 1.

**Why this priority**: Starting runs without editing files is the main reason for the app.
Together with User Story 1 it replaces the command line for everyday work.

**Independent Test**: Start the reference coupled scenario from the app with a changed fuel
moisture, and check that a run folder appears that is identical to running the same scenario
from the command line.

**Acceptance Scenarios**:

1. **Given** the example scenarios, **When** the user picks one, **Then** its inputs are shown
   grouped by section (time, ambient, fuel, combustion air, furnace and heaters, thermal oil,
   controllers, product feed, dryer), with values and units.
2. **Given** a changed value, **When** the user starts the run, **Then** it is validated with
   the twin's own rules; an invalid value is rejected with the field, the value, the reason and
   the allowed range, and no run is started.
3. **Given** a valid scenario, **When** the run starts, **Then** the user sees that it is running
   and how far it has got, and can keep using the app.
4. **Given** a finished run, **When** the user reruns its scenario from the command line,
   **Then** the results are identical (the scenario used by the app is saved with the run).
5. **Given** an edited scenario, **When** the user saves it under a new name, **Then** it can be
   chosen again later and is a normal scenario file that also works from the command line.
6. **Given** a run that fails (solver failure), **When** it ends, **Then** the app shows it as
   failed with the error message, and the run record is kept.

---

### User Story 3 - What-if runs for operators (Priority: P2)

An engineer marks a scenario as an operator scenario and releases a few of its inputs for
operators, each with an allowed range (for example fuel moisture 35–55 %, oil return
temperature 220–260 °C, drum inlet set point 480–600 °C, product feed 6–14 t/h); a released
input can be a fixed value or a step at a chosen time (for example "oil demand +20 % at
06:00"). An operator
picks that scenario, sees only the released inputs in a simple form, changes them within
their ranges, starts the run and sees the result next to the baseline run of that scenario:
the key outputs side by side and their differences (for example "fuel feed +8 %, oil outlet
on set point, product moisture −2 percentage points").

**Why this priority**: This is what makes the twin useful to operators, but it builds on
User Stories 1 and 2.

**Independent Test**: An engineer releases two inputs of the coupled reference scenario; an
operator changes one within range, starts the run and gets a comparison with the baseline;
a change outside the range is refused before the run starts.

**Acceptance Scenarios**:

1. **Given** an operator scenario, **When** an operator opens it, **Then** only the released
   inputs are editable, each with its unit and allowed range; all other inputs are shown
   read-only or hidden.
2. **Given** a value outside its released range, **When** the operator starts the run,
   **Then** it is refused with the allowed range, and no run starts.
3. **Given** a finished what-if run, **When** it opens, **Then** the key outputs are shown next
   to the baseline run, with their differences and any new warnings or flags.
4. **Given** an engineer saves a new version of an operator scenario, **When** it is saved,
   **Then** its baseline run is queued automatically, and what-if runs on that version are
   compared with that baseline (not with an older version's).
5. **Given** the operator view, **When** an operator works with it, **Then** the most important
   outcome (oil on set point, drum inlet on set point, product moisture, any warning) is
   readable without knowledge of the scenario files.

---

### User Story 4 - Compare a run with plant measurements (Priority: P3)

An engineer uploads a measured time series (the same file format as the command line's
`compare`) for a run and sees the comparison: measured and predicted curves together, the
deviation statistics per output, the tolerances and whether each output passed, and the
excluded samples.

**Why this priority**: Calibration against plant data is engineering work that already
works from the command line; seeing it in plots makes it easier but is not needed first.

**Independent Test**: Upload the synthetic boiler measurements for the oil step scenario
and check that the app shows the same biases, tolerances and pass/fail as the command line.

**Acceptance Scenarios**:

1. **Given** a measured file, **When** it is uploaded for a scenario, **Then** it is validated
   with the twin's own rules and rejected with reasons if invalid.
2. **Given** a valid measured file, **When** the comparison has run, **Then** measured and
   predicted values are plotted together and the statistics per output match the command
   line's comparison report.

---

### Edge Cases

- A run folder contains a run from an older or newer version of the twin, or a damaged run
  record: it is listed with a clear note and does not stop the other runs from being shown.
- A run is still in progress when the app is closed or the machine restarts: the run is shown
  as interrupted, not as completed, and no partial results are presented as final; runs that
  were waiting are shown as "not started" and are not started automatically.
- Several runs are started at once: they wait in a queue, and the user sees their order.
- A long run (several days of plant time): progress stays visible, and the app remains usable.
- A scenario uses input time series files: they are shown (name, period, number of samples),
  and a changed or missing file is reported, as on the command line.
- An engineer changes an operator scenario while an operator is using it: the operator's run
  uses the version that was shown when the run was started, this version is recorded, and the
  run is compared with that version's baseline.
- The baseline run of a version fails: what-if runs on that version are still run but shown
  without a comparison, with a note that the baseline failed.
- A what-if run produces warnings that the baseline did not have (for example the furnace
  above its rated load): they are highlighted in the comparison.
- Very many runs in the folder (hundreds): the list stays usable (search, filter by scenario
  and status).
- The app is opened from a second browser window: both show the same runs and queue.

## Requirements *(mandatory)*

### Functional Requirements

**Runs and results (US1)**

- **FR-001**: The app MUST list all runs of the configured run folder with scenario name,
  creation time, status (completed, failed, running, queued, not started, interrupted) and whether the
  checks (balances, validation) passed.
- **FR-002**: The app MUST show the time series of a run as plots. It MUST offer a default
  set of key outputs per subsystem (boiler house, dryer, controllers) and let the user add any
  other output of the run's result files.
- **FR-003**: Values MUST be shown in display units with the unit stated (for example °C, t/h,
  %, MW); the stored and computed values stay in SI units, and the conversion is done in one
  place.
- **FR-004**: The app MUST show a run's balance report (every entry and quantity, with residual
  and tolerance), its range warnings (quantity, limit, extreme value, period) and its flags,
  and MUST mark flagged and out-of-range periods on the plots.
- **FR-005**: The user MUST be able to plot the outputs of two or more runs together.
- **FR-006**: For coupled runs with profiles, the app SHOULD show the dryer's profiles along the
  drum at a chosen time.

**Scenarios and starting runs (US2)**

- **FR-007**: The user MUST be able to open the example scenarios and saved scenarios, see all
  their inputs grouped by section with values and units, edit them and save them under a new
  name as normal scenario files.
- **FR-007a**: Any input that accepts a time series MAY instead be given as a step sequence in
  the app: a start value and one or more steps (time, new value), each value with its unit
  and checked against the input's allowed range. A saved step sequence MUST be stored so that
  the scenario runs identically from the command line. Inputs that already come from a
  time-series file are shown (file, period, samples, value range) but not edited; they can be
  replaced by a fixed value or a step sequence. Uploading new input files is out of scope.
- **FR-008**: Before a run starts, the scenario MUST be validated with the twin's own rules
  (the same as the command line). Rejected values MUST be shown with field, value, reason and
  allowed range, and no run may start.
- **FR-009**: A run started from the app MUST produce a normal run folder and run record,
  identical to a command-line run of the same scenario; the scenario exactly as run MUST be
  saved with it so that the run can be repeated.
- **FR-010**: Runs MUST execute in the background, one at a time in order (queue), while the app
  remains usable; the user MUST see each run's state and progress (simulated time reached).
- **FR-011**: A failed run MUST be shown as failed with its error message; a run interrupted by
  closing the app MUST be shown as interrupted. The queue MUST survive closing the app: after
  a restart, runs that were waiting are shown as "not started", and the user can start or
  drop each of them, or restart the interrupted run. Nothing starts automatically after a
  restart.

**Operator what-if runs (US3)**

- **FR-012**: An engineer MUST be able to mark a scenario as an operator scenario and release
  selected inputs for operators, each with a minimum and maximum (in its unit) and a short
  label. Released ranges MUST lie inside the twin's own valid ranges.
- **FR-013**: In the operator view, only released inputs MUST be editable, and values outside the
  released range MUST be refused before a run starts.
- **FR-014**: Operator scenarios MUST be versioned: every save creates a new version, and each
  version MUST get its own baseline run, queued automatically when the version is saved. A
  what-if run MUST record the version it used and MUST be shown next to that version's
  baseline, with the key outputs, their differences (absolute and relative) and any warnings
  or flags that the baseline did not have. A what-if run started before its baseline has
  finished waits for it in the queue.
- **FR-014a**: The outputs in a what-if comparison MUST default to: oil outlet temperature,
  fuel feed, O₂ (dry), drum inlet temperature, product moisture, evaporation rate and heat to
  the oil (outputs a scenario does not have, e.g. dryer outputs in a boiler-only scenario,
  are left out). The engineer MAY add or remove outputs per operator scenario; the choice is
  part of the operator scenario version.
- **FR-015**: The operator view MUST always state the main outcome in plain terms, whatever
  outputs are chosen: whether the oil and drum inlet temperatures are on their set points,
  the product moisture, and any warnings.
- **FR-016**: The engineer and operator views MUST be distinguishable, and the operator view
  MUST NOT allow changing inputs that are not released. In this feature the app is used on
  the computer it runs on only (not reachable from other computers), and the view is chosen
  when the app is opened, without sign-in. Every action MUST nevertheless be checked against
  the view it comes from (not only hidden in the page), so that sign-in and network access
  can be added in a later feature without changing these rules.

**Comparison with measurements (US4)**

- **FR-017**: The user MUST be able to upload a measured time series for a scenario; the file
  MUST be validated with the twin's own rules, and the comparison (statistics, tolerances,
  pass/fail, excluded samples) MUST match the command line's comparison report.
- **FR-018**: Measured and predicted values MUST be plotted together, with excluded samples
  marked.

**Export**

- **FR-018a**: Every plot MUST be downloadable as an image, and the data behind it (the plotted
  series, or the what-if or measurement comparison table) as a CSV file with a unit row and the
  run IDs it comes from. Both views (engineer and operator) may download. A formatted report
  (PDF or print layout) is out of scope.

**Formulas**

- **FR-023**: The app MUST have one page listing every formula the models use, as implemented,
  with the code that implements it and links to the literature it comes from (DOI or
  open-access copy where one is known; otherwise a marked literature search, never an
  invented link). Both views can open it.

**Desktop program**

- **FR-024**: The app MUST also be delivered as one Windows program (`BoiDryTwin.exe`) that
  needs no installed Python: starting it starts the app and opens the browser by itself;
  runs and saved scenarios are kept in the user's data folder (`Documents\BoiDryTwin`);
  starting it again while it runs only opens the browser; closing its window stops it.

**Cross-cutting**

- **FR-019**: The app MUST NOT change the models or their results; everything it computes goes
  through the twin's existing scenario, run and comparison functions.
- **FR-020**: The app MUST be started with one command on the user's machine and opened in a
  browser; it MUST work without internet access.
- **FR-021**: Every user action that starts, saves or deletes something (run, scenario,
  release settings) MUST be logged with time, view (engineer or operator) and what was done.
- **FR-022**: Uploaded files MUST be checked before use (type, size, content) and stored next to
  the run they belong to; the original file MUST be kept unchanged.

### Key Entities *(include if feature involves data)*

- **Run (view)**: one run folder as the app shows it: run record, status, result tables,
  balance report, warnings, flags, and for app-started runs the queue position and progress.
- **Scenario**: a scenario file (example or saved). Its inputs grouped by section; for app
  edits, the name it was saved under and the scenario it was derived from.
- **Operator scenario**: a scenario plus its released inputs (input, label, minimum, maximum,
  unit) and its comparison outputs, in numbered versions; each version has exactly one
  baseline run.
- **What-if run**: a run of one operator scenario version with the operator's changed inputs,
  linked to that version and its baseline run.
- **Run queue**: the ordered list of waiting and running runs, with their state and progress.
- **Measured series**: an uploaded measured time series, linked to the scenario and the
  comparison run made with it.
- **Action log entry**: time, view, action and its target (run, scenario, release settings).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A run folder with 200 runs is listed, and any run opens with its key plots, in
  under 3 seconds.
- **SC-002**: An operator who has never used the app completes a what-if run (change one
  released input, start it, read the comparison with the baseline) in under 5 minutes, without
  help, in at least 4 of 5 trials.
- **SC-003**: Every run started from the app gives results identical to the command-line run
  of its saved scenario (checked by rerun; 100 % of runs in the test set).
- **SC-004**: 100 % of the rejection rules of the scenario validation are reported in the app
  with field, value, reason and allowed range, as on the command line.
- **SC-005**: No input outside its released range can be submitted from the operator view (0
  out-of-range runs in a test set covering every released input at and beyond its limits).
- **SC-006**: The app remains responsive (opening runs, editing scenarios) while a coupled
  24-hour run is in progress, and the run takes no more than 10 % longer than from the
  command line.
- **SC-007**: The plotted values of every output match the run's result files within display
  rounding, and a downloaded CSV reproduces the plotted values exactly (in its stated units).

## Assumptions

- The app runs on a Windows engineering PC that has the twin installed; it is a local web app,
  opened in a current desktop browser on that PC. Mobile layouts are out of scope.
- Access from other computers in the plant network and sign-in (user accounts, roles) are
  out of scope for this feature and planned for a later one; the engineer/operator view
  choice is a convenience, not a security boundary, until then.
- One shared run folder and scenario folder per installation, configured at start (default:
  `runs/` and `examples/` plus a folder for saved scenarios).
- Runs are executed one at a time on the same machine; the typical coupled 24-hour run takes
  about 35 s (feature 002), so a simple queue is enough.
- Display units default to engineering units used in the plant (°C, t/h, kg/s, %, MW, kPa);
  choosing other display units is out of scope for this feature.
- The language of the interface is English, like the rest of the project.
- No live plant data connection: the app works with scenario files, run folders and uploaded
  measured files only. Online coupling to the plant control system is out of scope.
- Deleting runs is allowed for engineers only and asks for confirmation; operators cannot
  delete anything.
- The models and their valid ranges are those of features 001 and 002; released operator
  ranges are a subset of those valid ranges.
