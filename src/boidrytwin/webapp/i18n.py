"""Page language (FR-027): German by default, English on request.

The language comes from the ``lang`` cookie. Texts are written in English in the templates,
``t("…")`` looks up the German text; a text without a German entry stays English (the tests
check that the home page, the navigation and the drawings have every entry). Numbers get a
decimal comma in German.
"""

from __future__ import annotations

import math
from typing import Any

from jinja2 import pass_context
from starlette.requests import Request

LANGS = ("de", "en")
DEFAULT_LANG = "de"

DE: dict[str, str] = {
    # navigation and header
    "Plant twin": "Anlagenzwilling",
    "Runs": "Läufe",
    "Scenarios": "Szenarien",
    "What-if": "Was-wäre-wenn",
    "Queue": "Warteschlange",
    "Formulas": "Formeln",
    "engineer view": "Ingenieur-Ansicht",
    "operator view": "Bediener-Ansicht",
    "Language": "Sprache",
    # home page
    "Digital twin · biomass boiler house and wood chip drum dryer": (
        "Digitaler Zwilling · Biomasse-Kesselhaus und Hackschnitzel-Trommeltrockner"
    ),
    "Simulate the boiler house, the thermal oil supply and the drum dryer as one plant, "
    "try what-if cases and compare with plant data.": (
        "Kesselhaus, Thermalölversorgung und Trommeltrockner als eine Anlage simulieren, "
        "Was-wäre-wenn-Fälle durchspielen und mit Anlagendaten vergleichen."
    ),
    "Working as": "Ansicht",
    "Choose how you work": "Wählen Sie Ihre Ansicht",
    "Engineer": "Ingenieur",
    "scenarios, runs, balances, calibration": "Szenarien, Läufe, Bilanzen, Kalibrierung",
    "Operator": "Bediener",
    "what-if cases against the baseline": "Was-wäre-wenn-Fälle gegen den Basisfall",
    "Oil supply": "Ölvorlauf",
    "set point": "Sollwert",
    "Fuel feed": "Brennstoffzufuhr",
    "load": "Last",
    "Heat to oil": "Wärme an Öl",
    "Drum inlet": "Trommeleintritt",
    "Product moisture": "Produktfeuchte",
    "feed": "Aufgabe",
    "Evaporation": "Verdampfung",
    "Plant at the end of the latest run": "Anlage am Ende des letzten Laufs",
    "active flag(s)": "aktive Meldung(en)",
    "Open the run": "Lauf öffnen",
    "No runs yet": "Noch keine Läufe",
    "Recent runs": "Letzte Läufe",
    "all": "alle",
    "None yet.": "Noch keine.",
    "coupled": "gekoppelt",
    "boiler": "Kesselhaus",
    "dryer": "Trockner",
    "unknown": "unbekannt",
    "What you can do": "Was Sie tun können",
    "plots, balances, warnings and process drawings of every run": (
        "Verläufe, Bilanzen, Warnungen und Prozessbilder jedes Laufs"
    ),
    "change inputs (also as steps over time) and start runs": (
        "Eingaben ändern (auch als Stufen über die Zeit) und Läufe starten"
    ),
    "(engineer)": "(Ingenieur)",
    "change released inputs and compare with the baseline": (
        "freigegebene Eingaben ändern und mit dem Basisfall vergleichen"
    ),
    "running": "laufend",
    "waiting": "wartend",
    "every model formula with its literature": "alle Modellformeln mit Literatur",
    "Runs only on this computer. The view is a convenience, not a sign-in.": (
        "Läuft nur auf diesem Rechner. Die Ansicht ist eine Erleichterung, keine Anmeldung."
    ),
    # drawings
    "Plant overview at": "Anlagenübersicht um",
    "Colour: gas temperature": "Farbe: Gastemperatur",
    "Fuel": "Brennstoff",
    "Feed": "Zufuhr",
    "Moisture": "Feuchte",
    "Furnace + heater 1 (radiant)": "Feuerung + Erhitzer 1 (Strahlung)",
    "O₂ dry": "O₂ trocken",
    "Load": "Last",
    "Air": "Verbrennungsluft",
    "Heater": "Erhitzer",
    "Bypass damper": "Bypassklappe",
    "Flue gas": "Rauchgas",
    "Oil consumers (production)": "Ölverbraucher (Produktion)",
    "supply": "Vorlauf",
    "return": "Rücklauf",
    "Flow": "Durchfluss",
    "Heat": "Wärme",
    "Dilution air": "Mischluft",
    "Drum dryer": "Trommeltrockner",
    "drum inlet": "Trommeleintritt",
    "Product": "Produkt",
    "exhaust": "Abluft",
    "Specific energy": "Spez. Energie",
    "Heat supplied": "Zugeführte Wärme",
    "Exhaust humidity": "Abluftfeuchte",
    "Thermal oil heaters at": "Thermalölerhitzer um",
    "Thermal oil heaters: gas and oil in counter-current": (
        "Thermalölerhitzer: Gas und Öl im Gegenstrom"
    ),
    "gas flows left to right, oil right to left": (
        "Gas strömt von links nach rechts, Öl von rechts nach links"
    ),
    "Thermal oil": "Thermalöl",
    "radiant": "Strahlung",
    "convective": "Konvektion",
    "gas": "Gas",
    "bypass": "Bypass",
    "Oil return": "Ölrücklauf",
    "Oil flow": "Öldurchfluss",
    "Max. film temperature": "Max. Filmtemperatur",
    "Min. oil velocity": "Min. Ölgeschwindigkeit",
    "Colour: gas 100–1000 °C · oil 200–300 °C": "Farbe: Gas 100–1000 °C · Öl 200–300 °C",
    "Drum dryer at": "Trommeltrockner um",
    "Rotary drum dryer (co-current)": "Trommeltrockner (Gleichstrom)",
    "upper band: gas temperature, lower band: chip moisture, per cell": (
        "oberes Band: Gastemperatur, unteres Band: Hackschnitzelfeuchte, je Zelle"
    ),
    "profiles not recorded for this run: shading between inlet and outlet": (
        "Profile für diesen Lauf nicht aufgezeichnet: Verlauf zwischen Ein- und Austritt"
    ),
    "cell": "Zelle",
    "chips": "Hackschnitzel",
    "Flue gas + dilution": "Rauchgas + Mischluft",
    "Wet chips": "Nasse Hackschnitzel",
    "Temperature": "Temperatur",
    "Exhaust flow": "Abluftstrom",
    "Product temperature": "Produkttemperatur",
    "Dry product": "Trockenprodukt",
    "Shell loss": "Mantelverlust",
    "Hold-up": "Füllmenge",
    "gas 100–1000 °C · moisture 0–60 %": "Gas 100–1000 °C · Feuchte 0–60 %",
}


