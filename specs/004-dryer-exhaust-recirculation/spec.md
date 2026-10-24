# Feature Specification: Dryer Exhaust Gas Recirculation

**Feature Branch**: `004-dryer-exhaust-recirculation`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "Trocknerabluftrückführung (dryer exhaust gas recirculation): a
recirculation damper returns part of the drum dryer exhaust and mixes it with the flue gas from
the boiler house (after bypass and dilution air) before the drum inlet."

## Context

Feature 001 left exhaust gas recirculation out of scope: the gas passes the drum once and
leaves as exhaust. In the plant, a recirculation damper can return part of the exhaust to the
drum inlet. Mixing warm, humid exhaust into the hot flue gas lowers the drum inlet temperature
without fresh dilution air, so less heat leaves with the exhaust; it also lowers the oxygen
content at the drum inlet (less fire risk) and raises the humidity of the drying gas (slower
drying). In the plant the recirculation damper holds the negative pressure (draft) in the
mixing chamber in front of the drum: the exhaust fan behind the dryer draws the gas through the
drum, and the damper returns as much exhaust from the fan's pressure side as the mixing chamber
needs to stay on its pressure set point. This feature adds the recirculation, a simple pressure
and flow model of the gas path and the pressure control to the dryer model, to coupled plant
runs and to the web app.

## Clarifications

### Session 2026-10-24

- Q: How is the recirculation damper controlled (FR-007)? → A: The damper controls the negative
  pressure in the mixing chamber (not the drum inlet temperature, not a prescribed share).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Simulate the dryer with exhaust recirculation (Priority: P1)

A process engineer describes a scenario in which a share of the drum exhaust is returned and
mixed with the incoming gas before the drum inlet, runs it, and sees how drum inlet
temperature, humidity and oxygen, product moisture, evaporation, exhaust to the stack and
specific energy change against the same scenario without recirculation.

**Why this priority**: The recirculation is the feature; everything else builds on it.

**Independent Test**: Can be tested with a dryer-only scenario (flue gas from the boundary
condition) with recirculation off, and with a fixed recirculation share: results without
recirculation are identical to today's, results with recirculation match a hand calculation of
the mixing at steady state, and all balances close.

**Acceptance Scenarios**:

1. **Given** a scenario without recirculation settings, **When** it runs, **Then** the results
   are identical to the results before this feature (no change for existing scenarios).
2. **Given** a recirculation share of 0 %, **When** it runs, **Then** the results equal those
   without recirculation.
3. **Given** a fixed recirculation share, **When** the run reaches steady state, **Then** the
   drum inlet gas is the mass and energy weighted mix of the incoming gas and the returned
   exhaust, the drum inlet humidity is higher and the oxygen fraction lower than without
   recirculation, and the exhaust to the stack equals the drum outlet gas minus the returned
   part.
4. **Given** a recirculation share that changes as a step over time, **When** the run passes
   the step, **Then** drum inlet and exhaust respond without a jump in the balances.
5. **Given** any run with recirculation, **When** the checks run, **Then** the mass, water and
   energy balances of the dryer, of the recirculation loop and of the whole plant close within
   the existing tolerances.

---

### User Story 2 - Recirculation in the coupled plant and its control (Priority: P1)

An engineer runs the boiler house and the dryer as one plant with recirculation and sees how
the recirculation damper holds the mixing chamber pressure on its set point, while the existing
split-range controller holds the drum inlet temperature with bypass and fresh dilution air, and
how dilution air, bypass, stack exhaust and fuel demand change.

**Why this priority**: In the plant the recirculation exists to keep the draft in the mixing
chamber with the exhaust fan running; without it in the coupled plant the feature has little
value.

**Independent Test**: Coupled reference scenario with recirculation: the mixing chamber pressure
stays on its set point and the drum inlet temperature on its set point; a step in the exhaust
fan speed or in the flue gas flow is answered by the recirculation damper.

**Acceptance Scenarios**:

1. **Given** the coupled reference scenario with recirculation, **When** it runs, **Then** the
   mixing chamber pressure is held on its set point and the drum inlet temperature on its set
   point, and the result shows damper position, recirculation share, recirculated flow, mixing
   chamber pressure and fresh dilution air over time.
2. **Given** a disturbance (a step in the exhaust fan speed, the oil demand or the feed
   moisture), **When** the controllers react, **Then** the recirculation damper opens when the
   pressure falls below its set point (draft too strong) and closes when it rises above it, and
   all damper positions stay within their limits.
3. **Given** the pressure controller in manual mode, **When** the run starts, **Then** the
   recirculation damper follows the prescribed position and the mixing chamber pressure follows
   from the flows.
