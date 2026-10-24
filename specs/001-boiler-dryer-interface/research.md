# Research: Flue Gas Interface and Dynamic Rotary Drum Dryer Model

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-10-24

This document resolves the open technical questions of the plan using a literature search
done on 2026-10-24. Each decision lists the rationale, the alternatives considered and the
sources.

**Verification status of sources.** Citations were checked by web search (publisher records,
Crossref, repository pages). Most full texts are paywalled and were **not** read; equation
forms of the classic correlations are taken from secondary literature. Entries marked
**UNVERIFIED** could not be confirmed. Before any coefficient from these sources is coded, it
MUST be checked against the original or a standard handbook (see [Open items](#open-items)).

---

## R1. Overall model structure

**Decision**: An axial **cells-in-series** model of the drum (default N = 20, configurable
10–40). Each cell holds a **two-phase solids** inventory (passive: in flights or bed; active:
airborne in the falling curtains), a gas volume and a **lumped drum shell node**. All balances
are written in flux (conservative) form so that mass and energy are conserved by
construction. States per cell:

| State | Meaning | Unit |
|---|---|---|
| `m_dp`, `m_da` | dry solids mass, passive / active phase | kg |
| `m_wp`, `m_wa` | water mass in solids, passive / active phase | kg |
| `T_s` | solids temperature (both phases) | K |
| `T_g` | gas temperature | K |
| `Y_g` | gas humidity (kg H₂O per kg dry gas) | kg/kg |
| `T_sh` | drum shell temperature | K |

8 states × 20 cells = 160 ODEs. Gas states are kept as ODEs with the real (small) gas
hold-up instead of being solved as algebraic equations; the stiffness this creates is
handled by an implicit solver (R7). This avoids a DAE solver and keeps the model one ODE
system.

**Rationale**: Cells in series is the most common structure in published dynamic rotary dryer
models (10 cells: Iguaz et al. 2003, Pérez-Correa et al. 1998; 36 cells fitted to an
industrial RTD: Duchesne et al. 1996). It is equivalent to an upwind method-of-lines
discretisation. N can be set physically from the measured residence time distribution,
N ≈ 1/σθ². The two-phase (active/passive) split follows the James Cook University
compartment models (Schneider et al. 2003; Sheehan et al. 2005; Britton et al. 2006). It
captures gas drag on airborne chips, which the literature identifies as the controlling
transport mechanism for wood particles (Kamke & Wilson 1985/1986). A lumped shell state is
the main source of slow warm-up and load-change dynamics, which most published models leave
out.

**Alternatives considered**:
- Distributed PDE with orthogonal collocation (Wang et al. 1993): oscillates at sharp
  moisture fronts and is harder to keep robust; no accuracy gain for a twin.
- A single mixed tank or pure plug flow: gets residence time distribution and dead time wrong.
- CFD-DEM (Sudbrock et al. 2016): far too slow; usable offline only, to derive hold-up.
- Separate solids temperatures per phase: doubles the thermal states for little gain;
  revisit if calibration demands it.
- Algebraic (quasi-steady) gas balances: needs a DAE solver or an inner nonlinear solve per
  cell; deferred unless profiling shows stiffness is a problem.

**Sources**: Iguaz et al. 2003 [D5]; Pérez-Correa et al. 1998 [D6]; Duchesne et al. 1996
[D4]; Wang et al. 1993 [D3]; Schneider et al. 2003 [T16]; Sheehan et al. 2005 [T17];
Britton et al. 2006 [T18]; Kamke & Wilson 1986 [W1]; Sudbrock et al. 2016 [W6].

---

## R2. Solids transport: residence time and hold-up

**Decision**: Two-phase **Matchett–Baker-type transport** inside each cell, following
Sheehan, Ajayi & Lee (2008):

- passive → active (flight unloading): `k2 · m_p`, with `k2` from flight geometry, drum speed
  and loading relative to the design load (Baker 1988; Ajayi & Sheehan 2012);
- active → passive (curtain return): `k3 · m_a`, with `k3 ≈ 1 / t_fall`;
- passive, cell i → i+1 (kilning / rolling): `k4 · m_p`;
- active, cell i → i+1 (co-current gas drag): `C_F · m_a · f(u_g, ρ_g, particle mass)`,
  using a **curtain-level** drag form (Baker 1992), not single-sphere drag.

Moisture is carried with the dry solids (water mass flows in the same proportion as dry mass
between phases and cells). Because chips lose mass as they dry, drag transport depends on
the state and speeds up towards the outlet.

Mean residence time and hold-up are **results** of the model, not inputs. At steady state
they MUST reproduce the trends of Friedman–Marshall and Saeman–Mitchell; those correlations
are kept as plausibility checks in the validation tests.

**Parameters to calibrate** (most to least sensitive): drag coefficient `C_F`; kilning
coefficient `k4`; flight capacity multiplier (chip cohesion, fouling); N from RTD.
**Data needed** from the plant: one tracer RTD at two gas flows, a hold-up measurement
(crash stop) or a drive-power proxy, and outlet moisture.

**Alternatives considered**:
- Friedman–Marshall or Saeman–Mitchell as the primary law (`outflow = m / τ_cell`): rejected.
  Their single linear drag term fails at the high co-current gas velocities of biomass
  dryers, and Cao & Langrish (1999) document large errors; Matchett–Baker fitted best (mean
  error ≈ −10 %). Kept as sanity checks.
- Sullivan (1927) and Perron & Bui (1990) kiln models: no flights and no gas drag; usable
  only for the kilning term.
- Kamke–Wilson particle trajectories: too heavy for a dynamic twin; used to shape the drag
  term.
- Axial dispersion PDE (Ajayi & Sheehan 2014): only for sections without flights, if the
  plant's drum has them.

**Note**: No peer-reviewed RTD study of a **flighted, co-current wood chip** drum dryer was
found. Colin et al. (2015, open access) shows near-plug flow of wood chips in a kiln without
flights, and that Saeman's equation needs a shape correction for chips (error 20 % → 5 %).

**Sources**: [T1]–[T13], [T16]–[T20], [W1], [W2], [W3].

---

## R3. Gas–solid heat and mass transfer

**Decision**: A mechanistic, **calibrated** heat transfer term for each cell:

`Q_gs = C_a · h_p · a_eff · (T_g − T_s)`

- `h_p` from the **Gnielinski** single-particle correlation (Ranz–Marshall as a check), using
  the chip equivalent-sphere diameter and the slip velocity (≈ fall velocity relative to gas);
- `a_eff = (6 / d_p) · m_a / ρ_p`: surface of the airborne solids, taken from the transport
  model of R2, plus a smaller bed-surface term for the passive phase;
- `C_a`: calibration multiplier, starting at 1 (expected range ≈ 0.3–3). It covers
  non-spherical chips, curtain shielding and lumped radiation.

Mass transfer uses the **Chilton–Colburn heat/mass transfer analogy** to get `k_y` from `h_p`,
so evaporation and heat transfer stay consistent (R4).

The published volumetric coefficients (Friedman & Marshall 1949, Ua ∝ G^0.67/D; McCormick
1962; Myklestad 1963, Ua ∝ G^0.8) are **dimensional, fitted to sand or ore in small drums**,
and differ by a factor of 3–5. They are used only as plausibility bounds in tests.

**Alternatives considered**:
- A single published Ua correlation: cannot respond to hold-up or loading changes; large
  scatter; not fitted to wood chips.
- Full curtain CFD: too expensive.
- An explicit gas radiation model (WSGG, Smith et al. 1982): at 300–700 °C with dilute flue
  gas, gas emissivity is ≈ 0.1–0.2. That gives ≈ 5–15 W/m²K acting only on wall and bed
  surfaces, a few percent overall, mostly in the first cells. It is absorbed into `C_a`. An
  optional gray-gas term can be added later if inlet temperatures near 700 °C give a poor fit.

**Parameters to calibrate**: `C_a` (against outlet moisture and outlet gas temperature);
optional gas-flow exponent n ∈ [0.67, 0.8].

**Sources**: [H1]–[H10], [H13]–[H16].

---

## R4. Drying kinetics and wood chip properties

**Decision**: A **two-period characteristic drying curve** (CDC) per cell and phase:

- **Constant-rate period** (X > X_cr): evaporation is limited by external transfer,
  `ṁ_evap = k_y · a_eff · (Y_s* − Y_g)`, where Y_s* is the saturation humidity at the
  solids surface temperature. The solids sit near the wet-bulb temperature.
- **Falling-rate period** (X ≤ X_cr): rate = constant-rate value × `f(Φ) = Φ^n`, with
  `Φ = (X − X_e) / (X_cr − X_e)`.
- **Equilibrium moisture X_e**: Hailwood–Horrobin isotherm from the USDA *Wood Handbook*
  (2021), ch. 4, Eq. 4-5, evaluated at gas humidity and solids temperature.
- The latent heat includes a **bound-water (sorption) term** below fibre saturation, from
  the Clausius–Clapeyron relation applied to the same isotherm, so the two stay consistent.

**Properties** (all from the USDA *Wood Handbook* (2021), ch. 4, open access):
- moisture content held **internally on a dry basis**, X = kg water / kg dry wood; reported
  on a **wet basis** w at inputs and outputs, as the bioenergy industry and ISO 18134 use.
  Conversion: X = w / (1 − w);
- dry wood heat capacity: Eq. 4-18a, `c_p0 = 0.1031 + 0.003867·T` (kJ/kg·K, T in K);
- moist wood heat capacity: Eq. 4-19/4-20 below fibre saturation (valid 280–420 K), rule of
  mixtures above it;
- fibre saturation point X_fsp = 0.30 (default, configurable);
- chip bulk and particle density: plant measurement (indicative 150–165 kg/m³ dry bulk).

**Valid range and extrapolation**: the EMC data behind Hailwood–Horrobin only reach about
130 °C. At flue gas temperatures X_e ≈ 0, so the error matters only near the drum outlet.
The model clips the isotherm, and FLAGS operation outside the data range (FR-012).

**Parameters to calibrate or measure**: critical moisture content X_cr (indication: drying
of pine chips showed no constant-rate period, with critical moisture above 0.42 wet basis,
Núñez-Retana et al. 2025); falling-rate exponent n; effective particle size distribution;
chip bulk and particle density.

**Alternatives considered**:
- Thin-layer models (Lewis, Page, Henderson–Pabis): purely empirical, valid only at their
  test conditions, no verified high-temperature wood chip parameters, and no clean link to
  the energy balance.
- Intraparticle diffusion PDE: uncertain diffusivity, needs particle geometry, too costly per
  cell. Usable offline to check n.
- Reaction engineering approach (REA; Chen & Xie 1997; Putranto et al. 2011, wood up to
  230 °C): a credible **fallback** if the CDC fits calibration data poorly.

**Sources**: [W7]–[W17].

---

## R5. Drum shell heat losses and thermal inertia

**Decision**: One lumped shell node per cell:

`m_sh·c_sh·dT_sh/dt = h_in·A_in·(T_g − T_sh) + h_ws·A_ws·(T_s − T_sh)
                     − A_out·[h_nc·(T_sh − T_amb) + ε·σ·(T_sh⁴ − T_amb⁴)]`

- `h_in`: forced convection gas → shell (pipe-flow correlation on the drum's free cross
  section);
- `h_ws`: shell ↔ solids contact; calibration prior ≈ 50–150 W/m²K (UNVERIFIED range);
- `h_nc`: external free convection from a horizontal cylinder (Churchill & Chu 1975), plus an
  optional wind term;
- `ε ≈ 0.8` for an oxidised or painted shell; insulation as a series resistance.

The shell mass includes the flights. Expected time constant: tens of minutes, which matters
for start-up and load changes. Validation target: total shell loss of a few percent of the
heat supplied (Sheehan 2006 measured ≈ 3.5 % of fuel on an industrial ore dryer), and shell
surface temperature if measured.

**Alternatives considered**: an adiabatic drum or a constant loss fraction. Both miss shell
inertia during transients and the temperature dependence of losses.

**Sources**: [H11], [H12], [H13].

---

## R6. Flue gas and water properties

**Decision**:
- **Gas thermodynamics**: in-house **NASA 7-coefficient polynomials**, two ranges split at
  1000 K, for N₂, O₂, CO₂, H₂O and Ar (Ar represents "other"). Coefficients taken from the
  GRI-Mech 3.0 thermodynamic data set as shipped with Cantera (`gri30.yaml`), source cited in
  the code. cp, h and s are evaluated vectorised across cells. Ideal-gas mixture rules.
- **Transport properties** (viscosity, conductivity, needed for Re, Pr, h): per-species
  correlations (Sutherland for N₂, O₂ and Ar; polynomial fits for CO₂ and H₂O, as in the VDI
  Heat Atlas) with the **Wilke** mixing rule. Target accuracy ≈ 3–5 %, well inside the
  uncertainty of the calibrated heat transfer.
- **Water**: in-house **IAPWS-IF97 Region 4** saturation pressure and its explicit inverse
  (saturation temperature, used for dew point); latent heat from the difference between
  NASA ideal-gas H₂O enthalpy and IF97 liquid enthalpy (or the Watson correlation).
- **Humidity**: `Y = m_H2O / m_dry gas` with the **actual dry-gas molar mass**. The air
  constant 0.622 MUST NOT be used, because the CO₂ content changes the molar mass.
  Partial pressure `p_w = p·Y / (Y + M_w/M_dry)`; dew point `T_dp = T_sat(p_w)`.
- **Test oracles** (test-only dependencies): Cantera for gas cp/h (target < 0.1 % deviation)
  and CoolProp for water saturation.

**Alternatives considered**:
- Cantera at runtime: excellent but per-call overhead inside the ODE right-hand side, and a
  heavy dependency. Used as a test oracle.
- thermo/chemicals: flexible but high per-call Python overhead.
- CoolProp HAPropsSI and psychrolib: moist air only, fixed composition; psychrolib is
  unmaintained since 2020.
- iapws (pip): GPL-3 licence and slow; not used.

**Sources**: [G1]–[G6].

---

## R7. Python numerical and software stack

**Decision** (all checked on PyPI on 2026-10-24):

| Purpose | Choice | Version (≥) | Licence | Note |
|---|---|---|---|---|
| Arrays | numpy | 2.x | BSD | vectorised right-hand side over cells |
| ODE solver | scipy `solve_ivp`, **BDF** (Radau fallback) | 1.18 | BSD | `jac_sparsity` banded pattern, fixed rtol/atol, `t_eval` at output steps, `max_step` ≤ boundary data interval |
| Units at the boundary | pint | 0.26 | BSD-3 | units stripped to SI floats before the core; never inside the right-hand side |
| Schemas and validation | pydantic v2 | 2.14 | MIT | frozen models for scenario, configuration and interface; physical-range validators |
| Time series I/O | pandas | 3.1 | BSD-3 | UTC `DatetimeIndex`, resampling; CSV in and out |
| Structured logging | structlog over stdlib logging | 26.1 | MIT/Apache-2.0 | JSON renderer by default, console renderer in development; bound run_id |
| Scenario files | TOML via stdlib `tomllib` | — | — | no extra dependency |
| CLI | stdlib `argparse` | — | — | no extra dependency |
| Tests | pytest, hypothesis (property tests for validation rules) | — | MIT/MPL-2.0 | `pytest.approx` with explicit tolerances |
| Test oracles | cantera 3.2, CoolProp 8.0 | — | BSD-3 / MIT | dev dependency group only |
| Quality | ruff, mypy (strict on `src/`) | — | MIT | CI gates |

**Performance**: with ~160 states and a vectorised right-hand side, 24 h of operation at
1-minute output should take seconds to tens of seconds (estimate, not measured). A benchmark
test against SC-007 (< 1 min) is planned early. Escalation path if too slow: numba for the
right-hand side, then CasADi for exact Jacobians.

**Determinism** (SC-006): fixed solver settings, no randomness in the model, results recorded
with library versions; identical results are guaranteed on the same platform and library
versions.

**Calibration (later feature)**: lmfit on top of `scipy.optimize.least_squares`.

**Alternatives considered**: scikits.odes/SUNDIALS (hard to install on Windows with uv);
Assimulo (stale on PyPI); CasADi (big architectural commitment, kept for later); JAX
(overkill); polars (no unit or index semantics needed here); unyt and astropy.units (smaller
ecosystem or heavy); typer/click (unneeded dependency for a small CLI).

**Sources**: [G7].

---

## R8. Subsystem interface design

**Decision**: The flue gas supply is a **typed interface** with one method, conceptually
`state_at(t) → FlueGasState`. Two implementations exist in this feature: constant and
time-series boundary conditions; a boiler house model implements the same interface in a
later feature. The dryer depends only on the interface, never on a concrete source (FR-005,
SC-008, constitution principle III). A `FlueGasState` carries mass flow, temperature,
pressure and composition (mole fractions, normalised, dry or wet basis converted at the
boundary) in SI units. Optional dilution air is a separate input of the dryer, not part of
the interface, because it belongs to the dryer, not to the boiler house.

**Time series handling**: piecewise-linear interpolation between samples. Gaps longer than a
configurable limit (default 5 min) are an error by default, or produce flagged periods when
the user explicitly allows them; no silent filling (FR-015).

**Alternatives considered**: passing raw arrays between subsystems (no validation, units
lost); a shared mutable plant state (violates "no subsystem reads another's internal state").

---

## R9. Validation and reference cases

**Decision**: Four levels of evidence, each as automated tests:

1. **Physics checks** (always runnable): balance closure (SC-002); adiabatic limits (a
   dryer with no losses and an infinite residence time approaches adiabatic saturation);
   zero-feed and no-heat edge cases; settling to a steady state that matches the model's own
   steady-state balance (FR-010).
2. **Hand-calculation steady-state cases**: a worked mass and energy balance for a typical
   wood chip drum (e.g. 10 t/h wet chips from 50 % to 15 % wet basis), prepared in
   `tests/validation/` with its derivation documented.
3. **Literature cases**:
   - Perry's *Chemical Engineers' Handbook*, 8th ed., Example 12-23 (co-current cascading
     rotary dryer sizing): steady-state balance and residence time check;
   - Kamke & Wilson (1985, 1986): wood particles in a commercial dryer, retention time by
     radioactive tracer, axial temperature and moisture profiles; their model errors (14 %
     retention time, 22 % outlet moisture) give a realistic accuracy benchmark;
   - Iguaz et al. (2003) and/or Ajayi & Sheehan (2015): qualitative and, if data can be
     digitised, quantitative response to a step in inlet gas temperature (SC-004).
4. **Plant data** (when available): measured time series from the user's dryer, with
   calibration of `C_F`, `k4`, `C_a` and X_cr on one period and validation on another.
   Until then, User Story 4 is tested with synthetic data generated by the model with known
   perturbations.

**Rationale**: No open, tabulated dynamic dataset for a wood chip drum dryer fired with
boiler flue gas was found. The literature cases require full texts (see Open items).

---

## Open items

These do not block the plan, but they block specific tasks and MUST be resolved before the
corresponding implementation step:

1. **Full texts needed** to verify correlation coefficients and digitise validation data:
   Kamke & Wilson 1985 and 1986; Baker 1988 and 1992; Matchett & Baker 1987; Sheehan et al.
   2005; Ajayi & Sheehan 2015; Perry's Example 12-23; Krokida et al. 2007 (Handbook of
   Industrial Drying, ch. 7). The user may be able to supply these through library access.
2. **Plant data** from the user's dryer: drum dimensions, slope, speed, flight type and
   count; typical flue gas and chip conditions; whether historian time series and any RTD or
   hold-up measurements exist.
3. **Chip properties**: bulk and particle density, particle size distribution, and ideally
   a drying curve measured at 100–250 °C to set X_cr and n.

---

## References

Verification: ✔ confirmed by publisher record, Crossref or repository; ◐ confirmed only via
secondary reference lists; ✖ UNVERIFIED. OA = open access.

### Solids transport [T]
- [T1] ◐ Sullivan, J.D., Maier, C.G., Ralston, O.C. (1927). *Passage of solid particles
  through rotary cylindrical kilns.* US Bureau of Mines Technical Paper 384.
- [T2] ◐ Friedman, S.J., Marshall, W.R. (1949). Studies in rotary drying. Part I: Holdup and
  dusting. *Chem. Eng. Prog.* 45(8), 482–493.
- [T3] ◐ Saeman, W.C., Mitchell, T.R. (1954). Analysis of rotary dryer and cooler
  performance. *Chem. Eng. Prog.* 50, 467–475.
- [T4] ◐ Matchett, A.J., Baker, C.G.J. (1987). Particle residence times in cascading rotary
  dryers. Part 1. *J. Separ. Proc. Technol.* 8, 11–17. (Part 2, 1988: ✖)
- [T5] ✔ Cao, W.F., Langrish, T.A.G. (1999). Comparison of residence time models for
  cascading rotary dryers. *Drying Technol.* 17(4–5), 825–836. https://www.osti.gov/biblio/355710
- [T6] ✔ Perron, J., Bui, R.T. (1990). Rotary cylinders: solid transport prediction by
  dimensional and rheological analysis. *Can. J. Chem. Eng.* 68(1), 61–68.
  doi:10.1002/cjce.5450680108
- [T7] ✖ Kelly, J.J., O'Donnell, P. (1977). Residence time model for rotary drums.
  *Trans. IChemE*.
- [T8] ✔ Thibault, J. et al. (2010). Modeling the mean
  residence time in a rotary dryer for various types of solids. *Drying Technol.* 28(10),
  1136–1141. doi:10.1080/07373937.2010.483045
- [T9] ◐ Baker, C.G.J. (1988). The design of flights in cascading rotary dryers. *Drying
  Technol.* 6(4), 631–653.
- [T10] ◐ Baker, C.G.J. (1992). Air–solids drag in cascading rotary dryers. *Drying Technol.*
  10(2), 365–393.
- [T11] ✖ Revol, D., Briens, C.L., Bernier, J.M. (2001). Design of flights in rotary dryers.
  *Powder Technol.* 121, 230–238.
- [T12] ◐ Sherritt, Caple, Behie, Mehrotra (1993). The movement of
  solids through flighted rotating drums. Part I. *Can. J. Chem. Eng.* 71, 337–346.
  (Sherritt MSc thesis 1991, OA: https://prism.ucalgary.ca/handle/1880/24602)
- [T13] ✔ Ajayi, O.O., Sheehan, M.E. (2012). Design loading of free flowing and cohesive
  solids in flighted rotary dryers. *Chem. Eng. Sci.* 73, 400–411.
  doi:10.1016/j.ces.2012.01.033
- [T14] ◐ Duchesne, C., Thibault, J., Bazin, C. (1996) — see [D4].
- [T15] ◐ Renaud, Thibault, Trusiak (2000; author order differs between sources). Solids transportation model of an
  industrial rotary dryer. *Drying Technol.* 18(4–5), 843–865.
- [T16] ✔ Schneider, P.A., Sheehan, M.E., Brown, S.T. (2003). Modelling the dynamics of solids
  transport in flighted rotary dryers. *Comput. Aided Chem. Eng.* 14, 911–916.
  doi:10.1016/S1570-7946(03)80233-X
- [T17] ✔ Sheehan, M.E., Britton, P.F., Schneider, P.A. (2005). A model for solids transport
  in flighted rotary dryers based on physical considerations. *Chem. Eng. Sci.* 60(15),
  4171–4182. doi:10.1016/j.ces.2005.02.055
- [T18] ✔ Britton, P.F., Sheehan, M.E., Schneider, P.A. (2006). A physical description of
  solids transport in flighted rotary dryers. *Powder Technol.* 165(3), 153–160.
  doi:10.1016/j.powtec.2006.04.006
- [T19] ✔ Sheehan, M.E., Ajayi, O.O., Lee, A. (2008). Modelling solids transport in an
  industrial flighted rotary dryer. ESCAPE-18. OA:
  https://skoge.folk.ntnu.no/prost/proceedings/escape18/Topic_4/Poster/FP_00127.doc
- [T20] ✔ Ajayi, O.O., Sheehan, M.E. (2014). Pseudophysical compartment modeling of an
  industrial rotary dryer with flighted and unflighted sections: solids transport.
  *Ind. Eng. Chem. Res.* 53, 15980–15989. doi:10.1021/ie502607m

### Heat transfer and shell [H]
- [H1] ◐ Friedman, S.J., Marshall, W.R. (1949). Studies in rotary drying. Part II: Heat and
  mass transfer. *Chem. Eng. Prog.* 45, 573–588.
- [H2] ◐ McCormick, P.Y. (1962). Gas velocity effects on heat transfer in direct heat rotary
  dryers. *Chem. Eng. Prog.* 58(6), 57–62.
- [H3] ✖ Myklestad, O. (1963). Heat and mass transfer in rotary dryers. *Chem. Eng. Prog.
  Symp. Ser.* 59(41), 129–137.
- [H4] ◐ Ranz, W.E., Marshall, W.R. (1952). Evaporation from drops. *Chem. Eng. Prog.* 48(3),
  141–146.
- [H5] ◐ Gnielinski, V. (1975). Berechnung mittlerer Wärme- und Stoffübergangskoeffizienten
  an laminar und turbulent überströmten Einzelkörpern. *Forsch. Ing.-Wes.* 41(5). Also in
  the *VDI Heat Atlas*, Springer.
- [H6] ✔ Wang, F.Y., Cameron, I.T., Litster, J.D., Douglas, P.L. (1993) — see [D3]; and
  Wang et al. (1995), *Drying Technol.* 13(3), 737–751. doi:10.1080/07373939508916981
- [H7] ✔ Sheehan et al. (2005) — see [T17].
- [H8] ✔ Ajayi, O.O., Sheehan, M.E. (2015) — see [D10].
- [H9] ✔ Le Guen, L., Piton, M., Hénaut, Q., Huchet, F., Richard, P. (2017). Heat convection
  and radiation in flighted rotary kilns: a minimal model. *Can. J. Chem. Eng.* 95, 100–110.
  doi:10.1002/cjce.22659. OA: arXiv:1612.05762
- [H10] ✔ Silva, M.G., Lira, T.S., Arruda, E.B., Murata, V.V., Barrozo, M.A.S. (2012).
  Modelling of fertilizer drying in a rotary dryer: parametric sensitivity analysis.
  *Braz. J. Chem. Eng.* 29(2). doi:10.1590/S0104-66322012000200016. OA.
- [H11] ✔ Sheehan, M.E. (2006). A systems and resistance analysis of heat loss through an
  industrial flighted rotary ore dryer. *Proc. IHTC-13*, Sydney.
  https://researchonline.jcu.edu.au/4286
- [H12] ✔ Churchill, S.W., Chu, H.H.S. (1975). Correlating equations for laminar and
  turbulent free convection from a horizontal cylinder. *Int. J. Heat Mass Transfer* 18(9),
  1049–1053. doi:10.1016/0017-9310(75)90222-7
- [H13] ◐ Smith, T.F., Shen, Z.F., Friedman, J.N. (1982). Evaluation of coefficients for the
  weighted sum of gray gases model. *J. Heat Transfer* 104, 602–608.
- [H14] ◐ Krokida, M., Marinos-Kouris, D., Mujumdar, A.S. (2007). Rotary drying. Ch. 7 in
  Mujumdar (ed.), *Handbook of Industrial Drying*, 3rd ed., CRC Press.
- [H15] ✔ Shene, C., Cubillos, F., Pérez, R., Álvarez, P. (1996). Modelling and simulation of
  a direct contact rotary dryer. *Drying Technol.* 14(10), 2419–2433.
  doi:10.1080/07373939608917214
- [H16] ✔ Berner, M.O., Scherer, V., Mönnigmann, M. (2019). Controllability analysis and
  optimal control of biomass drying with reduced order models. OA: arXiv:1911.04688

### Wood, biomass and drying kinetics [W]
- [W1] ✔ Kamke, F.A., Wilson, J.B. (1986). Computer simulation of a rotary dryer. Part I:
  Retention time. *AIChE J.* 32(2), 263–268. doi:10.1002/aic.690320213. Part II: Heat and
  mass transfer, 269–275. doi:10.1002/aic.690320214
- [W2] ◐ Kamke, F.A., Wilson, J.B. (1985). Analysis of a rotary dryer: drying of wood
  particles. *Forest Prod. J.* 35(9), 32–40. https://forestprod.org/?p=78751 (author
  attribution not shown on the page)
- [W3] ✔ Colin, B., Dirion, J.-L., Arlabosse, P., Salvador, S. (2015). Wood chips flow in a
  rotary kiln: experiments and modeling. *Chem. Eng. Res. Des.* 98, 179–187.
  doi:10.1016/j.cherd.2015.04.017. OA: https://hal-mines-albi.archives-ouvertes.fr/hal-01165159
- [W4] ✔ Xu, Q., Pang, S. (2008). Mathematical modeling of rotary drying of woody biomass.
  *Drying Technol.* 26(11), 1344–1350. doi:10.1080/07373930802331050
- [W5] ✔ Zabaniotou, A.A. (2000). Simulation of forestry biomass drying in a rotary dryer.
  *Drying Technol.* 18(7), 1415–1431. doi:10.1080/07373930008917785
- [W6] ✔ Sudbrock, F. et al. (2016). Coupled DEM–CFD simulation of drying wood chips in a
  rotary drum – baffle design and model reduction. *Fuel* 184, 896–904.
  doi:10.1016/j.fuel.2016.05.054
- [W7] ✔ Glass, S.V., Zelinka, S.L. (2021). Moisture relations and physical properties of
  wood. Ch. 4 in *Wood Handbook*, FPL-GTR-282, USDA Forest Products Laboratory. OA:
  https://research.fs.usda.gov/treesearch/62243
- [W8] ◐ TenWolde, A., McNatt, J.D., Krahn, L. (1988). *Thermal properties of wood and wood
  panel products for use in buildings.* DOE/USDA-21697/1.
- [W9] ◐ Hailwood, A.J., Horrobin, S. (1946). Absorption of water by polymers: analysis in
  terms of a simple model. *Trans. Faraday Soc.* 42B, 84–102.
- [W10] ◐ van Meel, D.A. (1958). Adiabatic convection batch drying with recirculation of air.
  *Chem. Eng. Sci.* 9(1), 36–44.
- [W11] ◐ Keey, R.B. (1972). *Drying: Principles and Practice.* Pergamon.
- [W12] ✔ Fagernäs, L., Brammer, J., Wilén, C., Lauer, M., Verhoeff, F. (2010). Drying of
  biomass for second generation synfuel production. *Biomass Bioenergy* 34(9), 1267–1277.
  doi:10.1016/j.biombioe.2010.04.005
- [W13] ✔ Chen, X.D., Xie, G.Z. (1997). Fingerprints of the drying behaviour of particulate
  or thin layer food materials established using a reaction engineering model. *Food Bioprod.
  Process.* 75, 213–222. doi:10.1205/096030897531612
- [W14] ✔ Putranto, A., Chen, X.D., Xiao, Z., Webley, P.A. (2011). Modeling of
  high-temperature treatment of wood using the reaction engineering approach (REA).
  *Bioresour. Technol.* 102(10), 6214–6220. doi:10.1016/j.biortech.2011.02.053
- [W15] ✔ Núñez-Retana, V.D. et al. (2025). Predictive models for the convective drying
  kinetics of Pinus spp. energy wood chips. *Appl. Sci.* 15, 10081.
  doi:10.3390/app151810081. OA.
- [W16] ✔ Kaplan, Ö., Çelik, C. (2018). An experimental research on woodchip drying using a
  screw conveyor dryer. *Fuel* 215, 468–473. doi:10.1016/j.fuel.2017.11.098
- [W17] ✔ Sridhar, D., Madhu, G.M. (2015). Drying kinetics and mathematical modeling of
  Casuarina equisetifolia wood chips at various temperatures. *Period. Polytech. Chem. Eng.*
  59(4), 288–295. doi:10.3311/PPch.7855. OA.

### Dynamic dryer models [D]
- [D1] ✔ Didriksen, H. (2002). Model based predictive control of a rotary dryer. *Chem. Eng.
  J.* 86(1–2), 53–60. doi:10.1016/S1385-8947(01)00272-8
- [D2] ◐ Douglas, P.L., Kwade, A., Lee, P.L., Mallick, S.K. (1993). Simulation of a rotary
  dryer for sugar crystalline. *Drying Technol.* 11(1), 129–155.
- [D3] ✔ Wang, F.Y., Cameron, I.T., Litster, J.D., Douglas, P.L. (1993). A distributed
  parameter approach to the dynamics of rotary drying processes. *Drying Technol.* 11(7),
  1641–1656. doi:10.1080/07373939308916922
- [D4] ✔ Duchesne, C., Thibault, J., Bazin, C. (1996). Modeling of the solids
  transportation within an industrial rotary dryer: a simple model. *Ind. Eng. Chem. Res.*
  35(7), 2334–2341. doi:10.1021/ie950625j. Also (1997) *Drying Technol.* 15(2), 477–510.
  doi:10.1080/07373939708917243
- [D5] ✔ Iguaz, A. et al. (2003). Mathematical
  modelling and simulation for the drying process of vegetable wholesale by-products in a
  rotary dryer. *J. Food Eng.* 59(2–3), 151–160. doi:10.1016/S0260-8774(02)00451-X
- [D6] ✔ Pérez-Correa, J.R., Cubillos, F. et al. (1998).
  Dynamic simulation and control of direct rotary dryers. *Food Control* 9(4), 195–203.
  doi:10.1016/S0956-7135(97)00077-7
- [D7] ◐ Shahhosseini, S., Cameron, I.T., Wang, F.Y. (2000). A simple dynamic model for solid
  transport in rotary dryers. *Drying Technol.* 18(4–5), 867–886.
- [D8] ✔ Yliniemi, L. (1999). *Advanced control of a rotary dryer.* PhD thesis, University of
  Oulu. OA: https://oulurepo.oulu.fi/handle/10024/36996
- [D9] ✔ Castaño, F., Rubio, F.R., Ortega, M.G. (2009). Modelado de secaderos rotatorios en
  isocorriente. *RIAI* 6(4), 32–43. doi:10.1016/S1697-7912(09)70106-2. OA.
- [D10] ✔ Ajayi, O.O., Sheehan, M.E. (2015). Pseudophysical compartment modeling of an
  industrial flighted rotary dryer with flighted and unflighted sections: energy.
  *Ind. Eng. Chem. Res.* 54(49), 12331–12341. doi:10.1021/acs.iecr.5b02833
- [D11] ✔ Bazin, C. et al. (1998). Data reconciliation on a rotary dryer. *Can. Metall. Q.*
  37, 333–342. doi:10.1016/S0008-4433(98)00026-3
- [D12] ◐ Green, D.W., Perry, R.H. (eds.) (2008). *Perry's Chemical Engineers' Handbook*, 8th
  ed., McGraw-Hill, Section 12 (Example 12-23).

### Properties and software [G]
- [G1] ✔ McBride, B.J., Zehe, M.J., Gordon, S. (2002). *NASA Glenn coefficients for
  calculating thermodynamic properties of individual species.* NASA/TP-2002-211556.
  https://ntrs.nasa.gov/citations/20020085330 (NASA-9 format; the NASA-7 data used here
  comes from GRI-Mech 3.0 / Cantera `gri30.yaml`)
- [G2] ◐ IAPWS (2007). Revised release on the IAPWS Industrial Formulation 1997 for the
  thermodynamic properties of water and steam (IAPWS-IF97).
- [G3] ◐ Wilke, C.R. (1950). A viscosity equation for gas mixtures. *J. Chem. Phys.* 18,
  517–519.
- [G4] ◐ VDI e.V. (ed.) (2010). *VDI Heat Atlas*, 2nd ed., Springer (property chapter D3).
- [G5] ✔ Cantera 3.2 (BSD-3), https://cantera.org — test oracle.
- [G6] ✔ CoolProp 8.0 (MIT), http://www.coolprop.org — test oracle.
- [G7] ✔ PyPI metadata for scipy, numpy, pint, pydantic, pandas, structlog, lmfit, numba,
  casadi, scikits.odes, assimulo, polars, unyt, psychrolib, iapws, thermo (checked
  2026-10-24).
