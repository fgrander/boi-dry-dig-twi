# Research: Dryer Exhaust Gas Recirculation

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Decisions for the open technical points of the plan. Each entry: decision, rationale,
alternatives considered.

## R1. Where the recirculation lives: in the dryer subsystem

**Decision**: The mixing chamber, the return duct, the recirculation damper, the exhaust fan,
the gas path resistances and the mixing chamber pressure controller are part of the **dryer
subsystem** (new module `src/boidrytwin/dryer/gas_path.py`; the loop states are added to the
dryer's state vector). The flue gas still enters through `FlueGasSupply` and the dilution air
through its `Signal`, unchanged.

**Rationale**: The recirculation takes gas from the dryer and returns it to the dryer; it must
work the same way in dryer-only runs (spec edge cases) and in coupled runs. Constitution III
requires each subsystem to run on its own; keeping the loop inside the dryer keeps the coupling
to the boiler house exactly as it is (flue gas and dilution air in), and the import boundary
test (`tests/contract/test_import_boundaries.py`) stays unchanged. The dryer package may import
`boidrytwin.control.pi`, which is shared, not a subsystem.

**Alternatives considered**:
- *Pressure loop in the plant coordinator, next to the drum inlet loop*: would not work in
  dryer-only runs and would make the plant read the dryer's outlet state (violates III).
- *A third subsystem "gas path"*: one more interface for a few algebraic equations; no
  benefit, since the gas path has no meaning without the dryer.

## R2. Pressure and flow: quasi-steady, solved in one unknown

**Decision**: The gas path pressures and flows are **quasi-steady** (algebraic in every
right-hand side evaluation). Relative to ambient, with the stack outlet at 0 Pa:

    p_fan_out = Δp_stack(V̇_stack)                       (stack resistance)
    p_mc      = p_fan_out − Δp_fan(V̇_fan, n) + Δp_path(V̇_drum)   (fan, drum + cyclone + ducts)
    G_drum    = G_in + G_rec                              (dry gas balance of the mixing chamber)
    G_rec     = φ(s) · C_d · sqrt(2 ρ_out (p_fan_out − p_mc)) / (1 + Y_out)   (damper)

with G_in the dry gas of flue gas plus dilution air, Y_out, T_out the drum outlet humidity and
temperature (last cell), s the damper position and φ(s) its characteristic. The stack carries
the fresh dry gas G_in plus the evaporated water, so `p_fan_out` does not depend on the
recirculation. What remains is one equation in G_rec ≥ 0:

    F(G_rec) = [Δp_fan − Δp_path](G_in + G_rec) − ((1 + Y_out) G_rec / (φ(s) C_d))² / (2 ρ_out) = 0

The first term falls with the flow (falling fan curve, rising resistance), the second rises, so
F is strictly decreasing and has at most one root. It is bracketed in [0, G_max] and solved by
`scipy.optimize.brentq` (xtol 1e-10 kg/s); if F(0) ≤ 0 (no pressure difference across the
damper), G_rec = 0 and the backflow warning applies.

**Rationale**: With a mixing chamber of some 10 m³ and the flow sensitivity of the fan and the
drum resistance (about 0.02 kg/(s·Pa)), the pressure time constant is a few milliseconds,
against seconds for the drum gas cells and minutes for the solids. A pressure state would add
a stiffness of 10³ to 10⁴ for no visible dynamics. A bracketed scalar solve per evaluation
costs about 10 cheap evaluations of the fan curve and keeps the right-hand side smooth in the
states (needed for BDF).

**Alternatives considered**:
- *Mixing chamber pressure as an ODE state*: physically fine, but very stiff (above). Rejected.
- *Solve all pressures and flows by Newton in several unknowns*: no benefit, since the
  structure reduces to one monotonic equation.

Spec impact: the assumption "only the mixing chamber has a gas volume (pressure dynamics
within seconds)" becomes "pressures and flows of the gas path are quasi-steady"; the mixing
chamber needs no volume. The spec is updated with this plan.

## R3. Characteristics: quadratic fan curve with fan laws, quadratic resistances, damper table

