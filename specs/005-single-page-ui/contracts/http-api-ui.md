# Contract: Additions to the HTTP Interface for the Single Page

Adds to [the interface of feature 003](../../003-web-frontend/contracts/http-api.md); its
request rules, error formats and guarantees apply unchanged.

## Pages

| Path | Views | Content |
|---|---|---|
| `/` | public | the single page. Sets the cookie `view=engineer` if it is not set to that |
| `/classic` | public | the start page of feature 003 with the view choice. Pages that need a view redirect here |
| `/ui/…` | public | scripts, styles and bundled libraries of the page |

## JSON interface

| Method and path | Views | Request | Response |
|---|---|---|---|
| `GET /api/ui/about` | both | | `{"guided_by", "ai_work_hours", "as_of", "version"}` |
| `PUT /api/scenarios/{name}` | engineer | `{"form": ScenarioForm}` as read from the saved scenario and edited | `200 {"name"}`; `404` for an example or unknown name; `409` if the file changed since the form was read; `422` issues with the form, nothing written |
| `DELETE /api/scenarios/{name}` | engineer | | `204`; the scenario, its step files and its meta file are removed; `404` for an example |
| `POST /api/scenarios/{name}/rename` | engineer | `{"name": new}` | `200 {"name"}`; step files and meta file move with it; `409` if the new name exists; `422` for a bad name |
| `GET /api/scenarios/{name}/file` | engineer | `?source=saved\|example` | the scenario file as download |
| `POST /api/scenarios/upload` | engineer | multipart: `file` (UTF-8 TOML, at most 1 MB), optional `name` (default: the file's name) | `201 {"name"}`; `409` if the name exists; `413` above 1 MB; `422` with the loader's issues, and nothing is kept |
| `POST /api/jobs/draft` | engineer | `{"form": ScenarioForm, "derived_from": "", "label": ""}` | `202 {"job_id"}`: a `run` job of the form as it is, with profiles; `422` issues with the form, and nothing is queued |
| `GET /api/runs/{id}/record` | both | | `{"run_id", "scenario_name", "scenario_file", "scenario_sha256", "model_version", "created_at", "status", "message", "start", "end", "python", "has_profiles"}` |
| `GET /api/formulas` | both | | `{"sections": [{"key", "title", "formulas": [Formula]}], "sources": {key: Source + "number"}}` |

`Formula`: `section`, `title`, `equations` (LaTeX), `symbols` (`tex`, `meaning`, `unit`),
`module`, `function`, `sources` (keys), `note`. `Source`: `citation`, `url`, `link_kind`,
`doi`.

## Guarantees

- A draft job freezes its own copy of the scenario like every job; the draft folder
  (`<runs>/.app/drafts/…`) is removed before the call returns. No scenario is saved and no
  example is changed.
- Action log entries: `scenario_saved` (with `overwritten`), `scenario_renamed`,
  `scenario_deleted`, `scenario_uploaded`, `run_started` (with `draft`).
- A scenario written to another folder (save as, draft, check) keeps pointing to the files it
  refers to, also through a plain `file` key.
