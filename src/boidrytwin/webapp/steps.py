"""Step sequences as time-series CSV files (FR-007a, research R5, data-model §5).

A step sequence (a start value and steps at given times) is written in the feature-001
time-series format next to the saved scenario, which references it as
``{ file = "<name>.steps/steps_<key>.csv", column = "value" }``. The scenario therefore runs
unchanged from the command line. A step at time t from a to b becomes the rows (t, a),
(t + 1 s, b), as in the examples. The sequences themselves are kept in ``<name>.meta.json`` so
the app can show them as steps again.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, Field

STEP_RAMP = timedelta(seconds=1)
COLUMN = "value"


class StepError(ValueError):
    """A step sequence whose times are not strictly increasing inside the scenario period."""


class Step(BaseModel):
    time: AwareDatetime
    value: float


class StepSequence(BaseModel):
    unit: str
    start_value: float
    steps: list[Step] = Field(default_factory=list)


class Meta(BaseModel):
    derived_from: str = ""
    saved_at: AwareDatetime | None = None
    steps: dict[str, StepSequence] = Field(default_factory=dict)


def _stamp(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def step_csv(seq: StepSequence, start: datetime, end: datetime) -> str:
    previous = start
    for step in seq.steps:
        if not previous < step.time < end or step.time + STEP_RAMP >= end:
            raise StepError(
                f"step at {_stamp(step.time)}: times must increase and lie inside "
                f"{_stamp(start)} – {_stamp(end)}"
            )
        previous = step.time + STEP_RAMP
    rows = ["time,value", f"unit,{seq.unit}", f"{_stamp(start)},{seq.start_value!r}"]
    value = seq.start_value
    for step in seq.steps:
        rows.append(f"{_stamp(step.time)},{value!r}")
        value = step.value
        rows.append(f"{_stamp(step.time + STEP_RAMP)},{value!r}")
    rows.append(f"{_stamp(end)},{value!r}")
    return "\n".join(rows) + "\n"


def steps_dir(target: Path) -> Path:
    return target.parent / f"{target.stem}.steps"


def steps_ref(target: Path, key: str) -> str:
    return f"{target.stem}.steps/steps_{key}.csv"


def meta_path(target: Path) -> Path:
    return target.parent / f"{target.stem}.meta.json"


def read_meta(target: Path) -> Meta:
    path = meta_path(target)
    if not path.is_file():
        return Meta()
    return Meta.model_validate(json.loads(path.read_text(encoding="utf-8")))


def write_meta(target: Path, meta: Meta) -> None:
    meta_path(target).write_text(meta.model_dump_json(indent=2), encoding="utf-8")
