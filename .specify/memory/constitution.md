# boi-dry-dig-twi Constitution

A digital twin of an industrial dryer: a Python system that models, simulates and monitors
the drying process using physical models and measured process data.

## Core Principles

### I. Test-First (NON-NEGOTIABLE)

- Tests MUST be written before the implementation and MUST be observed failing before
  production code is written (Red → Green → Refactor).
- Every functional requirement in a spec MUST map to at least one automated test.
- Model and calculation code MUST have unit tests with known reference values (analytical
  solutions, hand calculations or published data) and stated numeric tolerances.
- Interfaces between components (data ingestion, model, outputs/APIs) MUST have contract or
  integration tests.
- A bug fix MUST start with a test that reproduces the bug.

Rationale: a digital twin is only trustworthy if its behaviour is verified. Writing tests first
forces requirements to be precise and stops untested physics from reaching production.

### II. Data Integrity & Validation

- All external inputs (sensor data, configuration, operator input, files) MUST be validated
  at the system boundary against an explicit schema, including types, ranges and required
  fields. Invalid data MUST be rejected or flagged, never silently coerced.
- Every physical quantity MUST carry an explicit unit (in its type, schema or name). Unit
  conversions MUST happen in one well-defined place, and SI units MUST be used internally.
- Timestamps MUST be timezone-aware and stored in UTC.
- Missing, stale or out-of-range measurements MUST be represented explicitly (e.g. a quality
  flag), not replaced with silent defaults.
- Simulation runs MUST be reproducible: inputs, parameters, model version and random seeds
  MUST be recorded so a run can be repeated with identical results.
- Raw ingested data MUST be kept immutable; derived data MUST be traceable to its sources.

Rationale: wrong units, silent gaps and untraceable data are the most common ways a twin
diverges from reality without anyone noticing.

### III. Validated Model Fidelity

- Every model (physical, empirical or data-driven) MUST document its assumptions, valid
  operating range and expected accuracy.
- Model outputs MUST be validated against measured or reference data with explicit acceptance
  tolerances before a model is used for decisions; these validations MUST be automated.
- Using a model outside its documented valid range MUST be detected and reported.
- Model and parameter changes MUST be versioned, and their effect on validation results MUST
  be visible in review.

Rationale: a digital twin is useful only to the extent that it matches the real dryer, within
known and stated limits.

### IV. Observability

- The system MUST use structured logging (machine-parseable, with timestamps, component and
  context such as run or asset IDs). `print` MUST NOT be used for operational output.
- Key operations (data ingestion, simulation runs, model validation) MUST emit metrics or
  logged summaries: counts, durations, rejected-data rates and model-vs-measurement deviation.
- Errors MUST be logged with enough context to diagnose them without a debugger, and MUST NOT
  be swallowed silently.
- Log levels MUST be configurable without code changes.

Rationale: operators and developers need to see what the twin is doing and why it deviates,
both during development and in operation.

## Technology Stack & Constraints

- Language: Python 3.12 or newer.
- Dependency and environment management: `uv`, with dependencies declared in `pyproject.toml`
  and a committed lock file.
- Testing: `pytest`. Numeric assertions MUST use explicit tolerances (e.g. `pytest.approx`).
- Code quality: `ruff` for linting and formatting; type hints are REQUIRED on all public
  functions and MUST pass a static type checker (e.g. `mypy` or `pyright`) in CI.
- Validation and units: boundary schemas SHOULD use a validation library (e.g. `pydantic`);
  unit handling SHOULD use a units library (e.g. `pint`) or unit-carrying types.
- Secrets and credentials MUST NOT be committed; configuration comes from the environment or
  untracked config files.
- New dependencies MUST be justified in the feature's plan.

## Development Workflow & Quality Gates

- All work follows the Spec Kit flow: `/speckit-specify` → (`/speckit-clarify`) →
  `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`. Each plan MUST include a
  Constitution Check against these principles.
- Each feature is developed on its own feature branch and merged to `main` through review.
- Before merge, all of the following MUST pass: the full test suite, the linter, the type
  checker and the automated model validations affected by the change.
- Reviews MUST verify that tests were written first, that inputs and units are validated, and
  that new behaviour is observable.
- Deviations from this constitution MUST be recorded and justified in the plan's Complexity
  Tracking section.

## Governance

- This constitution supersedes other development practices for this project. Where guidance
  conflicts, the constitution wins.
- Amendments are made with `/speckit-constitution`, MUST be documented in the commit that
  makes them, and MUST include a migration note when existing code or specs become
  non-compliant.
- Versioning follows semantic versioning: MAJOR for removing or redefining principles, MINOR
  for adding principles or sections or materially expanding guidance, PATCH for
  clarifications and wording fixes.
- Compliance is checked in every plan (Constitution Check) and every review. Unjustified
  violations block merge.

**Version**: 1.0.0 | **Ratified**: 2026-10-24 | **Last Amended**: 2026-10-24
