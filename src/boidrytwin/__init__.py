"""Digital twin of a boiler house and wood chip rotary drum dryer.

Library API (contracts/cli.md)::

    from boidrytwin import load_scenario, run

    scenario = load_scenario("scenario.toml")  # raises ScenarioValidationError
    record = run(scenario, out_dir="runs")     # returns RunRecord
    record, report = compare(scenario, "measured.csv")  # returns ValidationReport too
"""

from boidrytwin.records import RunRecord, compare, run
from boidrytwin.scenario.loader import LoadedScenario, load_scenario

__all__ = ["LoadedScenario", "RunRecord", "compare", "load_scenario", "run"]
