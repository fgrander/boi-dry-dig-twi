"""Quasi-steady pressure and flow of the dryer gas path with exhaust recirculation.

Research R2/R3 of feature 004. The gas path is mixing chamber -> drum, cyclone and ducts ->
exhaust fan -> stack, with a return line from the fan's pressure side through the
recirculation damper back into the mixing chamber. Assumptions:

- pressures are relative to ambient (Pa) and small, so densities use ambient pressure;
- pressures and flows settle within milliseconds, far faster than the drum: they are
  algebraic in every evaluation (no mixing chamber volume);
- fan curve: a quadratic through 3 points at nominal speed, scaled by the fan laws and by
  density (Carolus 2013, ch. 2; Bleier 1998, ch. 4);
- resistances: constant loss coefficient, dp = dp_d (rho_d / rho) (m / m_d)^2 from one design
  point (Idelchik 2007, ch. 1);
- damper: relative flow coefficient over position from a monotone table (PCHIP), fully open
  design point (ASHRAE Handbook HVAC Systems and Equipment 2020, ch. 47).
"""

from __future__ import annotations
