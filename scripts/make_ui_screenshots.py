"""Make the pictures of the single-page interface for the README and docs/webapp.md.

    uv run --extra web --with playwright python scripts/make_ui_screenshots.py

Options: ``--lang de|en`` (default en) and ``--out FOLDER`` (default docs/screenshots).

Starts the app on a spare port with empty run and scenario folders, uses the page like a person
(new scenario, run, pin, step sequence, second run, comparison with measurements, report) and
saves every view as a whole page. Needs Microsoft Edge or Google Chrome; no browser is
downloaded. Also prints what it saw, so it doubles as a check of the whole flow.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO = Path(__file__).parents[1]
PORT = 8791
URL = f"http://127.0.0.1:{PORT}"
RUN_TIMEOUT_MS = 300_000


def start_app(work: Path) -> subprocess.Popen[bytes]:
    (work / "runs").mkdir(parents=True)
    (work / "scenarios").mkdir()
    command = [
        sys.executable, "-m", "boidrytwin", "serve", "--no-browser", "--port", str(PORT),
        "--runs", str(work / "runs"), "--scenarios", str(work / "scenarios"),
        "--examples", str(REPO / "examples"),
    ]  # fmt: skip
    # the log is closed again at once, so that the folder can be removed at the end
    with (work / "server.log").open("w") as log:
        server = subprocess.Popen(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(100):
        try:
            urllib.request.urlopen(URL + "/", timeout=1).read()
            return server
        except OSError:
            time.sleep(0.3)
    server.terminate()
    raise SystemExit("the web app did not start; see " + str(work / "server.log"))


def open_browser(playwright):  # type: ignore[no-untyped-def]
    for channel in ("msedge", "chrome"):
        try:
            return playwright.chromium.launch(channel=channel)
        except Exception:  # try the next browser
            continue
    raise SystemExit("neither Microsoft Edge nor Google Chrome was found")


def field(page: Page, group: str, key: str) -> str:
    return f"[data-group='{group}'] [data-key='{key}']"


def checked(page: Page) -> None:
    """Wait until the service has checked the inputs as they are now."""
    page.wait_for_timeout(900)
    page.wait_for_function(
        "(() => { const e = document.querySelector('#check-state');"
        " return e && e.textContent.trim().length > 0 && !e.textContent.includes('…'); })()"
    )


def run(page: Page, shown_before: str | None) -> str:
    """Press Run and wait for the results of the new run; returns its id line."""
    page.click("#nav-results")
    page.click("#btn-run")
    page.wait_for_function(
        "(before) => { const r = document.querySelector('#results');"
        " return r && !document.querySelector('#progress') && r.dataset.run !== before; }",
        arg=shown_before,
        timeout=RUN_TIMEOUT_MS,
    )
    page.wait_for_timeout(1200)
    return page.get_attribute("#results", "data-run") or ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=REPO / "docs" / "screenshots")
    parser.add_argument("--lang", choices=("de", "en"), default="en")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    with (
        tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp,
        sync_playwright() as playwright,
    ):
        server = start_app(Path(tmp))
        try:
            browser = open_browser(playwright)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900}, color_scheme="light"
            )
            page = context.new_page()
            page.on(
                "console",
                lambda m: problems.append(f"{m.type}: {m.text}") if m.type == "error" else None,
            )
            page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
            page.goto(URL + "/")
            page.wait_for_selector("#nav-set")
            page.click(f"#lang-{args.lang}")

            def shot(name: str) -> None:
                page.wait_for_timeout(500)
                page.screenshot(path=str(args.out / f"ui-{name}.png"), full_page=True)

            # a new scenario from an example, 4 h long
            page.select_option("#new-example", "plant_recirculation")
            page.click("#btn-new")
            page.wait_for_selector("#form details.group")
            checked(page)
            page.fill(field(page, "time", "end") + " input", "2026-01-01T04:00:00Z")
            checked(page)
            first = run(page, None)
            page.click("#btn-pin")

            # the feed moisture steps from 50 % to 55 % after one hour
            page.click("#nav-set")
            moisture = field(page, "product_feed", "moisture_wet_basis")
            page.click(f"{moisture} .marks button")
            page.click(f"{moisture} .steps .row:last-child button")
            page.fill(
                f"{moisture} .steps .row:nth-child(2) input:nth-of-type(1)", "2026-01-01T01:00:00Z"
            )
            page.fill(f"{moisture} .steps .row:nth-child(2) input:nth-of-type(2)", "55")
            checked(page)
            print("check:", page.inner_text("#check-state"))
            page.locator(moisture).scroll_into_view_if_needed()
            shot("set")
            second = run(page, first)
            print("runs:", first, second)
            print(
                "key figures:", page.locator("#kpis .kpi").count(),
                "charts:", page.locator("figure.chart").count(),
                "pinned table:", page.locator("#pins-table").count(),
            )  # fmt: skip
            shot("results")

            page.click("#nav-report")
            page.wait_for_selector("#report-head")
            print("changed inputs in the report:", page.locator("#report-changed tbody tr").count())
            shot("report")
            page.emulate_media(media="print")
            pdf = page.pdf(format="A4")
            page.emulate_media(media="screen")
            print("report pages:", len(re.findall(rb"/Type\s*/Page[^s]", pdf)))

            page.click("#nav-formulas")
            page.wait_for_selector("article.formula")
            print(
                "formulas:", page.locator("article.formula").count(),
                "typeset:", page.locator("math").count(),
                "not typeset:", page.locator("code.fail").count(),
            )  # fmt: skip
            page.fill("#formula-search", "saeman")
            page.wait_for_timeout(300)
            print("formulas for 'saeman':", page.locator("article.formula").count())
            page.fill("#formula-search", "")
            shot("formulas")

            # save, rename, and a comparison with measurements
            page.click("#nav-set")
            page.click("#btn-saveas")
            page.fill("#name-input", "feed_step")
            page.click("#name-ok")
            page.wait_for_function(
                "document.querySelector('#set-badge').textContent.includes('feed_step')"
            )
            checked(page)
            print("saved as:", page.inner_text("#set-badge").strip())
            page.select_option("#new-example", "reference_timeseries")
            page.click("#btn-new")
            page.wait_for_function(
                "document.querySelector('#set-badge').textContent.includes('reference_timeseries')"
            )
            checked(page)
            page.click("#nav-data")
            page.set_input_files(
                "#measured-file", str(REPO / "examples" / "synthetic_measured.csv")
            )
            page.click("#btn-compare")
            page.wait_for_selector("#comparison", timeout=RUN_TIMEOUT_MS)
            page.wait_for_timeout(1200)
            print("compared outputs:", page.locator("#comparison-outputs tbody tr").count())
            shot("data")
            browser.close()
        finally:
            server.terminate()
            server.wait(timeout=15)
    print("problems:", len(problems))
    for problem in problems:
        print("  ", problem[:300])
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
