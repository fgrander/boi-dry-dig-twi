# Contract: Command-Line Interface Additions

**Extends**: [001 cli](../../001-boiler-dryer-interface/contracts/cli.md)

No new commands. The existing commands accept boiler-house and coupled scenarios.

| Command | Boiler-house-only scenario | Coupled scenario |
|---|---|---|
| `validate` | validates all sections | validates all sections |
| `run` | writes `run_record.json`, `boiler_results.csv`, `final_state.json` | as feature 001 plus `boiler_results.csv`, `flue_gas_to_dryer.csv`, `dilution_air.csv` |
| `rerun` | as feature 001 | as feature 001 |
| `compare` | measured columns name boiler outputs | measured columns may name dryer and boiler outputs |

- **Run summary on stdout:** `balances passed` / `FAILED: <subsystem>.<quantity>`, plus
  controller saturation counts.
- **Exit codes:** unchanged (0 / 1 / 2 / 3). A plant balance failure gives 2.
- **New script:** `scripts/tune_controllers.py <scenario>` runs open-loop step tests on the
  twin, fits FOPDT models and prints SIMC settings for the three loops (research R8).
