"""The model's formulas with links to the literature (feature 003, FR-023).

One entry per formula as implemented, with the code that implements it and its sources.
Links: the DOI where the research notes of features 001/002 record one, else an open-access
copy recorded there, else a search for the exact reference (marked as such). No link is
invented: a test checks every DOI against the research notes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote_plus

LinkKind = Literal["doi", "open access", "publisher", "search"]


@dataclass(frozen=True)
class Source:
    citation: str
    url: str
    link_kind: LinkKind
    doi: str | None = None


@dataclass(frozen=True)
class Formula:
    section: str
    title: str
    formula: str
    symbols: str
    module: str  # repository-relative path of the implementing code
    function: str | None
    sources: tuple[str, ...]
    note: str = ""


def doi(citation: str, value: str) -> Source:
    return Source(citation, f"https://doi.org/{value}", "doi", value)


def open_access(citation: str, url: str) -> Source:
    return Source(citation, url, "open access")


def search(citation: str, query: str | None = None) -> Source:
    return Source(
        citation, "https://scholar.google.com/scholar?q=" + quote_plus(query or citation), "search"
    )


SOURCES: dict[str, Source] = {
    # fuel and combustion
    "channiwala2002": doi("Channiwala, S.A., Parikh, P.P. (2002). A unified correlation for estimating HHV of solid, liquid and gaseous fuels. Fuel 81(8), 1051–1063.", "10.1016/S0016-2361(01)00131-4"),
    "iso18125": Source("ISO 18125:2017. Solid biofuels – Determination of calorific value.", "https://www.iso.org/search.html?q=ISO%2018125", "publisher"),
    "alakangas2016": open_access("Alakangas, E., Hurskainen, M., Laatikainen-Luntama, J., Korhonen, J. (2016). Properties of indigenous fuels in Finland. VTT Technology 272.", "http://urn.fi/URN:ISBN:978-951-38-8455-0"),
    "bauer2010": doi("Bauer, R., Gölles, M., Brunner, T., Dourdoumas, N., Obernberger, I. (2010). Modelling of grate combustion in a medium scale biomass furnace for control purposes. Biomass and Bioenergy 34(4), 417–427.", "10.1016/j.biombioe.2009.12.005"),
    "boehler2020": doi("Böhler, L., Krail, J., Görtler, G., Kozek, M. (2020). Fuzzy model predictive control for small-scale biomass combustion furnaces. Applied Energy 276, 115339.", "10.1016/j.apenergy.2020.115339"),
    # furnace and heaters
    "lobo1939": search("Lobo, W.E., Evans, J.E. (1939). Heat transfer in the radiant section of petroleum heaters. Trans. AIChE 35, 743–748."),
    "hottel1967": search("Hottel, H.C., Sarofim, A.F. (1967). Radiative Transfer. McGraw-Hill.", "Hottel Sarofim Radiative Transfer 1967"),
    "zukauskas1972": doi("Žukauskas, A. (1972). Heat transfer from tubes in crossflow. Advances in Heat Transfer 8, 93–160.", "10.1016/S0065-2717(08)70038-8"),
    "vdi2010": doi("VDI e.V. (ed.) (2010). VDI Heat Atlas, 2nd ed. Springer.", "10.1007/978-3-540-77877-6"),
    "zbogar2005": doi("Zbogar, A., Frandsen, F., Jensen, P.A., Glarborg, P. (2005). Heat transfer in ash deposits: a modelling tool-box. Progress in Energy and Combustion Science 31, 371–421.", "10.1016/j.pecs.2005.08.002"),
    "pelini2008": search("Pelini, R.G. (2008). Heat flux and film temperature in fired, thermal-fluid heaters. Chemical Engineering 115(13)."),
    "astm_d341": search("ASTM D341. Standard practice for viscosity-temperature equations and charts for liquid petroleum products.", "ASTM D341 viscosity temperature charts liquid petroleum products"),
    "shell_s2": search("Shell Heat Transfer Oil S2, Technical Data Sheet v1.1 (2014-01-27).", "Shell Heat Transfer Oil S2 technical data sheet"),
    # control
    "astrom_murray": search("Åström, K.J., Murray, R.M. Feedback Systems: An Introduction for Scientists and Engineers, ch. 10 (open access).", "Astrom Murray Feedback Systems An Introduction for Scientists and Engineers"),
    "skogestad2003": doi("Skogestad, S. (2003). Simple analytic rules for model reduction and PID controller tuning. Journal of Process Control 13(4), 291–309.", "10.1016/S0959-1524(02)00062-8"),
    "reyeslua2020": doi("Reyes-Lúa, A., Skogestad, S. (2020). Multi-input single-output control for extending the operating range: generalized split range control using the baton strategy. Journal of Process Control 91, 1–11.", "10.1016/j.jprocont.2020.05.001"),
    # dryer: transport
    "saeman1954": search("Saeman, W.C., Mitchell, T.R. (1954). Analysis of rotary dryer and cooler performance. Chem. Eng. Prog. 50, 467–475."),
    "friedman1949": search("Friedman, S.J., Marshall, W.R. (1949). Studies in rotary drying. Part I: Holdup and dusting. Chem. Eng. Prog. 45(8), 482–493."),
    "schneider2003": doi("Schneider, P.A., Sheehan, M.E., Brown, S.T. (2003). Modelling the dynamics of solids transport in flighted rotary dryers. Computer Aided Chemical Engineering 14, 911–916.", "10.1016/S1570-7946(03)80233-X"),
    "sheehan2005": doi("Sheehan, M.E., Britton, P.F., Schneider, P.A. (2005). A model for solids transport in flighted rotary dryers based on physical considerations. Chemical Engineering Science 60(15), 4171–4182.", "10.1016/j.ces.2005.02.055"),
    "baker1992": doi("Baker, C.G.J. (1992). Air–solids drag in cascading rotary dryers. Drying Technology 10(2), 365–393.", "10.1080/07373939208916442"),
    # dryer: heat and mass transfer
    "gnielinski1975": doi("Gnielinski, V. (1975). Berechnung mittlerer Wärme- und Stoffübergangskoeffizienten an laminar und turbulent überströmten Einzelkörpern mit Hilfe einer einheitlichen Gleichung. Forschung im Ingenieurwesen 41.", "10.1007/bf02560793"),
    "gnielinski1975_tube": doi("Gnielinski, V. (1975). Neue Gleichungen für den Wärme- und den Stoffübergang in turbulent durchströmten Rohren und Kanälen. Forschung im Ingenieurwesen 41, 8–16.", "10.1007/bf02559682"),
    "ranz1952": search("Ranz, W.E., Marshall, W.R. (1952). Evaporation from drops. Chem. Eng. Prog. 48(3), 141–146."),
    "chilton1934": doi("Chilton, T.H., Colburn, A.P. (1934). Mass transfer (absorption) coefficients: prediction from data on heat transfer and fluid friction. Industrial & Engineering Chemistry 26(11), 1183–1187.", "10.1021/ie50299a012"),
    "vanmeel1958": doi("van Meel, D.A. (1958). Adiabatic convection batch drying with recirculation of air. Chemical Engineering Science 9, 36–44.", "10.1016/0009-2509(58)87005-0"),
    "keey1972": search("Keey, R.B. (1972). Drying: Principles and Practice. Pergamon.", "Keey Drying Principles and Practice 1972"),
    "dittus1930": doi("Dittus, F.W., Boelter, L.M.K. (1930). Heat transfer in automobile radiators of the tubular type. Univ. California Publ. Eng. 2, 443–461; reprinted in International Communications in Heat and Mass Transfer 12 (1985), 3–22.", "10.1016/0735-1933(85)90003-x"),
    "churchill1975": doi("Churchill, S.W., Chu, H.H.S. (1975). Correlating equations for laminar and turbulent free convection from a horizontal cylinder. Int. J. Heat Mass Transfer 18(9), 1049–1053.", "10.1016/0017-9310(75)90222-7"),
    # wood and properties
    "woodhandbook2021": open_access("Glass, S.V., Zelinka, S.L. (2021). Moisture relations and physical properties of wood. Ch. 4 in Wood Handbook, FPL-GTR-282, USDA Forest Products Laboratory.", "https://research.fs.usda.gov/treesearch/62243"),
    "hailwood1946": doi("Hailwood, A.J., Horrobin, S. (1946). Absorption of water by polymers: analysis in terms of a simple model. Transactions of the Faraday Society 42B, 84–102.", "10.1039/tf946420b084"),
    "skaar1988": doi("Skaar, C. (1988). Wood-Water Relations. Springer Series in Wood Science, Springer.", "10.1007/978-3-642-73683-4"),
    "mcbride2002": open_access("McBride, B.J., Zehe, M.J., Gordon, S. (2002). NASA Glenn coefficients for calculating thermodynamic properties of individual species. NASA/TP-2002-211556.", "https://ntrs.nasa.gov/citations/20020085330"),
    "wilke1950": doi("Wilke, C.R. (1950). A viscosity equation for gas mixtures. The Journal of Chemical Physics 18, 517–519.", "10.1063/1.1747673"),
    "iapws2007": search("IAPWS (2007). Revised release on the IAPWS Industrial Formulation 1997 for the thermodynamic properties of water and steam (IAPWS-IF97).", "IAPWS-IF97 revised release 2007 industrial formulation water steam"),
}  # fmt: skip

SECTIONS: dict[str, str] = {
    "fuel": "Fuel and combustion",
    "furnace": "Furnace, radiant heater and fuel bed",
    "heaters": "Convective thermal oil heaters and thermal oil",
    "control": "Control loops",
    "transport": "Dryer: solids transport",
    "transfer": "Dryer: heat and mass transfer, drying",
    "wood": "Wood chip properties",
    "gas": "Gas and water properties",
}

F = Formula
FORMULAS: tuple[Formula, ...] = (
    # --- fuel and combustion -------------------------------------------------------------
    F("fuel", "Higher heating value (dry fuel)",
      "HHV_d = 0.3491 C + 1.1783 H + 0.1005 S − 0.1034 O − 0.0151 N − 0.0211 A   [MJ/kg]",
      "C, H, S, O, N, A: mass percent of the dry fuel (A = ash)",
      "src/boidrytwin/properties/fuel.py", "hhv_dry", ("channiwala2002",)),
    F("fuel", "Lower heating value, dry and as received",
      "LHV_d = HHV_d − 0.2122 H − 0.0008 (O + N);   LHV_ar = LHV_d (1 − M/100) − 0.02443 M   [MJ/kg]",
      "M: moisture in percent of the as-received fuel",
      "src/boidrytwin/properties/fuel.py", "lhv_dry", ("iso18125",),
      "The dry-basis coefficients are still marked VERIFY against the ISO text."),
    F("fuel", "Default fuel compositions (wood chips, bark)",
      "C, H, N, S, ash in mass percent of the dry fuel; O by difference",
      "dry-basis ultimate analysis",
      "src/boidrytwin/properties/fuel.py", "default", ("alakangas2016",)),
    F("fuel", "Stoichiometric oxygen and complete combustion",
      "n_O2,min = C/M_C + H/(2 M_H2) + S/M_S − O/M_O2;   air = λ · n_O2,min / x_O2,air",
      "per kg of dry fuel; λ: excess air ratio; products CO₂, H₂O, N₂, O₂, Ar, SO₂ (every element balances)",
      "src/boidrytwin/properties/fuel.py", "stoichiometry", ("alakangas2016", "channiwala2002")),
    # --- furnace -----------------------------------------------------------------------------
    F("furnace", "Fuel feed transport delay",
      "dṁ₁/dt = (ṁ_cmd − ṁ₁)/(θ/2);   dṁ₂/dt = (ṁ₁ − ṁ₂)/(θ/2)",
      "two first-order stages with a mean delay θ (feed dead time)",
      "src/boidrytwin/boiler_house/fuel_bed.py", "feed_stage_rates", ("bauer2010", "boehler2020")),
    F("furnace", "Fuel bed drying and burnout",
      "dm_w/dt = w ṁ_f − m_w/τ_w;   dm_d/dt = (1 − w) ṁ_f − m_d/τ_bed",
      "m_w, m_d: water and dry fuel on the grate; w: moisture (wet basis); τ_w, τ_bed: time constants",
      "src/boidrytwin/boiler_house/fuel_bed.py", "bed_rates", ("bauer2010", "boehler2020")),
    F("furnace", "Radiant section (well-stirred zone)",
      "Q_rad = σ (αA_cp) ε_fl (T_g⁴ − T_w⁴) + h_c A_t (T_g − T_w)",
      "αA_cp: effective cold-plane area; ε_fl: effective flame emissivity; A_t: tube area",
      "src/boidrytwin/boiler_house/furnace.py", "radiant_heat", ("lobo1939", "hottel1967")),
    # --- heaters -----------------------------------------------------------------------------
    F("heaters", "Convective cell, gas side (quasi-static gas)",
      "T_out = T_w + (T_in − T_w) exp(−UA / (ṁ c_p));   Q = ṁ [h(T_in) − h(T_out)]",
      "per cell; the casing loss uses the same form towards ambient",
      "src/boidrytwin/boiler_house/heaters.py", "gas_cell", ("vdi2010",)),
    F("heaters", "Staggered tube bank (Žukauskas)",
      "Nu = C Re^m Pr^0.36;   C = 0.35 (S_t/S_l)^0.2, m = 0.6 for Re < 2·10⁵, else C = 0.022, m = 0.84",
      "S_t, S_l: transverse and longitudinal pitch; Re on the maximum velocity",
      "src/boidrytwin/boiler_house/heaters.py", "nu_zukauskas_staggered", ("zukauskas1972",)),
    F("heaters", "Gas radiation in the passes",
      "h_rad = ε_g σ (T_g² + T_w²)(T_g + T_w)",
      "ε_g: gas emissivity",
      "src/boidrytwin/boiler_house/heaters.py", "gas_htc_bank", ("hottel1967",)),
    F("heaters", "Ash fouling resistance",
      "1/U = 1/h_gas + R_f",
      "R_f: fouling resistance, m² K/W (calibration parameter)",
      "src/boidrytwin/boiler_house/heaters.py", "overall_gas_side", ("zbogar2005",)),
    F("heaters", "Oil side, tube flow (Gnielinski)",
      "Nu = (ξ/8)(Re − 1000) Pr / (1 + 12.7 √(ξ/8) (Pr^(2/3) − 1)),   ξ = (1.8 log₁₀ Re − 1.5)⁻²;   Nu = 3.66 laminar, blended over Re 2300–10⁴",
      "Re, Pr of the oil at its bulk temperature",
      "src/boidrytwin/boiler_house/heaters.py", "nu_tube", ("gnielinski1975_tube", "vdi2010")),
    F("heaters", "Oil film temperature",
      "T_film = T_oil + F_C F_L q″_avg / h_i",
      "F_C F_L: peak-to-average heat flux factor; h_i: oil-side coefficient",
      "src/boidrytwin/boiler_house/heaters.py", "film_temperature", ("pelini2008",)),
    F("heaters", "Thermal oil viscosity (Walther)",
      "log₁₀ log₁₀(ν + 0.7) = A − B log₁₀ T",
      "ν: kinematic viscosity in mm²/s; T in K; A, B through the data sheet's 40/100 °C values",
      "src/boidrytwin/properties/thermal_oil.py", "viscosity", ("astm_d341", "shell_s2")),
    # --- control -------------------------------------------------------------------------------
    F("control", "PI controller with back-calculation anti-windup",
      "v = K_c e + I;   u = sat(v);   dI/dt = (K_c/T_i) e + (u − v)/T_t",
      "e: set point − measurement (reverse action); T_t: tracking time (default T_i); sat: smooth clip",
      "src/boidrytwin/control/pi.py", "integral_rate", ("astrom_murray",)),
    F("control", "SIMC tuning",
      "K_c = τ₁ / (k (τ_c + θ));   T_i = min(τ₁, 4 (τ_c + θ));   τ_c = θ (not below 10 s)",
      "k, τ₁, θ: gain, time constant and dead time of the fitted first-order-plus-dead-time model",
      "scripts/tune_controllers.py", "simc", ("skogestad2003",)),
    F("control", "Half rule (second order to first order plus dead time)",
      "τ₁' = τ₁ + τ₂/2;   θ' = θ + τ₂/2",
      "τ₁ ≥ τ₂: the two time constants of the fitted second-order model",
      "scripts/tune_controllers.py", "fit", ("skogestad2003",)),
    F("control", "Split range of the drum inlet controller",
      "u ≤ s: bypass = (s − u)/s, dilution = 0;   u ≥ s: bypass = 0, dilution = (u − s)/(1 − s) · ṁ_dil,max",
      "u ∈ [0, 1]: controller output; s: split value",
      "src/boidrytwin/control/split_range.py", "split", ("reyeslua2020",)),
    # --- dryer: transport ------------------------------------------------------------------------
    F("transport", "Residence time without gas (Saeman–Mitchell)",
      "τ = L / (f(H) D n tan S),   f(H) = π",
      "L, D: drum length and diameter; n: revolutions per second; S: slope",
      "src/boidrytwin/dryer/transport.py", "saeman_mitchell_residence_time", ("saeman1954",)),
    F("transport", "Residence time plausibility check (Friedman–Marshall)",
      "τ [min] = 0.23 (L/D) / (S N^0.9)",
      "S: slope (m/m); N: rpm; used as a check only",
      "src/boidrytwin/dryer/transport.py", "friedman_marshall_residence_time", ("friedman1949",)),
    F("transport", "Flight unloading and curtain fall (two-phase compartments)",
      "passive → active: m_p / t_p, t_p = T_rev / f_cap − t_fall;   active → passive: m_a / t_fall, t_fall = √(2 h_fall / g)",
      "h_fall = 0.6 D; f_cap: flight capacity factor (calibration)",
      "src/boidrytwin/dryer/transport.py", "transport_rates", ("schneider2003", "sheehan2005")),
    F("transport", "Axial advance of falling chips with gas drag",
      "v_a = (h_fall tan S + ½ a_drag t_fall²) / t_fall;   a_drag = C_F · ½ ρ_g u_g² C_D A_p / m_p",
      "C_F: curtain drag coefficient (calibration); C_D = 1; m_p grows with moisture",
      "src/boidrytwin/dryer/transport.py", "transport_rates", ("baker1992", "sheehan2005")),
    # --- dryer: heat and mass transfer -------------------------------------------------------------
    F("transfer", "Gas–chip heat transfer (single sphere, Gnielinski)",
      "Nu = 2 + √(Nu_lam² + Nu_turb²);   Nu_lam = 0.664 Re^½ Pr^⅓;   Nu_turb = 0.037 Re^0.8 Pr / (1 + 2.443 Re^−0.1 (Pr^(2/3) − 1))",
      "Re on the chip diameter and the relative gas–chip velocity",
      "src/boidrytwin/dryer/heat_transfer.py", "nu_sphere_gnielinski", ("gnielinski1975", "vdi2010")),
    F("transfer", "Single sphere check (Ranz–Marshall)",
      "Nu = 2 + 0.6 Re^½ Pr^⅓",
      "used as a check of the Gnielinski correlation",
      "src/boidrytwin/dryer/heat_transfer.py", "nu_sphere_ranz_marshall", ("ranz1952",)),
    F("transfer", "Mass transfer by the Chilton–Colburn analogy",
      "k_y = h / c_p,humid · Le^(−2/3),   Le = 1",
      "k_y in kg/(m² s) per unit humidity difference",
      "src/boidrytwin/dryer/heat_transfer.py", "mass_transfer_coefficient", ("chilton1934",)),
    F("transfer", "Evaporation and characteristic drying curve",
      "E = C_a k_y A (Y_sat(T_s) − Y_g) f(Φ);   f = 1 for X > X_cr, else Φⁿ,   Φ = (X − X_e)/(X_cr − X_e)",
      "C_a: heat transfer multiplier (calibration); X_e from the sorption isotherm; no condensation onto the chips",
      "src/boidrytwin/dryer/drying.py", "evaporation", ("vanmeel1958", "keey1972")),
    F("transfer", "Gas to shell (pipe flow)",
      "Nu = 0.023 Re^0.8 Pr^0.4,   at least 3.66 (laminar)",
      "on the drum diameter",
      "src/boidrytwin/dryer/heat_transfer.py", "nu_pipe", ("dittus1930",)),
    F("transfer", "Shell to ambient, free convection (Churchill–Chu)",
      "Nu = (0.60 + 0.387 Ra^(1/6) / (1 + (0.559/Pr)^(9/16))^(8/27))²   (plus grey-body radiation)",
      "horizontal cylinder; insulation as a series resistance",
      "src/boidrytwin/dryer/heat_transfer.py", "nu_cylinder_churchill_chu", ("churchill1975",)),
    # --- wood --------------------------------------------------------------------------------------------
    F("wood", "Equilibrium moisture content (Hailwood–Horrobin, Wood Handbook Eq. 4-5)",
      "X_e = (1800/W) [K h / (1 − K h) + (K₁ K h + 2 K₁ K₂ K² h²) / (1 + K₁ K h + K₁ K₂ K² h²)]   [%]",
      "h: relative humidity; W, K, K₁, K₂: quadratic in the temperature (°C), data up to 130 °C",
      "src/boidrytwin/properties/wood.py", "emc", ("woodhandbook2021", "hailwood1946")),
    F("wood", "Heat capacity of dry wood (Wood Handbook Eq. 4-18a)",
      "c_p0 = 0.1031 + 0.003867 T   [kJ/(kg K)]",
      "T in K",
      "src/boidrytwin/properties/wood.py", "cp_dry", ("woodhandbook2021",)),
    F("wood", "Heat capacity of moist wood (Wood Handbook Eq. 4-19, 4-20)",
      "c_p = (c_p0 + 4.18 X)/(1 + X) + A_c;   A_c = x (b₁ + b₂ T + b₃ x),   b₁ = −0.06191, b₂ = 2.36·10⁻⁴, b₃ = −1.33·10⁻⁴   [kJ/(kg K)]",
      "X: moisture (dry basis, kg/kg) and x = 100 X in percent, both capped at fibre saturation; free water above it by the rule of mixtures; T in K",
      "src/boidrytwin/properties/wood.py", "cp_moist", ("woodhandbook2021",)),
    F("wood", "Sorption heat of bound water",
      "Δh_s = Δh₀ (1 − X / X_fsp)²,   Δh₀ = 1.0 MJ/kg",
      "X_fsp: fibre saturation moisture; Δh₀ marked VERIFY",
      "src/boidrytwin/properties/wood.py", "sorption_heat", ("skaar1988",)),
    # --- gas and water ---------------------------------------------------------------------------------
    F("gas", "Heat capacity and enthalpy of gas species (NASA 7-coefficient polynomials)",
      "c_p/R = a₁ + a₂ T + a₃ T² + a₄ T³ + a₅ T⁴;   h/(RT) = a₁ + a₂T/2 + a₃T²/3 + a₄T³/4 + a₅T⁴/5 + a₆/T",
      "two temperature ranges split at 1000 K; data of GRI-Mech 3.0 as shipped with Cantera",
      "src/boidrytwin/properties/gas.py", "cp_molar", ("mcbride2002",)),
    F("gas", "Viscosity of gas mixtures (Wilke)",
      "μ = Σᵢ xᵢ μᵢ / Σⱼ xⱼ Φᵢⱼ;   Φᵢⱼ = [1 + (μᵢ/μⱼ)^½ (Mⱼ/Mᵢ)^¼]² / √(8 (1 + Mᵢ/Mⱼ))",
      "xᵢ: mole fractions; Mᵢ: molar masses",
      "src/boidrytwin/properties/gas.py", "viscosity", ("wilke1950",)),
    F("gas", "Saturation pressure of water (IAPWS-IF97 region 4)",
      "p_sat(T) from the explicit IF97 saturation equation, 273.15–647.096 K",
      "used for the humidity, dew point and drying driving force",
      "src/boidrytwin/properties/water.py", "p_sat", ("iapws2007",)),
)  # fmt: skip


def by_section() -> list[tuple[str, str, list[Formula]]]:
    return [
        (key, title, [f for f in FORMULAS if f.section == key]) for key, title in SECTIONS.items()
    ]


def numbered_sources() -> dict[str, int]:
    """Source key → reference number, in order of first use on the page."""
    order: dict[str, int] = {}
    for f in FORMULAS:
        for s in f.sources:
            order.setdefault(s, len(order) + 1)
    return order