**Decision**:
- **Exhaust fan**: curve Δp₀(V̇) at nominal speed n₀, given as 3 points (V̇, Δp) and fitted
  exactly by a quadratic a₀ + a₁V̇ + a₂V̇²; at speed n by the fan laws
  Δp(V̇, n) = a₀(n/n₀)² + a₁(n/n₀)V̇ + a₂V̇², corrected for density by ρ/ρ_ref
  (Carolus, *Ventilatoren*, 2013, ch. 2; Bleier, *Fan Handbook*, 1998, ch. 4). The curve must
  fall over the given range (a₂ < 0, dΔp/dV̇ < 0 between the points); otherwise the scenario is
  rejected. Outside the points' flow range: range warning, curve extrapolated.
- **Resistances** (drum + cyclone + ducts, stack): Δp = Δp_d · (ρ_d/ρ) · (ṁ/ṁ_d)², from one
  design point (ṁ_d, Δp_d, T_d), i.e. a constant loss coefficient (Idelchik, *Handbook of
  Hydraulic Resistance*, 4th ed., 2007, ch. 1).
- **Recirculation damper**: ṁ = φ(s) · ṁ_open,d · sqrt(ρ Δp / (ρ_d Δp_d)) with the fully open
  design point (ṁ_open,d at Δp_d, T_d), and φ(s) a monotonic table of relative flow coefficients
  over position (default: inherent characteristic of a multi-blade opposed damper, roughly
  equal-percentage in the lower range; ASHRAE Handbook, *HVAC Systems and Equipment*, 2020,
  ch. 47 "Dampers"), interpolated by a monotone cubic (PCHIP) so it is smooth; φ(0) may be a
  small leakage > 0 (default 1 %).

**Rationale**: Plant data for fans and dampers come as data sheet points; the quadratic forms
are the textbook basis, need only 2 or 3 numbers each, and can later be calibrated against
measured pressures.

**Alternatives considered**: tabulated fan curve with splines (more data than the plant has);
a linear damper characteristic (unrealistic for dampers; available by giving a linear table).

## R4. Mixing at the drum inlet

**Decision**: `DrumDryerModel.inlet(t)` becomes `inlet(t, y)` (the last cell's state is
needed). The incoming gas G_in, Y_fresh, H_fresh is mixed as today; then the returned gas is
added on a dry gas basis:

    G_drum = G_in + G_rec
    Y_drum = (G_in Y_fresh + G_rec Y_out) / G_drum
    H_drum = (G_in H_fresh + G_rec H_out − Q_duct) / G_drum

with H_out the last cell's enthalpy per kg dry gas and Q_duct an optional duct heat loss
(a duct of conductance UA cooling the returned gas towards ambient,
Q_duct = C (T_out − T_ambient)(1 − e^(−UA/C)) with C its heat capacity flow; ≈ UA·ΔT for a
short duct, 0 without flow; UA = 0 by default). The dry gas composition of the drum stays the fresh
mix of flue gas and dilution air: the model holds one dry composition for the whole drum (no
composition state), and at steady state the returned dry gas has exactly that composition.
Oxygen at the drum inlet therefore changes only through the humidity (more water vapour, lower
O₂ mole fraction), which is the effect the spec asks for (lower O₂).

**Rationale**: Mass and energy are conserved by construction (the returned flux leaves the last
cell's balance and enters the first cell's); the model's quasi-steady gas composition
assumption (feature 001, research R2) is kept.

**Alternatives considered**: tracking the dry composition per cell (8 → 9+ states per cell) only
to follow a transient of a few seconds of gas residence time. Rejected.

## R5. Pressure measurement and controller

**Decision**: The mixing chamber pressure is measured through a first-order transmitter lag
(τ = 2 s default, state in the dryer vector), as the drum inlet temperature is in the plant
(`DRUM_SENSOR_TIME_CONSTANT`). A `PIController` (feature 002, back-calculation anti-windup,
smooth saturation) with **reverse action** drives the damper position s ∈ [0, 1]: pressure
below the set point (draft too strong) → error > 0 → the damper opens. Its integral is a
second extra state. Manual mode: the position follows the prescribed value (constant, series
or steps). The "set point not reached" flag uses `not_reached_mask` with the loop's band and
hold (defaults 50 Pa, 10 min).

Default tuning by SIMC on step tests on the twin (as in feature 002,
`scripts/tune_controllers.py`, extended with the pressure loop); expected order: gain
~ 0.002 1/Pa, integral time ~ 10 s. The tuned values go into the example scenarios.

**Rationale**: Without the lag the controller output would depend algebraically on the
pressure, which depends on the output (algebraic loop inside the right-hand side). The lag is
also physical (transmitters are damped).

