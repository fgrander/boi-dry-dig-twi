# Feature Specification: Boiler House Model Supplying Flue Gas to the Dryer

**Feature Branch**: `002-boiler-house-model`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "boiler house model supplying flue gas to the dryer"

## Clarifications

### Session 2026-10-24

- Q: What produces the flue gas for the dryer? → A: A biomass furnace (hot gas generator)
  burning wood chips / bark; its flue gas is used directly by the dryer.
- Q: Does the boiler house deliver heat to other consumers? → A: Yes. Several thermal oil
  heat exchangers in the flue gas path heat thermal oil to 282 °C; the oil supplies energy to
  other manufacturing areas. The dryer gets the flue gas leaving the thermal oil heaters.
- Q: Open loop or with control loops? → A: With basic control loops.
- Q: Does all flue gas pass every thermal oil heater before the dryer, or can hot gas reach
  the dryer another way? → A: A damper-controlled bypass around some or all heaters joins
  the gas going to the dryer.
- Q: What moves the bypass damper? → A: Split range on the drum inlet temperature: the
  damper opens when the gas reaching the dryer is too cold, dilution air opens when it is
  too hot.
- Q: How does the thermal oil flow through the heaters? → A: One circuit, heaters in series,
  oil counter-current to the gas (enters at the last heater, leaves at the first).
- Q: What are the furnace's rated fuel power and the number of thermal oil heaters? → A:
  15 MW, 3 heaters (accepted suggestion; reference values for examples and defaults, not
  measured plant data).

## Context

Feature 001 delivered the flue gas supply interface and a dynamic drum dryer model that runs
on a boundary-condition flue gas source. This feature adds the **boiler house** as a second
source behind the same interface, so that the boiler house and the dryer run together as one
coupled plant. The dryer model and its configuration stay unchanged (feature 001 FR-005).

Flue gas path in this feature: **biomass furnace → thermal oil heaters (in series) → dryer**,
with a **damper-controlled bypass** around some or all heaters that joins the gas going to the
dryer (dilution air is mixed in before the drum, as in feature 001). The thermal oil heaters and the
dryer are both consumers of the furnace's heat; the oil supply to manufacturing is the
priority consumer, the dryer receives the remaining flue gas.

## User Scenarios & Testing *(mandatory)*

The primary user is a **process engineer** who models the plant, runs scenarios and checks
the twin against the real plant.

### User Story 1 - Simulate the boiler house on its own (Priority: P1)

A process engineer describes the boiler house: the fuel (amount, moisture, composition or a
default wood fuel), the combustion air, the furnace and the thermal oil heaters, the thermal
oil circuit (oil flow and return temperature from the manufacturing areas) and the controller
settings, starting from a defined initial state. The system computes over time the flue gas
leaving the boiler house towards the dryer (mass flow, temperature, pressure, composition),
the thermal oil outlet temperature, the heat delivered to the oil, the heat released by
combustion, the heat losses and the controller actions.

**Why this priority**: The boiler house is the missing source of the plant twin, and it also
supplies the manufacturing areas; on its own it lets engineers study fuel, air and oil
demand.

**Independent Test**: Can be fully tested with reference settings whose combustion and heat
exchange results are calculated by hand, and with step changes in oil demand that the
controllers must compensate.

**Acceptance Scenarios**:

1. **Given** a fuel with known composition and moisture and a set oxygen content, **When** the
   engineer runs the model in steady operation, **Then** the flue gas composition matches the
   complete-combustion hand calculation and the energy split between thermal oil, losses and
   outlet flue gas matches the hand-calculated energy balance within tolerance.
2. **Given** the thermal oil temperature controller in automatic, **When** the oil heat demand
   rises (higher oil flow or colder return), **Then** the fuel feed increases and the oil outlet
   temperature returns to 282 °C within the stated settling time, without sustained
   oscillation.
3. **Given** the oxygen controller in automatic, **When** the fuel feed changes, **Then** the
   combustion air follows so that the flue gas oxygen returns to its set point.
4. **Given** an oil heat demand above the furnace's maximum capacity, **When** the model runs,
   **Then** the fuel feed stays at its maximum, the oil outlet temperature falls below set
   point, and the period is flagged.
5. **Given** fuel so wet that stable combustion is not possible, **When** the model runs, **Then**
   the period is flagged and the run continues.
6. **Given** the same inputs run twice, **When** the results are compared, **Then** they are
   identical.

---

### User Story 2 - Run the boiler house and the dryer as one plant (Priority: P1)

