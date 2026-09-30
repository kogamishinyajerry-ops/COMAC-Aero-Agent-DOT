"""Optional real-browser QA for the focused geometry/thermal/mission workflow.

    python -m pip install playwright==1.62.0
    python -m playwright install chromium
    python tests/ui_cad_smoke.py --output-dir output

Uses the actual stdlib HTTP API and solver. Browser or socket denial is a test
failure/blocker, never a passing UI result. Screenshots are saved for review.
"""
from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aerolab.server import Handler  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import expect, sync_playwright

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results = {'status': 'running', 'errors': [], 'console_errors': [], 'flows': []}
    try:
        with sync_playwright() as playwright:
            launch = {'headless': True}
            if os.environ.get('AEROLAB_CHROMIUM'):
                launch['executable_path'] = os.environ['AEROLAB_CHROMIUM']
            browser = playwright.chromium.launch(**launch)
            page = browser.new_page(viewport={'width': 1440, 'height': 1100}, device_scale_factor=1)
            page.on('pageerror', lambda error: results['errors'].append(str(error)))
            page.on('console', lambda message: results['console_errors'].append(message.text) if message.type == 'error' else None)
            page.goto(f'http://127.0.0.1:{server.server_port}/', wait_until='networkidle')
            expect(page.locator('#guide-provenance')).to_contain_text('回放', timeout=120000)
            page.locator('[data-view="cad"]').click()
            expect(page.locator('#cad-results')).to_be_visible(timeout=120000)
            expect(page.locator('#cad-error')).to_be_hidden()
            expect(page.locator('#guided-view')).to_be_hidden()
            expect(page.locator('.app-layout')).to_be_hidden()
            expect(page.locator('[data-cad-metric="mass_kg"]')).to_contain_text('3.183')
            reference = json.loads(page.locator('#cad-evidence-json').text_content())
            candidate = reference['steady_state_comparison']['candidate']
            assert page.locator('#cad-preview svg').get_attribute('data-geometry-fingerprint') == candidate['metrics']['fingerprint']
            assert candidate['cad']['verification'] == 'verified_brep'
            page.screenshot(path=str(args.output_dir / 'ui-cad-reference.png'), full_page=True)
            results['flows'].append('Reference dimensions, same-geometry preview and actual server metrics with independent CAD evidence')

            page.locator('#cad-preset').select_option('light')
            expect(page.locator('#cad-results')).to_be_hidden()
            expect(page.locator('#cad-apply')).to_be_disabled()
            expect(page.locator('#cad-export-json')).to_be_disabled()
            expect(page.locator('#cad-dirty')).to_be_visible()
            expect(page.locator('#cad-preview svg')).to_be_visible()
            page.locator('#cad-evaluate').click()
            expect(page.locator('#cad-results')).to_be_visible(timeout=120000)
            assert page.locator('#cad-fin_count').input_value() == '31'
            light = json.loads(page.locator('#cad-evidence-json').text_content())['steady_state_comparison']
            assert light['candidate']['metrics']['mass_kg'] < light['reference']['metrics']['mass_kg']
            page.screenshot(path=str(args.output_dir / 'ui-cad-light.png'), full_page=True)
            results['flows'].append('Preset edits invalidate old results and exports; recalculation uses the edited geometry')

            # Preserve a genuine HTTP response, edit away and back while it is in
            # flight, then release it. Equality of the final numeric values must
            # not revive a response from an older edit revision.
            held = []
            page.route('**/api/cad/compare', lambda route: held.append(route))
            page.locator('#cad-fin_count').fill('30')
            with page.expect_request('**/api/cad/compare'):
                page.locator('#cad-evaluate').click()
            page.locator('#cad-fin_count').fill('29')
            page.locator('#cad-fin_count').fill('30')
            assert len(held) == 1
            real_response = held[0].fetch()
            held[0].fulfill(response=real_response)
            expect(page.locator('#cad-evaluate')).to_be_enabled(timeout=120000)
            expect(page.locator('#cad-results')).to_be_hidden()
            expect(page.locator('#cad-apply')).to_be_disabled()
            expect(page.locator('#cad-export-json')).to_be_disabled()
            page.unroute('**/api/cad/compare')
            page.locator('#cad-evaluate').click()
            expect(page.locator('#cad-results')).to_be_visible(timeout=120000)
            results['flows'].append('Late response cannot overwrite a newer edit, including edit-away-and-back to identical values')

            page.locator('#cad-fin_count').fill('43')
            page.locator('#cad-fin_thickness_mm').fill('10')
            page.locator('#cad-evaluate').click()
            expect(page.locator('#cad-error')).to_be_visible(timeout=120000)
            expect(page.locator('#cad-error')).to_contain_text('gap')
            expect(page.locator('#cad-results')).to_be_hidden()
            expect(page.locator('#cad-apply')).to_be_disabled()
            results['flows'].append('Overlapping fins are rejected by the real server with a visible error and no mixed old evidence')

            page.locator('#cad-preset').select_option('reference')
            page.locator('.cad-boundary summary').click()
            page.locator('#cad-mass_flow_kg_s').fill('0.001')
            page.locator('#cad-evaluate').click()
            expect(page.locator('#cad-results')).to_be_visible(timeout=120000)
            expect(page.locator('#cad-applicability-warning')).to_be_visible()
            expect(page.locator('#cad-conclusion')).to_contain_text('不能得出有效')
            assert page.locator('.cad-metric-delta.improved').count() == 0
            invalid = json.loads(page.locator('#cad-evidence-json').text_content())['steady_state_comparison']
            assert invalid['candidate']['thermal']['within_model_limits'] is False
            assert invalid['candidate']['thermal']['interface_temperature_c'] > 150
            page.screenshot(path=str(args.output_dir / 'ui-cad-applicability-warning.png'), full_page=True)
            results['flows'].append('Out-of-range thermal conditions show a prominent warning and suppress favorable design conclusions')

            page.locator('#cad-mass_flow_kg_s').fill('0')
            page.locator('#cad-evaluate').click()
            expect(page.locator('#cad-evaluate')).to_be_enabled(timeout=120000)
            expect(page.locator('[data-cad-metric="base_temperature_c"]')).to_contain_text('无稳态')
            expect(page.locator('#cad-applicability-warning')).to_be_visible()
            results['flows'].append('Zero-flow heat load remains an explicit no-equilibrium result rather than a fabricated temperature')

            page.locator('#cad-mass_flow_kg_s').fill('0.085')
            page.locator('#cad-preset').select_option('dense')
            # Enter from a numeric input exercises normal keyboard form submission.
            page.locator('#cad-fin_count').focus()
            page.locator('#cad-fin_count').press('Enter')
            expect(page.locator('#cad-results')).to_be_visible(timeout=120000)
            expect(page.locator('#cad-applicability-warning')).to_be_hidden()
            with page.expect_download() as download:
                page.locator('#cad-export-json').click()
            download.value.save_as(str(args.output_dir / 'ui-cad-evidence.json'))
            exported = json.loads((args.output_dir / 'ui-cad-evidence.json').read_text(encoding='utf-8'))
            assert exported['steady_state_comparison']['candidate']['geometry']['fin_count'] == 57
            with page.expect_download(timeout=120000) as download:
                page.locator('#cad-export-step').click()
            download.value.save_as(str(args.output_dir / 'ui-cad-heatsink.step'))
            assert b'ISO-10303-21' in (args.output_dir / 'ui-cad-heatsink.step').read_bytes()[:100]
            results['flows'].append('Keyboard submit, matching JSON evidence and genuine current-geometry STEP downloads')

            # On the standard browser CI job no optional kernel is installed;
            # custom numeric designs still calculate but STEP is clearly gated.
            has_kernel = page.request.get(f'http://127.0.0.1:{server.server_port}/api/cad/catalog').json()['kernel']['available']
            if not has_kernel:
                page.locator('#cad-fin_count').fill('56')
                page.locator('#cad-evaluate').click()
                expect(page.locator('#cad-results')).to_be_visible(timeout=120000)
                expect(page.locator('#cad-export-step')).to_be_disabled()
                expect(page.locator('#cad-step-status')).to_contain_text('CadQuery')
                expect(page.locator('#cad-export-json')).to_be_enabled()
                page.locator('#cad-preset').select_option('dense')
                page.locator('#cad-evaluate').click()
                expect(page.locator('#cad-results')).to_be_visible(timeout=120000)
                results['flows'].append('Without CAD kernel custom geometry still computes; STEP availability is accurately disclosed')

            page.locator('#cad-apply').click()
            expect(page.locator('#cad-mission-result')).to_be_visible(timeout=180000)
            expect(page.locator('#cad-error')).to_be_hidden()
            expect(page.locator('#cad-mission-result')).to_contain_text('控制器最高温度')
            expect(page.locator('#cad-mission-result')).to_contain_text('电机最高温度')
            mission = json.loads(page.locator('#cad-evidence-json').text_content())['mission']
            for run in mission.values():
                assert run['meta']['inputs']['cad_geometry']['fin_count'] == 57
                assert run['validation']['fixed_hardware'] is True
                assert run['meta']['model_kind'] == 'cad_controller_motor_split'
                assert all('controller_temperature_c' in row and 'motor_temperature_c' in row for row in run['trace'])
            page.screenshot(path=str(args.output_dir / 'ui-cad-mission.png'), full_page=True)
            results['flows'].append('Full fixed-hardware mission uses split controller/motor nodes and traces actual blower cost')

            page.locator('#cad-mission-ambient').fill('39')
            expect(page.locator('#cad-mission-result')).to_be_hidden()
            assert json.loads(page.locator('#cad-evidence-json').text_content())['mission'] is None
            results['flows'].append('Mission edits remove stale mission evidence without invalidating unchanged geometry evidence')
            page.set_viewport_size({'width': 390, 'height': 844})
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(args.output_dir / 'ui-cad-mobile.png'), full_page=True)
            assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
            results['flows'].append('390px responsive layout has no document-level horizontal overflow')

            page.locator('#guided-mode-button').click()
            expect(page.locator('#guided-view')).to_be_visible()
            expect(page.locator('#cad-view')).to_be_hidden()
            page.locator('[data-guide-step="5"]').click()
            expect(page.locator('#guide-compute-sweep')).to_be_visible()
            page.locator('#guide-open-cad').click()
            expect(page.locator('#cad-view')).to_be_visible()
            page.locator('#expert-mode-button').click()
            expect(page.locator('.app-layout')).to_be_visible()
            expect(page.locator('#cad-view')).to_be_hidden()
            assert page.locator('#provenance').inner_text() == '已存结果回放'
            results['flows'].append('Guide step 6, CAD navigation and expert return preserve independent six-step and legacy results')
            assert not results['errors'], results['errors']
            # The invalid-geometry check intentionally returns HTTP 400.
            unexpected = [item for item in results['console_errors'] if '404' not in item and '400' not in item]
            assert not unexpected, unexpected
            browser.close()
            results['status'] = 'passed'
    except Exception as failure:
        results['status'] = 'failed'
        results['failure'] = str(failure)
        raise
    finally:
        server.shutdown()
        server.server_close()
        (args.output_dir / 'ui-cad-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
