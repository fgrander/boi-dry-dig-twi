"""Split-range mapping of the drum inlet temperature controller (research.md R8).

One controller output u ∈ [0, 1]:

- u ≤ s: bypass damper position (s - u) / s, dilution air 0 (gas too cold: more hot gas);
- u ≥ s: bypass 0, dilution air (u - s) / (1 - s) · max_dilution (gas too hot).

The two actuators are never open at the same time. The split value s should follow the
gain ratio of the two actuators (Reyes-Lúa & Skogestad 2020); the default 0.5 is a
placeholder until the tuning step tests.
"""

from __future__ import annotations

from typing import overload

import numpy as np

from boidrytwin.properties.gas import FloatArray


@overload
def split(u: float, s: float, max_dilution: float) -> tuple[float, float]: ...
@overload
def split(u: FloatArray, s: float, max_dilution: float) -> tuple[FloatArray, FloatArray]: ...
def split(
    u: float | FloatArray, s: float, max_dilution: float
) -> tuple[float, float] | tuple[FloatArray, FloatArray]:
    if not 0.0 < s < 1.0:
        raise ValueError(f"split value must satisfy 0 < s < 1, got {s}")
    ua = np.clip(np.asarray(u, dtype=float), 0.0, 1.0)
    bypass = np.where(ua < s, (s - ua) / s, 0.0)
    dilution = np.where(ua > s, (ua - s) / (1.0 - s) * max_dilution, 0.0)
    if np.ndim(u) == 0:
        return float(bypass), float(dilution)
    return np.asarray(bypass), np.asarray(dilution)