def lang_of(request: Request | None) -> str:
    lang = request.cookies.get("lang") if request is not None else None
    return lang if lang in LANGS else DEFAULT_LANG


def _lang(context: Any) -> str:
    lang = context.get("lang")
    return lang if lang in LANGS else lang_of(context.get("request"))


def translate(text: str, lang: str) -> str:
    return DE.get(text, text) if lang == "de" else text


def number(value: Any, lang: str, digits: int | None = None) -> str:
    """A ``Value`` (with its unit) or a plain number, with a decimal comma in German."""
    if hasattr(value, "text"):
        out = str(value.text)
        if digits is not None and value.value is not None and math.isfinite(value.value):
            out = f"{value.value:.{digits}f} {value.unit}".strip()
    elif value is None or not math.isfinite(float(value)):
        out = "–"
    else:
        out = f"{float(value):.{digits or 0}f}"
    return out.replace(".", ",") if lang == "de" else out


@pass_context
def t(context: Any, text: str) -> str:
    return translate(text, _lang(context))


@pass_context
def num(context: Any, value: Any, digits: int | None = None) -> str:
    return number(value, _lang(context), digits)


@pass_context
def current_lang(context: Any) -> str:
    return _lang(context)


def install(env: Any) -> None:
    env.globals.update(t=t, num=num, current_lang=current_lang, LANGS=LANGS)
