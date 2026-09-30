"""Real Chromium acceptance for the saved pressure/fin tradeoff replay.

Run only after integration, in an environment authorized for browser execution:
    python tests/ui_tradeoff_smoke.py --output-dir output

Authoring or compiling this file does not constitute a browser pass. Screenshots
and the results report are produced only by an actual invocation of main(). No
saved result, DOM substitute, or fabricated image stands in for browser QA.
"""
from __future__ import annotations

import argparse
import copy
from http.server import ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import traceback
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
CASES = ("nominal", "pressure_loss", "asymmetric_blockage", "combined_fault")
LOADS = (40, 60, 80)
DESIGNS = tuple(f"n{n}_t{t}" for n in (12, 16, 20) for t in (600, 860, 1200))
DEFAULT = {"design_id": "n16_t860", "case_id": "combined_fault", "heat_load_W": 60}
EXCLUDED = {"n12_t600", "n12_t860"}
REPLAY_ROUTE = re.compile(r"/api/physics/tradeoff(?:\?.*)?$")
HASH = re.compile(r"^[0-9a-f]{64}$")
FAILURE = re.compile(r"失败|不通过|未通过|未满足|不满足|不达标|fail", re.I)


def load_record(candidate, case_id, heat_load):
    records = candidate["cases"][case_id]["heat_load_records"]
    matches = [r for r in records if r["heat_load_W"] == heat_load]
    assert len(matches) == 1, (candidate["design_id"], case_id, heat_load)
    return matches[0]


def assert_envelope(report, selection):
    assert report["schema"] == "aerolab-pressure-fin-replay-v1"
    assert report["execution"] == "verified_research_replay"
    assert report["live_computation"] is False
    assert report["selection"] == selection, report["selection"]
    assert report["selected"]["design_id"] == selection["design_id"]
    assert report["baseline"]["design_id"] == DEFAULT["design_id"]
    fixed = report["selected"]["fixed_60W_combined_criterion"]
    assert fixed["heat_load_W"] == 60 and fixed["case_id"] == "combined_fault"
    assert fixed["raw_mass_temperature_pass"] is False
    assert fixed["Reynolds_qualified_conditional_pass"] is False
    assert fixed["status_is_unchanged_by_display_load_selection"] is True
    for key in ("package_manifest_sha256", "source_model_sha256", "presweep_plan_sha256"):
        assert HASH.fullmatch(report["provenance"][key]), key


