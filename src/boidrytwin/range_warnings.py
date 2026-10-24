"""Range warning periods (shared by all subsystems; re-exported by checks.ranges)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray
from pydantic import AwareDatetime, BaseModel, ConfigDict

LimitType = Literal["min", "max"]


class RangeWarning(BaseModel):
    model_config = ConfigDict(frozen=True)

    quantity: str
    limit_type: LimitType
    limit: float
    observed_extreme: float
    period_start: AwareDatetime
    period_end: AwareDatetime


def detect_periods(
    index: pd.DatetimeIndex,
    values: ArrayLike,
    *,
    limit: float,
    limit_type: LimitType,
    quantity: str,
) -> list[RangeWarning]:
    """One warning per contiguous run of samples beyond ``limit`` (NaN is not a violation)."""
    v = np.asarray(values, dtype=float)
    with np.errstate(invalid="ignore"):
        bad = v > limit if limit_type == "max" else v < limit
    bad &= ~np.isnan(v)
    warnings: list[RangeWarning] = []
    i, n = 0, len(v)
    while i < n:
        if not bad[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and bad[j + 1]:
            j += 1
        segment = v[i : j + 1]
        warnings.append(
            RangeWarning(
                quantity=quantity,
                limit_type=limit_type,
                limit=limit,
                observed_extreme=float(segment.max() if limit_type == "max" else segment.min()),
                period_start=index[i].to_pydatetime(),
                period_end=index[j].to_pydatetime(),
            )
        )
        i = j + 1
    return warnings


def out_of_range_mask(
    index: pd.DatetimeIndex, warnings: Sequence[RangeWarning]
) -> NDArray[np.bool_]:
    """Boolean per sample: inside any warning period."""
    mask = np.zeros(len(index), dtype=bool)
    for w in warnings:
        mask |= (index >= pd.Timestamp(w.period_start)) & (index <= pd.Timestamp(w.period_end))
    return mask
