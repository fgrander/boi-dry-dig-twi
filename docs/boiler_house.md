# Boiler house model

Biomass furnace (hot gas generator) burning wood chips or bark, a radiant thermal oil
heater and convective thermal oil heaters in series, a damper-controlled bypass and three
control loops. The flue gas leaves towards the drum dryer through the feature-001 flue gas
interface. Feature 002: [spec](../specs/002-boiler-house-model/spec.md),
[research](../specs/002-boiler-house-model/research.md) (sources and decisions R1–R11).

> **Validation status**: not validated against plant data. The model has been checked
> against hand calculations (combustion, energy split), exact mass/element/energy balances,
> a Cantera oracle (adiabatic temperature) and its own step responses. Defaults marked
> **VERIFY** are typical values from the literature that still need checking against the
> primary sources or the plant (task T061, blocked until those are available).

## Structure

```text
fuel feed ──▶ [2-stage delay] ──▶ fuel bed ──▶ furnace gas (well stirred) ──▶ heater 1 (radiant)
                                     ▲              │ refractory (hot face, bulk) ──▶ ambient
combustion air (λ from the O₂ loop) ─┘              ▼
                         ┌── bypass (after heater b) ───────────────┐
                         ▼                                          ▼
               heaters 2 … n (convective cells) ──────────────▶ mixing ──▶ flue gas to the dryer
thermal oil: return ──▶ last cell ──▶ … ──▶ heater 1 ──▶ supply (counter-current to the gas)
```

Code: `src/boidrytwin/boiler_house/` (no import of `dryer` or `plant`), coordinated with
the dryer by `src/boidrytwin/plant/`.

## Equations as implemented

### Fuel and combustion (`properties/fuel.py`, R2)

- Composition per kg dry fuel (C, H, N, S, ash, O by difference); defaults for wood chips
  and bark from VTT Technology 272. Custom compositions must sum to 1 ± 0.005.
- HHV: Channiwala & Parikh (2002). LHV_d = HHV_d − 0.2122·H − 0.0008·(O + N) MJ/kg
  (ISO 18125 form, **VERIFY** coefficients); LHV_ar = LHV_d·(1 − M) − 2.443·M MJ/kg.
- Complete combustion: O₂,min = C/M_C + ½·H₂/M_H₂ + S/M_S − O₂/M_O₂ per kg dry fuel.
  Products CO₂, H₂O (fuel H, fuel moisture, air humidity), N₂, excess O₂, Ar and SO₂ (in
  "other", with its mass). Every element balances exactly.
- Air: λ·O₂,min·burnout (the O₂ loop sets λ) or a fixed humid air mass flow with the O₂
  loop in manual. Smooth lower bounds: the fans' minimum air and λ ≥ 1.05.

### Fuel bed (`fuel_bed.py`, R3; Bauer et al. 2010, Böhler et al. 2020)

- Feed transport: two first-order stages, mean delay `feed_dead_time` (**VERIFY**, 2 min).
- dm_w/dt = w·ṁ_f − m_w/τ_w (drying), dm_d/dt = (1 − w)·ṁ_f − m_d/τ_bed (burnout,
  including ash). τ_bed = 15 min, τ_w = 10 min (**VERIFY**, from plant step tests).

### Furnace and radiant heater (`furnace.py`, R4)

- Furnace gas: one well-stirred node with constant hold-up; the state is its enthalpy:
  dH/dt = burnout·LHV + evaporation·h_l,ref + fuel and air enthalpy − ash enthalpy
  − ṁ_g·h(T_f) − Q_rad − Q_refractory.
- Radiant heater (Lobo–Evans / Hottel well-stirred zone):
  Q_rad = σ·(αA_cp)·ε_fl·(T_f⁴ − T_w⁴) + h_c·A_t·(T_f − T_w); ε_fl = 0.5 (**VERIFY**,
  calibration parameter).
- Refractory: hot face and bulk nodes; the bulk loses heat to ambient through `loss_ua`
  (≈ 1 % of rated power). The bulk time constant is ≈ 11.5 h at the reference.

### Convective heaters (`heaters.py`, R5, R6)

- Each heater has `n_cells` cells along the gas path; gas quasi-static, wall and oil
  dynamic per cell:
  T_out = T_w + (T_in − T_w)·exp(−UA/(ṁ c_p)), heat ṁ·[h(T_in) − h(T_out)] (exact balance).
- Gas side: Žukauskas staggered bank (Incropera Table 7.5), Nu = C·Re^m·Pr^0.36 with
  C = 0.35·(S_t/S_l)^0.2, m = 0.6 (Re < 2·10⁵), else C = 0.022, m = 0.84; gas radiation
  ε_g = 0.1 (**VERIFY**); fouling R_f = 0.008 m²K/W (**VERIFY**, calibration parameter).