4. **Given** a draft the damper cannot hold (damper fully closed and the pressure still above the
   set point, or fully open and still below), **When** it happens, **Then** the run raises the
   "set point not reached" flag for the mixing chamber pressure.

---

### User Story 3 - See and change the recirculation in the web app (Priority: P2)

An engineer or operator sees the recirculation line, its damper and its values in the plant
and dryer drawings, and can set the recirculation in a scenario; an engineer can release it
for operator what-if cases.

**Why this priority**: Makes the feature usable without editing files, but the model works
without it.

**Independent Test**: A run with recirculation shows the line, damper position and
recirculated flow in the drawings; a run without it shows no recirculation line; the scenario
page accepts and validates the recirculation settings.

**Acceptance Scenarios**:

1. **Given** a run with recirculation, **When** the plant or dryer drawing is opened, **Then**
   the return line from the drum outlet to the drum inlet, the damper position and the
   recirculated flow and temperature are shown, in German and English.
2. **Given** a run without recirculation, **When** a drawing is opened, **Then** no
   recirculation line is drawn.
3. **Given** the scenario page, **When** an engineer enters a recirculation share outside its
   allowed range, **Then** the check reports the problem at that field.

---

### Edge Cases

- Recirculation share at its maximum: the drum gas flow grows; the model must stay within its
  valid range or report the range warning, never fail silently.
- Very humid exhaust: the mixed drum inlet gas must not be at or below its dew point; if it
  would be, the run reports a warning (condensation risk in the inlet duct).
- Recirculation with a cold, empty drum at start-up: the returned gas is the drum outlet gas
  of that moment; the run must start without special handling.
- Dryer-only scenarios with flue gas from a file or constant boundary condition: recirculation
  works the same way as in a coupled run.
- The recirculation and the fresh dilution air both lower the drum inlet temperature, and both
  enter the mixing chamber: the pressure controller and the temperature controller act on each
  other and must stay stable together with their default tuning (no sustained oscillation).
- Positive pressure in the mixing chamber (draft lost, e.g. fan too slow or stopped): the run
  warns, since hot gas would escape into the building.
- Exhaust fan at its flow or pressure limit: the run reports the range warning instead of
  extrapolating the fan curve.

## Requirements *(mandatory)*

### Functional Requirements

**Recirculation in the dryer**

- **FR-001**: A scenario MUST be able to describe an exhaust recirculation: the recirculation
  damper, its flow characteristic and limits, the exhaust fan and the gas path resistances
  (FR-016), and the damper position either set by the pressure controller (FR-007) or given as
  a constant, a time series or steps over time (manual).
- **FR-002**: The returned gas MUST have the composition, humidity and temperature of the gas
  leaving the drum at that moment and MUST be mixed, with mass and energy conserved, with the
  incoming gas (flue gas plus dilution air) in the mixing chamber before the drum inlet.
- **FR-003**: The returned duct MUST be treated as adiabatic with no hold-up, unless a heat
  loss is given in the scenario. *(Assumption; see Assumptions.)*
- **FR-004**: The exhaust to the stack MUST be the drum outlet gas minus the returned gas; all
  exhaust results (flow, temperature, humidity, composition, dew point) MUST refer to the
  stack exhaust, and the drum outlet gas MUST remain available as its own results.
- **FR-005**: Scenarios without recirculation settings MUST give exactly the results they gave
  before this feature.
- **FR-006**: The results MUST include the recirculation damper position, the recirculation
  share, the recirculated mass flow and temperature, the mixing chamber pressure, the exhaust fan
  flow and pressure rise, and the drum inlet humidity and oxygen fraction, over time.

**Control**

- **FR-007**: The recirculation damper MUST be driven by its own controller on the mixing
  chamber pressure: below the set point (draft too strong) it opens and returns more exhaust,
  above it it closes. The set point MUST be given in the scenario (also as steps over time).
  The existing split-range controller keeps holding the drum inlet temperature with bypass and
  fresh dilution air, unchanged.
- **FR-008**: The pressure controller's output MUST respect the damper limits (with anti-windup
  as the existing controllers), MUST be shown in the results, and MUST raise the existing "set
  point not reached" flag when the mixing chamber pressure cannot be held.
- **FR-009**: Manual mode MUST let the recirculation damper follow a prescribed position.

**Validity and checks**

- **FR-010**: The scenario check MUST reject a recirculation share outside 0 % to its maximum,
  a maximum of 100 % or more, and recirculation settings in a scenario without a dryer.
- **FR-011**: The run MUST warn when the mixed drum inlet gas is less than a stated margin
  above its dew point, when the mixing chamber pressure rises above ambient (positive pressure),
  and when the exhaust fan leaves its curve; the existing range warnings MUST apply to the
  larger drum gas flow.
