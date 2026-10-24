"""Fuel feed delay and lumped fuel bed (research.md R3; Bauer et al. 2010, Böhler et al. 2020).

- Feed transport: two equal first-order stages, mean delay = ``dead_time``.
- Bed water:  dm_w/dt = w·ṁ_f − m_w/τ_w   (evaporation m_w/τ_w)
- Bed dry fuel: dm_d/dt = (1 − w)·ṁ_f − m_d/τ_bed   (burnout m_d/τ_bed, including ash)

Time constants are placeholders until plant step tests (VERIFY).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from boidrytwin.properties.gas import FloatArray


def feed_stage_rates(stages: FloatArray, command: float, dead_time: float) -> FloatArray:
    tau = dead_time / 2.0
    return np.array([(command - stages[0]) / tau, (stages[0] - stages[1]) / tau])


@dataclass(frozen=True)
class BedRates:
    d_water: float
    d_dry: float
    evaporation: float  # kg/s water
    burnout: float  # kg/s dry fuel (incl. ash)


def bed_rates(
    m_water: float, m_dry: float, feed: float, moisture_wet: float, tau_bed: float, tau_water: float
) -> BedRates:
    evaporation = max(m_water, 0.0) / tau_water
    burnout = max(m_dry, 0.0) / tau_bed
    return BedRates(
        d_water=moisture_wet * feed - evaporation,
        d_dry=(1.0 - moisture_wet) * feed - burnout,
        evaporation=evaporation,
        burnout=burnout,
    )


def steady_inventory(
    feed: float, moisture_wet: float, tau_bed: float, tau_water: float
) -> tuple[float, float]:
    return moisture_wet * feed * tau_water, (1.0 - moisture_wet) * feed * tau_bed
