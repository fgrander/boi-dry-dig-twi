# Drum dryer model

Dynamic model of a directly heated, co-current, single-pass rotary drum dryer for wood chips
fed with flue gas from a boiler house. Decisions and sources:
[research.md](../specs/001-boiler-dryer-interface/research.md). Code: `src/boidrytwin/dryer/`.

> **Validation status.** The model is verified against physics checks (exact mass and
> energy balances, steady-state hand balance, settling, step responses) and property oracles
> (Cantera, CoolProp). It is **not yet validated against plant or literature data**, and its
> calibration parameters are uncalibrated defaults. With these defaults the reference case
> under-dries (≈ 32 % outlet moisture, ≈ 295 °C exhaust), i.e. the gas-chip heat transfer is
> under-predicted. Do not use results for decisions before calibration (constitution III).

## Structure

The drum is divided into N axial cells (default 20). Gas and solids enter cell 1 and flow
towards cell N. Per cell the solver integrates 8 states:

| State | Meaning | Unit |
|---|---|---|
| m_dp, m_da | dry solids in the flights/bed (passive) and falling (active) | kg |
| m_wp, m_wa | water in the passive and active solids | kg |
| U_s | enthalpy of the solids (both phases share one temperature) | J |
| H_g | enthalpy of the humid gas | J |
| Y_g | gas humidity | kg water / kg dry gas |
| T_sh | shell temperature | K |

Enthalpies are integrated instead of temperatures so that every balance is in flux form:
what leaves a cell enters the next, and mass and energy are conserved by construction. The
solids temperature follows analytically from U_s (the moist-wood enthalpy is quadratic in T);
the gas temperature by Newton iteration. The dry-gas hold-up of a cell is constant
(p V M_air / (R · 450 K)); the gas stays about a second in a cell. Temperatures are relative
to 298.15 K for all enthalpies.

## Inlet

Flue gas (mass flow, temperature, pressure, wet composition from the `FlueGasSupply`) is
mixed with optional dilution air at ambient temperature and humidity. The mixed dry-gas flow
G, humidity Y_in and specific enthalpy H_in enter cell 1. The heat supplied (FR-002) is the
sensible enthalpy flow of flue gas plus dilution air relative to 298.15 K.

## Solids transport (`transport.py`)

| Flow | Rate | Notes |
|---|---|---|
| passive → active (flight unloading) | m_dp / t_p | t_p = T_rev / f_cap − t_fall: one cycle per revolution |
| active → passive (curtain landing) | m_da / t_fall | t_fall = √(2 h_fall / g), h_fall = 0.6 D |
| active, cell i → i+1 | m_da v_a / Δz | v_a = (h_fall tan S + ½ a_drag t_fall²) / t_fall |
| passive, cell i → i+1 (kilning) | m_dp v_p / Δz | v_p = k_kiln (π − 0.6) D tan S / t_p |

a_drag = C_F · ½ ρ_g u_g² C_D A_p / m_p with C_D = 1 and the chip mass m_p growing with its
moisture, so drying chips are pushed further by the gas. With k_kiln = 1 and no gas, the
steady residence time equals Saeman & Mitchell (1954) with f(H) = π. Water moves with the dry
solids in proportion to each phase's moisture content.

## Gas-solids heat and mass transfer (`heat_transfer.py`, `drying.py`)

- Heat: Q = C_a h A (T_g − T_s) per phase. h from the Gnielinski single-sphere correlation
  (gas properties from `properties.gas`), relative velocity √(u_g² + (g t_fall / 2)²) for
  falling chips and u_g for the passive phase. Area: all chip surface of the active phase,
  10 % of it for the passive phase (`PASSIVE_EXPOSURE`).
- Evaporation: E = C_a k_y A (Y_sat(T_s) − Y_g) · f(Φ), k_y = h / c_p,humid (Chilton-Colburn,
  Lewis number 1). Y_sat uses p_sat capped at 0.95 p. No condensation onto the solids (E ≥ 0,
  flagged).
- Drying curve: f = 1 above the critical moisture X_cr; below it f = Φⁿ with
  Φ = (X − X_e)/(X_cr − X_e). X_e from the Hailwood-Horrobin isotherm (Wood Handbook 2021,
  Eq. 4-5) at the solids temperature and the gas partial pressure, clipped at 130 °C.
