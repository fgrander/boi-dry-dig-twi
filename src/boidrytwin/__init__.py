"""Digital twin of a boiler house and wood chip rotary drum dryer.

Library API (contracts/cli.md)::

    from boidrytwin import load_scenario, run

    scenario = load_scenario("scenario.toml")  # raises ScenarioValidationError
    record = run(scenario, out_dir="runs")     # returns RunRecord
"""

from boidrytwin.records import RunRecord, run
from boidrytwin.scenario.loader import LoadedScenario, load_scenario

__all__ = ["LoadedScenario", "RunRecord", "load_scenario", "run"]
