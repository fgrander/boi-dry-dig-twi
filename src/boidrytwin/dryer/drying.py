"""Characteristic drying curve (research.md R4).

Constant-rate period (X > X_cr): evaporation limited by external mass transfer,
E = k_y A (Y_sat(T_s) - Y_g). Falling-rate period: E times f(Φ) = Φ^n with
Φ = (X - X_e) / (X_cr - X_e) (van Meel 1958; Keey 1972). Water never condenses onto the
solids: a negative driving force gives E = 0 and a flag.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from boidrytwin.properties import water
from boidrytwin.properties.gas import FloatArray

MAX_SATURATION_FRACTION = 0.95  # caps p_sat near boiling to keep Y_sat finite


def saturation_humidity(T_s: ArrayLike, p: ArrayLike, M_dry: ArrayLike) -> FloatArray:
    """Humidity of gas saturated at the solids surface temperature, kg/kg dry gas."""
    pa = np.asarray(p, dtype=float)
    p_s = np.minimum(
        water.p_sat(np.minimum(np.asarray(T_s, dtype=float), 640.0)), MAX_SATURATION_FRACTION * pa
    )
    return water.humidity_from_partial_pressure(p_s, pa, M_dry)


def rate_factor(X: ArrayLike, X_e: ArrayLike, X_cr: float, n: float) -> FloatArray:
    """Relative drying rate f(Φ): 1 in the constant-rate period, Φ^n below X_cr."""
    xa = np.asarray(X, dtype=float)
    xe = np.minimum(np.asarray(X_e, dtype=float), 0.999 * X_cr)
    phi = np.clip((xa - xe) / (X_cr - xe), 0.0, 1.0)
    return np.asarray(phi**n)


def evaporation(
    kA: ArrayLike, Y_sat: FloatArray, Y_g: FloatArray, factor: FloatArray
) -> tuple[FloatArray, NDArray[np.bool_]]:
    """Evaporation rate, kg/s, and a flag where the gas would condense onto the solids."""
    drive = np.asarray(Y_sat) - np.asarray(Y_g)
    return np.asarray(np.asarray(kA) * np.maximum(drive, 0.0) * factor), np.asarray(drive < 0)
