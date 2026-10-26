"""The test scenarios: one page per example scenario with drawing, explanation and plots.

Each example in ``examples/`` gets a description in German and English (what it tests, how it
is set up, what to look at, what to expect), the result columns its page plots, the drawing
shown first and the times of its steps (marked in the plots). The values on the page come
from the latest completed run of the scenario; nothing is computed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Text:
    title: str
    summary: str
    purpose: str
    setup: tuple[str, ...]
    watch: tuple[str, ...]
    expect: str


@dataclass(frozen=True)
class Case:
    name: str  # file stem in examples/
    group: str  # dryer | boiler | plant | recirculation | input
    de: Text
    en: Text
    columns: tuple[str, ...] = ()
    diagram: str = "plant"
    steps: tuple[tuple[str, str], ...] = ()  # (ISO time, label)
    tests: tuple[str, ...] = field(default_factory=tuple)

    def text(self, lang: str) -> Text:
        return self.de if lang == "de" else self.en


GROUPS = {
    "dryer": ("Trommeltrockner allein", "Drum dryer alone"),
    "boiler": ("Kesselhaus allein", "Boiler house alone"),
    "plant": ("Gekoppelte Anlage", "Coupled plant"),
    "recirculation": ("Abgasrückführung am Trockner", "Dryer exhaust recirculation"),
    "input": ("Eingabeprüfung", "Input checks"),
}

DRYER_COLUMNS = (
    "drum_inlet_gas_temperature",
    "product_moisture_wet_basis",
    "exhaust_temperature",
    "evaporation_rate",
    "product_temperature",
    "specific_energy",
)
BOILER_COLUMNS = (
    "oil_outlet_temperature",
    "fuel_feed",
    "heat_to_oil",
    "load_fraction",
    "o2_dry_measured",
    "furnace_temperature",
)
PLANT_COLUMNS = (
    "oil_outlet_temperature",
    "fuel_feed",
    "heat_to_oil",
    "drum_inlet_gas_temperature",
    "bypass_position",
    "dilution_air_flow",
    "product_moisture_wet_basis",
    "evaporation_rate",
)
RECIRCULATION_COLUMNS = (
    "mixing_chamber_pressure",
    "recirculation_damper_position",
    "recirculation_share",
    "recirculation_mass_flow",
    "drum_inlet_gas_temperature",
    "drum_inlet_humidity",
    "drum_inlet_x_O2",
    "product_moisture_wet_basis",
    "specific_energy",
)

DRYER_SETUP_DE = (
    "Trommel 20 m × 4 m, 2° Neigung, 4 U/min, 24 Hubschaufeln, Gleichstrom, 20 Zellen",
    "Nasse Hackschnitzel 10 t/h mit 50 % Feuchte bei 10 °C",
    "Umgebung 10 °C, 70 % relative Feuchte",
)
DRYER_SETUP_EN = (
    "Drum 20 m × 4 m, 2° slope, 4 rpm, 24 flights, co-current, 20 cells",
    "Wet chips 10 t/h at 50 % moisture and 10 °C",
    "Ambient 10 °C, 70 % relative humidity",
)
BOILER_SETUP_DE = (
    "Biomassefeuerung 15 MW Brennstoffleistung, Hackschnitzel mit 45 % Feuchte",
    "Erhitzer 1 als Strahlungsteil in der Feuerung, Erhitzer 2 und 3 konvektiv",
    "Thermalöl Shell S2, 60 kg/s, Vorlauf-Sollwert 282 °C; O₂-Sollwert 7 % trocken",
)
BOILER_SETUP_EN = (
    "Biomass furnace 15 MW fuel power, wood chips at 45 % moisture",
    "Heater 1 radiant in the furnace, heaters 2 and 3 convective",
    "Thermal oil Shell S2, 60 kg/s, supply set point 282 °C; O₂ set point 7 % dry",
)

CASES: tuple[Case, ...] = (
    Case(
        "reference_constant", "dryer",
        Text(
            "Referenzfall Trockner",
            "10 t/h nasse Hackschnitzel mit 50 % Feuchte, konstantes Rauchgas, Start mit leerer, kalter Trommel.",
            "Der Grundfall des Trocknermodells. Die Trommel ist zu Beginn leer und kalt; die "
            "Hackschnitzel füllen sie, bis Füllmenge, Temperaturen und Produktfeuchte einen "
            "stationären Zustand erreichen. An diesem Fall werden die Massen- und Energiebilanzen "
            "und der stationäre Zustand gegen eine Handrechnung geprüft.",
            (*DRYER_SETUP_DE,
             "Rauchgas konstant 8 kg/s bei 650 °C (6 % O₂, 12 % H₂O), dazu 2 kg/s Mischluft"),
            ("Anfahren: die Füllmenge steigt, bis das erste Produkt austritt (Verweilzeit)",
             "Trommeleintritt nach der Mischluft, Ablufttemperatur und Produktfeuchte im Beharrungszustand",
             "Spezifischer Energiebedarf je kg verdampftes Wasser"),
            "Nach dem Anfahren laufen alle Größen in einen stationären Zustand. Die Bilanzen "
            "schließen innerhalb der Toleranzen. Ganz am Anfang ist die Abluft nahe am Taupunkt "
            "(eine kurze Warnung zum Taupunktabstand ist normal).",
        ),
        Text(
            "Dryer reference case",
            "10 t/h wet chips at 50 % moisture, constant flue gas, start from an empty, cold drum.",
            "The base case of the dryer model. The drum starts empty and cold; the chips fill it "
            "until hold-up, temperatures and product moisture reach a steady state. The mass and "
            "energy balances and the steady state are checked against a hand calculation here.",
            (*DRYER_SETUP_EN,
             "Flue gas constant 8 kg/s at 650 °C (6 % O₂, 12 % H₂O), plus 2 kg/s dilution air"),
            ("Start-up: the hold-up grows until the first product leaves (residence time)",
             "Drum inlet after the dilution air, exhaust temperature and product moisture at steady state",
             "Specific energy per kg of water evaporated"),
            "After start-up every output settles. The balances close within their tolerances. At "
            "the very start the exhaust is close to its dew point (a short dew point margin "
            "warning is normal).",
        ),
        columns=(*DRYER_COLUMNS, "solids_holdup"), diagram="dryer",
        tests=("tests/validation/test_reference_steady_state.py", "tests/integration/test_balances_close.py"),
    ),
    Case(
        "reference_timeseries", "dryer",
        Text(
            "Referenzfall mit Rauchgas als Zeitreihe",
            "Wie der Referenzfall, das Rauchgas kommt aber aus einer (konstanten) CSV-Zeitreihe.",
            "Prüft, dass die Rauchgasquelle austauschbar ist: eine Zeitreihe mit denselben Werten "
            "muss dasselbe Ergebnis liefern wie die konstante Quelle. Derselbe Lauf ist auch die "
            "Grundlage für den Vergleich mit (synthetischen) Messdaten.",
            (*DRYER_SETUP_DE, "Rauchgas aus tests/data/flue_gas_constant.csv, 2 kg/s Mischluft"),
            ("Die Verläufe sind deckungsgleich mit dem Referenzfall",
             "Vergleich mit Messdaten: Bias und RMSE für Produktfeuchte und Ablufttemperatur"),
            "Gleiche Ergebnisse wie der Referenzfall. Zwischen den Stützstellen der Zeitreihe wird "
            "interpoliert; diese Zeitpunkte tragen die Eingangsqualität „interpolated“ (gezählt als "
            "input_quality_not_good). Mit synthetic_measured.csv verglichen liegen beide Ausgaben "
            "innerhalb der Standardtoleranzen (±1 Prozentpunkt, ±5 K).",
        ),
        Text(
            "Reference case with flue gas as a time series",
            "As the reference case, but the flue gas comes from a (constant) CSV time series.",
            "Checks that the flue gas source can be swapped: a time series with the same values "
            "must give the same result as the constant source. The same run is the basis of the "
            "comparison with (synthetic) measurements.",
            (*DRYER_SETUP_EN, "Flue gas from tests/data/flue_gas_constant.csv, 2 kg/s dilution air"),
            ("The curves coincide with the reference case",
             "Comparison with measurements: bias and RMSE of product moisture and exhaust temperature"),
            "Same results as the reference case. Between the samples of the time series the "
            "input is interpolated; those times carry the input quality 'interpolated' (counted as "
            "input_quality_not_good). Compared with synthetic_measured.csv, both outputs are within "
            "the default tolerances (±1 percentage point, ±5 K).",
        ),
        columns=DRYER_COLUMNS, diagram="dryer",
        tests=("tests/integration/test_interface_timeseries.py", "tests/contract/test_cli_compare.py"),
    ),
    Case(
        "step_feed_moisture", "dryer",
        Text(
            "Sprung der Aufgabefeuchte",
            "Die Aufgabefeuchte springt um 06:00 von 50 % auf 55 %; Start aus dem stationären Zustand.",
            "Zeigt die Dynamik des Trockners: Wie schnell und wie stark reagieren Produktfeuchte, "
            "Ablufttemperatur und Verdampfung auf nassere Hackschnitzel bei gleicher Wärmezufuhr? "
            "Der Lauf beginnt im Beharrungszustand, so dass nur die Wirkung des Sprungs zu sehen ist.",
            (*DRYER_SETUP_DE[:1],
             "Nasse Hackschnitzel 10 t/h, Feuchte aus data/feed_moisture_step.csv: 50 % → 55 % um 06:00",
             "Rauchgas konstant 8 kg/s bei 650 °C, 2 kg/s Mischluft"),
            ("Totzeit bis zur ersten Reaktion am Austritt (Transport durch die Trommel)",
             "Neuer Beharrungswert der Produktfeuchte und der Ablufttemperatur",
             "Die Verdampfung steigt, die Ablufttemperatur fällt"),
            "Die Produktfeuchte steigt nach einer Verzögerung von etwa einer Verweilzeit auf einen "
            "neuen, höheren Wert; die Abluft wird kühler und feuchter. Keine Warnungen.",
        ),
        Text(
            "Feed moisture step",
            "The feed moisture steps from 50 % to 55 % at 06:00; start from steady state.",
            "Shows the dynamics of the dryer: how fast and how much do product moisture, exhaust "
            "temperature and evaporation respond to wetter chips at the same heat input? The run "
            "starts at steady state, so only the effect of the step is seen.",
            (*DRYER_SETUP_EN[:1],
             "Wet chips 10 t/h, moisture from data/feed_moisture_step.csv: 50 % → 55 % at 06:00",
             "Flue gas constant 8 kg/s at 650 °C, 2 kg/s dilution air"),
            ("Delay until the outlet responds (transport through the drum)",
             "New steady values of product moisture and exhaust temperature",
             "Evaporation rises, exhaust temperature falls"),
            "After a delay of about one residence time the product moisture rises to a new, "
            "higher value; the exhaust gets cooler and more humid. No warnings.",
        ),
        columns=(*DRYER_COLUMNS, "exhaust_humidity"), diagram="dryer",
        steps=(("2026-01-01T06:00:00Z", "50 → 55 %"),),
        tests=("tests/validation/test_step_response.py",),
    ),
    Case(
        "heat_limited", "dryer",
        Text(
            "Wärmebegrenzter Trockner",
            "Rauchgas auf 1,5 kg/s reduziert, keine Mischluft: zu wenig Wärme für 10 t/h.",
            "Prüft die Meldung „heat limited“: Das Gas gibt fast sein ganzes nutzbares "
            "Temperaturgefälle ab, die Hackschnitzel werden nicht mehr trocken. Ohne Mischluft "
            "liegt der Trommeleintritt mit 650 °C über dem validierten Bereich (Bereichswarnung).",
            (*DRYER_SETUP_DE, "Rauchgas 1,5 kg/s bei 650 °C, keine Mischluft; Start leer und kalt"),
            ("Schattierte Zeiträume: Meldung heat_limited und Bereichswarnungen",
             "Ablufttemperatur nähert sich der Produkttemperatur",
             "Produktfeuchte bleibt hoch"),
            "Die Meldung heat_limited ist über weite Teile des Laufs aktiv, die Produktfeuchte "
            "bleibt weit über dem Referenzfall. Der Trommeleintritt liegt den ganzen Lauf über "
            "600 °C (Bereichswarnung).",
        ),
        Text(
            "Heat-limited dryer",
            "Flue gas reduced to 1.5 kg/s, no dilution air: too little heat for 10 t/h.",
            "Checks the heat_limited flag: the gas gives up nearly all of its usable temperature "
            "drop and the chips no longer get dry. Without dilution air the drum inlet at 650 °C "
            "is above the validated range (range warning).",
            (*DRYER_SETUP_EN, "Flue gas 1.5 kg/s at 650 °C, no dilution air; empty, cold start"),
            ("Shaded periods: the heat_limited flag and range warnings",
             "Exhaust temperature approaches the product temperature",
             "Product moisture stays high"),
            "The heat_limited flag is active for most of the run and the product moisture stays "
            "far above the reference case. The drum inlet is above 600 °C for the whole run "
            "(range warning).",
        ),
        columns=(*DRYER_COLUMNS, "exhaust_dew_point"), diagram="dryer",
        tests=("tests/integration/test_heat_limited.py",),
    ),
    Case(
        "out_of_range_inlet", "dryer",
        Text(
            "Rauchgas außerhalb des gültigen Bereichs",
            "Rauchgas von 08:00 bis 10:00 mit 950 °C: Trommeleintritt über dem validierten Bereich.",
            "Prüft, dass der Zwilling Eingaben außerhalb des validierten Bereichs rechnet, aber "
            "kennzeichnet: Zeiträume mit Bereichswarnung oder schlechter Eingangsqualität werden in "
            "den Ergebnissen markiert und im Laufprotokoll aufgeführt.",
            (*DRYER_SETUP_DE,
             "Rauchgas aus data/flue_gas_hot_period.csv: 650 °C, von 08:00 bis 10:00 950 °C",
             "2 kg/s Mischluft; Start leer und kalt"),
            ("Heiße Periode 08:00–10:00 im Trommeleintritt und in der Ablufttemperatur",
             "Markierte Zeiträume (out_of_range, Eingangsqualität)",
             "Produkt wird in der heißen Periode trockener und wärmer"),
            "Der Trommeleintritt steigt für zwei Stunden deutlich an, das Produkt wird trockener. "
            "Die Periode trägt eine Bereichswarnung für den Trommeleintritt (über 600 °C) und ist "
            "als out_of_range markiert; danach kehrt der Trockner zum Referenzzustand zurück. Die "
            "interpolierten Zeitpunkte der Zeitreihe tragen die Eingangsqualität „interpolated“.",
        ),
        Text(
            "Flue gas outside the valid range",
            "Flue gas at 950 °C from 08:00 to 10:00: drum inlet above the validated range.",
            "Checks that the twin computes inputs outside the validated range but marks them: "
            "periods with a range warning or poor input quality are flagged in the results and "
            "listed in the run record.",
            (*DRYER_SETUP_EN,
             "Flue gas from data/flue_gas_hot_period.csv: 650 °C, 950 °C from 08:00 to 10:00",
             "2 kg/s dilution air; empty, cold start"),
            ("Hot period 08:00–10:00 in the drum inlet and exhaust temperature",
             "Flagged periods (out_of_range, input quality)",
             "The product gets drier and warmer during the hot period"),
            "The drum inlet rises clearly for two hours and the product gets drier. The period is "
            "carries a range warning for the drum inlet (above 600 °C) and is flagged out_of_range; "
            "afterwards the dryer returns to the reference state. The interpolated times of the "
            "time series carry the input quality 'interpolated'.",
        ),
        columns=DRYER_COLUMNS, diagram="dryer",
        steps=(("2026-01-01T08:00:00Z", "950 °C"), ("2026-01-01T10:00:00Z", "650 °C")),
        tests=("tests/integration/test_edge_cases.py",),
    ),
    Case(
        "boiler_house_only", "boiler",
        Text(
            "Kesselhaus allein",
            "15-MW-Kesselhaus mit drei Thermalölerhitzern, Öl 60 kg/s von 240 auf 282 °C, stationärer Start.",
            "Der Grundfall des Kesselhausmodells ohne Trockner. Der Ölregler hält den Vorlauf über "
            "die Brennstoffzufuhr auf 282 °C, der O₂-Regler die Verbrennungsluft auf 7 % O₂ "
            "trocken. Prüft Verbrennungsrechnung, Wärmeübertragung in den Erhitzern und die "
            "Element- und Energiebilanzen gegen eine Handrechnung.",
            (*BOILER_SETUP_DE, "Ölrücklauf konstant 240 °C, Bypass geschlossen"),
            ("Ölvorlauf auf dem Sollwert 282 °C",
             "Brennstoffzufuhr, Last und Wärme an das Öl im Beharrungszustand",
             "Feuerraumtemperatur und O₂ trocken"),
            "Alle Größen bleiben auf ihrem stationären Wert; Ölvorlauf 282 °C, O₂ 7 %. Keine "
            "Meldungen, alle Bilanzen geschlossen.",
        ),
        Text(
            "Boiler house alone",
            "15 MW boiler house with three thermal oil heaters, oil 60 kg/s from 240 to 282 °C, steady start.",
            "The base case of the boiler house model without the dryer. The oil loop holds the "
            "supply at 282 °C with the fuel feed, the O₂ loop holds the combustion air at 7 % O₂ "
            "dry. Checks combustion, heat transfer in the heaters and the element and energy "
            "balances against a hand calculation.",
            (*BOILER_SETUP_EN, "Oil return constant 240 °C, bypass closed"),
            ("Oil supply on its 282 °C set point",
             "Fuel feed, load and heat to the oil at steady state",
             "Furnace temperature and O₂ dry"),
            "Every output stays at its steady value; oil supply 282 °C, O₂ 7 %. No flags, all "
            "balances closed.",
        ),
        columns=BOILER_COLUMNS, diagram="heaters",
        tests=("tests/validation/test_boiler_hand_balance.py", "tests/validation/test_boiler_settles.py"),
    ),
    Case(
        "oil_demand_step", "boiler",
        Text(
            "Sprung im Ölwärmebedarf",
            "Ölrücklauf fällt um 06:00 von 240 auf 231,6 °C: +20 % Wärmebedarf; der Ölregler fährt nach.",
            "Der Regelungstest des Kesselhauses: Die Verbraucher entnehmen 20 % mehr Wärme, der "
            "Rücklauf wird kälter. Der Ölregler muss die Brennstoffzufuhr erhöhen und den Vorlauf "
            "wieder auf 282 °C bringen; der O₂-Regler führt die Luft nach. Mit diesem Fall wurden "
            "die Reglerparameter (SIMC) geprüft.",
            (*BOILER_SETUP_DE, "Ölrücklauf aus data/oil_return_step.csv: 240 → 231,6 °C um 06:00"),
            ("Einbruch und Ausregeln des Ölvorlaufs nach 06:00",
             "Brennstoffzufuhr an ihrer Obergrenze 2,2 kg/s, mit Brennstoff-Totzeit und Bettträgheit",
             "Last über 100 % nach dem Sprung (schattiert: Bereichswarnung load_fraction)"),
            "Der Vorlauf fällt um etwa 7 K (Minimum 06:04) und ist nach etwa 15 Minuten wieder "
            "innerhalb 0,5 K um 282 °C. Der Ölregler steht dabei rund 10 Minuten an der "
            "Brennstoffgrenze (controller_saturated). Danach läuft die Feuerung bei etwa 114 % "
            "statt 89 % Last: Die 20 % Mehrbedarf übersteigen die Nennleistung, daher die "
            "Bereichswarnung load_fraction bis zum Ende des Laufs.",
        ),
        Text(
            "Oil heat demand step",
            "Oil return drops from 240 to 231.6 °C at 06:00: +20 % heat demand; the oil loop follows.",
            "The control test of the boiler house: the consumers take 20 % more heat and the "
            "return gets colder. The oil loop must raise the fuel feed and bring the supply back to "
            "282 °C; the O₂ loop follows with the air. The controller settings (SIMC) were checked "
            "with this case.",
            (*BOILER_SETUP_EN, "Oil return from data/oil_return_step.csv: 240 → 231.6 °C at 06:00"),
            ("Dip and recovery of the oil supply after 06:00",
             "Fuel feed at its 2.2 kg/s limit, with the feed dead time and the bed inertia",
             "Load above 100 % after the step (shaded: load_fraction range warning)"),
            "The supply dips by about 7 K (minimum at 06:04) and is back within 0.5 K of 282 °C "
            "after about 15 minutes. The oil loop sits at its fuel limit for about 10 minutes "
            "(controller_saturated). Afterwards the furnace runs at about 114 % instead of 89 % "
            "load: the extra 20 % exceed the rated power, hence the load_fraction range warning "
            "until the end of the run.",
        ),
        columns=(*BOILER_COLUMNS, "max_film_temperature"), diagram="heaters",
        steps=(("2026-01-01T06:00:00Z", "+20 %"),),
        tests=("tests/validation/test_controller_steps.py",),
    ),
    Case(
        "plant_reference", "plant",
        Text(
            "Gekoppelte Anlage, Referenz",
            "Das Kesselhaus liefert das Rauchgas für den Trockner; der Trommeleintritt wird auf 540 °C geregelt.",
            "Kesselhaus und Trockner als eine Anlage: Das Rauchgas nach den Erhitzern geht in den "
            "Trockner. Der Trommeleintrittsregler hält 540 °C mit Split-Range über Bypassklappe "
            "(heißer) und Mischluft (kälter). Prüft die Kopplung und die Gesamtbilanzen.",
            (*BOILER_SETUP_DE[:2], *DRYER_SETUP_DE[1:2],
             "Ölvorlauf 282 °C, Rücklauf 240 °C; Trommeleintritt-Sollwert 540 °C"),
            ("Trommeleintritt auf 540 °C, Stellung von Bypass und Mischluft",
             "Ölvorlauf auf 282 °C trotz Kopplung",
             "Produktfeuchte und Verdampfung des Trockners"),
            "Beide Regelkreise halten ihren Sollwert, die Anlage ist stationär. Keine Meldungen, "
            "alle Bilanzen der Anlage geschlossen.",
        ),
        Text(
            "Coupled plant, reference",
            "The boiler house supplies the dryer's flue gas; the drum inlet is controlled to 540 °C.",
            "Boiler house and dryer as one plant: the flue gas after the heaters goes to the "
            "dryer. The drum inlet loop holds 540 °C with a split range over the bypass damper "
            "(hotter) and the dilution air (colder). Checks the coupling and the plant balances.",
            (*BOILER_SETUP_EN[:2], *DRYER_SETUP_EN[1:2],
             "Oil supply 282 °C, return 240 °C; drum inlet set point 540 °C"),
            ("Drum inlet on 540 °C, positions of bypass and dilution air",
             "Oil supply on 282 °C despite the coupling",
             "Product moisture and evaporation of the dryer"),
            "Both loops hold their set points and the plant is steady. No flags, all plant "
            "balances closed.",
        ),
        columns=PLANT_COLUMNS, diagram="plant",
        tests=("tests/contract/test_plant_coupling.py", "tests/integration/test_plant_balances_close.py"),
    ),
    Case(
        "plant_oil_step", "plant",
        Text(
            "Gekoppelte Anlage mit Ölbedarfssprung",
            "Wie die Anlagenreferenz, mit +20 % Ölwärmebedarf um 06:00.",
            "Der Ölbedarfssprung wirkt über die Kopplung bis in den Trockner: Mehr Brennstoff "
            "bedeutet mehr und heißeres Rauchgas nach den Erhitzern. Der Trommeleintrittsregler "
            "muss das mit Bypass und Mischluft ausgleichen.",
            (*BOILER_SETUP_DE[:2], *DRYER_SETUP_DE[1:2],
             "Ölrücklauf 240 → 231,6 °C um 06:00; Trommeleintritt-Sollwert 540 °C"),
            ("Ölvorlauf und Brennstoffzufuhr nach 06:00 (wie im Kesselhausfall)",
             "Rauchgas zum Trockner und Eingriff von Bypass und Mischluft",
             "Trommeleintritt bleibt nahe 540 °C, der Trockner merkt wenig"),
            "Der Ölvorlauf regelt wie im Kesselhausfall aus (Brennstoffgrenze für etwa 10 Minuten, "
            "danach rund 114 % Last mit Bereichswarnung load_fraction). Das zusätzliche Rauchgas wird "
            "über Mischluft und Bypass ausgeglichen; Trommeleintritt und Produktfeuchte ändern sich "
            "nur wenig.",
        ),
        Text(
            "Coupled plant with an oil demand step",
            "As the plant reference, with +20 % oil heat demand at 06:00.",
            "The oil demand step reaches the dryer through the coupling: more fuel means more and "
            "hotter flue gas after the heaters. The drum inlet loop has to balance this with the "
            "bypass and the dilution air.",
            (*BOILER_SETUP_EN[:2], *DRYER_SETUP_EN[1:2],
             "Oil return 240 → 231.6 °C at 06:00; drum inlet set point 540 °C"),
            ("Oil supply and fuel feed after 06:00 (as in the boiler house case)",
             "Flue gas to the dryer and the bypass and dilution air action",
             "The drum inlet stays near 540 °C, the dryer notices little"),
            "The oil supply recovers as in the boiler house case (fuel limit for about 10 minutes, "
            "then about 114 % load with the load_fraction range warning). The extra flue gas is "
            "balanced with dilution air and bypass; drum inlet and product moisture change only a "
            "little.",
        ),
        columns=(*PLANT_COLUMNS[:3], "flue_gas_to_dryer_temperature", *PLANT_COLUMNS[3:]),
        diagram="plant",
        steps=(("2026-01-01T06:00:00Z", "+20 %"),),
        tests=("tests/integration/test_plant_rerun.py",),
    ),
    Case(
        "dryer_recirculation", "recirculation",
        Text(
            "Trockner mit Abgasrückführung",
            "Referenztrockner mit Rückführung: die Rückführklappe hält die Mischkammer auf −200 Pa.",
            "Ein Teil der Abluft wird nach dem Abgasventilator über die Rückführklappe in die "
            "Mischkammer vor der Trommel zurückgeführt. Der Druckregler stellt die Klappe so, dass "
            "in der Mischkammer −200 Pa Unterdruck herrschen. Die Rückführung senkt die "
            "Eintrittstemperatur und den O₂-Gehalt und erhöht die Feuchte am Trommeleintritt.",
            (*DRYER_SETUP_DE,
             "Rauchgas 8 kg/s bei 650 °C, 2 kg/s Mischluft (wie Referenzfall)",
             "Abgasventilator mit Kennlinie, Widerstände von Trommel und Kamin, Rückführklappe; Sollwert −200 Pa"),
            ("Mischkammerdruck auf −200 Pa, Klappenstellung etwa 53 %",
             "Rückführanteil etwa 31 % und rückgeführter Massenstrom",
             "Trommeleintritt kühler (frisch 809 K → gemischt 729 K), feuchter, weniger O₂"),
            "Der Druckregler hält −200 Pa, der Rückführanteil liegt bei etwa 31 %. Die Bilanz des "
            "Rückführkreises schließt. Beispielwerte, keine Anlagendaten.",
        ),
        Text(
            "Dryer with exhaust recirculation",
            "Reference dryer with recirculation: the recirculation damper holds the mixing chamber at −200 Pa.",
            "Part of the exhaust is returned after the exhaust fan through the recirculation "
            "damper into the mixing chamber in front of the drum. The pressure loop sets the damper "
            "so that the mixing chamber is at −200 Pa. Recirculation lowers the inlet temperature "
            "and O₂ and raises the humidity at the drum inlet.",
            (*DRYER_SETUP_EN,
             "Flue gas 8 kg/s at 650 °C, 2 kg/s dilution air (as the reference case)",
             "Exhaust fan with its curve, drum and stack resistances, recirculation damper; set point −200 Pa"),
            ("Mixing chamber pressure on −200 Pa, damper about 53 %",
             "Recirculation share about 31 % and the recirculated mass flow",
             "Drum inlet cooler (fresh 809 K → mixed 729 K), more humid, less O₂"),
            "The pressure loop holds −200 Pa and the recirculation share is about 31 %. The "
            "recirculation loop balance closes. Example values, not plant data.",
        ),
        columns=RECIRCULATION_COLUMNS, diagram="dryer",
        tests=("tests/integration/test_recirculation_run.py", "tests/validation/test_recirculation_hand_mix.py"),
    ),
    Case(
        "plant_recirculation", "recirculation",
        Text(
            "Gekoppelte Anlage mit Abgasrückführung",
            "Anlagenreferenz plus Rückführung: −200 Pa in der Mischkammer, Trommeleintritt 540 °C.",
            "Die vollständige Anlage mit beiden Gaswegreglern: Die Rückführklappe hält den "
            "Unterdruck in der Mischkammer, der Trommeleintrittsregler hält mit Bypass und "
            "Mischluft 540 °C – nun für das gemischte Gas. Rückführung und Mischluft wirken auf "
            "dieselbe Temperatur; die Rückführung spart Wärme.",
            (*BOILER_SETUP_DE[:2], *DRYER_SETUP_DE[1:2],
             "Trommeleintritt-Sollwert 540 °C, Mischkammer-Sollwert −200 Pa",
             "Abgasventilator mit 35 % mehr Druck als im Trocknerfall, damit die Klappe Regelreserve hat"),
            ("Mischkammerdruck −200 Pa bei etwa 49 % Klappenstellung, Rückführanteil etwa 29 %",
             "Trommeleintritt auf 540 °C; Bypass und Mischluft im Vergleich zur Anlagenreferenz",
             "Spezifischer Energiebedarf sinkt gegenüber der Anlagenreferenz (etwa 7,5 → 7,2 MJ/kg)"),
            "Beide Regler halten ihre Sollwerte, die gemeinsame Bilanz schließt. Der spezifische "
            "Energiebedarf liegt unter dem der Anlagenreferenz. Weil der Bypass weiter öffnet, um "
            "das kühlere Mischgas auf 540 °C zu bringen, braucht der Ölkreis mehr Brennstoff: Die "
            "Last liegt mit etwa 102 % knapp über der Nennlast (Bereichswarnung load_fraction über "
            "den ganzen Lauf). Beispielwerte, keine Anlagendaten.",
        ),
        Text(
            "Coupled plant with exhaust recirculation",
            "Plant reference plus recirculation: −200 Pa in the mixing chamber, drum inlet 540 °C.",
            "The complete plant with both gas path loops: the recirculation damper holds the "
            "mixing chamber draft, the drum inlet loop holds 540 °C with bypass and dilution air – "
            "now for the mixed gas. Recirculation and dilution air act on the same temperature; "
            "recirculation saves heat.",
            (*BOILER_SETUP_EN[:2], *DRYER_SETUP_EN[1:2],
             "Drum inlet set point 540 °C, mixing chamber set point −200 Pa",
             "Exhaust fan with 35 % more pressure than in the dryer case, so the damper keeps range"),
            ("Mixing chamber −200 Pa at about 49 % damper, recirculation share about 29 %",
             "Drum inlet on 540 °C; bypass and dilution air compared with the plant reference",
             "Specific energy falls compared with the plant reference (about 7.5 → 7.2 MJ/kg)"),
            "Both loops hold their set points and the joint balance closes. The specific energy "
            "is below that of the plant reference. Because the bypass opens further to bring the "
            "cooler mixed gas to 540 °C, the oil loop needs more fuel: the load is about 102 %, "
            "just above rated (load_fraction range warning for the whole run). Example values, not "
            "plant data.",
        ),
        columns=(*RECIRCULATION_COLUMNS[:5], "oil_outlet_temperature", "bypass_position",
                 "dilution_air_flow", *RECIRCULATION_COLUMNS[5:]),
        diagram="plant",
        tests=("tests/integration/test_plant_recirculation.py",),
    ),
    Case(
        "invalid_flue_gas", "input",
        Text(
            "Ungültige Eingabe",
            "Absichtlich fehlerhaftes Rauchgas: fehlende Einheit, Zusammensetzung 93 %, negativer Massenstrom.",
            "Prüft die Eingabeprüfung: Das Szenario darf nicht gerechnet werden. Jeder Fehler wird "
            "mit Feld, Wert, Grund und erlaubtem Bereich gemeldet, alle auf einmal.",
            ("Rauchgas mass_flow = −1 kg/s", "temperature = \"650\" ohne Einheit",
             "Zusammensetzung summiert sich auf 93 % statt 100 %"),
            ("Die Liste der Fehler unten (direkt aus der Eingabeprüfung des Zwillings)",),
            "Kein Lauf; die Prüfung meldet alle drei Fehler mit ihrer Stelle in der Datei.",
        ),
        Text(
            "Invalid input",
            "Deliberately invalid flue gas: missing unit, composition 93 %, negative mass flow.",
            "Checks the input validation: the scenario must not run. Every problem is reported "
            "with field, value, reason and allowed range, all at once.",
            ("Flue gas mass_flow = −1 kg/s", "temperature = \"650\" without a unit",
             "Composition sums to 93 % instead of 100 %"),
            ("The list of problems below (straight from the twin's validation)",),
            "No run; the validation reports all three problems with their place in the file.",
        ),
        tests=("tests/contract/test_cli_validate.py",),
    ),
)  # fmt: skip

BY_NAME = {c.name: c for c in CASES}
