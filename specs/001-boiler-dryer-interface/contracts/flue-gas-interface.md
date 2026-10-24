# Contract: Flue Gas Supply Interface

**Covers**: FR-001 – FR-006, SC-005, SC-008 | **Entities**: [data-model.md §1](../data-model.md)

This is the contract between a heat source (boundary condition now, boiler house model later)
and the dryer. It is a Python library interface in package `boidrytwin.interface`.

## Public types

```python
class FlueGasSupply(Protocol):
    source_id: str

    def state_at(self, t: float) -> FlueGasState: ...
    """Return the flue gas state at simulation time t (seconds since scenario start)."""

    def covers(self, t_start: float, t_end: float) -> bool: ...
    """True if the source provides data for the whole period."""

    def conditions_at(self, t: float) -> FlueGasConditions: ...
    """Same data as state_at(t) as plain SI floats and a mole-fraction array, without
    building a pydantic model. Used inside the ODE right-hand side for speed; the data
    was validated when the source was built."""
```

`breakpoints() -> array` returns the times (s) where the supplied conditions change slope
(empty for a constant source); the simulator restarts the solver there instead of limiting
its step size.

`FlueGasConditions` is a named tuple `(mass_flow, temperature, pressure, x, quality)` with `x`
the wet-basis mole fractions in the order N₂, O₂, CO₂, H₂O, other (Ar).

`FlueGasState` and `GasComposition` are frozen pydantic models with the fields of the data
model, all in SI units.

## Guarantees of every implementation

1. `state_at` is **pure and deterministic**: the same t gives the same state.
2. Returned states are always **valid** per the rules in the data model; invalid data is
   rejected when the source is built, never during simulation.
3. Composition is on a **wet basis, mole fractions, summing to exactly 1**.
4. A time outside `covers(...)` raises `SupplyCoverageError` naming the requested time and
   the covered period.
5. Gaps are never filled silently: returned states inside an allowed gap carry
   `quality = "missing"`.

## Obligations of every consumer (the dryer)

1. The dryer reads flue gas **only** through `state_at`; it does not access source
   internals.
2. Before a run, the dryer calls `covers(t_start, t_end)` and rejects the scenario if it
   returns false.
3. The dryer records `source_id` in the run record.

## Validation errors (boundary)

Raised as `InterfaceValidationError` with a list of issues, each with:

| Field | Example |
|---|---|
| `field` | `flue_gas.composition.x_CO2` |
| `value` | `"1.2 vol%"` as given by the user |
| `reason` | `"composition sums to 0.93, expected 1 ± 0.005"` |
| `allowed` | `"0 ≤ x ≤ 1, sum = 1 ± 0.005"` |
| `location` | file and row/line where available |

Required rejections (test catalogue for SC-005):

| Case | Reason text contains |
|---|---|
| missing unit on any value | `unit missing` |
| incompatible unit (e.g. `kg` for temperature) | `incompatible unit` |
| negative mass flow | `must be ≥ 0` |
| absolute pressure ≤ 0 or outside 0.5–2 bar(a) | `out of range` |
| temperature outside 0–1200 °C | `out of range` |
| fraction < 0 or > 1 | `out of range` |
| fractions not summing to 1 ± 0.005 | `sums to` |
| dry basis given without water content | `water content required for dry basis` |
| time series with unordered or duplicate timestamps | `not strictly increasing` + timestamps |
| time series without timezone | `timezone required` |
| gap > max_gap and gaps not allowed | `gap` + start and end |

## Swap test (SC-008)

A contract test runs the same dryer scenario with (a) a `ConstantFlueGasSupply` and (b) a
`TimeSeriesFlueGasSupply` holding the same constant values, and asserts identical results
without any change to the dryer configuration. Any future `FlueGasSupply` implementation MUST
pass the shared contract test suite in `tests/contract/test_flue_gas_supply.py`.