**Alternatives considered**: a damper actuator travel-rate state instead of the lag (adds
a nonsmooth rate limit); solving the loop algebraically (nested root, no physical gain).

## R6. Steady-state start of coupled runs with recirculation

**Decision**: The two-stage steady state of feature 002 (boiler house and loops first, then
the dryer for that inlet) relies on "nothing upstream depends on the dryer". With a
recirculation the drum inlet temperature, which the boiler house loop measures, depends on the
dryer outlet. Coupled runs with a recirculation therefore add a **third stage**: starting from
the two-stage result (computed with the recirculation loop inside the dryer stage), march and
polish the **whole plant** together with the existing `_march_and_polish`. The upstream-only
shortcut in the solver (`with_dryer=False`, `n_upstream`) stays for runs without a
recirculation. `Plant.jac_sparsity` marks the dependence of the drum inlet measurement row on
the last dryer cell and the dryer's loop states.

**Rationale**: Reuses the tested steady-state machinery; the two-stage result is a close
starting point, so the joint polish converges in a few Newton steps.

**Alternatives considered**: a fixed-point iteration between the stages (slower near strong
coupling, needs its own stopping rule).

## R7. Balances

**Decision**: The **dryer subsystem boundary** encloses drum, mixing chamber, return duct and
fan: inflows are flue gas, dilution air and feed; outflows are the stack exhaust, product,
shell loss and duct loss. The returned gas is internal. A separate **recirculation loop check**
compares what leaves the last cell towards the return duct with what enters the mixing chamber
(mass and energy minus duct loss), within the existing tolerances. The plant balance and the
interface balance (flue gas) are unchanged.

**Rationale**: The existing dryer balance (`checks/balances.py`) keeps its meaning (what goes
in and out of the dryer as a whole); the loop check catches errors in the mixing code.

## R8. Results, without changing runs without recirculation

**Decision**: New result columns are written **only** when the scenario has a recirculation
(see [contracts/results-recirculation.md](contracts/results-recirculation.md)). `exhaust_*`
columns describe the stack exhaust; with a recirculation `exhaust_mass_flow` becomes the stack
flow, and the drum outlet flow gets its own column `drum_outlet_mass_flow`. Temperature,
humidity, composition and dew point of the stack exhaust equal those of the drum outlet gas
(adiabatic cyclone and fan). `heat_supplied` stays the heat of flue gas plus dilution air (the
returned heat is internal), so `specific_energy` keeps its meaning and shows the saving.

Without a recirculation the model takes exactly today's code path (`inlet` ignores `y`; no
extra states), so all existing results stay byte-identical (SC-001), checked by the existing
determinism and rerun tests plus a new test against stored results of every example.

## R9. Scenario file and web app

**Decision**:
- A new optional top-level section `[recirculation]` with sub-tables `damper`, `exhaust_fan`,
  `resistances`, `controller` (see [contracts/scenario-file-recirculation.md](contracts/scenario-file-recirculation.md)).
  It needs `[dryer.*]` sections (dryer-only or coupled run), else it is rejected (FR-010).
- New examples: `examples/dryer_recirculation.toml` (dryer-only, constant flue gas) and
  `examples/plant_recirculation.toml` (coupled, the reference plant with recirculation).
- Web app: the scenario form edits the fields line by line and needs no change for existing
  sections; a new action **"Add recirculation"** on the scenario page appends the default
  `[recirculation]` block (from a template) to a scenario that has a dryer and no recirculation,
  so SC-006 holds without editing files. Releases for operator what-if cases already work on any
  field key (e.g. `recirculation.controller.setpoint`, `recirculation.exhaust_fan.speed`).
- Drawings (`plant.svg`, `dryer.svg`): mixing chamber, return line from the fan's pressure side,
  damper with position, exhaust fan; drawn only when the run has the recirculation columns.
- Plots: a "Recirculation and draft" group. Formula page: mixing, damper, fan, resistance and
  pressure formulas with the sources above. German texts in `i18n.DE`.

## R10. Performance (SC-005)

**Decision**: Budget per right-hand side evaluation: one `brentq` (≈ 10 fan/resistance
evaluations, scalar arithmetic) and one extra mixing step. The Jacobian gains a dense column
block (every cell depends on the last cell through G_drum and the inlet), which the sparse
finite-difference Jacobian handles with a few more groups. The benchmark
`tests/performance/test_plant_benchmark.py` gets a recirculation case asserting ≤ 1.5 × the
reference case's time.