- **FR-012**: The mass, water and energy balances MUST include the recirculation loop and
  MUST close within the existing tolerances for the dryer and the whole plant.

**Web app**

- **FR-013**: The plant and dryer drawings MUST show the recirculation line with its damper
  position, recirculated flow and temperature when the run has a recirculation, in German and
  English.
- **FR-014**: The scenario page MUST let engineers set the recirculation settings, checked by
  the model's own rules; an engineer MUST be able to release the recirculation share for
  operator what-if cases like other inputs.
- **FR-015**: The formula page MUST list the mixing, recirculation balance, pressure and flow
  formulas (fan curve, damper and resistance characteristics, mixing chamber pressure) with
  their sources.

**Gas path pressure and flow**

- **FR-016**: With a recirculation, the drum gas flow MUST follow from the draft: the exhaust fan
  (curve at nominal speed, speed given in the scenario as a constant, time series or steps) draws
  the gas from the mixing chamber through drum, cyclone and ducts (flow resistances); the mixing
  chamber pressure MUST follow from its mass balance (flue gas, dilution air and recirculated gas
  in, drum gas out); the recirculated flow MUST follow from the pressure difference between the
  fan outlet and the mixing chamber and the damper position.
- **FR-017**: The flue gas flow from the boiler house and the fresh dilution air flow set by the
  temperature controller MUST stay as today (they are not changed by the mixing chamber pressure).
- **FR-018**: Without a recirculation, no pressure model is active and the drum gas flow is the
  sum of the incoming flows as today (FR-005).

### Key Entities

- **Recirculation settings**: damper flow characteristic and position limits, optional duct heat
  loss (W/K or W), mode (pressure controlled or manual position), maximum share for the range
  warning.
- **Mixing chamber**: gas volume, pressure (relative to ambient), pressure set point.
- **Exhaust fan**: curve (pressure rise over volume flow) at nominal speed, speed over time,
  flow limits.
- **Gas path resistances**: pressure drop over flow for drum, cyclone and ducts.
- **Pressure controller**: set point, gains, limits, mode (as the existing controllers).
- **Recirculated gas**: mass flow, temperature, humidity and composition of the returned gas
  at each output time.
- **Drum inlet mix**: incoming gas (flue gas plus dilution air) and recirculated gas mixed;
  temperature, humidity, oxygen fraction, dew point.
- **Stack exhaust**: drum outlet gas minus the recirculated gas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing scenarios give identical results (no change in any result column)
  with this feature in place.
- **SC-002**: For a fixed recirculation share at steady state, the drum inlet temperature,
  humidity and oxygen fraction match a hand calculation of the mixing within 0.5 K, 1 % and
  1 % respectively.
- **SC-003**: Mass, water and energy balances with recirculation close within the existing
  tolerances (0.1 % mass, 1 % energy) in every example scenario.
- **SC-004**: In the coupled reference scenario with recirculation, after start-up the mixing
  chamber pressure stays within 50 Pa of its set point and the drum inlet within 5 K of its set
  point, also after a 10 % step in the exhaust fan speed (back within the band in under 5 min).
- **SC-005**: A coupled run with recirculation takes at most 1.5 times as long as the same run
  without it.
- **SC-006**: An engineer can set up and run a recirculation case from the web app in under
  5 minutes without editing files.

## Assumptions

- The gas path is drum → cyclone → exhaust fan → stack; the recirculation is taken on the fan's
  pressure side and returned into the mixing chamber in front of the drum, where flue gas
  (after bypass) and fresh dilution air also enter. Cyclone and fan are adiabatic, dust is not
  modelled, so the returned gas has the state of the drum outlet gas.
- Pressures are relative to ambient and small (a few hundred pascal), so gas densities use
  ambient pressure; the mixing chamber pressure set point defaults to −200 Pa.
- The fan curve and the resistances are quadratic characteristics fitted to two or three
  operating points (data sheet or plant); the fan speed scales the curve by the fan laws.
- The furnace pressure in the boiler house is not part of this feature: the flue gas flow comes
  from the boiler model, and the fresh dilution air flow from the temperature controller, as today.
- The return duct is adiabatic and has no gas hold-up or dead time, unless a duct heat loss is
  given; only the mixing chamber has a gas volume (pressure dynamics within seconds).
- The maximum recirculation share for the range warning defaults to 70 % of the drum outlet gas.
- The dew point margin for the warning defaults to 10 K.
- The existing drum inlet temperature set point and controller settings stay valid; the new
  pressure controller gets tuned defaults from step tests on the twin, as in feature 002.
- Exhaust composition and humidity results keep their names and now mean the stack exhaust,
  which equals the drum outlet gas when there is no recirculation (FR-005).
