"""Well-stirred furnace zone, radiant exchange and refractory (research.md R4).

Radiant section (Lobo-Evans / Hottel well-stirred zone):
    Q_rad = σ·(αA_cp)·ε_fl·(T_g⁴ − T_w⁴) + h_c·A_t·(T_g − T_w)
with the exchange factor approximated by the effective flame emissivity ε_fl (VERIFY,
calibration parameter; biomass flames radiate mainly from fly ash and gas).
Refractory: hot-face and bulk nodes; the bulk loses heat to ambient through UA.
"""

from __future__ import annotations

import numpy as np

from boidrytwin.properties import fuel as fuel_props
from boidrytwin.properties import gas, water, wood

SIGMA = 5.670374419e-8


def radiant_heat(
    T_gas: float,
    T_wall: float,
    cold_plane_area: float,
    emissivity: float,
    tube_area: float,
    convective_htc: float,
) -> float:
    radiation = SIGMA * cold_plane_area * emissivity * (T_gas**4 - T_wall**4)
    return float(radiation + convective_htc * tube_area * (T_gas - T_wall))


def refractory_flows(
    T_gas: float,
    T_hot: float,
    T_bulk: float,
    T_ambient: float,
    gas_htc: float,
    area: float,
    conductance: float,
    loss_ua: float,
) -> tuple[float, float, float]:
    """(gas → hot face, hot face → bulk, bulk → ambient), W."""
    return (
        gas_htc * area * (T_gas - T_hot),
        conductance * (T_hot - T_bulk),
        loss_ua * (T_bulk - T_ambient),
    )


def gas_temperature(h: float, y: np.ndarray, T_guess: float = 1200.0) -> float:
    """Invert the sensible mixture enthalpy (J/kg, relative to 298.15 K) for T."""
    T = T_guess
    for _ in range(30):
        f = float(gas.h_sensible_mass(T, y)) - h
        T -= f / float(gas.cp_mass(T, y))
        if abs(f) < 1e-6:
            break
    return T


def adiabatic_temperature(
    fuel: fuel_props.FuelComposition,
    *,
    moisture_wet: float,
    excess_air: float,
    air_humidity: float,
    T_fuel: float,
    T_air: float,
) -> float:
    """Adiabatic temperature of complete combustion (no losses, no ash enthalpy)."""
    st = fuel_props.stoichiometry(
        fuel, moisture_wet=moisture_wet, air_humidity=air_humidity, excess_air=excess_air
    )
    X = moisture_wet / (1.0 - moisture_wet)
    air_y = gas.mass_fractions(fuel_props.DRY_AIR_X)
    h_in = (
        fuel.lhv_dry()
        + float(wood.h_dry(T_fuel))
        + X * float(water.h_liquid(T_fuel))
        + st.air_dry_mass * float(gas.h_sensible_mass(T_air, air_y))
        + st.air_water_mass * float(water.h_vapour(T_air))
    )
    y = gas.mass_fractions(st.mole_fractions())
    return gas_temperature(h_in / st.flue_mass, y, T_guess=1500.0)
