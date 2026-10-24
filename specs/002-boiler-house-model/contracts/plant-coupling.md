# Contract: Boiler House as a Flue Gas Source and Plant Coupling

**Covers**: FR-001, FR-009, FR-012 – FR-014, SC-003, SC-006 | **Entities**: [data-model.md](../data-model.md)

## Boiler house module (`boidrytwin.boiler_house`)

```python
class BoilerHouseModel:
    n_states: int
    def rhs(self, t: float, x: FloatArray, inputs: BoilerInputs) -> tuple[FloatArray, BoilerOutputs]: ...
    def jac_sparsity(self) -> csr_matrix: ...
    def initial_cold(self, t: float) -> FloatArray: ...
    def storage(self, x: FloatArray) -> dict[str, float]: ...      # mass, elements, energy
```

- `BoilerInputs` carries the fuel, air, oil and ambient signals at time t, plus the bypass
  position and dilution air flow commanded by the plant's drum inlet controller.
- `BoilerOutputs` carries `flue_gas_to_dryer: FlueGasConditions` (feature-001 type), the
  boundary flows for the balances, and the result columns.
- The module **must not import** `boidrytwin.dryer`. The dryer **must not import**
  `boidrytwin.boiler_house`. Only `boidrytwin.plant` imports both.

## Coupling (`boidrytwin.plant`)

1. The plant state is `[x_boiler, x_dryer]`. One BDF integration covers it, with a
   block-structured Jacobian pattern: the dryer's cell 0 depends on the boiler outlet states.
2. On every right-hand side evaluation the plant:
   1. evaluates the boiler house;
   2. sets `CoupledFlueGasSupply.current = outputs.flue_gas_to_dryer` and
      `ControlledSignal.current = dilution air`;
   3. evaluates the dryer, which reads them through its unchanged `FlueGasSupply` and
      `Signal` interfaces.
3. `CoupledFlueGasSupply` implements the full feature-001 `FlueGasSupply` protocol.
   `state_at(t)` validates and returns the current conditions, `covers` is always true, and
   `breakpoints` returns the boiler input breakpoints. It is only valid inside a plant
   evaluation.
4. The drum inlet temperature controller measures `dryer.inlet(t).temperature`, i.e. after
   mixing with the dilution air. That is a function of the interface values only.
5. Guarantees:
   - the flue gas leaving the boiler house equals the flue gas entering the dryer at every
     evaluation (interface balance residual is exactly 0);
   - the dryer configuration is not changed by coupling (SC-006);
   - the boiler outlet is validated against the interface ranges, with a RangeWarning, not an
     exception, if the gas leaves them during a run.

## Swap test (SC-006)

A contract test runs a coupled scenario and writes `flue_gas_to_dryer.csv` and
`dilution_air.csv`. It then runs the same dryer configuration standalone with
`flue_gas.source = "timeseries"` (those files) and a dilution-air time series. All dryer
results must agree within 0.1 %. Exact agreement is not expected, because the time series
sample the boiler output at 1-minute intervals and are linearly interpolated.