def capture_screenshot(page, target, results):
    """Write actual browser pixels as a bounded JPEG; never synthesize them."""
    for quality in (85, 70, 55, 40):
        page.screenshot(path=str(target), type="jpeg", quality=quality, full_page=True)
        if target.is_file() and 0 < target.stat().st_size < 250_000:
            results["screenshots"].append(str(target))
            results.setdefault("screenshot_quality", {})[str(target)] = quality
            return
    raise AssertionError(f"Browser screenshot exceeds250KB cap: {target} ({target.stat().st_size} bytes)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = {
        "status": "running", "flows": [], "page_errors": [], "screenshots": [],
        "saved_selections_checked": [], "browser_execution": "not_started",
    }
    server = thread = browser = page = None
    try:
        sys.path.insert(0, str(ROOT))
        # Direct script invocation must not depend on a namespace package named
        # tests: an unrelated installed regular package could shadow it.
        sys.path.insert(1, str(ROOT / "tests"))
        from aerolab.pressure_fin_replay import read_pressure_fin_replay
        from aerolab.server import Handler
        from ui_nacelle_smoke import wait_for_held_route
        from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright

        expected_cache = {}

        def expected(selection):
            key = tuple(selection[k] for k in ("design_id", "case_id", "heat_load_W"))
            if key not in expected_cache:
                expected_cache[key] = read_pressure_fin_replay(**selection)
                assert_envelope(expected_cache[key], selection)
            return expected_cache[key]

        initial = expected(DEFAULT)
        package_identity = initial["provenance"]["package_manifest_sha256"]
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        with sync_playwright() as p:
            launch = {"headless": True}
            if os.environ.get("AEROLAB_CHROMIUM"):
                launch["executable_path"] = os.environ["AEROLAB_CHROMIUM"]
            browser = p.chromium.launch(**launch)
            results["browser_execution"] = "real_chromium"
            page = browser.new_page(viewport={"width": 1440, "height": 1050}, device_scale_factor=1)
            page.on("pageerror", lambda error: results["page_errors"].append(str(error)))
            live_requests = []
            replay_requests = []

            def observe_request(request):
                path = urlparse(request.url).path
                if path == "/api/physics/evaluate":
                    live_requests.append(request.url)
                if path == "/api/physics/tradeoff":
                    replay_requests.append(request.url)
                    assert request.method == "GET", request.method

            page.on("request", observe_request)

            def screenshot(name):
                capture_screenshot(page, args.output_dir / name, results)

            def selected_controls():
                return {
                    "design_id": page.locator("#tradeoff-design").input_value(),
                    "case_id": page.locator("[data-tradeoff-case][aria-pressed='true']").get_attribute("data-tradeoff-case"),
                    "heat_load_W": int(page.locator("[data-tradeoff-load][aria-pressed='true']").get_attribute("data-tradeoff-load")),
                }

            def assert_points():
                points = page.locator("#tradeoff-scatter svg .tradeoff-point")
                expect(points).to_have_count(9)
                rows = points.evaluate_all("nodes => nodes.map(n => ({design:n.dataset.design, scope:n.dataset.scope, label:n.getAttribute('aria-label') || n.textContent}))")
                assert {r["design"] for r in rows} == set(DESIGNS), rows
                assert {r["design"] for r in rows if r["scope"] == "false"} == EXCLUDED, rows
                for row in rows:
                    assert row["scope"] in ("true", "false"), row
                    if row["design"] in EXCLUDED:
                        assert re.search(r"范围外|超范围|超出|超界|out.of.scope", row["label"], re.I), row

            def assert_display(selection):
                report = expected(selection)
                expect(page.locator("#tradeoff-export")).to_be_enabled(timeout=60000)
                expect(page.locator("#tradeoff-error")).to_be_hidden()
                expect(page.locator("#tradeoff-design")).to_have_value(selection["design_id"])
                expect(page.locator(f"[data-tradeoff-case='{selection['case_id']}']")).to_have_attribute("aria-pressed", "true")
                expect(page.locator(f"[data-tradeoff-load='{selection['heat_load_W']}']")).to_have_attribute("aria-pressed", "true")
                assert selected_controls() == selection
                expect(page.locator("#live-toolbar")).to_be_hidden()
                expect(page.locator("#tradeoff-state")).to_contain_text(re.compile(r"保存|回放|replay", re.I))
                comparison_rows = page.locator("#tradeoff-comparison .tradeoff-compare-row")
                expect(comparison_rows).to_have_count(2)
                for index, candidate in enumerate((report["baseline"], report["selected"])):
                    record = load_record(candidate, selection["case_id"], selection["heat_load_W"])
                    row = comparison_rows.nth(index)
                    expect(row).to_contain_text(f"{candidate['fin_only_aluminum_mass_g']:.2f}")
                    expect(row).to_contain_text(f"{record['required_uniform_base_temperature_C']:.2f}")
                    condition_class = "tradeoff-conditional" if record["selected_scenario_condition_pass"] else "tradeoff-fail"
                    expect(row.locator("p")).to_have_class(condition_class)
                channels = page.locator("#tradeoff-channels .tradeoff-channel")
                candidate = report["selected"]
                case = candidate["cases"][selection["case_id"]]
                assert candidate["geometry"]["N_channels"] == candidate["geometry"]["N_fins"] + 1
                expect(channels).to_have_count(candidate["geometry"]["N_channels"])
                for branch in case["branches"]:
                    item = page.locator(f"#tradeoff-channels .tradeoff-channel[data-index='{branch['index']}']")
                    expect(item).to_have_count(1)
                    expect(item).to_have_attribute("data-blocked", str(branch["blocked"]).lower())
                    value = float(item.get_attribute("data-mass-flow-kg-s"))
                    assert math.isclose(value, branch["mass_flow_kg_s"], rel_tol=1e-12, abs_tol=0), (selection, branch, value)
                    if branch["blocked"]:
                        assert branch["index"] == 1 and value == 0.0, branch
                        expect(item.locator(".channel-value")).to_have_text(re.compile(r"^封闭\s*·\s*0(?:\.0+)?$"))
                    else:
                        expect(item.locator(".channel-value")).to_have_text(f"{branch['mass_flow_kg_s'] * 1000:.3f}")
                expect(page.locator("#tradeoff-channel-note")).to_contain_text("g/s")
                expect(page.locator("#tradeoff-fault-summary")).to_contain_text(f"{case['mass_flow_kg_s'] * 1000:.3f}")
                assert_points()
                return report

            def action_and_check(action, selection):
                with page.expect_response(REPLAY_ROUTE, timeout=60000) as response_info:
                    action()
                response = response_info.value
                assert response.ok, (response.status, response.url)
                params = parse_qs(urlparse(response.url).query)
                for key, value in selection.items():
                    assert params.get(key, [str(DEFAULT[key])]) == [str(value)], (params, selection)
                report = response.json()
                assert_envelope(report, selection)
                assert report["provenance"]["package_manifest_sha256"] == package_identity
                assert report["selected"] == expected(selection)["selected"]
                assert_display(selection)
                return report

            def choose(selection):
                current = selected_controls()
                for key, control in (
                    ("design_id", lambda value: page.locator("#tradeoff-design").select_option(value)),
                    ("case_id", lambda value: page.locator(f"[data-tradeoff-case='{value}']").click()),
                    ("heat_load_W", lambda value: page.locator(f"[data-tradeoff-load='{value}']").click()),
                ):
                    if current[key] != selection[key]:
                        current = {**current, key: selection[key]}
                        action_and_check(lambda: control(selection[key]), current)
                return assert_display(selection)

            with page.expect_response(REPLAY_ROUTE, timeout=60000) as response_info:
                page.goto(url + "/physics#tradeoff", wait_until="networkidle")
            assert_envelope(response_info.value.json(), DEFAULT)
            expect(page.locator("#tab-tradeoff")).to_have_attribute("aria-selected", "true")
            expect(page.locator("#panel-tradeoff")).to_be_visible()
            expect(page.locator("#tradeoff-design option")).to_have_count(9)
            assert_display(DEFAULT)
            assert not live_requests, live_requests
            screenshot("ui-tradeoff-default-desktop.jpg")
            results["flows"].append("Direct /physics#tradeoff opens the verified saved baseline without a live-solve request")

            # The plotted alternatives are keyboard-operable controls as well
            # as persistent evidence points; exercise that route independently
            # of the nine-option select.
            point = page.locator(".tradeoff-point[data-design='n16_t600']")
            point.focus()
            action_and_check(lambda: page.keyboard.press("Enter"), {**DEFAULT, "design_id": "n16_t600"})
            expect(page.locator(".tradeoff-point[data-design='n16_t600']")).to_be_focused()
            results["flows"].append("A focused scatter point selects its saved design with Enter and retains keyboard focus")

            for design in DESIGNS:
                for case_id in CASES:
                    for heat_load in LOADS:
                        selection = {"design_id": design, "case_id": case_id, "heat_load_W": heat_load}
                        choose(selection)
                        results["saved_selections_checked"].append(selection)
            assert len(results["saved_selections_checked"]) == 108
            results["flows"].append("All nine designs, four fault cases and three saved loads match saved masses, temperatures and N+1 branch flows; nine points and two out-of-scope designs remain present")

            light = {"design_id": "n16_t600", "case_id": "combined_fault", "heat_load_W": 60}
            report = choose(light)
            expect(page.locator("#tradeoff-comparison")).to_contain_text("93.56")
            requirement = page.locator("#tradeoff-requirement")
            expect(requirement.locator("strong")).to_contain_text(FAILURE)
            expect(requirement).to_contain_text(re.compile(r"60\s*W"))
            expect(requirement).to_contain_text("93.56")
            def plotted_positions():
                return page.locator("#tradeoff-scatter .tradeoff-point").evaluate_all("""nodes => nodes.map(n => {
                    const circle=n.querySelector('circle');
                    return {design:n.dataset.design,x:circle.getAttribute('cx'),y:circle.getAttribute('cy')};
                })""")
            declared_positions = plotted_positions()
            screenshot("ui-tradeoff-combined-failure-desktop.jpg")
            choose({**light, "heat_load_W": 40})
            expect(page.locator("#tradeoff-comparison")).to_contain_text("70.71")
            expect(requirement.locator("strong")).to_contain_text(FAILURE)
            expect(requirement).to_contain_text(re.compile(r"60\s*W"))
            expect(requirement).to_contain_text("93.56")
            assert plotted_positions() == declared_positions
            expect(page.locator("#tradeoff-scatter")).to_contain_text(re.compile(r"60\s*W"))
            assert load_record(report["selected"], "combined_fault", 60)["thermal_criterion_pass"] is False
            screenshot("ui-tradeoff-lower-load-declared-failure-desktop.jpg")
            choose({**light, "heat_load_W": 80})
            assert plotted_positions() == declared_positions
            results["flows"].append("The lighter n16_t600 fails the declared60W combined fault at93.56°C; the40W preset shows70.71°C without erasing that failure, and40/80W leave the declared60W scatter unchanged")

            for open_case, blocked_case in (("nominal", "asymmetric_blockage"), ("pressure_loss", "combined_fault")):
                open_report = choose({**light, "case_id": open_case})
                open_values = {
                    int(item["index"]): float(item["mass"])
                    for item in page.locator("#tradeoff-channels .tradeoff-channel").evaluate_all(
                        "nodes => nodes.map(n => ({index:n.dataset.index,mass:n.dataset.massFlowKgS}))")
                }
                blocked_report = choose({**light, "case_id": blocked_case})
                a = open_report["selected"]["cases"][open_case]
                b = blocked_report["selected"]["cases"][blocked_case]
                for branch in b["branches"]:
                    actual = float(page.locator(f".tradeoff-channel[data-index='{branch['index']}']").get_attribute("data-mass-flow-kg-s"))
                    if branch["index"] == 1:
                        assert actual == 0.0
                    else:
                        assert math.isclose(actual, open_values[branch["index"]], rel_tol=1e-12, abs_tol=1e-16)
                assert math.isclose(a["mass_flow_kg_s"] - b["mass_flow_kg_s"], open_values[1], rel_tol=1e-12)
                expect(page.locator("#tradeoff-channel-note")).to_contain_text(re.compile(r"不变|不增加|未增加|unchanged", re.I))
            results["flows"].append("Sealing branch1 gives exact zero; at each fixed supply pressure surviving absolute branch flows remain unchanged while total flow drops")

            def download_and_check(selection, name):
                with page.expect_download() as download_info:
                    page.locator("#tradeoff-export").click()
                download = download_info.value
                assert download.failure() is None
                target = args.output_dir / name
                download.save_as(str(target))
                assert 0 < target.stat().st_size < 100_000, target.stat().st_size
                exported = json.loads(target.read_text(encoding="utf-8"))
                assert_envelope(exported, selection)
                assert exported["provenance"] == expected(selection)["provenance"]
                assert exported["selected"] == expected(selection)["selected"]
                assert exported["provenance"]["package_manifest_sha256"] == package_identity
                results.setdefault("downloads", []).append(str(target))
                return exported

            choose(light)
            download_and_check(light, "ui-tradeoff-evidence.json")
            results["flows"].append("Native JSON export matches the displayed selection and manifest/model/plan identity and stays below100KB")

            held = []
            page.route(REPLAY_ROUTE, lambda route: held.append(route))
            old_comparison = page.locator("#tradeoff-comparison").inner_text()
            with page.expect_request(REPLAY_ROUTE):
                page.locator("#tradeoff-design").select_option("n20_t600")
            pending = wait_for_held_route(page, held, "tradeoff cancellation")
            for selector in ("#tradeoff-refresh", "#tradeoff-export", "#tradeoff-design", "[data-tradeoff-case='nominal']", "[data-tradeoff-load='40']"):
                expect(page.locator(selector)).to_be_disabled()
            before_repeated = len(replay_requests)
            # Native .click() respects disabled buttons and cannot launch a
            # second request; do not force Playwright clicks past that guard.
            page.locator("#tradeoff-refresh").evaluate("node => { node.click(); node.click(); }")
            expect(page.locator("#tradeoff-cancel")).to_be_visible()
            assert len(replay_requests) == before_repeated and len(held) == 1
            page.locator("#tradeoff-cancel").click()
            expect(page.locator("#tradeoff-state")).to_contain_text(re.compile(r"取消|cancel", re.I))
            expect(page.locator("#tradeoff-refresh")).to_be_enabled()
            expect(page.locator("#tradeoff-design")).to_have_value(light["design_id"])
            assert selected_controls() == light
            assert page.locator("#tradeoff-comparison").inner_text() == old_comparison
            try:
                pending.abort()
            except PlaywrightError:
                # The browser may already have aborted the request.
                pass
            page.unroute(REPLAY_ROUTE)
            expect(page.locator("#tradeoff-export")).to_be_disabled()
            for _ in range(2):
                action_and_check(lambda: page.locator("#tradeoff-refresh").click(), light)
            download_and_check(light, "ui-tradeoff-recovered-evidence.json")
            results["flows"].append("Held-request cancellation and guarded repeated actions retain the previous displayed selection, disable stale export, then repeated reloads recover")

            def assert_rejected(action, selection, handler, message=None):
                old = page.locator("#tradeoff-comparison").inner_text()
                page.route(REPLAY_ROUTE, handler)
                action()
                expect(page.locator("#tradeoff-error")).to_be_visible()
                if message:
                    expect(page.locator("#tradeoff-error")).to_contain_text(message)
                expect(page.locator("#tradeoff-refresh")).to_be_enabled()
                expect(page.locator("#tradeoff-export")).to_be_disabled()
                assert selected_controls() == selection
                assert page.locator("#tradeoff-comparison").inner_text() == old
                expect(page.locator("#tradeoff-error")).to_contain_text(re.compile(r"上次|保留|旧|previous|stale", re.I))
                expect(page.locator("#tradeoff-state")).to_contain_text(re.compile(r"过期|不可用|未核对|previous|stale", re.I))
                page.unroute(REPLAY_ROUTE)
                action_and_check(lambda: page.locator("#tradeoff-refresh").click(), selection)

            def stale(route):
                route.fulfill(status=503, content_type="application/json", body=json.dumps({"error": "saved package deliberately stale in browser test"}))

            assert_rejected(lambda: page.locator("[data-tradeoff-case='nominal']").click(), light, stale, "stale")

            def mismatch(route):
                response = route.fetch()
                report = copy.deepcopy(response.json())
                report["selection"]["design_id"] = "n20_t600"
                route.fulfill(status=200, content_type="application/json", body=json.dumps(report))

            assert_rejected(lambda: page.locator("#tradeoff-refresh").click(), light, mismatch)

            def claims_live(route):
                response = route.fetch()
                report = copy.deepcopy(response.json())
                report["live_computation"] = True
                route.fulfill(status=200, content_type="application/json", body=json.dumps(report))

            assert_rejected(lambda: page.locator("#tradeoff-refresh").click(), light, claims_live)
            results["flows"].append("Stale-package errors, mismatched response selection and false live-computation claims are rejected without relabeling previous evidence")
            assert not live_requests, live_requests

            page.locator("#tab-flow").click()
            expect(page.locator("#live-toolbar")).to_be_visible()
            page.locator("#tab-flow").focus()
            page.keyboard.press("End")
            expect(page.locator("#tab-tradeoff")).to_be_focused()
            expect(page.locator("#panel-tradeoff")).to_be_visible()
            expect(page).to_have_url(re.compile(r"/physics#tradeoff$"))
            page.go_back()
            expect(page.locator("#panel-flow")).to_be_visible()
            page.go_forward()
            expect(page.locator("#panel-tradeoff")).to_be_visible()
            page.locator("#tab-tradeoff").focus()
            page.keyboard.press("ArrowRight")
            expect(page.locator("#tab-flow")).to_be_focused()
            page.keyboard.press("ArrowLeft")
            expect(page.locator("#tab-tradeoff")).to_be_focused()
            page.keyboard.press("Home")
            expect(page.locator("#tab-flow")).to_be_focused()
            page.keyboard.press("End")
            expect(page.locator("#tab-tradeoff")).to_be_focused()
            assert_display(light)
            results["flows"].append("The fourth tab is the keyboard End target; Home, arrow wrap and browser Back/Forward preserve panel and toolbar state")

            held = []
            page.route(REPLAY_ROUTE, lambda route: held.append(route))
            with page.expect_request(REPLAY_ROUTE):
                page.locator("[data-tradeoff-case='nominal']").click()
            pending = wait_for_held_route(page, held, "tradeoff panel departure")
            page.locator("#tab-channel").click()
            expect(page.locator("#panel-channel")).to_be_visible()
            expect(page.locator("#tradeoff-refresh")).to_be_enabled()
            assert selected_controls() == light
            expect(page.locator("#tradeoff-export")).to_be_disabled()
            try:
                pending.abort()
            except PlaywrightError:
                pass
            page.unroute(REPLAY_ROUTE)
            page.locator("#tab-tradeoff").click()
            action_and_check(lambda: page.locator("#tradeoff-refresh").click(), light)
            results["flows"].append("Leaving the fourth panel aborts a pending selection, preserves the last result and requires a fresh check before export")

            held = []
            page.route(REPLAY_ROUTE, lambda route: held.append(route))
            with page.expect_request(REPLAY_ROUTE):
                page.locator("#tradeoff-refresh").click()
            pending = wait_for_held_route(page, held, "tradeoff navigation")
            page.locator(".site-header nav a[href='/']").click()
            try:
                pending.abort()
            except PlaywrightError:
                pass
            page.unroute(REPLAY_ROUTE)
            page.go_back(wait_until="networkidle")
            expect(page.locator("#panel-tradeoff")).to_be_visible()
            expect(page.locator("#tradeoff-refresh")).to_be_enabled(timeout=60000)
            if not page.locator("#tradeoff-export").is_enabled():
                page.locator("#tradeoff-refresh").click()
            expect(page.locator("#tradeoff-export")).to_be_enabled(timeout=60000)
            assert_display(selected_controls())
            choose(light)
            results["flows"].append("Navigating away with a pending replay and returning with Back restores an enabled, correctly labeled saved-result page")

            page.set_viewport_size({"width": 390, "height": 844})
            expect(page.locator("#panel-tradeoff")).to_be_visible()
            for case_id in CASES:
                choose({**light, "case_id": case_id})
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), case_id
                for chart in ("#tradeoff-scatter",):
                    sizes = page.locator(chart + " svg text").evaluate_all("""nodes => nodes.map(n => {
                      const m=n.getScreenCTM(),size=parseFloat(getComputedStyle(n).fontSize);
                      return {text:n.textContent,px:m ? size*Math.min(Math.hypot(m.a,m.b),Math.hypot(m.c,m.d)) : 0};
                    })""")
                    assert sizes and min(row["px"] for row in sizes) >= 10 - 1e-6, (chart, case_id, sizes)
                    results.setdefault("mobile_svg_rendered_font_sizes", {})[f"{case_id}:{chart}"] = sizes
                branch_labels = page.locator("#tradeoff-channels .channel-label, #tradeoff-channels .channel-value").evaluate_all(
                    "nodes => nodes.map(n => ({text:n.textContent, px:parseFloat(getComputedStyle(n).fontSize)}))")
                assert branch_labels and min(row["px"] for row in branch_labels) >= 10, branch_labels
                screenshot(f"ui-tradeoff-{case_id}-mobile.jpg")
            results["flows"].append("All four faults render at390px without horizontal page overflow; actual transformed SVG labels stay at least10px")
            assert not results["page_errors"], results["page_errors"]
            results["status"] = "passed"
            browser.close()
            browser = None
    except Exception:
        results["status"] = "failed"
        results["traceback"] = traceback.format_exc()
        if page is not None and not page.is_closed():
            try:
                capture_screenshot(page, args.output_dir / "ui-tradeoff-failure.jpg", results)
            except Exception as capture_error:
                results["failure_screenshot_error"] = str(capture_error)
        raise
    finally:
        (args.output_dir / "ui-tradeoff-results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join()
        print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