A process engineer runs the boiler house and the dryer together: the flue gas leaving the
thermal oil heaters (mixed with any bypass gas) feeds the dryer through the flue gas supply
interface, and the drum inlet temperature controller holds the drum inlet temperature at its
set point with the bypass damper and the dilution air (split range). The engineer sees the dryer
results as before, plus the boiler house results, the controller actions and the balances for
each subsystem, the interface and the whole plant.

**Why this priority**: Coupling the subsystems is the purpose of the twin: it shows how the
oil demand of the manufacturing areas and the drying compete for the furnace's heat.

**Independent Test**: Can be tested by running a coupled scenario and checking that (a) the
dryer receives exactly the flue gas the boiler house delivers, (b) all balances close, and
(c) replacing the boiler house by a time series of its own outlet flue gas (and dilution air)
reproduces the dryer results.

**Acceptance Scenarios**:

1. **Given** a coupled scenario, **When** it runs, **Then** the flue gas leaving the boiler house
   equals the flue gas entering the dryer at every time step.
2. **Given** the drum inlet temperature controller in automatic, **When** the gas reaching the
   dryer is too hot, **Then** the dilution air opens (damper closed); **When** it is too cold,
   **Then** the bypass damper opens (dilution air closed); in both cases the drum inlet
   temperature returns to its set point.
3. **Given** the bypass damper opening, **When** less flue gas passes the heaters, **Then** the oil
   temperature controller raises the fuel feed so that the oil stays at 282 °C, i.e. the dryer's
   heat demand reaches the furnace through the oil loop.
4. **Given** a drop in oil demand, **When** the furnace turns down, **Then** the dryer receives
   less heat; if the drum inlet set point can no longer be reached (bypass fully open, no
   dilution air), this is flagged and the dryer reports heat-limited operation as in
   feature 001.
5. **Given** a coupled run, **When** the engineer views its summary, **Then** mass, element and
   energy balances are reported for the boiler house, the dryer, the interface and the whole
   plant, each with pass/fail.
6. **Given** the dryer configuration of an existing standalone scenario, **When** it is used in a
   coupled scenario, **Then** no change to the dryer configuration is needed.

---

### User Story 3 - Compare the boiler house with plant measurements (Priority: P3)

The engineer compares the boiler house with measured time series (e.g. flue gas oxygen and
temperature after the furnace and after the thermal oil heaters, oil outlet temperature, fuel
feed) in the same way as the dryer comparison of feature 001.

**Why this priority**: Validation against the plant matters, but depends on data and on
Stories 1 and 2.

**Independent Test**: Can be tested with synthetic measurements with known deviations.

**Acceptance Scenarios**:

1. **Given** measured boiler house time series, **When** the engineer runs the comparison,
   **Then** per-output deviation statistics and pass/fail are reported, with missing or bad
   values excluded and listed.

---

### Edge Cases

- Fuel feed stops (fuel trip): the furnace and the heaters cool with their thermal inertia,
  the oil outlet temperature falls (flagged), and the dryer keeps running on what it receives.
- Oil demand above furnace capacity: fuel feed at its maximum, oil below set point (flagged).
- Oil demand near zero: the furnace runs at its minimum load (or the controller would ask for
  less than the minimum: flagged); the dryer then gets little heat.
- Oil flow stops while the furnace is hot: the oil in the heaters overheats; the maximum oil
  film or bulk temperature is exceeded and flagged (oil degradation risk).
- Excess air too low for complete combustion: flagged as outside the valid range; incomplete
  combustion (CO, unburnt fuel) is not modelled.
- Fuel moisture so high that the combustion temperature falls below the stable range: flagged.
- Drum inlet set point not reachable: the gas is colder than the set point with the bypass
  fully open and no dilution air (flagged), or the dilution air would exceed its maximum
  (flagged).
- Bypass damper fully open while oil demand is high: less flue gas passes the heaters, so the
  oil may fall below its set point (flagged); the fuel controller compensates within the
  furnace's capacity.
- Controller output at a limit for a long time: integral wind-up is prevented, and the
  saturation is reported.
- Fuel composition not summing to 100 % (dry basis) or ash above a plausible limit: rejected.
- Combustion air given both as a fixed amount and as an oxygen controller in automatic:
  rejected as ambiguous.
- Flue gas leaving the boiler house outside the range the dryer interface accepts: rejected
  or flagged before it reaches the dryer.

## Requirements *(mandatory)*

### Functional Requirements

**Furnace and combustion**

- **FR-001**: The system MUST provide a boiler house model that supplies flue gas through the
  existing flue gas supply interface, so that the dryer can use it without change.
