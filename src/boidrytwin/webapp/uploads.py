"""Measured time series uploads (FR-017, FR-022; data-model §9).

An upload is checked before use: a ``.csv`` name, at most ``MAX_BYTES``, and the twin's own
``read_measured`` rules. It is kept byte for byte: first in the job folder, then next to the
comparison run (``measured/<name>``).
"""

from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from pathlib import Path

from boidrytwin.validation.compare import read_measured

MAX_BYTES = 50 * 1024 * 1024
SAFE_NAME = re.compile(r"[^A-Za-z0-9_.\-]")


class UploadError(ValueError):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


def safe_name(name: str) -> str:
    base = Path(name or "measured.csv").name
    return SAFE_NAME.sub("_", base)[:100] or "measured.csv"


def store_upload(content: bytes, filename: str, staging: Path) -> tuple[Path, str]:
    """Write the upload to a staging folder after the checks; returns (path, sha256).

    Raises :class:`UploadError` (413/422) or ``ScenarioValidationError`` (invalid content).
    """
    name = safe_name(filename)
    if not name.lower().endswith(".csv"):
        raise UploadError(422, "the measured file must be a .csv file")
    if len(content) > MAX_BYTES:
        raise UploadError(413, f"the measured file is larger than {MAX_BYTES // (1024 * 1024)} MB")
    folder = staging / uuid.uuid4().hex
    folder.mkdir(parents=True)
    path = folder / name
    path.write_bytes(content)
    try:
        read_measured(path)  # the twin's own rules; raises ScenarioValidationError
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return path, hashlib.sha256(content).hexdigest()


def keep_with_run(measured: Path, run_folder: Path) -> Path:
    target = run_folder / "measured" / measured.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(measured, target)
    return target
