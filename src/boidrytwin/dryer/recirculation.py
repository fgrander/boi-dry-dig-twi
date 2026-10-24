"""Exhaust recirculation loop of the dryer: pressure transmitter and damper controller.

Research R5 of feature 004. The mixing chamber pressure is measured through a first-order
transmitter lag; a PI controller (feature 002) with reverse action sets the recirculation
damper: pressure below the set point (draft too strong) opens the damper. Both are dryer
states, so the loop works the same in dryer-only and coupled runs (research R1).
"""

from __future__ import annotations
