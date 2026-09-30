"""Real Chromium acceptance for the source/physics explanation page.

Run only in an environment authorized for browser execution (GitHub CI here).
Screenshots are actual browser output; no DOM-only substitute is called a pass.
"""
from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aerolab.server import Handler
from aerolab.physics_lab import physics_evidence
from tests.ui_nacelle_smoke import wait_for_held_route


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import expect, sync_playwright
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = {"status": "running", "flows": [], "page_errors": [], "screenshots": []}
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as p:
            launch = {"headless": True}
            if os.environ.get("AEROLAB_CHROMIUM"):
                launch["executable_path"] = os.environ["AEROLAB_CHROMIUM"]
            browser = p.chromium.launch(**launch)
            page = browser.new_page(viewport={"width": 1440, "height": 1050}, device_scale_factor=1)
            page.on("pageerror", lambda error: results["page_errors"].append(str(error)))
            page.goto(url + "/physics", wait_until="networkidle")
            expect(page.locator("#run-state")).to_contain_text("本次计算", timeout=60000)
            expect(page.locator("#error")).to_be_hidden()
            expect(page.locator(".scope")).to_contain_text("仍未验证")
            expect(page.locator("#area-chart .area-row")).to_have_count(4)
            expect(page.locator("#pressure-check")).to_contain_text("−19.20%".replace("−", "-"))
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            expected = physics_evidence()
            def screenshot(name):
                target = args.output_dir / name
                page.screenshot(path=str(target), full_page=True)
                results["screenshots"].append(name)
            screenshot("ui-physics-flow-desktop.png")
            results["flows"].append("Live source areas and conditional errors render with averaging, calibration and physical-validation boundaries")

            page.locator("#tab-channel").click()
            expect(page.locator("#panel-channel")).to_be_visible()
            expect(page.locator("#channel-comparison")).to_contain_text("3.13")
            expect(page.locator("#channel-comparison")).to_contain_text("3.46")
            expect(page.locator("#material-summary")).to_contain_text("52.9")
            screenshot("ui-physics-channel-desktop.png")
            results["flows"].append("Historical same-boundary area/friction tradeoff and mass-consistent material capacity are visible")

            page.locator("#tab-coupling").click()
            expect(page.locator("#panel-coupling")).to_be_visible()
            expect(page.locator("#heat-map svg rect")).to_have_count(17 * 17 + 1)
            for value in [expected["duct"]["thermal"]["outlet_wall_c"]["left"], expected["duct"]["thermal"]["outlet_bulk_c"], expected["duct"]["thermal"]["outlet_wall_c"]["right"]]:
                expect(page.locator("#wall-comparison")).to_contain_text(f"{value:.2f}")
            expect(page.locator("#coupling-answer")).to_contain_text("仍向流体加热")
            expect(page.locator("#verification-grid")).to_contain_text("8.23565")
            expect(page.locator("#verification-grid")).not_to_contain_text("—")
            screenshot("ui-physics-coupling-desktop.png")
            results["flows"].append("Actual finite-volume sample field and unequal-wall temperatures agree with solver; numerical verification remains separate")

            page.go_back()
            expect(page.locator("#panel-channel")).to_be_visible()
            page.go_forward()
            expect(page.locator("#panel-coupling")).to_be_visible()
            page.locator("#tab-coupling").focus()
            page.keyboard.press("Home")
            expect(page.locator("#tab-flow")).to_be_focused()
            expect(page.locator("#panel-flow")).to_be_visible()
            page.keyboard.press("End")
            expect(page.locator("#panel-coupling")).to_be_visible()
            results["flows"].append("Tab keyboard navigation and browser Back/Forward preserve the selected panel")

            for case, phrase in (("equal", "分布恢复对称"), ("one_wall", "绝热壁"), ("balanced", "总热流为零"), ("reversed", "仍向流体加热"), ("zero_flow", "不给出稳态温度"), ("asymmetric", "仍向流体加热")):
                page.locator(f"[data-case='{case}']").click()
                expect(page.locator(f"[data-case='{case}']")).to_have_attribute("aria-pressed", "true", timeout=60000)
                expect(page.locator("#coupling-answer")).to_contain_text(phrase)
                expect(page.locator("#error")).to_be_hidden()
                if case == "zero_flow":
                    expect(page.locator("#heat-map svg")).to_have_count(0)
                    expect(page.locator("#wall-comparison")).to_contain_text("—")
                if case == "reversed":
                    expect(page.locator("#heat-map")).to_contain_text("← 气流方向")
            results["flows"].append("Equal, one-wall, balanced, reversed and zero-flow cases retain correct physical meanings; zero flow never draws fabricated temperature")

            with page.expect_download() as download:
                page.locator("#export").click()
            target = args.output_dir / "ui-physics-evidence.json"
            download.value.save_as(str(target))
            exported = json.loads(target.read_text(encoding="utf-8"))
            assert exported["case"] == "asymmetric"
            assert exported["duct"]["provenance"]["input_sha256"] == expected["duct"]["provenance"]["input_sha256"]
            assert not any(exported["claims"].values())
            assert target.stat().st_size < 100_000
            results["flows"].append("Native evidence download matches displayed case and solver identity, below100KB")

            held = []
            page.route("**/api/physics/evaluate", lambda route: held.append(route))
            with page.expect_request("**/api/physics/evaluate"):
                page.locator("#refresh").click()
            pending = wait_for_held_route(page, held, "physics cancellation")
            expect(page.locator("#refresh")).to_be_disabled()
            expect(page.locator("#export")).to_be_disabled()
            expect(page.locator("[data-case='equal']")).to_be_disabled()
            page.locator("#cancel").click()
            expect(page.locator("#run-state")).to_contain_text("已取消等待")
            expect(page.locator("#refresh")).to_be_enabled()
            pending.abort()
            page.unroute("**/api/physics/evaluate")
            page.locator("#refresh").click()
            expect(page.locator("#run-state")).to_contain_text("本次计算", timeout=60000)
            results["flows"].append("Repeated actions are guarded; cancelled request preserves explicitly old evidence and fresh calculation recovers")

            def fail(route):
                route.fulfill(status=503, content_type="application/json", body=json.dumps({"error": "verification deliberately stale in test"}))
            page.route("**/api/physics/evaluate", fail)
            page.locator("[data-case='equal']").click()
            expect(page.locator("#error")).to_contain_text("stale")
            expect(page.locator("#run-state")).to_contain_text("显示上次计算")
            expect(page.locator("[data-case='asymmetric']")).to_have_attribute("aria-pressed", "true")
            page.unroute("**/api/physics/evaluate")
            page.locator("[data-case='asymmetric']").click()
            expect(page.locator("#error")).to_be_hidden()
            expect(page.locator("#run-state")).to_contain_text("本次计算", timeout=60000)
            results["flows"].append("Stale-evidence/server failure is visible and does not relabel old temperatures as a new case")

            def wrong_case(route):
                response = route.fetch()
                data = response.json()
                data["case"] = "equal"
                route.fulfill(status=200, content_type="application/json", body=json.dumps(data))
            page.route("**/api/physics/evaluate", wrong_case)
            page.locator("#refresh").click()
            expect(page.locator("#error")).to_contain_text("工况不一致")
            expect(page.locator("[data-case='asymmetric']")).to_have_attribute("aria-pressed", "true")
            page.unroute("**/api/physics/evaluate")
            page.locator("#refresh").click()
            expect(page.locator("#run-state")).to_contain_text("本次计算", timeout=60000)
            results["flows"].append("Mismatched response case is rejected before replacing the displayed result")

            held = []
            page.route("**/api/physics/evaluate", lambda route: held.append(route))
            with page.expect_request("**/api/physics/evaluate"):
                page.locator("#refresh").click()
            pending = wait_for_held_route(page, held, "physics navigation")
            page.locator(".site-header nav a[href='/']").click()
            try:
                pending.abort()
            except Exception:
                pass
            page.unroute("**/api/physics/evaluate")
            page.go_back(wait_until="networkidle")
            expect(page.locator("#refresh")).to_be_enabled(timeout=60000)
            if not page.locator("#export").is_enabled():
                page.locator("#refresh").click()
                expect(page.locator("#export")).to_be_enabled(timeout=60000)
            results["flows"].append("Navigate away during pending calculation and Back returns an enabled evidence page")

            page.set_viewport_size({"width": 390, "height": 844})
            for panel in ("flow", "channel", "coupling"):
                page.locator(f"#tab-{panel}").click()
                expect(page.locator(f"#panel-{panel}")).to_be_visible()
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), panel
                screenshot(f"ui-physics-{panel}-mobile.png")
            results["flows"].append("All three panels render on390px mobile without horizontal overflow")
            assert not results["page_errors"], results["page_errors"]
            results["status"] = "passed"
            browser.close()
    except Exception:
        results["status"] = "failed"
        results["traceback"] = traceback.format_exc()
        raise
    finally:
        (args.output_dir / "ui-physics-results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        server.shutdown()
        server.server_close()
        thread.join()
        print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
