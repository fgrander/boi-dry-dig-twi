"""Editable form of a scenario file (FR-007, FR-008; research R4, data-model §4).

The scenario TOML is read line by line into sections and fields, keeping every line's
original text. Writing changes only the lines of edited fields, so comments and layout
survive, and an unchanged form writes back byte-identically. Validation always goes through
the twin's own loader: the form is written to a temporary file, loaded with
``load_scenario``, and the loader's issues are attached to the fields they name.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from boidrytwin.errors import ScenarioValidationError
from boidrytwin.scenario.loader import load_scenario, require_runnable
from boidrytwin.webapp.steps import (
    COLUMN,
    Meta,
    StepSequence,
    read_meta,
    step_csv,
    steps_dir,
    steps_ref,
    write_meta,
)

Kind = Literal["quantity", "number", "text", "bool", "series_file", "steps", "other"]
KEY_LINE = re.compile(r"^(?P<lead>\s*)(?P<key>[A-Za-z0-9_\-]+)\s*=\s*")
HEADER = re.compile(r"^\s*(?P<open>\[\[?)\s*(?P<name>[A-Za-z0-9_.\-]+)\s*\]\]?")
# a number, then nothing or a unit that starts like one ("45 %", "282 degC", "0.8")
QUANTITY = re.compile(
    r"^\s*(?P<num>[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?)\s*(?P<unit>([A-Za-z%°µ(].*?)?)\s*$"
)


class Issue(BaseModel):
    field: str
    value: str = ""
    reason: str
    allowed: str = ""
    location: str | None = None


class FormField(BaseModel):
    key: str
    kind: Kind
    raw: str  # the TOML value text
    value: str | None = None  # quantities: number; text: the string
    unit: str | None = None
    steps: StepSequence | None = None
    series_ok: bool = False  # the input accepts a time series (set by the API)
    remove: bool = False
    line: int
    orig_raw: str
    orig_value: str | None = None
    orig_unit: str | None = None
    issues: list[Issue] = Field(default_factory=list)


class Section(BaseModel):
    name: str  # "" for top-level keys; arrays of tables numbered: "boiler_house.heaters[2]"
    fields: list[FormField] = Field(default_factory=list)

    @property
    def path(self) -> str:
        """Dotted path without the array number (for signal names)."""
        return re.sub(r"\[\d+\]$", "", self.name)

    def field(self, key: str) -> FormField:
        for f in self.fields:
            if f.key == key:
                return f
        raise KeyError(f"{self.name}.{key}")


class ScenarioForm(BaseModel):
    source: str
    read_only: bool = False
    lines: list[str]
    newline_at_end: bool = True
    sections: list[Section]
    issues: list[Issue] = Field(default_factory=list)

    def section(self, name: str) -> Section:
        for s in self.sections:
            if s.name == name:
                return s
        raise KeyError(name)


# --- reading ----------------------------------------------------------------------------


def _split_value(rest: str) -> str:
    """The value part of ``rest`` (after ``=``), without a trailing comment."""
    quote: str | None = None
    depth = 0
    for i, ch in enumerate(rest):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        elif ch == "#" and depth == 0:
            return rest[:i].rstrip()
    return rest.rstrip()


def _classify(raw: str) -> tuple[Kind, str | None, str | None]:
    try:
        value = tomllib.loads(f"x = {raw}")["x"]
    except tomllib.TOMLDecodeError:
        return "other", None, None
    if isinstance(value, bool):
        return "bool", str(value).lower(), None
    if isinstance(value, int | float):
        return "number", raw, None
    if isinstance(value, str):
        m = QUANTITY.match(value)
        if m:
            return "quantity", m.group("num"), m.group("unit")
        return "text", value, None
    if isinstance(value, dict) and "file" in value:
        return "series_file", str(value["file"]), str(value.get("column", ""))
    return "other", None, None


def read_form(
    path: Path, *, read_only: bool = False, series_keys: set[str] | None = None
) -> ScenarioForm:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    end_nl = text.endswith("\n")
    if end_nl:
        lines = lines[:-1]
    meta = read_meta(path)
    sections = [Section(name="")]
    counts: dict[str, int] = {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        h = HEADER.match(line)
        if h:
            name = h.group("name")
            if h.group("open") == "[[":
                counts[name] = counts.get(name, 0) + 1
                name = f"{name}[{counts[name]}]"
            sections.append(Section(name=name))
            continue
        m = KEY_LINE.match(line)
        if not m:
            continue
        raw = _split_value(line[m.end() :])
        kind, value, unit = _classify(raw)
        sec = sections[-1]
        full = f"{sec.path}.{m.group('key')}" if sec.path else m.group("key")
        steps = meta.steps.get(full)
        if kind == "series_file" and steps is not None:
            kind = "steps"
        sec.fields.append(FormField(
            key=m.group("key"), kind=kind, raw=raw, value=value, unit=unit, steps=steps,
            series_ok=full in (series_keys or set()), line=i, orig_raw=raw,
            orig_value=value, orig_unit=unit,
        ))  # fmt: skip
    return ScenarioForm(
        source=str(path), read_only=read_only, lines=lines, newline_at_end=end_nl,
        sections=[s for s in sections if s.fields or s.name],
    )  # fmt: skip


# --- editing ------------------------------------------------------------------------------


def set_field(
    form: ScenarioForm, section: str, key: str, *, value: str | None = None,
    unit: str | None = None, raw: str | None = None, steps: StepSequence | None = None,
    remove: bool = False,
) -> None:  # fmt: skip
    field = form.section(section).field(key)
    if remove:
        field.remove = True
    elif steps is not None:
        field.kind, field.steps = "steps", steps
    elif raw is not None:
        field.raw = raw
    else:
        if field.kind in ("series_file", "steps"):
            field.kind = "quantity"
        field.value, field.unit = value, unit if unit is not None else field.unit


def _toml_string(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _scenario_times(form: ScenarioForm) -> tuple[datetime, datetime]:
    time = form.section("time")

    def stamp(key: str) -> datetime:
        f = time.field(key)
        text = f.value if f.raw == f.orig_raw and f.value else tomllib.loads(f"x = {f.raw}")["x"]
        t = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=UTC)

    return stamp("start"), stamp("end")


def _new_raw(field: FormField, section: Section, form: ScenarioForm, target: Path,
             source_dir: Path, written: dict[str, str]) -> str:  # fmt: skip
    full = f"{section.path}.{field.key}" if section.path else field.key
    if field.kind == "steps":
        assert field.steps is not None
        start, end = _scenario_times(form)
        written[full] = step_csv(field.steps, start, end)
        return f'{{ file = "{steps_ref(target, full)}", column = "{COLUMN}" }}'
    if field.raw != field.orig_raw:
        return field.raw
    if field.kind == "quantity" and (field.value, field.unit) != (
        field.orig_value,
        field.orig_unit,
    ):
        return _toml_string(f"{field.value} {field.unit or ''}".strip())
    if field.kind in ("text",) and field.value != field.orig_value:
        return _toml_string(field.value or "")
    if field.kind == "number" and field.value != field.orig_value:
        return str(field.value)
    if field.kind == "series_file" and target.parent.resolve() != source_dir.resolve():
        ref = Path(field.value or "")
        if not ref.is_absolute():
            original = (source_dir / ref).resolve()
            try:
                rel = Path(os.path.relpath(original, target.parent.resolve())).as_posix()
            except ValueError:  # another drive on Windows
                rel = original.as_posix()
            return f'{{ file = "{rel}", column = "{field.unit}" }}'
    return field.raw


def materialize(form: ScenarioForm, target: Path, *, dry_run: bool = False,
                derived_from: str = "") -> str:  # fmt: skip
    """Write the form as a scenario file at ``target`` (with its step files); returns the text."""
    source = Path(form.source)
    if form.read_only and target.resolve() == source.resolve():
        raise PermissionError(f"{source.name} is read-only")
    lines = list(form.lines)
    written: dict[str, str] = {}
    drop: set[int] = set()
    for section in form.sections:
        for field in section.fields:
            if field.remove:
                drop.add(field.line)
                continue
            raw = _new_raw(field, section, form, target, source.parent, written)
            if raw != field.orig_raw:
                line = lines[field.line]
                m = KEY_LINE.match(line)
                assert m is not None
                start = m.end()
                end = start + len(field.orig_raw)
                lines[field.line] = line[:start] + raw + line[end:]
    out = [line for i, line in enumerate(lines) if i not in drop]
    text = "\n".join(out) + ("\n" if form.newline_at_end else "")
    if dry_run:
        return text
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    if written:
        folder = steps_dir(target)
        folder.mkdir(exist_ok=True)
        for key, csv in written.items():
            (folder / f"steps_{key}.csv").write_text(csv, encoding="utf-8", newline="\n")
        steps = {
            f"{s.path}.{f.key}" if s.path else f.key: f.steps
            for s in form.sections for f in s.fields if f.kind == "steps" and f.steps
        }  # fmt: skip
        write_meta(target, Meta(derived_from=derived_from, saved_at=datetime.now(UTC), steps=steps))
    return text


# --- validation ---------------------------------------------------------------------------


def _attach(form: ScenarioForm, issue: Issue) -> None:
    for section in form.sections:
        for field in section.fields:
            full = f"{section.name}.{field.key}" if section.name else field.key
            plain = f"{section.path}.{field.key}" if section.path else field.key
            for name in (full, plain):
                if issue.field == name or issue.field.startswith((name + ".", name + "[")):
                    field.issues.append(issue)
                    return
    form.issues.append(issue)


def validate_form(form: ScenarioForm, tmp_dir: Path | None = None) -> list[Issue]:
    """All loader issues of the form (attached to the fields); empty if it loads."""
    for section in form.sections:
        for field in section.fields:
            field.issues.clear()
    form.issues.clear()
    issues: list[Issue] = []
    with tempfile.TemporaryDirectory(dir=tmp_dir) as tmp:
        target = Path(tmp) / "scenario.toml"
        try:
            materialize(form, target)
            loaded = load_scenario(target)
            require_runnable(loaded)
        except ScenarioValidationError as exc:
            issues = [Issue(field=i.field, value=str(i.value), reason=i.reason, allowed=i.allowed,
                            location=i.location) for i in exc.issues]  # fmt: skip
        except ValueError as exc:  # step sequence outside the scenario period
            issues = [Issue(field="steps", reason=str(exc))]
    for issue in issues:
        _attach(form, issue)
    return issues


def form_dict(form: ScenarioForm) -> dict[str, Any]:
    return form.model_dump(mode="json")
