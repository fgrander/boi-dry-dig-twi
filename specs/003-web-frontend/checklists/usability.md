# Usability test: operator what-if run (SC-002)

**Target**: an operator who has never used the app completes a what-if run in under 5 minutes,
without help, in at least 4 of 5 trials.

**Status**: not run yet. This is a manual test with plant operators. The results below are to be
filled in.

## Set-up (by an engineer, before the trials)

1. `uv run boidrytwin serve`.
2. In the engineer view, create the what-if case "Fuel and oil demand" from `plant_reference`,
   releasing *Fuel moisture* 35–55 % (step allowed) and *Oil return temperature* 220–260 °C.
   Wait until its baseline is *ready*.
3. Open the start page in a new browser window for each participant.

## Task given to each participant (read aloud, no further help)

> "The fuel will be wetter today, about 52 % moisture. Use the app to find out whether the
> boiler house still keeps the oil at its set point, and how dry the product will be."

The time starts when the participant sees the start page. It stops when they state the
answer that is on the what-if result page (oil on set point yes/no, product moisture in %).

## Results

| Trial | Participant role | Time (min:s) | Completed without help | Answer correct | Notes |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

- [ ] At least 4 of 5 trials completed without help in under 5 minutes
- [ ] Observed problems recorded and turned into issues
