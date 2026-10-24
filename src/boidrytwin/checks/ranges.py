"""Operating-range checks (FR-012, constitution principle III).

A run is flagged where it leaves the range the model is validated for: drum inlet gas
temperature above its limit, exhaust gas too close to its dew point, solids hotter than the
EMC data range, and configuration values outside their validated ranges (whole run).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import AwareDatetime, BaseModel, ConfigDict

from boidrytwin.dryer.config import DryerConfiguration, RangeViolation
from boidrytwin.properties.gas import FloatArray

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
    values: FloatArray,
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


def range_warnings(
    results: pd.DataFrame,
    config: DryerConfiguration,
    config_violations: Sequence[RangeViolation],
) -> list[RangeWarning]:
    index = pd.DatetimeIndex(results.index)
    out: list[RangeWarning] = []
    out += detect_periods(
        index,
        results["drum_inlet_gas_temperature"].to_numpy(),
        limit=config.max_drum_inlet_gas_temperature,
        limit_type="max",
        quantity="drum_inlet_gas_temperature",
    )
    margin = results["exhaust_temperature"].to_numpy() - results["exhaust_dew_point"].to_numpy()
    out += detect_periods(
        index,
        margin,
        limit=config.min_dew_point_margin,
        limit_type="min",
        quantity="exhaust_dew_point_margin",
    )
    out += detect_periods(
        index,
        results["_max_solids_temperature"].to_numpy(),
        limit=config.emc_data_limit,
        limit_type="max",
        quantity="solids_temperature",
    )
    for v in config_violations:
        out.append(
            RangeWarning(
                quantity=f"dryer.{v.field}",
                limit_type=v.limit_type,
                limit=v.limit,
                observed_extreme=v.value,
                period_start=index[0].to_pydatetime(),
                period_end=index[-1].to_pydatetime(),
            )
        )
    return out


def out_of_range_mask(index: pd.DatetimeIndex, warnings: Sequence[RangeWarning]) -> FloatArray:
    """Boolean per sample: inside any warning period."""
    mask = np.zeros(len(index), dtype=bool)
    for w in warnings:
        mask |= (index >= pd.Timestamp(w.period_start)) & (index <= pd.Timestamp(w.period_end))
    return mask