- Casing loss per cell in exact exponential form towards ambient.
- Oil side: Gnielinski (VDI Heat Atlas), laminar Nu = 3.66, blend over Re 2300–10⁴.
  Film temperature (Pelini 2008): T_film = T_oil + q″_peak / h_i.
- Thermal oil: Shell Thermia S2 or Therminol 66 property fits; limits bulk 300 °C, film
  320 °C (S2, **VERIFY** against the plant's oil data sheet).
- Oil flows counter-current: it enters the last cell and leaves heater 1 (the supply,
  controlled to 282 °C).

### Bypass and mixing (`bypass.py`, R7)

The damper position sets the bypass share of the gas after heater `starts_after_heater`.
The bypass duct has an optional loss UA; mixing before the dryer is exact in mass and
enthalpy. Damper characteristic and leakage are not modelled.

### Control loops (`control/`, `plant/model.py`, R8)

Continuous PI, v = K_c·e + I, u = sat(v) (smooth), dI/dt = (K_c/T_i)·e + (u − v)/T_t
(back-calculation anti-windup, T_t = T_i); manual mode tracks the manual output (bumpless).

| Loop | Measurement | Output | Default tuning |
|---|---|---|---|
| oil temperature | oil supply after heater 1 | fuel feed, 0.47–2.2 kg/s | K_c 0.191 kg/(s·K), T_i 1157 s |
| oxygen | O₂ dry, analyser lag 30 s (**VERIFY**) | λ, 1.1–2.5 | K_c 32.1, T_i 30 s |
| drum inlet temperature (coupled) | mixed drum inlet, sensor lag 20 s (**VERIFY**) | split range u ∈ [0, 1] | K_c 0.004 1/K, T_i 5 min |

The oil and O₂ settings are SIMC from step tests on the twin (`scripts/tune_controllers.py`,
results in `examples/data/controller_tuning.json`). The O₂ loop's τ_c is not set below
10 s, because the twin has no analyser dead time (**VERIFY**). Drum inlet split range:
u ≤ s opens the bypass ((s − u)/s), u ≥ s opens the dilution air
((u − s)/(1 − s)·ṁ_dil,max); they are never open together.

## States

| State | Unit | Count (reference) |
|---|---|---|
| feed stages | kg/s | 2 |
| bed water, bed dry fuel | kg | 2 |
| furnace gas enthalpy | J | 1 |
| refractory hot face, bulk | K | 2 |
| heater wall per node | K | 1 + Σ n_cells = 11 |
| oil specific enthalpy per node | J/kg | 11 |
| measured O₂ | mol/mol dry | 1 |
| controller integrals | output unit | 2 (3 coupled) |
| drum inlet sensor (coupled) | K | 1 |

Initial states: `cold`, `steady_state` (frozen-input march plus root polish; coupled plants
in two stages, the boiler house and controllers first, then the dryer) or `explicit` (from
a `final_state.json`, with the controller states).

## Valid operating range (R9, FR-011)

| Quantity | Range | Flag |
|---|---|---|
| fuel moisture, wet basis | 10–55 % | `combustion_out_of_range` |
| excess air λ | ≥ 1.2 | `combustion_out_of_range` |
| furnace temperature | 850–1150 °C | `combustion_out_of_range` |
| load | 30–100 % (flag below 50 %) | `load_out_of_range` |
| oil velocity, Reynolds | ≥ 2 m/s (**VERIFY**), ≥ 10⁴ | range warning |
| oil bulk, film temperature | below the oil's limits; film pre-warning at 80 % of the margin | `oil_limit` |

Controller flags: `controller_saturated` (automatic loop beyond its limits) and
`setpoint_not_reached` (outside the band for longer than the hold time).

## Calibration parameters

Typical values to be fitted to plant data, in order of influence: `flame_emissivity`,
`fouling_resistance`, `bed_time_constant`, `water_time_constant`, `feed_dead_time`,
`refractory_gas_htc`, `loss_ua`, the analyser and sensor lags, then the controller tuning
(rerun `scripts/tune_controllers.py` after calibration). Comparisons with plant data use
`boidrytwin compare` with measured columns named after `boiler_results.csv` outputs;
default tolerances (SC-008): O₂ ±0.5 vol% dry, flue gas temperatures ±10 K, oil outlet
±2 K.

## VERIFY list

ISO 18125 LHV coefficients; minimum load 30 %; refractory gas coefficient; ash discharge
temperature and specific heat; minimum combustion air; bed, drying and feed time
constants; O₂ analyser lag and dead time; drum inlet sensor lag; flame and gas
emissivities; convective coefficient of the radiant section; fouling resistance; oil
velocity practice limit; thermal oil limits and property data. Sources and the reasoning
for each default: research.md R2–R9.
