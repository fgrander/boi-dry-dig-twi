# Web app

A local web app for the plant twin (feature 003,
[spec](../specs/003-web-frontend/spec.md)). It lists and plots runs, edits and starts
scenarios, runs operator what-if cases against a baseline, and compares runs with plant
measurements. It never changes the models: every run is made by the same functions as
`boidrytwin run` and `boidrytwin compare`, and reruns from the command line give identical
results.

## Start

```powershell
uv sync --extra web
uv run boidrytwin serve                     # http://127.0.0.1:8765, opens the browser
uv run boidrytwin serve --runs D:\twin\runs --scenarios D:\twin\scenarios --port 8800 --no-browser
```

`Ctrl+C` stops the app. A run in progress at that moment is marked *interrupted*, and runs
still waiting are shown as *not started* the next time. Nothing starts on its own; start or
drop them on the Queue page. Exit codes: 0 normal stop, 1 bad folder or missing `web` extra,
3 port in use.

## Windows program (no Python needed)

`BoiDryTwin.exe` contains the whole app. Double-click it: a small window opens with the data
folder, then the browser opens on the app. Close the window to stop the app. Starting it again
while it runs just opens the browser.

- Runs, saved scenarios and a copy of the examples are kept in `Documents\BoiDryTwin\`
  (another folder with the environment variable `BOIDRYTWIN_HOME`). The examples there are
  refreshed when a new version of the program is started; runs and scenarios are never touched.
- The first start of each launch takes about 10 s (the program unpacks itself).
- Build it with `powershell -File scripts\build_exe.ps1` (output `dist\BoiDryTwin.exe`, about
  70 MB). `BOIDRYTWIN_NO_BROWSER=1` starts it without opening the browser (automated tests).

## Views

The start page asks for a view:

- **Engineer**: everything. Edit and save scenarios, start runs, create what-if cases for
  operators, delete runs, upload measurements.
- **Operator**: the run list and run pages, the what-if cases, starting what-if runs within
  the released ranges, and downloads.

The app is served to **this computer only** (`127.0.0.1`), and it refuses requests with a
foreign `Host` or a cross-site origin. There is no sign-in: **the view is a convenience, not a
security boundary**. The server still checks every request against the permission table
(`src/boidrytwin/webapp/permissions.py`); network access and sign-in can be added later at
that point.

## Pages

| Page | What it shows |
|---|---|
| Runs | every run folder, newest first, with status, kind, origin and the checks; search, filters; tick several to plot them together |
| Run | key plots in display units (°C, t/h, %, MW, kPa) with shaded warning and flag periods, any other output on request, the balance table, the range warnings, the dryer profiles, and the comparison with measurements if there is one; a PNG button on every plot and a CSV of the plotted data |
| Scenarios (engineer) | examples (read-only) and saved scenarios; open one to edit, save under a new name, run; the measurement upload |
| Scenario | the inputs by section, as value and unit; **Check** validates with the twin's own rules and shows each problem at its field; inputs that accept a time series can be given as a **step sequence** |
| What-if | the operator cases with their released inputs and baseline state; engineers create new cases here |
| What-if case | the released inputs with their ranges (and an optional step); engineers also see the release settings and save new versions |
| What-if result | a plain-language summary (oil and drum inlet on set point, product moisture, new warnings), the outputs against the baseline, overlay plots, CSV |
| Queue | jobs in order with state and progress; start or drop |
| Formulas | every formula of the models as implemented, grouped by subsystem, with the implementing code and numbered links to the literature (DOI or open-access copy; otherwise a marked literature search) |

## Scenarios and step sequences

Saved scenarios are normal scenario files in the scenario folder and run unchanged from the
command line (`boidrytwin run scenarios/<name>.toml`). Only the edited lines change, so
comments are kept. A step sequence is stored as a time-series CSV in
`<name>.steps/steps_<input>.csv` (feature-001 format), referenced from the TOML, and listed
in `<name>.meta.json` so the editor can show it as steps again. A step at time t from a to b
becomes the samples (t, a) and (t + 1 s, b).

## What-if cases

An engineer releases a few inputs of a scenario, each with a label, unit, minimum and
maximum, and whether a step is allowed. A release is accepted only if the scenario loads
with the input at its minimum and at its maximum, so a released range never goes beyond
what the twin accepts. Every save creates a new numbered version
(`scenarios/operator/<name>/v<N>/`) and queues its **baseline** run. A what-if run is the
version's scenario with only the released inputs changed. It is compared with the baseline
of its own version, so changing a case never changes earlier comparisons.

The comparison outputs default to the oil outlet temperature, fuel feed, O₂ (dry), drum
inlet temperature, product moisture, evaporation rate and heat to the oil, leaving out
those the scenario does not have; engineers can change them per case.

## Files the app writes

```text
<runs>/<run_id>/            normal run folders (feature 001/002); comparison runs also keep measured/<file>
<runs>/.app/queue.json      the queue (jobs and states)
<runs>/.app/jobs/<job_id>/  the frozen scenario (and inputs, uploaded file) each job ran
<runs>/.app/progress/       progress per job
<runs>/.app/whatif.json     what-if runs and their case, version and baseline
<runs>/.app/actions.jsonl   who did what: runs started, scenarios and versions saved, runs deleted
<scenarios>/<name>.toml     saved scenarios (+ .steps/ and .meta.json)
<scenarios>/operator/       what-if cases and their versions
```

Formats: [contracts/app-state.md](../specs/003-web-frontend/contracts/app-state.md); the HTTP
interface: [contracts/http-api.md](../specs/003-web-frontend/contracts/http-api.md).

## Limits

- One run at a time; a coupled 24 h run takes about 35 s.
- Uploads: `.csv`, at most 50 MB.
- Current desktop browsers on the same computer; no mobile layout.
- The editor changes existing keys only. Use a text editor to add new sections or keys.
