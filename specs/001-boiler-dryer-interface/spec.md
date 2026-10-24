# Feature Specification: Boiler House to Dryer Interface and Standalone Dryer Model

**Feature Branch**: `001-boiler-dryer-interface`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "boiler house to dryer interface and standalone dryer model"

## Clarifications

### Session 2026-10-24

- Q: Which heat carriers must the interface support? → A: Hot flue gas only.
- Q: Which dryer type and product? → A: Rotary drum dryer for wood chips / biomass.
- Q: Steady-state or dynamic? → A: Dynamic (time-dependent) simulation.

## User Scenarios & Testing *(mandatory)*

The primary user is a **process engineer** who models the drying plant, runs scenarios
and checks the twin against the real plant. The boiler house model itself is out of scope
for this feature. This feature defines how hot flue gas is handed from a boiler house to a
directly heated rotary drum dryer, and delivers a dynamic drum dryer model that runs on its
own.

### User Story 1 - Describe the flue gas supply to the dryer (Priority: P1)

A process engineer describes the hot flue gas that the boiler house delivers to the dryer
over time: its mass flow, temperature, pressure and composition. Instead of a boiler house
model, the engineer provides these conditions directly as a boundary condition (constant
values or a time series). The system checks every value, with its unit, and rejects anything
physically impossible or incomplete with a clear explanation.

**Why this priority**: The interface is the contract that every later boiler house and dryer
model depends on. Without it, the dryer cannot be fed and the subsystems cannot be coupled.

**Independent Test**: Can be fully tested by entering valid and invalid flue gas descriptions
and checking that valid ones are accepted (converted to consistent units) and invalid ones are
rejected with messages naming the field and the reason.

**Acceptance Scenarios**:

1. **Given** a complete flue gas description with values in common engineering units
   (e.g. °C, mbar(g), t/h, vol-%), **When** the engineer submits it, **Then** it is accepted and
   every quantity is available in consistent SI units.
2. **Given** a flue gas description with a negative mass flow, a missing temperature or a
   composition whose fractions do not add up to 100 %, **When** the engineer submits it,
   **Then** it is rejected and the message names the offending field, the given value and the
   allowed range.
3. **Given** a flue gas time series with a gap, **When** it is submitted, **Then** the gap is
   reported explicitly and is not filled in silently.

---

### User Story 2 - Simulate the drum dryer over time (Priority: P1)

A process engineer runs the drum dryer model over a period of time with: a flue gas supply
boundary condition, an optional dilution (tempering) air flow, a wet wood chip / biomass feed
(amount, moisture, temperature), ambient conditions and the dryer's configuration, starting
from a defined initial state. The system computes, for every time step, the dried product
(amount, final moisture, temperature), the exhaust gas leaving the drum, the heat used for
drying and the specific energy use per unit of water evaporated.

**Why this priority**: The standalone dryer model is the first working part of the twin and
delivers value on its own: engineers can study how the dryer reacts to load and gas changes
without a boiler house model.

**Independent Test**: Can be fully tested by running reference scenarios with known results
(hand calculations, published cases or steady-state limits) and comparing outputs within
stated tolerances.

**Acceptance Scenarios**:

1. **Given** valid inputs and an initial state, **When** the engineer runs a simulation over a
   period, **Then** a time series is produced for product outlet moisture and temperature,
   exhaust gas flow, temperature and humidity, heat used and specific energy use.
2. **Given** constant inputs held long enough, **When** the simulation runs, **Then** the outputs
   settle to a steady state that matches the steady-state reference result within tolerance.
3. **Given** a step change in feed rate, feed moisture or flue gas temperature, **When** the
   simulation runs, **Then** the outputs change gradually with the dryer's thermal and material
   inertia, not instantly, and settle to the new steady state.
4. **Given** inputs that need more heat than the flue gas can deliver, **When** the simulation
   runs, **Then** it reports heat-limited operation and the resulting higher product moisture,
   rather than failing or using heat that is not available.
5. **Given** the same inputs, initial state and time settings run twice, **When** results are
   compared, **Then** they are identical.

---

### User Story 3 - Trust the results: balance and range checks (Priority: P2)

After every run the engineer sees whether the mass balance (dry solids, water, gas) and the
energy balance close over the run, accounting for what is stored in the dryer, and whether
any input lay outside the model's documented valid operating range at any time.

**Why this priority**: Balance and range checks are how the engineer knows a result can be
trusted. They are required by the project constitution, but the model is usable for
exploration before they are polished.

**Independent Test**: Can be tested by running scenarios inside and outside the valid range
and with deliberately inconsistent inputs, and checking the reported balances and warnings.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the engineer views its summary, **Then** the mass and
   energy balance residuals over the run (inputs − outputs − change in stored amount) are
   shown, with a pass/fail against the stated tolerance.
2. **Given** an input outside the documented valid range at some time (e.g. drum inlet gas
   temperature above the modelled range), **When** the simulation runs, **Then** the result is
   flagged as out of range, naming the input, the range and the time period affected.

---