- Evaporated water leaves the solids as vapour at T_s; the energy needed (latent heat,
  sorption heat below fibre saturation, heat-capacity effects) follows from the moist-wood
  enthalpy (`properties.wood`).

## Shell (`heat_transfer.py`)

One lumped shell node per cell: m_sh c_sh dT_sh/dt = Q_gas→shell − Q_shell→solids − Q_loss.

- Gas → shell: pipe flow (Dittus-Boelter, laminar floor Nu = 3.66) on the inner area.
- Shell → solids: h_ws (calibration) on 25 % of the inner area, scaled down when the bed
  fills less than 5 % of the cell volume.
- Shell → ambient: Churchill & Chu free convection plus grey-body radiation, insulation as a
  series resistance.

## Outputs and flags

`results.csv` holds the `DryerResults` columns of
[data-model.md](../specs/001-boiler-dryer-interface/data-model.md#dryerresults). Flags:

- `heat_limited`: the gas has given up ≥ 90 % of its usable temperature drop,
  (T_in − T_exhaust) ≥ 0.9 (T_in − T_product).
- `condensation_risk`: exhaust within `min_dew_point_margin` (10 K) of its dew point. Cold
  chips near the inlet are often below the dew point of the humid gas; the model then sets
  their evaporation to zero (no condensation onto the solids is modelled) but does not flag
  it, because it is normal operation.
- `out_of_range`: inside a range warning period (below).

## Valid operating range

Range warnings (`checks/ranges.py`) are raised for:

| Check | Default limit |
|---|---|
| drum inlet gas temperature | ≤ 600 °C (`max_drum_inlet_gas_temperature`) |
| exhaust temperature above dew point | ≥ 10 K (`min_dew_point_margin`) |
| solids temperature (EMC data range) | ≤ 130 °C (`emc_data_limit`) |
| every configuration value | its validated range (`dryer/config.py`, `FIELDS`) |

A cold start always produces a one-sample dew-point warning at t = 0: the drum is then full
of ambient air close to its dew point.

Expected accuracy: unknown until validated. Targets (spec SC-003/SC-004): outlet moisture
±1 percentage point, exhaust temperature ±5 K for ≥ 90 % of steady operation, settling
times within ±20 %.

## Calibration parameters

| Parameter | Default | Meaning | Source / status |
|---|---|---|---|
| `heat_transfer_multiplier` (C_a) | 1.0 | gas-solids heat and mass transfer | research R3; first parameter to calibrate (outlet moisture, exhaust temperature) |
| `drag_coefficient` (C_F) | 0.1 | curtain drag relative to single-sphere drag | Baker 1992. VERIFY |
| `kilning_coefficient` | 1.0 | passive axial advance relative to Saeman-Mitchell f = π | Saeman & Mitchell 1954. VERIFY |
| `flight_capacity_factor` | 1.0 | cascades per revolution | Baker 1988, Ajayi & Sheehan 2012 |
| `shell_contact_htc` | 100 W/(m² K) | shell-solids contact | prior 50-150 W/(m² K). VERIFY |
| `critical_moisture_dry_basis` | 0.8 | end of the constant-rate period | Núñez-Retana et al. 2025 (> 0.42 wet basis) |
| `falling_rate_exponent` | 1.0 | falling-rate curve | to be fitted |

Fixed modelling constants still to verify against the original sources
([research.md Open item 1](../specs/001-boiler-dryer-interface/research.md#open-items), task
T078): fall height 0.6 D and C_D = 1 (`transport.py`), passive exposure 10 %, wall contact
25 % and bed fill reference 5 % (`model.py`), sorption heat 1.0 MJ/kg at X = 0 (`wood.py`),
and the Friedman-Marshall residence-time and Ua plausibility correlations.

## Numerics

`scipy.integrate.solve_ivp`, BDF, states scaled to order one, banded Jacobian sparsity
(cell i depends on cells i and i−1). The integration restarts at input breakpoints (where a
time series changes slope). Cumulative boundary flows are integrated alongside the model so
that the balance check measures only solver error (≈ 1e-8 relative). The steady state is
found by a loose-tolerance march followed by a Newton-type root solve (residual ≈ 1e-14).
24 h at 1-minute output takes about 10 s.
