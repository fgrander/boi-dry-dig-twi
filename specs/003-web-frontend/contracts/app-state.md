# Contract: App State and Scenario Folders

**Covers**: FR-007a, FR-009–FR-014, FR-021, clarifications Q1, Q3, Q5 | **Research**: R3, R5, R6

All files are UTF-8 and written atomically (temporary file, then rename). Times are ISO 8601
UTC. The run folders themselves are the feature-001/002 format and are not described here.

## App folder (default `<runs>/.app/`)

```text
<runs>/.app/
├── queue.json            # {"version": 1, "jobs": [Job, ...]} in queue order
├── progress/<job_id>.json  # {"phase", "simulated_s", "duration_s", "updated_at"}
├── whatif.json           # {"version": 1, "runs": {run_id: WhatIfRun}}
├── jobs/<job_id>/        # the frozen scenario (and step files, measured upload) of a job
└── actions.jsonl         # one ActionLogEntry per line
```

- `Job` fields and states as in data-model §8. Unknown fields are kept when rewriting.
  A file with a higher `version` than the app knows is not modified, and the app says so.
- At server start: `running` → `interrupted`, `queued` → `not_started`, each logged. Nothing
  starts automatically (Q5).
- `jobs/<job_id>/` is written before the job is queued. The worker runs exactly that file, so
  later edits of the scenario don't affect a queued job (edge case).

## Scenario folder (default `scenarios/`)

```text
scenarios/
├── <name>.toml                    # saved scenario (normal scenario file, runs from the CLI)
├── <name>.steps/                  # its generated step-sequence CSVs, referenced by the TOML
│   └── steps_<key>.csv
├── <name>.meta.json               # {"derived_from", "saved_at", "steps": {key: StepSequence}}
└── operator/<op_name>/
    ├── v1/
    │   ├── scenario.toml          # frozen copy, normal scenario file
    │   ├── scenario.steps/
    │   └── operator.toml          # releases, comparison outputs
    └── v2/ ...
```

`operator.toml`:

```toml
version = 1
name = "Fuel and oil demand what-if"
created_at = "2026-10-24T10:00:00Z"
comparison_outputs = ["oil_outlet_temperature", "fuel_feed", "o2_dry", "drum_inlet_gas_temperature",
                      "product_moisture_wet_basis", "evaporation_rate", "heat_to_oil"]

[[release]]
key = "boiler_house.fuel.moisture_wet_basis"
label = "Fuel moisture"
unit = "%"
minimum = 35
maximum = 55
allow_step = true

[baseline]
job_id = "…"
run_id = "…"          # set when the baseline has completed
```

Step-sequence CSV (feature-001 time-series format):

```text
time,value
unit,%
2026-01-01T00:00:00Z,45
2026-01-01T06:00:00Z,45
2026-01-01T06:00:01Z,50
2026-01-02T00:00:00Z,50
```

The TOML references it as `moisture_wet_basis = { file = "<name>.steps/steps_<key>.csv",
column = "value" }`. Examples (`examples/`) are read-only for the app.