### User Story 4 - Compare the dryer model with plant measurements (Priority: P3)

The engineer provides measured time series from the real dryer (inputs and measured outputs).
The system runs the model with the measured inputs and reports, per output, the deviation from
the measurements over time and whether it is within the acceptance tolerance.

**Why this priority**: Validation against the real plant is what makes the model a twin, but
it depends on measured data being available and on Stories 1 and 2 being complete.

**Independent Test**: Can be tested with a measured or synthetic dataset with known
deviations, checking that the report shows the right deviations and pass/fail results.

**Acceptance Scenarios**:

1. **Given** measured time series for a period of operation, **When** the engineer runs the
   comparison, **Then** a report shows, per output, predicted and measured values over time,
   deviation statistics and pass/fail.
2. **Given** a dataset where some measurements are missing or flagged as bad, **When** the
   comparison runs, **Then** those values are excluded and listed as excluded, not counted as
   passes or failures.

---

### Edge Cases

- Flue gas temperature at or below the product temperature, so no heat can be transferred:
  the model reports zero drying and the resulting outcome, without failing.
- Flue gas or drum inlet temperature above the model's valid range (wood chip ignition risk):
  flagged as out of range for the affected period; fire behaviour is not modelled.
- Flue gas flow drops to zero (boiler house trip): the drum cools down according to its
  thermal inertia and the product leaves wetter; the model keeps running.
- Zero product feed (drum running empty): the model runs and reports gas passing through with
  no evaporation.
- Feed already at or below the target moisture: the model reports little or no evaporation.
- Exhaust gas approaching its dew point: flagged as a condensation risk.
- Units missing on an input value: rejected; no unit is assumed.
- Time series with unordered or duplicate timestamps: rejected with the timestamps named.
- Requested simulation period not covered by the input time series: rejected, naming the
  uncovered period.

## Requirements *(mandatory)*

### Functional Requirements

**Flue gas supply interface**

- **FR-001**: The system MUST define a flue gas supply interface between a boiler house and a
  dryer carrying, at each point in time: flue gas mass flow, temperature, pressure and
  composition (at least O₂, CO₂, H₂O and N₂ fractions, with the remainder allowed as "other").
- **FR-002**: The system MUST derive the heat content delivered across the interface from the
  flue gas conditions, relative to a stated reference temperature.
- **FR-003**: Every quantity on the interface MUST carry an explicit unit. The system MUST
  accept common engineering units (including volume and mass fractions, wet and dry basis)
  and convert them to SI units consistently. Values without a unit MUST be rejected.
- **FR-004**: The system MUST reject physically invalid interface values (e.g. negative flow,
  absolute pressure at or below zero, composition fractions outside 0–100 % or not summing to
  100 % within tolerance) with a message naming the field, value and allowed range.
- **FR-005**: The interface MUST be identical whether the flue gas comes from a boundary
  condition or, in a later feature, from a boiler house model, so that swapping the source
  requires no change to the dryer model or its configuration.
- **FR-006**: Users MUST be able to provide the flue gas supply as a boundary condition, either
  as constant values or as a time series.

**Standalone rotary drum dryer model**

- **FR-007**: Users MUST be able to run a directly heated rotary drum dryer model for wood
  chips / biomass with: a flue gas supply (per FR-001); an optional dilution air flow mixed
  with the flue gas before the drum; a wet product feed (mass flow, moisture content,
  temperature); ambient conditions (temperature, relative humidity, pressure); and a dryer
  configuration (drum dimensions, rotation speed, residence time or its drivers, and
  product properties).
- **FR-008**: The dryer model MUST compute, for every time step: dry product mass flow,
  product outlet moisture and temperature, evaporated water, exhaust gas mass flow,
  temperature, humidity and composition, heat used for drying, heat losses to the
  surroundings, and specific energy use per kg of water evaporated.
- **FR-009**: The dryer model MUST be dynamic: it MUST simulate a user-defined period from a
  user-defined initial state (e.g. cold and empty, or a given operating state), and MUST
  represent the thermal inertia of the drum and the material hold-up and residence time of
  the product, so that outputs respond to input changes with realistic delay.
- **FR-010**: When constant inputs are held, the dynamic model MUST settle to a steady state
  consistent with the same model's steady-state energy and mass balances.
- **FR-011**: When the heat demanded exceeds what the gas can deliver, the model MUST use only
  the available heat, report heat-limited operation for the affected period and compute the
  resulting product moisture.
- **FR-012**: The dryer model MUST document its assumptions, valid operating range and expected
  accuracy, and MUST flag any period in which inputs or states fall outside that range,
  including drum inlet gas temperature and exhaust gas dew point margin.

**Checks, traceability and validation**

- **FR-013**: Every run MUST report the dry solids, water, gas and energy balance residuals over
  the run, accounting for the change in stored mass and energy in the dryer, each with
  pass/fail against a stated tolerance.
- **FR-014**: Every run MUST record its inputs, initial state, time settings, parameters, model
  version and a unique run identifier, so that rerunning with the same record gives identical
  results.
