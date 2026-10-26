"""The model's formulas with links to the literature (feature 003, FR-023).

One entry per formula as implemented: its equations in LaTeX (typeset in the browser by the
vendored Temml as MathML), its symbols, the code that implements it and its sources.
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
class Symbol:
    tex: str  # LaTeX
    meaning: str
    unit: str


@dataclass(frozen=True)
class Formula:
    section: str
    title: str
    equations: tuple[str, ...]  # LaTeX, typeset in the browser by Temml (MathML)
    symbols: tuple[Symbol, ...]
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
    # exhaust recirculation and draft (feature 004, research R2-R4)
    "carolus2013": search("Carolus, T. (2013). Ventilatoren: Aerodynamischer Entwurf, Schallvorhersage, Konstruktion, 3rd ed., ch. 2. Springer Vieweg.", "Carolus Ventilatoren Aerodynamischer Entwurf 2013"),
    "bleier1998": search("Bleier, F.P. (1998). Fan Handbook: Selection, Application, and Design, ch. 4. McGraw-Hill.", "Bleier Fan Handbook Selection Application Design 1998"),
    "idelchik2007": search("Idelchik, I.E. (2007). Handbook of Hydraulic Resistance, 4th ed., ch. 1. Begell House.", "Idelchik Handbook of Hydraulic Resistance 4th edition"),
    "ashrae2020": search("ASHRAE (2020). ASHRAE Handbook – HVAC Systems and Equipment, ch. 47: Dampers.", "ASHRAE Handbook HVAC Systems and Equipment 2020 dampers"),
    "baehr_kabelac": search("Baehr, H.D., Kabelac, S. Thermodynamik: Grundlagen und technische Anwendungen, ch. 5 (humid air). Springer Vieweg.", "Baehr Kabelac Thermodynamik Grundlagen technische Anwendungen"),
    "iapws2007": search("IAPWS (2007). Revised release on the IAPWS Industrial Formulation 1997 for the thermodynamic properties of water and steam (IAPWS-IF97).", "IAPWS-IF97 revised release 2007 industrial formulation water steam"),
}  # fmt: skip

SECTIONS: dict[str, str] = {
    "fuel": "Fuel and combustion",
    "furnace": "Furnace, radiant heater and fuel bed",
    "heaters": "Convective thermal oil heaters and thermal oil",
    "control": "Control loops",
    "balances": "Plant balances: bypass, dryer inlet, cells and shell",
    "transport": "Dryer: solids transport",
    "transfer": "Dryer: heat and mass transfer, drying",
    "recirculation": "Dryer: exhaust recirculation and draft",
    "wood": "Wood chip properties",
    "gas": "Gas and water properties",
}

S = Symbol
F = Formula
FORMULAS: tuple[Formula, ...] = (
    # --- fuel and combustion -------------------------------------------------------------
    F("fuel", "Higher heating value (dry fuel)",
      (r"\mathrm{HHV}_d = 0.3491\,C + 1.1783\,H + 0.1005\,S - 0.1034\,O - 0.0151\,N - 0.0211\,A",),
      (S(r"\mathrm{HHV}_d", "higher heating value of the dry fuel", "MJ/kg"),
       S(r"C, H, S, O, N, A", "carbon, hydrogen, sulphur, oxygen, nitrogen and ash of the dry fuel", "mass %")),
      "src/boidrytwin/properties/fuel.py", "hhv_dry", ("channiwala2002",)),
    F("fuel", "Lower heating value, dry and as received",
      (r"\mathrm{LHV}_d = \mathrm{HHV}_d - 0.2122\,H - 0.0008\,(O + N)",
       r"\mathrm{LHV}_{ar} = \mathrm{LHV}_d \left(1 - \frac{M}{100}\right) - 0.02443\,M"),
      (S(r"\mathrm{LHV}_d,\ \mathrm{LHV}_{ar}", "lower heating value, dry and as received", "MJ/kg"),
       S(r"M", "moisture of the as-received fuel", "%")),
      "src/boidrytwin/properties/fuel.py", "lhv_dry", ("iso18125",),
      "The dry-basis coefficients are still marked VERIFY against the ISO text."),
    F("fuel", "Default fuel compositions (wood chips, bark)",
      (r"O = 100 - C - H - N - S - A",),
      (S(r"C, H, N, S, A", "ultimate analysis of the dry fuel (VTT tables)", "mass %"),
       S(r"O", "oxygen, by difference", "mass %")),
      "src/boidrytwin/properties/fuel.py", "default", ("alakangas2016",)),
    F("fuel", "Stoichiometric oxygen and combustion air",
      (r"n_{\mathrm{O_2},\min} = \frac{C}{M_\mathrm{C}} + \frac{H}{2\,M_\mathrm{H}} + \frac{S}{M_\mathrm{S}} - \frac{O}{M_{\mathrm{O_2}}}",
       r"\dot{n}_\mathrm{air} = \lambda\,\frac{n_{\mathrm{O_2},\min}}{x_{\mathrm{O_2},\mathrm{air}}}\,\dot{m}_\mathrm{burn}"),
      (S(r"n_{\mathrm{O_2},\min}", "oxygen for complete combustion per kg of dry fuel", "mol/kg"),
       S(r"C, H, S, O", "mass fractions of the dry fuel", "kg/kg"),
       S(r"M_i", "molar masses", "kg/mol"),
       S(r"\lambda", "excess air ratio (set by the O₂ loop)", "–"),
       S(r"\dot{m}_\mathrm{burn}", "dry fuel burnout rate", "kg/s")),
      "src/boidrytwin/properties/fuel.py", "stoichiometry", ("alakangas2016", "channiwala2002"),
      "Products CO₂, H₂O, N₂, O₂, Ar and SO₂; every element balances exactly."),
    # --- furnace -----------------------------------------------------------------------------
    F("furnace", "Fuel feed transport delay",
      (r"\frac{d\dot{m}_1}{dt} = \frac{\dot{m}_\mathrm{cmd} - \dot{m}_1}{\theta/2}, \qquad \frac{d\dot{m}_2}{dt} = \frac{\dot{m}_1 - \dot{m}_2}{\theta/2}",),
      (S(r"\dot{m}_\mathrm{cmd}", "fuel feed command of the oil temperature loop", "kg/s"),
       S(r"\dot{m}_2", "fuel delivered to the grate", "kg/s"),
       S(r"\theta", "feed dead time (mean delay)", "s")),
      "src/boidrytwin/boiler_house/fuel_bed.py", "feed_stage_rates", ("bauer2010", "boehler2020")),
    F("furnace", "Fuel bed drying and burnout",
      (r"\frac{dm_w}{dt} = w\,\dot{m}_f - \frac{m_w}{\tau_w}, \qquad \frac{dm_d}{dt} = (1 - w)\,\dot{m}_f - \frac{m_d}{\tau_\mathrm{bed}}",),
      (S(r"m_w,\ m_d", "water and dry fuel on the grate", "kg"),
       S(r"w", "fuel moisture, wet basis", "kg/kg"),
       S(r"\dot{m}_f", "delivered fuel", "kg/s"),
       S(r"\tau_w,\ \tau_\mathrm{bed}", "drying and burnout time constants", "s")),
      "src/boidrytwin/boiler_house/fuel_bed.py", "bed_rates", ("bauer2010", "boehler2020")),
    F("furnace", "Radiant section (well-stirred zone)",
      (r"Q_\mathrm{rad} = \sigma\,(\alpha A_{cp})\,\varepsilon_\mathrm{fl}\left(T_g^4 - T_w^4\right) + h_c A_t\,(T_g - T_w)",),
      (S(r"\sigma", "Stefan–Boltzmann constant", "W/(m² K⁴)"),
       S(r"\alpha A_{cp}", "effective cold-plane area", "m²"),
       S(r"\varepsilon_\mathrm{fl}", "effective flame emissivity (calibration)", "–"),
       S(r"T_g,\ T_w", "furnace gas and tube wall temperature", "K"),
       S(r"h_c,\ A_t", "convective coefficient and tube area", "W/(m² K), m²")),
      "src/boidrytwin/boiler_house/furnace.py", "radiant_heat", ("lobo1939", "hottel1967")),
    F("furnace", "Furnace gas energy balance (well-stirred node)",
      (r"\frac{dH_f}{dt} = B\,\mathrm{LHV}_d + E\,h_{l,\mathrm{ref}} + \dot H_\mathrm{fuel} + \dot H_\mathrm{air} - B\,a\,h_\mathrm{ash} - \dot m_g\,h(T_f) - Q_\mathrm{rad} - Q_\mathrm{refr}",
       r"T_f:\ \ h(T_f, y) = H_f / m_{g,\mathrm{hold}} \quad \text{(Newton)}"),
      (S(r"H_f,\ m_{g,\mathrm{hold}}", "enthalpy and constant gas hold-up of the furnace", "J, kg"),
       S(r"B,\ E", "dry fuel burnout and water evaporation from the bed", "kg/s"),
       S(r"h_{l,\mathrm{ref}}", "liquid water enthalpy at 25 °C (the water leaves as vapour in the gas)", "J/kg"),
       S(r"\dot H_\mathrm{fuel},\ \dot H_\mathrm{air}", "sensible enthalpy flows of fuel and humid combustion air", "W"),
       S(r"a,\ h_\mathrm{ash}", "ash fraction of the dry fuel and ash enthalpy at discharge", "kg/kg, J/kg"),
       S(r"\dot m_g,\ T_f", "flue gas leaving the furnace and furnace temperature", "kg/s, K"),
       S(r"Q_\mathrm{rad},\ Q_\mathrm{refr}", "heat to heater 1 and to the refractory", "W")),
      "src/boidrytwin/boiler_house/model.py", "rhs", ("bauer2010", "vdi2010"),
      "Enthalpies relative to 298.15 K; the species and element balances close exactly."),
    F("furnace", "Refractory: hot face and bulk",
      (r"m_h c_r \frac{dT_h}{dt} = \alpha_r A_r (T_f - T_h) - K_r (T_h - T_b), \qquad m_b c_r \frac{dT_b}{dt} = K_r (T_h - T_b) - UA_\mathrm{loss} (T_b - T_a)",),
      (S(r"T_h,\ T_b", "hot face and bulk temperature of the refractory", "K"),
       S(r"m_h,\ m_b,\ c_r", "masses and specific heat of the two refractory nodes", "kg, J/(kg K)"),
       S(r"\alpha_r A_r,\ K_r", "gas to hot face and hot face to bulk conductance", "W/K"),
       S(r"UA_\mathrm{loss}", "loss to ambient (about 1 % of rated power)", "W/K")),
      "src/boidrytwin/boiler_house/furnace.py", "refractory_flows", ("vdi2010",),
      "The bulk time constant is about 11.5 h at the reference: a slow drift after load changes."),
    # --- heaters -----------------------------------------------------------------------------
    F("heaters", "Convective cell, gas side (quasi-static gas)",
      (r"T_\mathrm{out} = T_w + (T_\mathrm{in} - T_w)\,\exp\!\left(-\frac{UA}{\dot{m}\,c_p}\right)",
       r"Q = \dot{m}\,\left[h(T_\mathrm{in}) - h(T_\mathrm{out})\right]"),
      (S(r"T_\mathrm{in},\ T_\mathrm{out}", "gas temperature into and out of the cell", "K"),
       S(r"T_w", "tube wall temperature of the cell", "K"),
       S(r"UA", "overall conductance of the cell", "W/K"),
       S(r"\dot{m},\ c_p,\ h", "gas mass flow, heat capacity, enthalpy", "kg/s, J/(kg K), J/kg")),
      "src/boidrytwin/boiler_house/heaters.py", "gas_cell", ("vdi2010",),
      "The casing loss of each cell uses the same exponential form towards ambient."),
    F("heaters", "Staggered tube bank (Žukauskas)",
      (r"\mathrm{Nu} = C\,\mathrm{Re}^m\,\mathrm{Pr}^{0.36}",
       r"C = 0.35\left(\frac{S_t}{S_l}\right)^{0.2},\ m = 0.6 \quad (\mathrm{Re} < 2\cdot 10^5); \qquad C = 0.022,\ m = 0.84 \quad \text{otherwise}"),
      (S(r"S_t,\ S_l", "transverse and longitudinal pitch", "m"),
       S(r"\mathrm{Re}", "Reynolds number on the maximum velocity", "–")),
      "src/boidrytwin/boiler_house/heaters.py", "nu_zukauskas_staggered", ("zukauskas1972",)),
    F("heaters", "Gas radiation in the passes",
      (r"h_\mathrm{rad} = \varepsilon_g\,\sigma\,\left(T_g^2 + T_w^2\right)(T_g + T_w)",),
      (S(r"\varepsilon_g", "gas emissivity", "–"),),
      "src/boidrytwin/boiler_house/heaters.py", "gas_htc_bank", ("hottel1967",)),
    F("heaters", "Ash fouling resistance",
      (r"\frac{1}{U} = \frac{1}{h_\mathrm{gas}} + R_f",),
      (S(r"R_f", "fouling resistance (calibration)", "m² K/W"),),
      "src/boidrytwin/boiler_house/heaters.py", "overall_gas_side", ("zbogar2005",)),
    F("heaters", "Oil side, tube flow (Gnielinski)",
      (r"\mathrm{Nu} = \frac{(\xi/8)\,(\mathrm{Re} - 1000)\,\mathrm{Pr}}{1 + 12.7\,\sqrt{\xi/8}\,\left(\mathrm{Pr}^{2/3} - 1\right)}, \qquad \xi = \left(1.8 \log_{10}\mathrm{Re} - 1.5\right)^{-2}",),
      (S(r"\mathrm{Re},\ \mathrm{Pr}", "of the oil at its bulk temperature", "–"),
       S(r"\xi", "friction factor", "–")),
      "src/boidrytwin/boiler_house/heaters.py", "nu_tube", ("gnielinski1975_tube", "vdi2010"),
      "Nu = 3.66 for laminar flow, blended linearly over Re 2300–10⁴."),
    F("heaters", "Oil film temperature",
      (r"T_\mathrm{film} = T_\mathrm{oil} + \frac{F_C F_L\,q''_\mathrm{avg}}{h_i}",),
      (S(r"F_C F_L", "peak-to-average heat flux factor", "–"),
       S(r"q''_\mathrm{avg}", "average heat flux into the oil", "W/m²"),
       S(r"h_i", "oil-side heat transfer coefficient", "W/(m² K)")),
      "src/boidrytwin/boiler_house/heaters.py", "film_temperature", ("pelini2008",)),
    F("heaters", "Tube wall and thermal oil per cell (counter-current)",
      (r"C_w \frac{dT_w}{dt} = Q_{g \to w} - h_i A_i (T_w - T_\mathrm{oil})",
       r"m_\mathrm{oil} \frac{dh_\mathrm{oil}}{dt} = \dot m_\mathrm{oil}\,(h_\mathrm{up} - h_\mathrm{oil}) + h_i A_i (T_w - T_\mathrm{oil})"),
      (S(r"C_w", "heat capacity of the tube wall of the cell", "J/K"),
       S(r"Q_{g \to w}", "heat from the gas (radiant section or convective cell)", "W"),
       S(r"h_i A_i", "oil-side coefficient times inner area of the cell", "W/K"),
       S(r"m_\mathrm{oil},\ h_\mathrm{oil}", "oil content and specific enthalpy of the cell", "kg, J/kg"),
       S(r"h_\mathrm{up}", "oil enthalpy of the upstream cell; the return enters the last cell", "J/kg")),
      "src/boidrytwin/boiler_house/model.py", "rhs", ("vdi2010",),
      "Oil enters the last convective cell and leaves heater 1 as the supply, controlled to its set point."),
    F("heaters", "Thermal oil viscosity (Walther)",
      (r"\log_{10}\log_{10}(\nu + 0.7) = A - B\,\log_{10} T",),
      (S(r"\nu", "kinematic viscosity", "mm²/s"),
       S(r"T", "oil temperature", "K"),
       S(r"A,\ B", "fitted through the data sheet's 40 °C and 100 °C values", "–")),
      "src/boidrytwin/properties/thermal_oil.py", "viscosity", ("astm_d341", "shell_s2")),
    # --- control -------------------------------------------------------------------------------
    F("control", "PI controller with back-calculation anti-windup",
      (r"v = K_c\,e + I, \qquad u = \operatorname{sat}(v), \qquad \frac{dI}{dt} = \frac{K_c}{T_i}\,e + \frac{u - v}{T_t}",),
      (S(r"e", "set point − measurement (reverse action)", "unit of the measurement"),
       S(r"K_c,\ T_i", "gain and integral time", "–, s"),
       S(r"T_t", "tracking time (default T_i)", "s"),
       S(r"\operatorname{sat}", "smooth saturation to the output limits", "–")),
      "src/boidrytwin/control/pi.py", "integral_rate", ("astrom_murray",)),
    F("control", "SIMC tuning",
      (r"K_c = \frac{\tau_1}{k\,(\tau_c + \theta)}, \qquad T_i = \min\!\left(\tau_1,\ 4\,(\tau_c + \theta)\right), \qquad \tau_c = \max(\theta,\ 10\ \mathrm{s})",),
      (S(r"k,\ \tau_1,\ \theta", "gain, time constant and dead time of the fitted model", "–, s, s"),
       S(r"\tau_c", "desired closed-loop time constant", "s")),
      "scripts/tune_controllers.py", "simc", ("skogestad2003",)),
    F("control", "Half rule (second order to first order plus dead time)",
      (r"\tau_1' = \tau_1 + \frac{\tau_2}{2}, \qquad \theta' = \theta + \frac{\tau_2}{2}",),
      (S(r"\tau_1 \ge \tau_2", "time constants of the fitted second-order model", "s"),),
      "scripts/tune_controllers.py", "fit", ("skogestad2003",)),
    F("control", "Split range of the drum inlet controller",
      (r"u \le s:\ \ y_\mathrm{bypass} = \frac{s - u}{s},\ \ \dot{m}_\mathrm{dil} = 0; \qquad u \ge s:\ \ y_\mathrm{bypass} = 0,\ \ \dot{m}_\mathrm{dil} = \frac{u - s}{1 - s}\,\dot{m}_{\mathrm{dil},\max}",),
      (S(r"u", "controller output", "0–1"),
       S(r"s", "split value", "–"),
       S(r"y_\mathrm{bypass}", "bypass damper position", "0–1"),
       S(r"\dot{m}_\mathrm{dil}", "dilution air", "kg/s")),
      "src/boidrytwin/control/split_range.py", "split", ("reyeslua2020",)),
    F("control", "Measurement lags (O₂ analyser, drum inlet sensor, draft transmitter)",
      (r"\tau_m\,\frac{dy_m}{dt} = y - y_m",),
      (S(r"y,\ y_m", "true and measured value", "unit of the measurement"),
       S(r"\tau_m", "lag: O₂ 30 s, drum inlet 20 s, mixing chamber pressure 2 s (VERIFY)", "s")),
      "src/boidrytwin/dryer/recirculation.py", "derivatives", ("astrom_murray",),
      "The controllers act on the measured value, so the lag is part of each loop."),
    # --- plant balances ----------------------------------------------------------------------
    F("balances", "Bypass split and mixing before the dryer",
      (r"\dot m_\mathrm{heat} = (1 - y_b)\,\dot m_g, \qquad \dot m_\mathrm{byp} = y_b\,\dot m_g",
       r"h(T_\mathrm{mix}) = \frac{\dot m_\mathrm{heat}\,h(T_\mathrm{heat}) + \dot m_\mathrm{byp}\,h(T_\mathrm{byp}) - Q_\mathrm{duct}}{\dot m_\mathrm{heat} + \dot m_\mathrm{byp}}, \qquad Q_\mathrm{duct} = UA_\mathrm{duct}\,y_b\,(T_\mathrm{byp} - T_a)"),
      (S(r"y_b", "bypass damper position (the share of the gas, no damper characteristic)", "0–1"),
       S(r"T_\mathrm{heat},\ T_\mathrm{byp}", "gas after the last heater and at the bypass start", "K"),
       S(r"UA_\mathrm{duct}", "optional heat loss conductance of the bypass duct", "W/K")),
      "src/boidrytwin/boiler_house/bypass.py", "mix", ("baehr_kabelac",),
      "Exact in mass and enthalpy; leakage and a pressure-driven split are not modelled."),
    F("balances", "Dryer inlet: flue gas plus dilution air (dry gas basis)",
      (r"G = \dot m_\mathrm{fg}\,(1 - w_\mathrm{fg}) + G_\mathrm{air}, \qquad G_\mathrm{air} = \frac{\dot m_\mathrm{air}}{1 + Y_\mathrm{air}}, \qquad Y_\mathrm{in} = \frac{\dot m_\mathrm{fg}\,w_\mathrm{fg} + G_\mathrm{air}\,Y_\mathrm{air}}{G}",
       r"H_\mathrm{in} = \frac{\dot m_\mathrm{fg}\,h_\mathrm{fg}(T_\mathrm{fg}) + G_\mathrm{air}\,h_\mathrm{humid}(T_a, Y_\mathrm{air})}{G}, \qquad \dot Q_\mathrm{supplied} = G\,H_\mathrm{in}"),
      (S(r"\dot m_\mathrm{fg},\ w_\mathrm{fg}", "flue gas mass flow and its water mass fraction", "kg/s, kg/kg"),
       S(r"\dot m_\mathrm{air},\ G_\mathrm{air},\ Y_\mathrm{air}", "dilution air (wet, dry) and its humidity at ambient", "kg/s, kg/kg"),
       S(r"G,\ Y_\mathrm{in},\ H_\mathrm{in}", "dry gas flow, humidity and enthalpy per kg dry gas into cell 1", "kg/s, kg/kg, J/kg"),
       S(r"\dot Q_\mathrm{supplied}", "heat supplied: sensible enthalpy flow relative to 298.15 K", "W")),
      "src/boidrytwin/dryer/model.py", "inlet", ("baehr_kabelac",),
      "With a recirculation the returned gas is mixed in afterwards (recirculation section); the heat supplied keeps this definition."),
    F("balances", "Dryer cell balances (flux form, co-current)",
      (r"\frac{dm_d}{dt} = \dot m_{d,\mathrm{in}} - \dot m_{d,\mathrm{out}}, \qquad \frac{dm_w}{dt} = \dot m_{w,\mathrm{in}} - \dot m_{w,\mathrm{out}} - E \quad \text{(passive and active phase)}",
       r"\frac{dU_s}{dt} = \dot U_\mathrm{in} - \dot U_\mathrm{out} + Q_{gs} + Q_{sh \to s} - E\,h_v(T_s)",
       r"\frac{dH_g}{dt} = G\,(H_{i-1} - H_i) + E\,h_v(T_s) - Q_{gs} - Q_{g \to sh}, \qquad m_g\,\frac{dY_g}{dt} = G\,(Y_{i-1} - Y_i) + E"),
      (S(r"m_d,\ m_w", "dry solids and water of a phase in the cell", "kg"),
       S(r"U_s,\ H_g", "solids and gas enthalpy of the cell (relative to 298.15 K)", "J"),
       S(r"E", "evaporation of the cell", "kg/s"),
       S(r"h_v(T_s)", "vapour enthalpy at the chip temperature", "J/kg"),
       S(r"Q_{gs},\ Q_{sh \to s},\ Q_{g \to sh}", "gas to chips, shell to chips, gas to shell", "W"),
       S(r"m_g,\ Y_g", "constant dry gas hold-up of the cell and its humidity", "kg, kg/kg")),
      "src/boidrytwin/dryer/model.py", "_evaluate", ("sheehan2005", "keey1972"),
      "What leaves a cell enters the next, so mass and energy are conserved by construction."),
    F("balances", "Drum shell node",
      (r"m_{sh} c_{sh}\,\frac{dT_{sh}}{dt} = h_\mathrm{in} A_\mathrm{in} (T_g - T_{sh}) - h_{ws}\,0.25\,A_\mathrm{in}\,\phi_\mathrm{fill}\,(T_{sh} - T_s) - Q_\mathrm{loss}",
       r"\phi_\mathrm{fill} = \min\!\left(1,\ \frac{m_p / \rho_\mathrm{bulk}}{0.05\,V_\mathrm{cell}}\right)"),
      (S(r"m_{sh} c_{sh}", "heat capacity of the shell of the cell", "J/K"),
       S(r"h_\mathrm{in} A_\mathrm{in}", "gas to shell (pipe flow) on the inner area", "W/K"),
       S(r"h_{ws}", "shell to chip contact coefficient (calibration)", "W/(m² K)"),
       S(r"m_p,\ \rho_\mathrm{bulk},\ V_\mathrm{cell}", "passive chips, bulk density, cell volume", "kg, kg/m³, m³"),
       S(r"Q_\mathrm{loss}", "shell to ambient (free convection, radiation, insulation)", "W")),
      "src/boidrytwin/dryer/heat_transfer.py", "shell_loss", ("vdi2010", "churchill1975")),
    F("balances", "Dryer key figures and flags",
      (r"e_\mathrm{spec} = \frac{\dot Q_\mathrm{supplied}}{\sum E}, \qquad x_\mathrm{product} = \frac{\dot m_{w,\mathrm{out}}}{\dot m_{d,\mathrm{out}} + \dot m_{w,\mathrm{out}}}",
       r"\text{heat limited: } T_\mathrm{in} - T_\mathrm{out} \ge 0.9\,(T_\mathrm{in} - T_\mathrm{product}); \qquad \text{condensation risk: } T_\mathrm{out} - T_\mathrm{dew}(Y_\mathrm{out}) < 10\ \mathrm{K}"),
      (S(r"e_\mathrm{spec}", "specific energy per kg of water evaporated", "J/kg"),
       S(r"x_\mathrm{product}", "product moisture, wet basis", "kg/kg"),
       S(r"T_\mathrm{in},\ T_\mathrm{out},\ T_\mathrm{product}", "drum inlet gas, exhaust and product temperature", "K"),
       S(r"T_\mathrm{dew}", "dew point of the exhaust", "K")),
      "src/boidrytwin/dryer/model.py", "diagnostics", ("keey1972", "baehr_kabelac"),
      "The 10 K margin is the scenario key min_dew_point_margin."),
    # --- dryer: transport ------------------------------------------------------------------------
    F("transport", "Residence time without gas (Saeman–Mitchell)",
      (r"\tau = \frac{L}{f(H)\,D\,n\,\tan S}, \qquad f(H) = \pi",),
      (S(r"L,\ D", "drum length and diameter", "m"),
       S(r"n", "speed", "1/s"),
       S(r"S", "drum slope", "rad")),
      "src/boidrytwin/dryer/transport.py", "saeman_mitchell_residence_time", ("saeman1954",)),
    F("transport", "Residence time check (Friedman–Marshall)",
      (r"\tau\,[\mathrm{min}] = \frac{0.23\,L/D}{S\,N^{0.9}}",),
      (S(r"S", "slope", "m/m"),
       S(r"N", "speed", "rpm")),
      "src/boidrytwin/dryer/transport.py", "friedman_marshall_residence_time", ("friedman1949",),
      "Used as a plausibility check only."),
    F("transport", "Flight unloading and curtain fall",
      (r"\dot{m}_{p \to a} = \frac{m_p}{t_p}, \quad t_p = \frac{T_\mathrm{rev}}{f_\mathrm{cap}} - t_\mathrm{fall}; \qquad \dot{m}_{a \to p} = \frac{m_a}{t_\mathrm{fall}}, \quad t_\mathrm{fall} = \sqrt{\frac{2\,h_\mathrm{fall}}{g}}",),
      (S(r"m_p,\ m_a", "chips in the flights (passive) and falling (active)", "kg"),
       S(r"T_\mathrm{rev}", "time of one revolution", "s"),
       S(r"f_\mathrm{cap}", "flight capacity factor (calibration)", "–"),
       S(r"h_\mathrm{fall} = 0.6\,D", "fall height", "m")),
      "src/boidrytwin/dryer/transport.py", "transport_rates", ("schneider2003", "sheehan2005")),
    F("transport", "Axial advance of falling chips with gas drag",
      (r"v_a = \frac{h_\mathrm{fall}\tan S + \tfrac{1}{2}\,a_\mathrm{drag}\,t_\mathrm{fall}^2}{t_\mathrm{fall}}, \qquad a_\mathrm{drag} = C_F\,\frac{\tfrac{1}{2}\,\rho_g u_g^2\,C_D\,A_p}{m_p}",),
      (S(r"C_F", "curtain drag coefficient (calibration)", "–"),
       S(r"C_D = 1", "single-sphere drag coefficient", "–"),
       S(r"\rho_g,\ u_g", "gas density and velocity", "kg/m³, m/s"),
       S(r"A_p,\ m_p", "chip cross-section and mass (grows with moisture)", "m², kg")),
      "src/boidrytwin/dryer/transport.py", "transport_rates", ("baker1992", "sheehan2005")),
    # --- dryer: heat and mass transfer -------------------------------------------------------------
    F("transfer", "Gas–chip heat transfer (single sphere, Gnielinski)",
      (r"\mathrm{Nu} = 2 + \sqrt{\mathrm{Nu}_\mathrm{lam}^2 + \mathrm{Nu}_\mathrm{turb}^2}",
       r"\mathrm{Nu}_\mathrm{lam} = 0.664\,\mathrm{Re}^{1/2}\,\mathrm{Pr}^{1/3}, \qquad \mathrm{Nu}_\mathrm{turb} = \frac{0.037\,\mathrm{Re}^{0.8}\,\mathrm{Pr}}{1 + 2.443\,\mathrm{Re}^{-0.1}\left(\mathrm{Pr}^{2/3} - 1\right)}"),
      (S(r"\mathrm{Re}", "on the chip diameter and the relative gas–chip velocity", "–"),),
      "src/boidrytwin/dryer/heat_transfer.py", "nu_sphere_gnielinski", ("gnielinski1975", "vdi2010")),
    F("transfer", "Single sphere check (Ranz–Marshall)",
      (r"\mathrm{Nu} = 2 + 0.6\,\mathrm{Re}^{1/2}\,\mathrm{Pr}^{1/3}",),
      (S(r"\mathrm{Nu}", "used as a check of the Gnielinski correlation", "–"),),
      "src/boidrytwin/dryer/heat_transfer.py", "nu_sphere_ranz_marshall", ("ranz1952",)),
    F("transfer", "Mass transfer by the Chilton–Colburn analogy",
      (r"k_y = \frac{h}{c_{p,\mathrm{humid}}}\,\mathrm{Le}^{-2/3}, \qquad \mathrm{Le} = 1",),
      (S(r"k_y", "mass transfer coefficient per unit humidity difference", "kg/(m² s)"),
       S(r"c_{p,\mathrm{humid}}", "humid heat of the gas", "J/(kg K)")),
      "src/boidrytwin/dryer/heat_transfer.py", "mass_transfer_coefficient", ("chilton1934",)),
    F("transfer", "Evaporation and characteristic drying curve",
      (r"E = C_a\,k_y A\,\left(Y_\mathrm{sat}(T_s) - Y_g\right) f(\Phi)",
       r"f = 1 \quad (X > X_{cr}), \qquad f = \Phi^n, \quad \Phi = \frac{X - X_e}{X_{cr} - X_e}"),
      (S(r"C_a", "heat transfer multiplier (calibration)", "–"),
       S(r"Y_\mathrm{sat},\ Y_g", "saturation humidity at the chip temperature, gas humidity", "kg/kg dry gas"),
       S(r"X,\ X_{cr},\ X_e", "moisture, critical moisture, equilibrium moisture (dry basis)", "kg/kg"),
       S(r"n", "falling-rate exponent", "–")),
      "src/boidrytwin/dryer/drying.py", "evaporation", ("vanmeel1958", "keey1972"),
      "No condensation onto the chips: a negative driving force gives E = 0."),
    F("transfer", "Gas to shell (pipe flow)",
      (r"\mathrm{Nu} = \max\!\left(0.023\,\mathrm{Re}^{0.8}\,\mathrm{Pr}^{0.4},\ 3.66\right)",),
      (S(r"\mathrm{Re}", "on the drum diameter", "–"),),
      "src/boidrytwin/dryer/heat_transfer.py", "nu_pipe", ("dittus1930",)),
    F("transfer", "Shell to ambient, free convection (Churchill–Chu)",
      (r"\mathrm{Nu} = \left(0.60 + \frac{0.387\,\mathrm{Ra}^{1/6}}{\left[1 + (0.559/\mathrm{Pr})^{9/16}\right]^{8/27}}\right)^2",),
      (S(r"\mathrm{Ra}", "Rayleigh number on the shell diameter", "–"),),
      "src/boidrytwin/dryer/heat_transfer.py", "nu_cylinder_churchill_chu", ("churchill1975",),
      "Plus grey-body radiation; insulation as a series resistance."),
    # --- wood --------------------------------------------------------------------------------------------
    F("wood", "Equilibrium moisture content (Hailwood–Horrobin)",
      (r"X_e = \frac{1800}{W}\left[\frac{K h}{1 - K h} + \frac{K_1 K h + 2 K_1 K_2 K^2 h^2}{1 + K_1 K h + K_1 K_2 K^2 h^2}\right]",),
      (S(r"X_e", "equilibrium moisture content", "%, dry basis"),
       S(r"h", "relative humidity", "–"),
       S(r"W,\ K,\ K_1,\ K_2", "quadratic in the temperature (Wood Handbook Eq. 4-5), data up to 130 °C", "–")),
      "src/boidrytwin/properties/wood.py", "emc", ("woodhandbook2021", "hailwood1946")),
    F("wood", "Heat capacity of dry wood",
      (r"c_{p0} = 0.1031 + 0.003867\,T",),
      (S(r"c_{p0}", "dry wood (Wood Handbook Eq. 4-18a)", "kJ/(kg K)"),
       S(r"T", "temperature", "K")),
      "src/boidrytwin/properties/wood.py", "cp_dry", ("woodhandbook2021",)),
    F("wood", "Heat capacity of moist wood",
      (r"c_p = \frac{c_{p0} + 4.18\,X}{1 + X} + A_c, \qquad A_c = x\,(b_1 + b_2 T + b_3 x)",
       r"b_1 = -0.06191, \quad b_2 = 2.36\cdot 10^{-4}, \quad b_3 = -1.33\cdot 10^{-4}"),
      (S(r"X,\ x = 100\,X", "moisture, dry basis (kg/kg and %), capped at fibre saturation", "kg/kg, %"),
       S(r"A_c", "bound-water correction (Wood Handbook Eq. 4-20)", "kJ/(kg K)")),
      "src/boidrytwin/properties/wood.py", "cp_moist", ("woodhandbook2021",),
      "Free water above fibre saturation is added by the rule of mixtures."),
    F("wood", "Sorption heat of bound water",
      (r"\Delta h_s = \Delta h_0\left(1 - \frac{X}{X_\mathrm{fsp}}\right)^2, \qquad \Delta h_0 = 1.0\ \mathrm{MJ/kg}",),
      (S(r"X_\mathrm{fsp}", "fibre saturation moisture", "kg/kg"),
       S(r"\Delta h_0", "sorption heat of dry wood (VERIFY)", "MJ/kg")),
      "src/boidrytwin/properties/wood.py", "sorption_heat", ("skaar1988",)),
    # --- exhaust recirculation and draft (feature 004) ------------------------------------
    F("recirculation", "Mixing of the returned gas at the drum inlet (dry gas basis)",
      (r"G_\mathrm{drum} = G_\mathrm{in} + G_\mathrm{rec}",
       r"Y_\mathrm{drum} = \frac{G_\mathrm{in} Y_\mathrm{fresh} + G_\mathrm{rec} Y_\mathrm{out}}{G_\mathrm{drum}}, \qquad H_\mathrm{drum} = \frac{G_\mathrm{in} H_\mathrm{fresh} + G_\mathrm{rec} H_\mathrm{out} - \dot Q_\mathrm{duct}}{G_\mathrm{drum}}",
       r"\dot Q_\mathrm{duct} = C\,(T_\mathrm{out} - T_a)\left(1 - e^{-UA/C}\right)"),
      (S(r"G_\mathrm{in},\ G_\mathrm{rec}", "fresh (flue gas + dilution air) and returned dry gas", "kg/s"),
       S(r"Y,\ H", "humidity and enthalpy per kg dry gas", "kg/kg, J/kg"),
       S(r"Y_\mathrm{out},\ H_\mathrm{out}", "gas leaving the last drum cell", "kg/kg, J/kg"),
       S(r"UA,\ C", "return duct conductance and heat capacity flow of the returned gas", "W/K")),
      "src/boidrytwin/dryer/model.py", "_mix", ("baehr_kabelac",),
      "The dry gas composition stays that of the fresh mix; O₂ falls through the added water vapour."),
    F("recirculation", "Fan curve and fan laws",
      (r"\Delta p_\mathrm{fan} = \left[a_0 \left(\frac{n}{n_0}\right)^2 + a_1 \frac{n}{n_0}\,\dot V + a_2 \dot V^2\right] \frac{\rho}{\rho_\mathrm{ref}}, \qquad \dot V = \frac{\dot m_\mathrm{drum}}{\rho}",),
      (S(r"a_0, a_1, a_2", "quadratic through the 3 curve points at nominal speed", "Pa, Pa s/m³, Pa s²/m⁶"),
       S(r"n,\ n_0", "fan speed and nominal speed", "1/s"),
       S(r"\rho,\ \rho_\mathrm{ref}", "gas density at the fan and of air at the curve temperature", "kg/m³")),
      "src/boidrytwin/dryer/gas_path.py", "fan_pressure_rise", ("carolus2013", "bleier1998")),
    F("recirculation", "Flow resistance of the drum path and the stack",
      (r"\Delta p = \Delta p_d\,\frac{\rho_d}{\rho} \left(\frac{\dot m}{\dot m_d}\right)^2",),
      (S(r"\dot m_d,\ \Delta p_d,\ \rho_d", "design point: mass flow, pressure drop, density", "kg/s, Pa, kg/m³"),),
      "src/boidrytwin/dryer/gas_path.py", "resistance", ("idelchik2007",),
      "A constant loss coefficient: drum, cyclone and ducts; stack."),
    F("recirculation", "Recirculation damper characteristic",
      (r"\dot m_\mathrm{rec} = \varphi(s)\,\dot m_{\mathrm{open},d} \sqrt{\frac{\rho\,\Delta p_\mathrm{damper}}{\rho_d\,\Delta p_d}}",),
      (S(r"s", "damper position", "–"),
       S(r"\varphi(s)", "relative flow coefficient, monotone table (PCHIP); φ(0) = leakage", "–"),
       S(r"\dot m_{\mathrm{open},d}", "flow fully open at the design pressure drop", "kg/s")),
      "src/boidrytwin/dryer/gas_path.py", "damper_flow", ("ashrae2020",)),
    F("recirculation", "Mixing chamber pressure and recirculated flow",
      (r"p_\mathrm{mc} = \Delta p_\mathrm{stack}(\dot m_\mathrm{stack}) - \left[\Delta p_\mathrm{fan}(\dot V) - \Delta p_\mathrm{drum}(\dot m_\mathrm{drum})\right]",
       r"\dot m_\mathrm{stack} = G_\mathrm{in}\,(1 + Y_\mathrm{out}), \qquad G_\mathrm{rec}:\ \dot m_\mathrm{rec}\!\left(s,\ \Delta p_\mathrm{fan} - \Delta p_\mathrm{drum}\right) = G_\mathrm{rec}\,(1 + Y_\mathrm{out})"),
      (S(r"p_\mathrm{mc}", "mixing chamber pressure relative to ambient (negative: draft)", "Pa"),
       S(r"\dot m_\mathrm{drum}", "wet gas through the drum, (G_in + G_rec)(1 + Y_out)", "kg/s")),
      "src/boidrytwin/dryer/gas_path.py", "solve", ("idelchik2007", "carolus2013"),
      "Quasi-steady: the recirculated flow is the root of one strictly decreasing equation (brentq)."),
    # --- gas and water ---------------------------------------------------------------------------------
    F("gas", "Heat capacity and enthalpy of gas species (NASA polynomials)",
      (r"\frac{c_p}{R} = a_1 + a_2 T + a_3 T^2 + a_4 T^3 + a_5 T^4",
       r"\frac{h}{R\,T} = a_1 + \frac{a_2 T}{2} + \frac{a_3 T^2}{3} + \frac{a_4 T^3}{4} + \frac{a_5 T^4}{5} + \frac{a_6}{T}"),
      (S(r"a_1 \ldots a_6", "coefficients for two ranges split at 1000 K (GRI-Mech 3.0 data)", "–"),
       S(r"R", "universal gas constant", "J/(mol K)")),
      "src/boidrytwin/properties/gas.py", "cp_molar", ("mcbride2002",)),
    F("gas", "Viscosity of gas mixtures (Wilke)",
      (r"\mu = \sum_i \frac{x_i\,\mu_i}{\sum_j x_j\,\Phi_{ij}}, \qquad \Phi_{ij} = \frac{\left[1 + (\mu_i/\mu_j)^{1/2}\,(M_j/M_i)^{1/4}\right]^2}{\sqrt{8\,(1 + M_i/M_j)}}",),
      (S(r"x_i,\ \mu_i,\ M_i", "mole fraction, viscosity and molar mass of species i", "–, Pa s, kg/mol"),),
      "src/boidrytwin/properties/gas.py", "viscosity", ("wilke1950",)),
    F("gas", "Saturation pressure and humidity of water",
      (r"p_\mathrm{sat} = p_\mathrm{sat}(T) \quad \text{(IAPWS-IF97 region 4, 273.15–647.096 K)}",
       r"Y = \frac{M_\mathrm{H_2O}}{M_\mathrm{dry}}\,\frac{p_w}{p - p_w}"),
      (S(r"Y", "humidity", "kg water / kg dry gas"),
       S(r"p_w,\ p", "partial pressure of water, total pressure", "Pa"),
       S(r"M_\mathrm{dry}", "actual molar mass of the dry gas", "kg/mol")),
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
