# Research: Boiler House Model Supplying Flue Gas to the Dryer

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-10-24

Decisions for feature 002, based on a literature search on 2026-10-24 (five topics in
parallel). Feature 001's decisions ([../001-boiler-dryer-interface/research.md](../001-boiler-dryer-interface/research.md))
still apply: the stack, NASA-7 gas properties, IAPWS-IF97 water, units at the boundary only,
enthalpy-based conservative balances, BDF with banded Jacobian, and run records.

**Verification status.** Citations were checked by DOI (Crossref) or by reading open PDFs.
Values marked **VERIFY** were not checked against a primary text, or are typical values
rather than measured ones. They are implemented as cited, configurable defaults and listed
in [Open items](#open-items).

---

## R1. Coupling architecture: one plant ODE, subsystems behind interfaces

**Decision**: **Monolithic integration** of all subsystems in one ODE system, with each
subsystem in its own module:

- `BoilerHouseModel` (new) has its own state vector, `rhs(t, x_b, inputs) → (dx_b, outputs)`,
  and exposes its outlet flue gas as `FlueGasConditions`.
- `DrumDryerModel` (feature 001) is **unchanged**. It gets its flue gas from a
  `FlueGasSupply` and its dilution air from an input signal.
- A `Plant` coordinator assembles the global state. On every right-hand side evaluation it
  first evaluates the boiler house. It hands the outlet flue gas to the dryer through a
  `CoupledFlueGasSupply`, an implementation of the feature-001 `FlueGasSupply` interface
  whose conditions are set by the coordinator. It also hands over the controller-set dilution
  air through a `ControlledSignal`. Then it evaluates the dryer. There is no algebraic loop,
  because the boiler outlet depends only on boiler states and controller states.
- The drum inlet temperature controller measures the mixed drum inlet temperature through
  the dryer's public `inlet()` method. That method is a function of the supplied flue gas and
  the dilution air; nothing reads the dryer's internal state.

**Rationale**:
- Co-simulation (FMI) holds the exchanged values between communication points. That creates
  or destroys energy at the coupling (Sadjina et al. 2017) and needs iteration for feedback
  loops.
- In a monolithic integration, the flows passed between subsystems are evaluated at the same
  instant on both sides. The interface energy balance is then exact to solver tolerance, with
  one error control and one Jacobian.
- The module separation required by constitution principle III is kept: the dryer still only
  sees a `FlueGasSupply`.

**Alternatives considered**:
- FMI-style co-simulation: rejected for now. It remains an optional wrapper for later, and
  would then need energy-residual monitoring.
- Running the boiler house first and feeding its outlet time series to the dryer: rejected.
  The drum inlet controller acts on the bypass, which changes the boiler house and the oil,
  so the two cannot be run one after the other.

**Sources**: FMI 3.0.1 (fmi-standard.org); Sadjina, S. et al. (2017), *Eng. Comput.* 33(3),
607–620, doi:10.1007/s00366-016-0492-8 (arXiv:1602.06434).

---

## R2. Fuel, heating value and complete-combustion stoichiometry

**Decision**:
- **Default fuels** (dry-basis wt%; O by difference; from VTT Technology 272, Tables 4.3 and
  4.7):

  | Fuel | C | H | N | S | ash | O |
  |---|---|---|---|---|---|---|
  | `wood_chips` (forest residue chips) | 51.3 | 6.1 | 0.4 | 0.02 | 1.3 | 40.88 |
  | `bark` (spruce) | 49.9 | 5.9 | 0.4 | 0.03 | 2.5 | 41.27 |

  The composition is a user input. O is renormalised by difference, and a sum other than
  100 % ± 0.5 % is rejected.
- **Heating value**:
  - Use the measured HHV_d if given. Otherwise use **Channiwala & Parikh (2002)**:
    HHV_d [MJ/kg] = 0.3491 C + 1.1783 H + 0.1005 S − 0.1034 O − 0.0151 N − 0.0211 A
    (wt% dry).
  - LHV_d = HHV_d − 0.2122 H − 0.0008 (O + N) (ISO 18125 form).
  - LHV_ar = LHV_d (1 − M/100) − 0.02443 M (ISO 18125, verified).
  - Check: forest residue chips give LHV_d ≈ 19.5 MJ/kg, consistent with VTT's 19.0–20.5.
- **Stoichiometry** (per kg dry fuel, molar):
  - O₂,min = c/12.011 + h/4.032 + s/32.06 − o/32.00.
  - Air is humid air with the dry-air composition of feature 001.
  - Complete combustion gives CO₂, H₂O (from H, from fuel moisture and from air humidity),
    SO₂, N₂ (from air and fuel N) and excess O₂.
  - Ash leaves as solid at the bed temperature. Its enthalpy is a small loss with c_p,ash =
    0.8 kJ/(kg K) (VERIFY).
  - **SO₂ and Ar are reported as "other"**, the fifth interface species. They are
    thermodynamically represented by Ar, which is fine at < 0.01 vol% SO₂, and accounted
    separately in the S element balance.
- **Energy reference**: consistent with feature 001. The dry fuel enters with LHV_d +
  sensible enthalpy, fuel moisture as liquid water (`water.h_liquid`), and products leave
  with NASA sensible enthalpy relative to 298.15 K. The flue gas temperature then follows
  from an exact energy balance, and the water latent heat is counted exactly once.

**Alternatives considered**: tabulated LHV only (loses consistency between composition and
heating value); chemical equilibrium (Cantera) for dissociation (negligible below 1300 °C; kept
as a test oracle for the adiabatic temperature).

**Sources**: Alakangas, E. et al. (2016), *Properties of indigenous fuels in Finland*, VTT
Technology 272, ISBN 978-951-38-8455-0, OA; Channiwala, S.A., Parikh, P.P. (2002), *Fuel*
81(8), 1051–1063, doi:10.1016/S0016-2361(01)00131-4; ISO 18125:2017.

---

## R3. Fuel bed and combustion dynamics

**Decision**: lumped fuel-bed balances in the form of Bauer et al. (2010) and Böhler et al.
(2020), simplified to the fuel feed as the only manipulated fuel input:

- **Feed transport**: two first-order stages approximate the feed dead time θ (default
  2 min, VERIFY).
- **Bed water** m_w: dm_w/dt = w·ṁ_f − m_w/τ_w. Evaporation is m_w/τ_w.
- **Bed dry fuel** m_d: dm_d/dt = (1 − w)·ṁ_f − m_d/τ_bed. The burnout ṁ_burn = m_d/τ_bed
  releases ṁ_burn·(1 − a)·LHV-based enthalpy; the ash a leaves with it.
- **Defaults**: τ_bed = 15 min and τ_w = 10 min (VERIFY). These are placeholders for
  10–20 MW grates until plant step tests are available.
- The excess air acts instantly on the gas composition; the O₂ sensor has a first-order lag
  τ_O2 = 30 s (VERIFY).

**Rationale**:
- It captures the main dynamic fact: heat release lags the fuel feed by minutes (Paces & Kozek
  2011, response over tens of minutes).
- It has few parameters, all identifiable from fuel-feed step tests.

**Alternatives considered**: multi-zone grate models with kinetics (Paces & Kozek 2011,
17–46 states), which have too many unidentifiable parameters; a pure first-order lag, which
loses the separate water inventory.

**Sources**: Bauer, R. et al. (2010), *Biomass Bioenergy* 34(4), 417–427,
doi:10.1016/j.biombioe.2009.12.005; Böhler, L. et al. (2020), *Appl. Energy* 276, 115339,
doi:10.1016/j.apenergy.2020.115339 (OA); Paces, N., Kozek, M. (2011), MMMse 2011 (OA).

---

## R4. Furnace and radiant section (heater 1)

**Decision**: a **well-stirred furnace zone** (Lobo–Evans / Hottel):

- **Furnace gas**: one gas node with a constant hold-up mass and its enthalpy as the state,
  as in the dryer cells.
- **Radiant tube heat**: Q_rad = σ·(αA_cp)·F·(T_g⁴ − T_w⁴) + h_c·A_t·(T_g − T_w), with
  h_c = 11 W/(m² K) (VERIFY).
- **Exchange factor**: F from an effective flame emissivity ε_fl. The default is 0.5
  (VERIFY), a **calibration parameter**, because biomass flames radiate mainly from fly ash
  and gas, and no lumped value was found.
- **Refractory**: two lumped nodes (hot face and bulk). The hot face exchanges heat with the
  gas through h_eff·A_refr (radiation linearised plus convection); the bulk conducts to the
  casing and loses heat to ambient through UA_loss.
- **Radiant heater tubes**: one wall node and one oil node.

Gas radiation coefficients (WSGG, Smith et al. 1982) are not implemented, since their
coefficients were not verified. The constant ε_fl replaces them and is folded into the
calibration.

**Rationale**:
- This is the standard lumped model for fired heaters.
- It has few parameters, and it is calibrated against the furnace exit temperature and the
  oil duty that the plant's DCS (distributed control system) measures.

**Alternatives considered**: zone method or CFD (too slow, no geometry data); plug-flow
furnace (needs a heat-release profile).

**Sources**: Lobo, W.E., Evans, J.E. (1939), *Trans. AIChE* 35, 743–748; Hottel & Sarofim,
*Radiative Transfer* (1967); Smith, T.F. et al. (1982), *J. Heat Transfer* 104, 602–608,
doi:10.1115/1.3245174 (not used numerically); Kern, *Process Heat Transfer*, ch. 19 worked
examples (FOSSEE notebook, OA).

---

## R5. Convective thermal oil heaters (heaters 2 and 3)

**Decision**: each convective heater is discretised into **N_c counter-current cells**
(default 5).

- Per cell, the **wall temperature** and **oil temperature** are dynamic states.
- The **gas is quasi-static**: per cell T_g,out = T_w + (T_g,in − T_w)·exp(−U_gA/(ṁ c_p)), and
  the heat to the wall is ṁ·[h(T_g,in) − h(T_g,out)]. This is exact for a constant wall
  temperature and conserves energy exactly.
- **Gas-side coefficient**:
  - **Žukauskas** staggered tube bank: Nu = C·Re^m·Pr^0.36, with C/m = 0.35/0.6 for
    Re 10³–2·10⁵ and 0.031/0.8 above 2·10⁴. (The (Pr/Pr_w)^0.25 and pitch-ratio factors are
    set to 1 for gas.)
  - Plus gas radiation, h_rad = ε_g σ (T_g² + T_w²)(T_g + T_w), with ε_g default 0.1 (VERIFY).
  - Plus a **fouling resistance R_f** = 0.008 m² K/W (VERIFY, calibration parameter; ash
    deposits typically give 0.005–0.015).
- **Oil-side coefficient**: **Gnielinski**. Laminar Nu = 3.66, with linear blending over
  Re 2300–10⁴ (VDI).
- **Wall**: metal mass per cell from the configured tube mass, c_steel = 500 J/(kg K).
- The **bypass** (R7) splits the gas flow before a configurable heater.

**Rationale**:
- Cells capture the strong temperature gradients and the counter-current oil flow, and the
  oil temperature after each heater is required by FR-006.
- The quasi-static gas avoids stiff gas states with negligible hold-up.

**Alternatives considered**: lumped ε-NTU per heater (loses the profile); finned-tube
correlations (biomass heaters use bare tubes because of ash).

**Sources**: Žukauskas, A. (1972), *Adv. Heat Transfer* 8, 93–160,
doi:10.1016/S0065-2717(08)70038-8 (constants confirmed via the `ht` package documentation);
Gnielinski in VDI Heat Atlas (2010), doi:10.1007/978-3-540-77877-6; Zbogar, A. et al. (2005),
*PECS* 31, 371–421, doi:10.1016/j.pecs.2005.08.002 (deposit conductivity).

---

## R6. Thermal oil and the oil circuit

**Decision**:
- **Default oil: Shell Heat Transfer Oil S2** (mineral, DIN 51522). Linear fits to the
  calculated table of TDS v1.1 (2014), T in °C, error ≤ 1 %:
  - ρ = 870 − 0.65 T kg/m³;
  - c_p = 1962 + 4.385 T J/(kg K);
  - k = 0.136 − 7.35·10⁻⁵ T W/(m K);
  - ν from ASTM D341: log₁₀ log₁₀(ν + 0.7) = 9.5208 − 3.7474 log₁₀(T_K), mm²/s.
  - Limits (VERIFY against your plant's oil): **bulk 300 °C, film 320 °C**.
  - The older Thermia B sheet gives c_p about 10 % lower; this is kept as a sensitivity case.
- **Alternative oil: Therminol 66**, with the fit equations checked against the Eastman
  table (ρ, c_p, k ≤ 1 %, ν ≤ 3 %). Limits: bulk 345 °C, film 375 °C.
- **Oil enthalpy**: the integral of the linear c_p, so it is quadratic in T and its inversion
  is exact.
- **Circuit**: one circuit, heaters in series, counter-current. Oil enters the last cell of
  heater 3 and leaves heater 1. The oil inventory per cell is constant (incompressible model;
  thermal expansion goes to the expansion vessel, which is not modelled). Oil advects upwind
  from cell to cell. The oil flow and return temperature are input signals.
- **Film temperature** (Pelini 2008): T_film = T_oil + q″_peak/h_i, with q″_peak = F_C·F_L·q″_avg.
  Defaults: F_C = 1.57 (helical coil) and F_L = 1.1 in the radiant heater; 1.0 in convective
  cells.
  - A range warning is raised when T_film > T_film,max or T_oil > T_bulk,max.
  - A pre-warning is raised when the film rise exceeds 80 % of the margin.
  - A velocity check gives a warning below 2.0 m/s (VERIFY, configurable) and below Re 10⁴.

**Rationale**: the only public datasets with tables are Shell S2 and Therminol 66. Film
temperature is the binding safety criterion (DIN 4754-1).

**Sources**: Shell Heat Transfer Oil S2 TDS v1.1 (2014-01-27), v1.4 (2020), v1.5 (2022);
Eastman Therminol 66 brochure (2025); Mobiltherm 600 series PDS; Pelini, R.G. (2008), *Chem.
Eng.* 115(13); DIN 4754-1:2015-03 (existence confirmed, content paywalled).

---

## R7. Bypass damper and mixing

**Decision**:
- The damper position u_b ∈ [0, 1] sets the bypass share of the flue gas leaving the
  furnace and heater 1. The bypass starts after a configurable heater (default: after
  heater 1, bypassing heaters 2 and 3).
- The bypass duct is adiabatic, with an optional loss UA.
- Mixing before the dryer is exact (mass and enthalpy).
- The flow split is set directly by the position, so damper characteristic, leakage and
  pressure-driven split are not modelled (spec assumption).

---

## R8. Control loops

**Decision**:
- **Continuous PI controllers**, with the integral as an ODE state:
  - v = K_c·e + I, and u = sat(v).
  - dI/dt = (K_c/T_i)·e + (u_sat − v)/T_t, a back-calculation anti-windup with T_t = T_i by
    default (Åström & Murray; Modelica LimPID).
- **Saturation**: smooth (softplus, ε = 0.5 % of span) to keep the right-hand side smooth for
  BDF. An exact mode is available for validation runs.
- **Manual mode**: the integral tracks u_manual through the same back-calculation term, which
  makes the transfer bumpless.
- **Initialisation**: steady-state initialisation sets I₀ = u₀ − K_c·e₀.
- **Loops**:
  1. **Oil outlet temperature → fuel feed**. Set point 282 °C; output in [ṁ_f,min, ṁ_f,max]
     from the furnace load range.
  2. **Furnace O₂ (dry, measured with lag) → combustion air**. Set point 7 vol% dry
     (λ ≈ 1.5); output limits from the fan range. Applied as a **feedforward ratio**
     (stoichiometric air from the current burnout rate times the controller's λ correction),
     so that the fuel-loop dynamics do not upset O₂.
  3. **Drum inlet temperature → split range**. One PI output u ∈ [0, 1]:
     - u ≤ s: bypass damper = (s − u)/s, dilution = 0.
     - u ≥ s: bypass = 0, dilution = (u − s)/(1 − s)·ṁ_dil,max.
     - Default split value s = 0.5, to be re-set from the gain ratio of the two actuators
       (Reyes-Lúa & Skogestad 2020). Anti-windup acts on the combined 0/1 limits.
     - The bypass is used when the gas is too cold and dilution when it is too hot, as
       clarified.
- **Default tuning**: **SIMC** (Skogestad 2003), with K_c = τ₁/(k(τ_c + θ)),
  T_i = min(τ₁, 4(τ_c + θ)) and τ_c = θ.
  - The FOPDT parameters (k, τ₁, θ) come from step tests on the twin itself, done by
    `scripts/tune_controllers.py` (half rule). The results are stored as documented defaults
    in the boiler house configuration.
  - Loop speeds, fastest to slowest: O₂, then drum inlet, then oil temperature.
- **Reported**: controller outputs, saturation periods, and periods in which the set point is
  not reached (FR-010).

**Alternatives considered**:
- Sampled (zero-order hold) controllers: they force a solver restart at every sample. Not
  needed against process time constants of minutes.
- Conditional-integration anti-windup: discontinuous right-hand side.
- Generalized split range with baton logic (Reyes-Lúa & Skogestad 2020): the upgrade path if
  a single T_i cannot serve both actuators.

**Sources**: Åström, K.J., Murray, R.M., *Feedback Systems*, ch. 10 (OA); Åström, K.J., "PID
Control", Caltech CDS101 notes (2002, OA); Skogestad, S. (2003), *J. Process Control* 13(4),
291–309, doi:10.1016/S0959-1524(02)00062-8; Reyes-Lúa, A., Skogestad, S. (2020), *J. Process
Control* 91, 1–11, doi:10.1016/j.jprocont.2020.05.001 (OA); Modelica Standard Library
`Blocks.Continuous.LimPID`.

---

## R9. Valid operating range (FR-011)

**Decision**: these defaults are configurable, each with a physical and a validated range as
in feature 001:

| Quantity | Validated range | Source |
|---|---|---|
| Fuel moisture (wet basis) | 10–55 %, warning above 55 %, error above 65 % | Nussbaumer 2024 (≤ 60 % for bark) |
| Excess air λ | ≥ 1.2 (complete-combustion validity) | Nussbaumer 2024 (1.2–1.6 typical) |
| Furnace (combustion zone) temperature | 850–1150 °C (warning 800–850, invalid < 800) | Nussbaumer 2024; ash deformation 1150–1210 °C (VTT 272) |
| Furnace load | 30–100 % of rated fuel power (warning below 50 %) | Nussbaumer 2024 (50–100 % typical; 30 % VERIFY) |
| Oil bulk / film temperature | ≤ 300 / 320 °C (Shell S2) | Shell TDS |
| Oil velocity in tubes | ≥ 2.0 m/s and Re ≥ 10⁴ | practice (VERIFY) |
| Flue gas to the dryer | within the feature-001 interface range | feature 001 |

**Sources**: Nussbaumer, T. (2024), IEA Bioenergy Task 32 report, ISBN 979-12-80907-42-4 (OA).

---

## R10. Outputs, balances and records

**Decision**:
- **Boiler house results** (`boiler_results.csv`, unit row): fuel feed, burnout, heat
  released, furnace temperature, flue gas after each heater, oil temperature after each
  heater, oil outlet temperature, heat to oil per heater and total, film temperatures,
  losses, λ, O₂ dry (true and measured), damper position, dilution air, controller outputs and
  modes, and flags (oil limits, combustion range, saturation, set point not reached).
- **Interface time series** (FR-014): `flue_gas_to_dryer.csv` and `dilution_air.csv`, both in
  the time-series input format of feature 001, so they can be used directly as
  boundary-condition sources.
- **Balances**: flow accumulators as in feature 001, extended per subsystem:
  - boiler house: mass, the elements C, H, O, N and S, and energy;
  - oil circuit: energy;
  - dryer: as in feature 001;
  - interface: boiler outlet = dryer inlet, by construction;
  - whole plant: sum of the above.
- **Run record**: as in feature 001, plus controller settings and states.
- **Comparison**: as in feature 001; the measured columns may also name boiler house outputs.

---

## R11. Validation and reference cases

1. **Hand calculation** of the combustion for wood chips at 45 % moisture and 7 % O₂ dry: air
   and flue gas flows, composition, LHV and adiabatic temperature. Cantera equilibrium serves
   as the test oracle for the adiabatic temperature (dissociation below 1300 °C is
   negligible).
2. **Steady-state hand energy balance** of the whole boiler house: heat released = oil duty +
   losses + flue gas to the dryer (SC-002).
3. **Plausibility checks against Lienz** (Obernberger et al. 2002, 6–6.5 MWth thermal oil
   boiler with oil at 300/250 °C and an efficiency of about 82 % NCV): the efficiency of the
   oil-only configuration (no dryer, bypass closed) should come out at 80–90 %.
4. **Controller step tests** (SC-004): a 20 % step in oil demand must settle within 30 min,
   with an overshoot of at most 5 K.
5. **Dryer specific energy**: 2.8–3.5 MJ per kg of water (Selivanovs et al. 2012) as a
   plausibility band in coupled runs.

**Data to request from the plant DCS** (for calibration, later feature):
- 2–4 weeks of 1–10 s historian data. Tags: O₂, furnace temperature, flue gas temperature
  before and after each heater, oil supply and return temperatures and flow, damper
  positions, dilution air, drum inlet and outlet temperatures, fuel feed, dryer throughput
  and moisture.
- Step tests on fuel feed (±10 %), bypass damper and dilution damper.
- Fuel lab analyses.
- Heater data sheets and acceptance tests (EN 12953-11).

---

## Open items

1. **VERIFY coefficients**:
   - the ISO 18125 coefficients 0.2122/0.0008 (the 0.02443 term is verified);
   - the validity ranges of the Channiwala–Parikh correlation;
   - flame emissivity 0.5 and convective-pass gas emissivity 0.1;
   - fouling resistance 0.008 m² K/W;
   - fuel-bed τ_bed, τ_w and θ, and the O₂ sensor lag;
   - the 2 m/s oil-velocity rule and the 30 % minimum load;
   - h_c = 11 W/(m² K) in the radiant section.
2. **Your plant's thermal oil product and its limits.** The default is Shell S2, with bulk
   300 °C and film 320 °C; newer TDS versions allow a 330 °C film.
3. **Calibration data** from the plant DCS (R11). The literature gives no open time series
   for this plant type.

---

## References

✔ verified via DOI/Crossref or an open PDF; ◐ bibliographic data only; ✖ UNVERIFIED.

- ✔ Alakangas, E., Hurskainen, M., Laatikainen-Luntama, J., Korhonen, J. (2016). *Properties
  of indigenous fuels in Finland*. VTT Technology 272. http://urn.fi/URN:ISBN:978-951-38-8455-0
- ◐ Channiwala, S.A., Parikh, P.P. (2002). A unified correlation for estimating HHV of solid,
  liquid and gaseous fuels. *Fuel* 81(8), 1051–1063. doi:10.1016/S0016-2361(01)00131-4
- ◐ ISO 18125:2017. Solid biofuels – Determination of calorific value.
- ✔ Nussbaumer, T. (2024). *Low emission biomass combustion in automated boilers for heat and
  power*. IEA Bioenergy Task 32. ISBN 979-12-80907-42-4.
- ◐ Bauer, R., Gölles, M., Brunner, T., Dourdoumas, N., Obernberger, I. (2010). Modelling of
  grate combustion in a medium scale biomass furnace for control purposes. *Biomass Bioenergy*
  34(4), 417–427. doi:10.1016/j.biombioe.2009.12.005
- ✔ Böhler, L., Krail, J., Görtler, G., Kozek, M. (2020). Fuzzy model predictive control for
  small-scale biomass combustion furnaces. *Appl. Energy* 276, 115339.
  doi:10.1016/j.apenergy.2020.115339
- ✔ Paces, N., Kozek, M. (2011). Modeling of a grate-firing biomass furnace for real-time
  application. MMMse 2011, IIIS.
- ◐ Lobo, W.E., Evans, J.E. (1939). Heat transfer in the radiant section of petroleum heaters.
  *Trans. AIChE* 35, 743–748.
- ◐ Hottel, H.C., Sarofim, A.F. (1967). *Radiative Transfer*. McGraw-Hill.
- ◐ Smith, T.F., Shen, Z.F., Friedman, J.N. (1982). *J. Heat Transfer* 104(4), 602–608.
  doi:10.1115/1.3245174
- ◐ Leckner, B. (1972). *Combust. Flame* 19, 33–48. doi:10.1016/S0010-2180(72)80084-1
- ◐ Žukauskas, A. (1972). Heat transfer from tubes in crossflow. *Adv. Heat Transfer* 8,
  93–160. doi:10.1016/S0065-2717(08)70038-8
- ◐ VDI e.V. (2010). *VDI Heat Atlas*, 2nd ed. Springer. doi:10.1007/978-3-540-77877-6
- ◐ Zbogar, A., Frandsen, F., Jensen, P.A., Glarborg, P. (2005). Heat transfer in ash
  deposits: a modelling tool-box. *PECS* 31, 371–421. doi:10.1016/j.pecs.2005.08.002
- ✔ Shell Heat Transfer Oil S2, Technical Data Sheet v1.1 (2014-01-27); v1.5 (2022-12-30).
- ✔ Eastman, Therminol 66 heat transfer fluid, technical brochure (2025).
- ✔ ExxonMobil, Mobiltherm 600 Series product data sheet.
- ✔ Pelini, R.G. (2008). Heat flux and film temperature in fired, thermal-fluid heaters.
  *Chemical Engineering* 115(13).
- ◐ DIN 4754-1:2015-03. Wärmeübertragungsanlagen mit organischen Wärmeträgern.
- ✔ Åström, K.J., Murray, R.M. *Feedback Systems*, v2.11b, ch. 10 (OA).
- ✔ Skogestad, S. (2003). Simple analytic rules for model reduction and PID controller tuning.
  *J. Process Control* 13(4), 291–309. doi:10.1016/S0959-1524(02)00062-8
- ✔ Reyes-Lúa, A., Skogestad, S. (2020). Multi-input single-output control for extending the
  operating range: generalized split range control using the baton strategy. *J. Process
  Control* 91, 1–11. doi:10.1016/j.jprocont.2020.05.001
- ✔ Modelica Standard Library, `Modelica.Blocks.Continuous.LimPID` documentation.
- ✔ Sadjina, S. et al. (2017). Energy conservation and power bonds in co-simulations. *Eng.
  Comput.* 33(3), 607–620. doi:10.1007/s00366-016-0492-8
- ✔ Obernberger, I., Thonhofer, P., Reisenhofer, E. (2002). Description and evaluation of the
  new 1,000 kWel ORC process integrated in the biomass CHP plant in Lienz. *Euroheat & Power*
  10/2002 (OA, BIOS).
- ◐ Selivanovs, J., Blumberga, D. et al. (2012). Research of woody biomass drying process in
  pellet production. *Environ. Climate Technol.* doi:10.2478/v10145-012-0017-7
- ◐ Máša, V., Pavlas, M., Švarc, P. (2011). Mathematical model of biomass boiler for control
  purposes. *Chem. Eng. Trans.* 25, 743–748.
- ◐ Schaßberger, T., Gröll, L., Hagenmeyer, V. (2024). Control-oriented modeling of
  direct-heat co-current rotary dryers. *Comput. Chem. Eng.* 189, 108774.
  doi:10.1016/j.compchemeng.2024.108774