- **FR-015**: Missing, stale or bad input values MUST be marked explicitly and MUST NOT be
  replaced with silent defaults. A time series value is *stale* when it has not changed for
  longer than a configurable limit (default 15 min) for quantities that normally fluctuate
  (flows, temperatures).
- **FR-016**: Users MUST be able to compare the dryer model with measured time series and
  receive, per output, predicted and measured values over time, deviation statistics and
  pass/fail against the acceptance tolerance.
- **FR-017**: Every run MUST produce a machine-readable run summary and log entries covering
  simulated period, run duration, rejected or flagged inputs, balance residuals and range
  warnings.

### Key Entities *(include if feature involves data)*

- **Flue Gas Supply Interface**: The connection between a boiler house and a dryer. Carries a
  flue gas stream over time and the derived heat content. Has exactly one source (boundary
  condition now, boiler house model later) and one consumer (the dryer). Nothing returns to
  the boiler house.
- **Flue Gas Stream**: Mass flow, temperature, pressure and composition at a point in time,
  each with a unit.
- **Boundary Condition Source**: User-provided flue gas conditions, as constant values or a
  time series, standing in for a boiler house.
- **Dilution Air**: Optional ambient air mixed into the flue gas before the drum to temper its
  temperature.
- **Product Feed**: The wet wood chips / biomass entering the drum over time: mass flow,
  moisture content and temperature.
- **Ambient Conditions**: Temperature, relative humidity and pressure of the surroundings.
- **Dryer Configuration**: Drum design and operating parameters and product properties, with
  their valid ranges.
- **Dryer State**: The stored quantities inside the dryer at a point in time (e.g. product
  hold-up and its moisture, drum and gas temperatures); used as the initial state and
  tracked during the run.
- **Dryer Results**: The time series of outputs listed in FR-008, plus heat-limited,
  out-of-range and condensation-risk flags.
- **Run Record**: Run identifier, inputs, initial state, time settings, parameters, model
  version, results, balance residuals and warnings for one run.
- **Measured Time Series**: Measured plant inputs and outputs over time, each value with a
  quality flag; used as a validation dataset.
- **Validation Report**: Per output: predicted and measured values over time, deviation
  statistics, tolerance and pass/fail, plus excluded values.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A process engineer can set up and run a standalone dryer scenario from a written
  scenario description in under 15 minutes on first use, and in under 2 minutes once familiar.
- **SC-002**: For 100% of valid runs, the dry solids, water and gas balances close within 0.1%
  of the total input and the energy balance closes within 1% of the heat supplied, after
  accounting for stored amounts.
- **SC-003**: For a validation dataset (published case or plant measurements), product outlet
  moisture is within ±1 percentage point and exhaust gas temperature within ±5 K for at least
  90% of steady-operation time. *Dependency*: requires a literature case or plant data (see
  Assumptions); until available, it is verified with synthetic data only.
- **SC-004**: After a step change in an input, the outputs change gradually and settle to the
  new steady state; the settling time is within ±20% of a published or measured response time.
  *Dependency*: as SC-003 for the quantitative ±20% check.
- **SC-005**: 100% of invalid or unit-less interface inputs in the test catalogue are rejected,
  each with a message naming the field, value and reason.
- **SC-006**: Rerunning any recorded run on the same platform with the same library versions
  gives identical results in 100% of cases.
- **SC-007**: 24 hours of plant operation at 1-minute resolution are simulated in under
  1 minute.
- **SC-008**: Replacing the boundary-condition flue gas source with another source of the same
  interface requires no change to the dryer model or its configuration (verified by swapping
  sources in a test).

## Assumptions

- The plant has one directly heated rotary drum dryer fed by one flue gas connection from the
  boiler house in this feature; several dryers or connections are out of scope.
- The drum is single-pass with flue gas and product flowing in the same direction
  (co-current), the usual layout for wood chip drum dryers.
- The flue gas passes through the drum and leaves as exhaust; nothing returns to the boiler
  house. Exhaust gas recirculation and exhaust cleaning (cyclone, filter, stack) are out of
  scope; the model reports exhaust conditions at the drum outlet.
- The boiler house model, live connection to plant data, operator dashboards, control logic,
  emissions, fire and explosion behaviour, and model calibration or optimisation are out of
  scope and follow in later features.
- Users are process engineers comfortable with describing scenarios in structured files; no
  graphical user interface is needed in this feature.
- Measured plant data may not be available yet. Until it is, validation uses reference
  scenarios from hand calculations or published cases, and User Story 4 is tested with
  synthetic data.
- Wood chip / biomass properties (e.g. dry solids heat capacity, sorption behaviour, bulk
  density) are supplied as part of the dryer configuration, with documented defaults.
- Gas pressure in the drum is close to atmospheric (slight suction from the exhaust fan).
- Tolerances stated in the success criteria are initial targets and may be tightened once
  measured data is available.
- Quantitative checks of SC-003 and SC-004 against an independent reference need a published
  validation case or plant data. Steady-state checks that need no such reference (mass and
  energy balance consistency) are part of this feature.