- **FR-002**: Users MUST be able to describe the fuel by moisture content (wet basis),
  temperature and composition (dry-basis mass fractions of C, H, O, N, S and ash), or by
  choosing a documented default composition for wood chips and bark. A lower heating value
  MAY be given; otherwise it MUST be derived from the composition with a documented
  correlation.
- **FR-003**: The combustion air temperature and humidity MUST be inputs; its amount MUST come
  either from the oxygen controller (FR-009) or from a prescribed mass flow / excess air ratio
  when that controller is in manual.
- **FR-004**: The model MUST compute the furnace flue gas composition (N₂, O₂, CO₂, H₂O, with
  SO₂ and argon reported as "other") and mass flow for complete combustion.

**Thermal oil heaters and oil circuit**

- **FR-005**: The model MUST include several thermal oil heaters in series in the flue gas
  path between the furnace and the dryer (number and design parameters configurable). Each
  transfers heat from the flue gas to the thermal oil, with heat transfer depending on flue
  gas and oil conditions.
- **FR-005a**: The model MUST include a flue gas bypass with a damper around a configurable
  range of heaters (from a configurable heater to the end of the heater train). The damper
  position (0 = closed, 1 = fully open) sets the share of flue gas that bypasses those
  heaters; bypassed and heater gas are mixed before the dryer, conserving mass and energy.
- **FR-006**: The thermal oil circuit MUST take the oil flow and the oil return temperature from
  the manufacturing areas as inputs (constant or time series) and compute the oil outlet
  temperature and the heat delivered to the oil. The oil flows in one circuit through all
  heaters in series, counter-current to the flue gas: it enters the last heater (coolest gas)
  and leaves the first heater (hottest gas) towards the consumers. The model MUST report the
  oil temperature leaving each heater. The thermal oil properties MUST be those of a
  configurable oil, with a documented default.
- **FR-007**: The model MUST compute the flue gas going to the dryer (heater outlet gas mixed
  with bypass gas) from the energy balance: heat released by combustion minus heat delivered
  to the oil, minus heat losses of furnace, heaters and bypass duct, minus energy stored.

**Dynamics and control**

- **FR-008**: The model MUST be dynamic: it MUST represent the thermal inertia of the furnace
  (e.g. refractory) and of the heaters and the oil they contain, so that flue gas and oil
  respond to changes with realistic delay, and MUST settle to a steady state consistent with its
  own balances.
- **FR-009**: The model MUST include these control loops, each with a set point, controller
  settings, output limits and a manual mode with a prescribed output:
  1. fuel feed controlling the **thermal oil outlet temperature** (default set point 282 °C);
  2. combustion air controlling the **flue gas oxygen content** after the furnace;
  3. **drum inlet gas temperature** of the dryer (coupled runs), in split range: below the set
     point the controller first opens the bypass damper; above it, with the damper closed, it
     opens the dilution air. Both actuators are never open against each other.
- **FR-010**: Controllers MUST prevent integral wind-up at their output limits and MUST report
  periods in which their output is saturated or their set point is not reached.

**Valid range**

- **FR-011**: The model MUST document its assumptions, valid operating range and expected
  accuracy, and MUST flag periods outside that range, including excess air below the
  complete-combustion limit, combustion temperature below the stable-combustion limit, fuel
  moisture above the modelled range, furnace load outside its minimum-maximum range (rated
  fuel power configurable, reference 15 MW), and oil temperature above its maximum
  permissible temperature.

**Coupled plant**

- **FR-012**: Users MUST be able to run a coupled scenario in which the boiler house supplies
  the dryer, using the dryer configuration of feature 001 unchanged; the bypass damper and the
  dilution air of the dryer are then set by the drum inlet temperature controller (or
  prescribed, in manual).
- **FR-013**: A coupled run MUST report mass and energy balances, and element balances for the
  combustion (C, H, O, N), for the boiler house, the thermal oil circuit, the dryer, the flue
  gas interface and the whole plant, each with pass/fail against a stated tolerance.
- **FR-014**: A coupled run MUST record the boiler house outlet flue gas and the dilution air as
  time series that can be used as boundary conditions for a standalone dryer run.

**Inputs, traceability, comparison**

- **FR-015**: All boiler house inputs MUST be validated at the boundary with units, as in
  feature 001; invalid inputs MUST be rejected with field, value, reason and allowed range.
- **FR-016**: Every run MUST be recorded and reproducible as in feature 001 (run record, rerun),
  including controller settings and states.
