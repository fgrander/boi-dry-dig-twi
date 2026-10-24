"""Operating-range checks (FR-012, constitution principle III).

A run is flagged where it leaves the range the model is validated for: drum inlet gas
temperature above its limit, exhaust gas too close to its dew point, solids hotter than the
EMC data range, and configuration values outside their validated ranges (whole run).
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from boidrytwin.dryer.config import DryerConfiguration, RangeViolation
from boidrytwin.range_warnings import (
    LimitType,
    RangeWarning,
    detect_periods,
    out_of_range_mask,
)


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


__all__ = ["LimitType", "RangeWarning", "detect_periods", "out_of_range_mask", "range_warnings"]
