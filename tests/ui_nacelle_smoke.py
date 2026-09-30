"""Actual-browser QA for the X-57 Mod II local assembly reconstruction.

    python tests/ui_nacelle_smoke.py --output-dir output

Uses the real HTTP handler, procedural mesh and thermal network. Screenshots
are actual Chromium output. A denied browser/socket is a blocker, never a pass.
"""
from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
import json
import os
import re
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aerolab.server import Handler  # noqa: E402


def wait_for_held_route(page, held, label, *, timeout_ms=10000):
    """Wait for the route callback, not merely the earlier request event.

    A synchronous Playwright API call must pump its dispatcher while waiting;
    time.sleep or threading.Event.wait would prevent the callback from running.
    The short wait below is condition-based, bounded, and never substitutes for
    any of the UI state assertions after releasing the real server response.
    """
    started = time.monotonic()
    deadline = started + timeout_ms / 1000
    while not held:
        remaining_ms = (deadline - time.monotonic()) * 1000
        if remaining_ms <= 0:
            raise AssertionError(
                f'{label}: request event fired, but route callback did not '
                f'capture a request within {timeout_ms} ms; page={page.url!r}'
            )
        page.wait_for_timeout(min(25, remaining_ms))
    assert len(held) == 1, (
        f'{label}: expected exactly one intercepted request, got {len(held)}; '
        f'urls={[route.request.url for route in held]}'
    )
    return held[0]


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
            launch = {'headless': True, 'args': ['--enable-unsafe-swiftshader']}
            if os.environ.get('AEROLAB_CHROMIUM'):
                launch['executable_path'] = os.environ['AEROLAB_CHROMIUM']
            browser = playwright.chromium.launch(**launch)
            page = browser.new_page(viewport={'width': 1440, 'height': 1100}, device_scale_factor=1)
            page.on('pageerror', lambda error: results['errors'].append(str(error)))
            page.on('console', lambda message: results['console_errors'].append(message.text) if message.type == 'error' else None)
            page.goto(f'http://127.0.0.1:{server.server_port}/nacelle', wait_until='networkidle')
            expect(page.locator('#thermal-results')).to_be_visible(timeout=120000)
            expect(page.locator('#nacelle-error')).to_be_hidden()
            canvas = page.locator('#assembly-canvas')
            expect(canvas).to_have_attribute('data-rendered', 'true')
            def mesh_pixel_coverage():
                coverage = canvas.evaluate('''(canvas) => {
                    const gl=canvas.getContext('webgl');
                    const pixels=new Uint8Array(canvas.width*canvas.height*4);
                    gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
                    let painted=0;for(let i=3;i<pixels.length;i+=16)if(pixels[i]>20)painted++;
                    return {painted_samples:painted,width:canvas.width,height:canvas.height,error:gl.getError()};
                }''')
                assert coverage['error'] == 0, coverage
                assert coverage['painted_samples'] > 500, coverage
                return coverage
            results['mesh_pixel_coverage'] = {'assembled': mesh_pixel_coverage()}
            assert int(canvas.get_attribute('data-component-count')) >= 40
            reference = json.loads(page.locator('#evidence-json').text_content())
            reference_result = reference['evaluation']
            fingerprint = reference_result['metrics']['fingerprint']
            assert canvas.get_attribute('data-geometry-fingerprint') == fingerprint
            assert reference['assembly_fingerprint'] == fingerprint
            assert reference['assembly_provenance']['original_NASA_CAD'] is False
            assert reference['assembly_provenance']['CFD_solved'] is False
            assert reference_result['geometry']['hv_fin_count'] != 43
            expect(page.locator('#heatsink-mass')).not_to_contain_text('—')
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            page.screenshot(path=str(args.output_dir / 'ui-nacelle-assembled.png'), full_page=True)
            results['flows'].append('Real 40+ component WebGL geometry, actual solver metrics and matching fingerprints')

            for mode in ('open', 'cutaway', 'exploded', 'assembled'):
                page.locator(f'button[data-mode="{mode}"]').click()
                expect(canvas).to_have_attribute('data-mode', mode)
                if mode == 'cutaway':
                    for component in ('motor_magnet', 'motor_rotor'):
                        expect(canvas).to_have_attribute('data-clipped-components', re.compile(rf'\b{component}\b'))
                expect(page.locator(f'button[data-mode="{mode}"]')).to_have_attribute('aria-pressed', 'true')
                results['mesh_pixel_coverage'][mode] = mesh_pixel_coverage()
                if mode != 'assembled':
                    page.screenshot(path=str(args.output_dir / f'ui-nacelle-{mode}.png'), full_page=True)
            page.locator('[data-select="cmc_left_hv"]').click()
            expect(page.locator('#part-name')).to_contain_text('左侧 CMC')
            expect(canvas).to_have_attribute('data-mode', 'open')
            expected = reference_result['thermal']['components']['cmc_left_hv']['temperature_c']
            expect(page.locator('#selected-temperature')).to_have_text(f'{expected:.1f}' if reference_result['thermal']['summary']['within_model_limits'] else '超范围')
            page.locator('#show-flow').check()
            page.locator('#show-thermal').check()
            expect(page.locator('#flow-disclaimer')).to_contain_text('不代表 CFD')
            expect(page.locator('#thermal-legend')).to_be_visible()
            page.screenshot(path=str(args.output_dir / 'ui-nacelle-flow-thermal.png'), full_page=True)
            if not reference_result['thermal']['summary']['within_model_limits']:
                expect(page.locator('#color-mode-label')).to_contain_text('热源功率')
                expect(page.locator('#legend-high')).to_contain_text('W')
            results['flows'].append('Assembly, shell removal, geometric clipping, explode and exact node selection; invalid-domain temperature suppressed and colors explicitly show source heat loads')

            before = canvas.get_attribute('data-camera')
            page.locator('#scene').focus()
            page.locator('#scene').press('ArrowLeft')
            page.wait_for_function('(before) => document.querySelector("#assembly-canvas").dataset.camera !== before', arg=before)
            page.locator('#zoom-in').click()
            page.locator('#reset-camera').click()
            bounds = canvas.bounding_box()
            page.mouse.move(bounds['x'] + bounds['width'] * .55, bounds['y'] + bounds['height'] * .52)
            page.mouse.down()
            page.mouse.move(bounds['x'] + bounds['width'] * .55 + 70, bounds['y'] + bounds['height'] * .52 + 22, steps=6)
            page.mouse.up()
            expect(page.locator('#nacelle-error')).to_be_hidden()
            results['flows'].append('Keyboard, drag orbit, zoom and reset camera remain interactive')

            page.locator('#geom-main_inlet_height_mm').fill('30')
            expect(page.locator('#thermal-results')).to_be_hidden()
            expect(page.locator('#stale-banner')).to_be_visible()
            expect(page.locator('#export-json')).to_be_disabled()
            expect(page.locator('#export-step')).to_be_disabled()
            page.locator('#evaluate-button').click()
            expect(page.locator('#thermal-results')).to_be_visible(timeout=120000)
            changed = json.loads(page.locator('#evidence-json').text_content())['evaluation']
            assert changed['geometry']['main_inlet_height_mm'] == 30
            assert changed['metrics']['fingerprint'] != fingerprint
            assert changed['flow']['total_inlet_kg_s'] != reference_result['flow']['total_inlet_kg_s']
            assert changed['thermal']['components']['motor_winding']['temperature_c'] != reference_result['thermal']['components']['motor_winding']['temperature_c']
            assert canvas.get_attribute('data-geometry-fingerprint') == changed['metrics']['fingerprint']
            results['flows'].append('Geometry edit changes actual mesh fingerprint, pressure-flow solution and temperatures; stale exports disabled')

            # Do not accept a response from before an edit-away-and-back revision.
            held = []
            page.route('**/api/nacelle/evaluate', lambda route: held.append(route))
            page.locator('#geom-hv_fin_count').fill('28')
            with page.expect_request('**/api/nacelle/evaluate'):
                page.locator('#evaluate-button').click()
            delayed_route = wait_for_held_route(page, held, 'edit-away-and-back evaluation')
            page.locator('#geom-hv_fin_count').fill('29')
            page.locator('#geom-hv_fin_count').fill('28')
            response = delayed_route.fetch()
            delayed_route.fulfill(response=response)
            expect(page.locator('#evaluate-button')).to_be_enabled(timeout=120000)
            expect(page.locator('#thermal-results')).to_be_hidden()
            expect(page.locator('#export-json')).to_be_disabled()
            page.unroute('**/api/nacelle/evaluate')
            page.locator('#evaluate-button').click()
            expect(page.locator('#thermal-results')).to_be_visible(timeout=120000)
            results['flows'].append('Delayed response discarded after edit-away-and-back, even with identical final parameter values')

            # Stop a pending evaluation, then complete a fresh one.
            held = []
            page.route('**/api/nacelle/evaluate', lambda route: held.append(route))
            with page.expect_request('**/api/nacelle/evaluate'):
                page.locator('#evaluate-button').click()
            cancelled_route = wait_for_held_route(page, held, 'cancelled evaluation')
            expect(page.locator('#evaluate-button')).to_be_disabled()
            page.locator('#cancel-button').click()
            expect(page.locator('#evaluate-button')).to_be_enabled()
            expect(page.locator('#thermal-results')).to_be_hidden()
            expect(page.locator('#export-json')).to_be_disabled()
            cancelled_route.abort()
            page.unroute('**/api/nacelle/evaluate')
            page.locator('#evaluate-button').click()
            expect(page.locator('#thermal-results')).to_be_visible(timeout=120000)
            results['flows'].append('Repeated submit guarded; cancellation discards in-flight work, fresh submit recovers')

            # A response with a wrong fingerprint must never be displayed/exported.
            def mismatched(route):
                response = route.fetch()
                data = response.json()
                data['metrics']['fingerprint'] = 'deliberate-mismatch-for-ui-guard-test'
                route.fulfill(status=200, content_type='application/json', body=json.dumps(data))
            page.route('**/api/nacelle/evaluate', mismatched)
            page.locator('#evaluate-button').click()
            expect(page.locator('#nacelle-error')).to_contain_text('指纹不一致', timeout=120000)
            expect(page.locator('#thermal-results')).to_be_hidden()
            expect(page.locator('#export-json')).to_be_disabled()
            page.unroute('**/api/nacelle/evaluate')
            page.locator('#evaluate-button').click()
            expect(page.locator('#thermal-results')).to_be_visible(timeout=120000)
            expect(page.locator('#nacelle-error')).to_be_hidden()
            results['flows'].append('Deliberately mismatched geometry/thermal fingerprint is rejected visibly, with no usable old result')

            # Navigating away during a pending request must not leave a cached
            # page permanently busy when Back restores it.
            held = []
            page.route('**/api/nacelle/evaluate', lambda route: held.append(route))
            with page.expect_request('**/api/nacelle/evaluate'):
                page.locator('#evaluate-button').click()
            navigation_route = wait_for_held_route(page, held, 'navigate-away evaluation')
            page.locator('.navigation a[href="/"]').click()
            expect(page.locator('#guided-view')).to_be_visible()
            try:
                navigation_route.abort()
            except Exception:
                pass  # Navigation can already have cancelled this request.
            page.unroute('**/api/nacelle/evaluate')
            page.go_back(wait_until='networkidle')
            expect(page.locator('#evaluate-button')).to_be_enabled(timeout=120000)
            if not page.locator('#thermal-results').is_visible():
                page.locator('#evaluate-button').click()
                expect(page.locator('#thermal-results')).to_be_visible(timeout=120000)
            if page.locator('#show-flow').is_checked():
                expect(page.locator('#flow-disclaimer')).to_be_visible()
                expect(page.locator('#flow-disclaimer')).to_contain_text('不代表 CFD')
            results['flows'].append('Navigate-away during a pending request and browser Back recovers an enabled calculation state and any restored flow disclaimer')

            # Browser-native invalid input is prevented; server rejection is explicit.
            page.locator('#geom-hv_fin_count').fill('41')
            page.locator('#evaluate-button').click()
            expect(page.locator('#thermal-results')).to_be_hidden()
            assert not page.locator('#geom-hv_fin_count').evaluate('(input) => input.checkValidity()')
            page.locator('#geom-hv_fin_count').fill('24')
            page.locator('#boundary-details summary').click()
            page.locator('#boundary-airspeed_m_s').fill('0')
            page.locator('#evaluate-button').click()
            expect(page.locator('#thermal-results')).to_be_visible(timeout=120000)
            expect(page.locator('#result-warning')).to_be_visible()
            expect(page.locator('#result-summary')).to_contain_text('无有限稳态')
            expect(page.locator('#selected-temperature')).to_have_text('—')
            zero = json.loads(page.locator('#evidence-json').text_content())['evaluation']
            assert zero['thermal']['summary']['steady_state_exists'] is False
            results['flows'].append('Invalid numeric dimensions blocked; zero ram with heat shows no-equilibrium without fabricated temperatures')

            page.locator('#boundary-airspeed_m_s').fill('39.1')
            # Back may restore bfcache or reload defaults. Make this explicitly
            # custom before checking the no-kernel custom-export gate.
            page.locator('#geom-main_inlet_height_mm').fill('30')
            page.locator('#geom-hv_fin_count').focus()
            page.locator('#geom-hv_fin_count').press('Enter')
            expect(page.locator('#thermal-results')).to_be_visible(timeout=120000)
            final = json.loads(page.locator('#evidence-json').text_content())['evaluation']
            if not final['thermal']['summary']['within_model_limits']:
                expect(page.locator('#result-warning')).to_be_visible()
                expect(page.locator('#result-warning')).to_contain_text('筛查')
            page.locator('#boundary-details summary').click()
            page.locator('#evidence-details summary').click()
            with page.expect_download() as download:
                page.locator('#export-json').click()
            download.value.save_as(str(args.output_dir / 'ui-nacelle-evidence.json'))
            artifact = json.loads((args.output_dir / 'ui-nacelle-evidence.json').read_text(encoding='utf-8'))
            assert artifact['assembly_fingerprint'] == final['metrics']['fingerprint']
            assert artifact['evaluation']['geometry']['hv_fin_count'] == 24
            catalog = page.request.get(f'http://127.0.0.1:{server.server_port}/api/nacelle/catalog').json()
            if catalog['geometry']['kernel_available']:
                with page.expect_download(timeout=180000) as download:
                    page.locator('#export-step').click()
                download.value.save_as(str(args.output_dir / 'ui-nacelle-assembly.step'))
                assert b'ISO-10303-21' in (args.output_dir / 'ui-nacelle-assembly.step').read_bytes()[:100]
            else:
                expect(page.locator('#export-step')).to_be_disabled()
                expect(page.locator('#step-status')).to_contain_text('CadQuery')
            # Baseline cached STEP is available even on the stdlib-only CI job.
            for key in ('main_inlet_height_mm', 'upper_inlet_height_mm', 'hv_fin_count', 'motor_bypass_gap_mm'):
                page.locator(f'#geom-{key}').fill(str(catalog['geometry']['defaults'][key]))
            page.locator('#evaluate-button').click()
            expect(page.locator('#thermal-results')).to_be_visible(timeout=120000)
            expect(page.locator('#export-step')).to_be_enabled()
            expect(page.locator('#step-status')).to_contain_text('缓存 STEP')
            with page.expect_download(timeout=180000) as download:
                page.locator('#export-step').click()
            download.value.save_as(str(args.output_dir / 'ui-nacelle-baseline.step'))
            assert b'ISO-10303-21' in (args.output_dir / 'ui-nacelle-baseline.step').read_bytes()[:100]
            held_step, stale_downloads = [], []
            page.route('**/api/nacelle/step', lambda route: held_step.append(route))
            page.on('download', lambda download: stale_downloads.append(download))
            with page.expect_request('**/api/nacelle/step'):
                page.locator('#export-step').click()
            stale_step_route = wait_for_held_route(page, held_step, 'stale STEP download')
            page.locator('#geom-upper_inlet_height_mm').fill('34')
            response = stale_step_route.fetch()
            stale_step_route.fulfill(response=response)
            expect(page.locator('#step-status')).to_contain_text('丢弃旧版本 STEP')
            assert not stale_downloads
            expect(page.locator('#export-step')).to_be_disabled()
            page.unroute('**/api/nacelle/step')
            page.locator('#evaluate-button').click()
            expect(page.locator('#thermal-results')).to_be_visible(timeout=120000)
            results['flows'].append('Current JSON, cached baseline STEP without a kernel, custom STEP gate, and stale in-flight STEP discarded after edits')
            page.locator('#evidence-details summary').click()

            # A deliberately selected reduced-heat teaching input is distinct
            # from the published full-load case; no hidden green default.
            page.locator('#boundary-details summary').click()
            page.locator('#boundary-preset').select_option('reduced_load_screening')
            expect(page.locator('#boundary-preset-note')).to_contain_text('不是 25% 飞机功率')
            page.locator('#evaluate-button').click()
            expect(page.locator('#thermal-results')).to_be_visible(timeout=120000)
            low_load = json.loads(page.locator('#evidence-json').text_content())['evaluation']
            assert low_load['boundary']['heat_scale'] == .25
            assert low_load['thermal']['summary']['within_model_limits'] is True
            assert low_load['thermal']['summary']['physically_validated'] is False
            expect(page.locator('#selected-temperature')).not_to_contain_text('超范围')
            expect(page.locator('#color-mode-label')).to_have_text('温度着色')
            page.locator('#show-flow').check()
            page.locator('#show-thermal').check()
            expect(page.locator('#thermal-legend')).to_be_visible()
            expect(page.locator('#flow-disclaimer')).to_be_visible()
            expect(page.locator('#flow-disclaimer')).to_contain_text('不代表 CFD')
            page.screenshot(path=str(args.output_dir / 'ui-nacelle-screening-thermal.png'), full_page=True)
            results['flows'].append('Explicit optional 0.25x heat-load teaching case enables in-domain proxy temperatures; never presented as quarter aircraft power or physical validation')
            page.locator('#boundary-details summary').click()

            # A separate leadership story uses six newly solved cases and
            # preserves every workbench field/result while switching scenes.
            workbench_evidence = page.locator('#evidence-json').text_content()
            workbench_fields = page.locator('#nacelle-form input, #boundary-fields input, #boundary-fields select').evaluate_all('(inputs) => inputs.map(input => [input.id, input.value])')
            workbench_camera = canvas.get_attribute('data-camera')
            with page.expect_response('**/api/nacelle/story', timeout=120000) as response:
                page.locator('#start-story').click()
            narrative = response.value.json()
            expect(page.locator('#story-panel')).to_have_attribute('data-step', '0', timeout=120000)
            expect(page.locator('#story-next')).to_be_enabled(timeout=120000)
            expect(page.locator('.inspector')).to_be_hidden()
            expect(page.locator('.design-dock')).to_be_hidden()
            assert narrative['execution'] == 'computed'
            assert narrative['cases']['source_load']['boundary']['heat_scale'] == 1
            assert canvas.get_attribute('data-geometry-fingerprint') == narrative['cases']['source_load']['metrics']['fingerprint']
            page.screenshot(path=str(args.output_dir / 'ui-nacelle-story-01-assembly.png'), full_page=True)
            for index, case_id in enumerate(('source_pressure', 'hot_day', 'more_fins', 'redistributed_cooling', 'redistributed_cooling'), start=1):
                page.locator('#story-next').click()
                expect(page.locator('#story-panel')).to_have_attribute('data-step', str(index), timeout=120000)
                expect(page.locator('#story-next')).to_be_enabled(timeout=120000)
                expect(canvas).to_have_attribute('data-story-case', case_id)
                assert canvas.get_attribute('data-geometry-fingerprint') == narrative['cases'][case_id]['metrics']['fingerprint']
                if index >= 2:
                    expect(page.locator('#story-boundary')).to_contain_text('不是 25% 飞机功率')
                if index in (3, 4):
                    delta = narrative['deltas_vs_hot_day'][case_id]
                    expected_sign = '+' if delta['motor_temperature_c'] > 0 else ''
                    expect(page.locator('#story-visual')).to_contain_text(f"{expected_sign}{delta['motor_temperature_c']:.1f}")
                page.screenshot(path=str(args.output_dir / f'ui-nacelle-story-0{index+1}.png'), full_page=True)
            expect(page.locator('.assembly-workspace')).to_be_hidden()
            expect(page.locator('#story-answer')).to_contain_text('还不可以')
            with page.expect_download() as download:
                page.locator('#export-story').click()
            download.value.save_as(str(args.output_dir / 'ui-nacelle-story-evidence.json'))
            story_export = json.loads((args.output_dir / 'ui-nacelle-story-evidence.json').read_text(encoding='utf-8'))
            assert story_export == narrative
            assert story_export['claims']['physically_validated'] is False
            results['flows'].append('Six-question live story: full-load credibility gate, explicit reduced heat, isolated hot-day perturbation, two independently solved geometry alternatives and uncertainty-qualified decision')
            results['flows'].append('All story geometry fingerprints and displayed deltas agree with actual solver responses; exact full story evidence download')
            page.set_viewport_size({'width': 390, 'height': 844})
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            page.screenshot(path=str(args.output_dir / 'ui-nacelle-story-mobile.png'), full_page=True)
            page.locator('#story-prev').click()
            expect(page.locator('#story-panel')).to_have_attribute('data-step', '4')
            expect(page.locator('.assembly-workspace')).to_be_visible()
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            page.screenshot(path=str(args.output_dir / 'ui-nacelle-story-mobile-model.png'), full_page=True)
            page.set_viewport_size({'width': 1440, 'height': 1100})
            page.locator('#open-workbench').click()
            expect(page.locator('#story-panel')).to_be_hidden()
            expect(page.locator('.inspector')).to_be_visible()
            assert page.locator('#evidence-json').text_content() == workbench_evidence
            assert page.locator('#nacelle-form input, #boundary-fields input, #boundary-fields select').evaluate_all('(inputs) => inputs.map(input => [input.id, input.value])') == workbench_fields
            expect(canvas).to_have_attribute('data-camera', workbench_camera)
            results['flows'].append('Story Back and 390px layouts work without overflow; leaving restores exact workbench inputs, evidence and camera')

            # Leaving while the complete story is computing must discard its
            # delayed response and keep the expert workspace's own evidence.
            held_story = []
            page.route('**/api/nacelle/story', lambda route: held_story.append(route))
            with page.expect_request('**/api/nacelle/story'):
                page.locator('#start-story').click()
            pending_story = wait_for_held_route(page, held_story, 'cancelled engineering story')
            expect(page.locator('#story-next')).to_be_disabled()
            page.locator('#open-workbench').click()
            response = pending_story.fetch()
            pending_story.fulfill(response=response)
            expect(page.locator('#story-panel')).to_be_hidden()
            expect(page.locator('#start-story')).to_be_enabled()
            assert page.locator('#evidence-json').text_content() == workbench_evidence
            page.unroute('**/api/nacelle/story')
            results['flows'].append('Cancelling a pending story rejects its late response without reviving the guided view or replacing workbench evidence')

            # A bad story mesh identity must be refused, and re-entry recovers.
            def wrong_story_mesh(route):
                response = route.fetch()
                data = response.json()
                data['fingerprint'] = 'invalid-story-mesh'
                route.fulfill(status=200, content_type='application/json', body=json.dumps(data))
            page.route('**/api/nacelle/geometry', wrong_story_mesh)
            page.locator('#start-story').click()
            expect(page.locator('#story-request-status')).to_contain_text('指纹不一致', timeout=120000)
            page.locator('#open-workbench').click()
            assert page.locator('#evidence-json').text_content() == workbench_evidence
            page.unroute('**/api/nacelle/geometry')
            page.locator('#start-story').click()
            expect(page.locator('#story-panel')).to_have_attribute('data-step', '0', timeout=120000)
            expect(page.locator('#story-next')).to_be_enabled(timeout=120000)
            expect(page.locator('#story-request-status')).to_be_empty()
            page.locator('#open-workbench').click()
            results['flows'].append('Story rejects a deliberately mismatched mesh fingerprint and recovers cleanly on re-entry')

            page.set_viewport_size({'width': 390, 'height': 844})
            expect(page.locator('#part-name')).to_be_visible()
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            expect(page.locator('#flow-disclaimer')).to_be_visible()
            for key in ('main_inlet_height_mm', 'motor_bypass_gap_mm'):
                assert page.locator(f'#geom-{key}').bounding_box()['width'] >= 75
            page.screenshot(path=str(args.output_dir / 'ui-nacelle-mobile.png'), full_page=True)
            page.set_viewport_size({'width': 1440, 'height': 1100})
            page.locator('.navigation a[href="/"]').click()
            expect(page.locator('#guided-view')).to_be_visible()
            page.go_back(wait_until='networkidle')
            expect(page.locator('#thermal-results')).to_be_visible(timeout=120000)
            results['flows'].append('390px responsive layout has no horizontal overflow; root navigation/back preserves independent views')
            assert not results['errors'], results['errors']
            # HTTP failures that are intentionally induced are recorded but JS errors fail.
            results['status'] = 'passed'
            browser.close()
    except Exception as exc:
        results['status'] = 'failed'
        results['failure'] = str(exc)
        results['failure_traceback'] = traceback.format_exc()
        raise
    finally:
        server.shutdown()
        server.server_close()
        (args.output_dir / 'ui-nacelle-qa.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