- **FR-017**: Users MUST be able to compare boiler house outputs with measured time series as
  in feature 001.

### Key Entities *(include if feature involves data)*

- **Fuel**: moisture, temperature, dry-basis composition (C, H, O, N, S, ash), optional lower
  heating value; the feed rate comes from the oil temperature controller (or is prescribed).
- **Combustion Air**: temperature, humidity; amount from the oxygen controller (or prescribed).
- **Furnace**: design parameters (thermal mass, heat losses, load range).
- **Thermal Oil Heater**: one of several heat exchangers in series in the flue gas path; design
  parameters (heat transfer characteristics, oil and metal inventory, losses).
- **Bypass Damper**: the heaters it bypasses, its position (share of flue gas bypassed),
  its flow characteristic and position limits.
- **Thermal Oil Circuit**: oil type, oil flow and return temperature from the consumers, oil
  outlet temperature, maximum permissible oil temperature.
- **Controller**: controlled quantity, set point, settings, output limits, mode
  (automatic/manual), internal state.
- **Boiler House State**: stored energy and inventories (furnace, heaters, oil) and controller
  states at a point in time; initial and final state of a run.
- **Boiler House Results**: time series of outlet flue gas (as the interface state), furnace
  flue gas, oil outlet temperature, heat released, heat to oil, losses, controller outputs,
  flags.
- **Plant Balance Report**: balances per subsystem, at the interface and for the whole plant.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the reference fuel and air settings, the furnace flue gas composition is
  within 0.1 percentage points (volume) of the complete-combustion hand calculation and the
  flue gas mass flow within 0.1 %.
- **SC-002**: In steady operation, the heat delivered to the oil and the flue gas temperature
  after the heaters match the hand-calculated energy balance within 1 % and 5 K.
- **SC-003**: For 100 % of valid runs, element (C, H, O, N) and mass balances close within 0.1 %
  and energy balances within 1 % for each subsystem, the interface and the whole plant.
- **SC-004**: With the oil temperature controller in automatic and demand within the furnace's
  capacity, the oil outlet temperature stays within ±0.5 K of its set point in steady operation
  and returns within ±2 K within 30 minutes after a 20 % step in oil heat demand, with an
  overshoot of no more than 5 K.
- **SC-005**: With the drum inlet temperature controller in automatic and the set point
  reachable, the drum inlet temperature stays within ±5 K of its set point in steady operation.
- **SC-006**: Replacing the boiler house in a coupled run by time series of its own outlet flue
  gas and dilution air reproduces the dryer results within 0.1 %, with no change to the dryer
  configuration.
- **SC-007**: A coupled 24-hour run at 1-minute resolution completes in under 2 minutes.
- **SC-008**: With measured data, flue gas oxygen is within ±0.5 percentage points, flue gas
  temperatures within ±10 K and oil outlet temperature within ±2 K for at least 90 % of
  steady-operation time. *Dependency*: requires plant data; until then verified with synthetic
  data only.

## Assumptions

- One biomass furnace supplies one dryer. The flue gas passes the thermal oil heaters in
  series or, through the damper-controlled bypass, around some or all of them; both streams
  are mixed before the dryer. Damper leakage and pressure-driven flow split are not modelled
  (the damper position sets the bypass share directly).
- Control structure: the fuel feed serves the oil outlet temperature; the dryer's inlet
  temperature is held with the bypass damper and dilution air (split range). The dryer's heat
  demand reaches the fuel feed only indirectly: opening the bypass takes heat from the oil,
  which the oil controller makes up with more fuel.
- Controllers are of PI type; their settings are inputs with documented defaults. Tuning
  methods, cascade control and advanced control are out of scope.
- The manufacturing areas are represented only by the oil flow and return temperature they
  impose; the oil network, pumps and expansion vessel are not modelled.
- Combustion is complete (no CO or unburnt fuel); its limits are flagged, not modelled.
- Wood chips and bark are the default fuels, with documented default compositions that users
  can override.
- Fuel feeding, ash handling, flue gas cleaning, fans, pressure losses and emissions are out of
  scope; the boiler house outlet pressure is an input.
- Feeding the dried chips back as fuel (a closed fuel loop) is out of scope for this feature.
- Reference plant for examples and defaults: a biomass furnace of 15 MW rated fuel power
  (lower heating value basis) with 3 thermal oil heaters in series (one radiant, two
  convective), feeding the drum dryer of feature 001. These are reference values, not
  measured data of the user's plant; all are configurable.
- Plant measurements may not be available yet; validation then uses hand calculations and
  synthetic data.
