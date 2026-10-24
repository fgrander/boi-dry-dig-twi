"""Validation issues and error types."""

from __future__ import annotations

import json
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict


class ValidationIssue(BaseModel):
    """One problem found while validating user input (contracts/flue-gas-interface.md)."""

    model_config = ConfigDict(frozen=True)

    field: str
    value: str
    reason: str
    allowed: str
    location: str | None = None

    def __str__(self) -> str:
        where = f" [{self.location}]" if self.location else ""
        return f"{self.field}: {self.reason} (given: {self.value}; allowed: {self.allowed}){where}"


class ScenarioValidationError(Exception):
    """A scenario (or one of its inputs) failed validation; carries every issue found."""

    def __init__(self, issues: Iterable[ValidationIssue]) -> None:
        self.issues: list[ValidationIssue] = list(issues)
        super().__init__(self._text())

    def _text(self) -> str:
        lines = [f"{len(self.issues)} validation issue(s):"]
        lines += [f"  - {issue}" for issue in self.issues]
        return "\n".join(lines)

    def to_json(self) -> str:
        payload = {"valid": False, "issues": [issue.model_dump() for issue in self.issues]}
        return json.dumps(payload, ensure_ascii=False, indent=2)


class InterfaceValidationError(ScenarioValidationError):
    """Invalid data at the flue gas supply interface."""


class SupplyCoverageError(Exception):
    """A flue gas source was asked for a time it has no data for."""


class SimulationError(Exception):
    """The ODE solver failed or produced an invalid state."""
