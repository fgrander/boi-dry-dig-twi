# Exhaust recirculation and draft

Optional part of the drum dryer model (feature 004): an exhaust fan behind the drum outlet
returns part of the exhaust through a recirculation damper into the mixing chamber in front of
the drum, where it mixes with the flue gas (after bypass and dilution air). The damper
controls the negative pressure (draft) in the mixing chamber. Decisions and sources:
[research.md](../specs/004-dryer-exhaust-recirculation/research.md). Code:
`src/boidrytwin/dryer/gas_path.py`, `dryer/recirculation.py`, `dryer/model.py`.

> **Validation status.** Verified against physics checks only: exact mass and energy
> balances of the loop, a hand-calculated mixing case
> ([recirculation_case.md](../tests/validation/recirculation_case.md)), step responses of the
> pressure loop, and identical results without `[recirculation]`. The fan, damper and
> resistance data of the examples are **not plant data**. Do not use results for decisions
> before the gas path is calibrated against measured pressures and flows (constitution III).

## Gas path (research R2, R3)

Mixing chamber → drum, cyclone and ducts → exhaust fan → stack, with the return line from the
fan's pressure side through the damper back to the mixing chamber.

- **Quasi-steady.** Pressures and flows settle within milliseconds, far faster than the drum,
  so they are solved algebraically at every evaluation; the mixing chamber has no volume.
  Pressures are relative to ambient (Pa); densities use ambient pressure.
- **Fan.** A quadratic through 3 curve points at nominal speed n₀, scaled by the fan laws and
  by density: Δp = [a₀(n/n₀)² + a₁(n/n₀)V̇ + a₂V̇²] ρ/ρ_ref (Carolus 2013, Bleier 1998). The
  curve must fall, ever more steeply.
- **Resistances** (drum path, stack): constant loss coefficient through one design point,
  Δp = Δp_d (ρ_d/ρ)(ṁ/ṁ_d)² (Idelchik 2007).
- **Damper.** ṁ = φ(s) ṁ_open,d √(ρ Δp / (ρ_d Δp_d)) with φ(s) a monotone table (PCHIP).
  The default is the inherent characteristic of an opposed-blade damper with 1 % leakage
  (ASHRAE 2020, ch. 47).
- **Operating point.** The stack carries the fresh gas (what the boiler house sends); the
  recirculated dry gas is the root of one strictly decreasing equation (brentq):
  p_mc = Δp_stack − (Δp_fan − Δp_drum).

## Mixing (research R4)

The returned gas is mixed in on a dry gas basis:
G_drum = G_in + G_rec, Y_drum = (G_in Y_fresh + G_rec Y_out)/G_drum, and likewise the
enthalpy minus an optional duct loss Q = C (T_out − T_a)(1 − e^(−UA/C)). The dry gas
composition of the drum stays the fresh mix (the model holds one dry composition for the
whole drum), so O₂ at the drum inlet falls only through the added water vapour.

`heat_supplied` and `specific_energy` keep their definition (flue gas plus dilution air); the
energy saved by recirculating shows there.

## Pressure control (research R5)

The mixing chamber pressure is measured through a first-order transmitter lag (2 s default),
and a PI controller (anti-windup, smooth saturation) drives the damper with **reverse
action**: draft stronger than the set point (pressure below it) opens the damper. Manual
mode: a constant position or a series. Two extra states per dryer: the measured pressure and
the controller integral. Example tuning by SIMC on a damper step test on the twin
(`uv run python scripts/tune_controllers.py pressure`): gain 1.22·10⁻⁴ 1/Pa, integral time
1.8 s; the damper actuator is not modelled and stands in as τ_c ≥ 5 s.

In the coupled plant the drum inlet temperature loop (bypass and dilution air) sees the mixed
gas, so recirculation and dilution air act on the same temperature. Retune that loop with
recirculation on the real plant.

## Steady state (research R6)

With a recirculation the dryer outlet feeds back to the drum inlet measurement. The steady
start therefore settles the boiler house with the fresh gas only, then the dryer, then
polishes the whole plant by a damped Newton method with a sparse Jacobian; the joint march is
the fallback.

## Scenario keys

The `[recirculation]` section and its four sub-tables (`damper`, `exhaust_fan`,
`resistances.drum_path` and `.stack`, `controller`) are described in
[scenario-file-recirculation.md](../specs/004-dryer-exhaust-recirculation/contracts/scenario-file-recirculation.md).
It needs a dryer. Time series are allowed for `exhaust_fan.speed`, `controller.setpoint` and,
in manual mode, `controller.manual_output`.

## Results

With a recirculation, `results.csv` gains the columns of
[results-recirculation.md](../specs/004-dryer-exhaust-recirculation/contracts/results-recirculation.md):
- damper position and recirculation share;
- recirculated flow and temperature;
- mixing chamber pressure, its set point and the measured pressure;
- fan speed, volume flow and pressure rise;
- drum inlet humidity, O₂ and dew point;
- duct loss.

`exhaust_*` then describes the stack exhaust. The run record gains the `mixing_chamber_pressure`
controller and the `recirculation_loop` balance. The flags `controller_saturated` and
`setpoint_not_reached` appear in the results.

## Valid operating range and warnings

| Check | Rejected (physical) | Warned (validated) |
|---|---|---|
| `controller.setpoint` | outside −2000 … 0 Pa | outside −1000 … −20 Pa |
| `exhaust_fan.speed` | < 0 or > 2 × nominal | outside 30–110 % of nominal |
| `max_share` | ≤ 0 or ≥ 100 % | share above it in the results |
| `duct_heat_loss` | < 0 | > 10 kW/K |
| `pressure_sensor_time_constant` | ≤ 0 or > 600 s | outside 0.5–30 s |

Warnings during a run:
- `mixing_chamber_overpressure`: positive pressure, so flue gas would escape;
- `recirculation_backflow`: no driving pressure across the damper;
- `drum_inlet_condensation_risk`: drum inlet within `dew_point_margin` of its dew point;
- `exhaust_fan_curve`: operating point outside the given curve points;
- `recirculation_share`: share above `max_share`.

Expected accuracy: unknown until calibrated. The gas path has three calibration handles: the
resistance design points, the fan curve and the damper characteristic.

## Numbers from the examples (not plant data)

| | `dryer_recirculation` | `plant_recirculation` |
|---|---|---|
| mixing chamber | −200 Pa, damper 53 % | −200 Pa, damper 49 % |
| recirculation share | 31 % | 29 % |
| drum inlet | 809 → 729 K (fresh → mixed) | 540 °C held by the drum inlet loop |
| specific energy | – | 7.46 → 7.25 MJ/kg |

A 24 h coupled run takes about 1.4 × the time of the run without recirculation.
