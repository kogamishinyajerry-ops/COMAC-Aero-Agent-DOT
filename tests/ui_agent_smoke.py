"""Actual Chromium acceptance for the unified recorded-native-agent demo.

Creates screenshots only from actual browser pixels. Authoring/compiling this
script is not a browser pass. Requires optional Playwright only for QA.
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = {'status': 'running', 'browser_execution': 'not_started', 'flows': [],
               'screenshots': [], 'page_errors': [], 'console_errors': []}
    server = thread = None
    try:
        sys.path.insert(0, str(ROOT))
        from aerolab.agent_replay import read_agent_replay
        from aerolab.server import Handler
        from playwright.sync_api import expect, sync_playwright
        expected = read_agent_replay()
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}'
        with sync_playwright() as p:
            launch = {'headless': True}
            if os.environ.get('AEROLAB_CHROMIUM'):
                launch['executable_path'] = os.environ['AEROLAB_CHROMIUM']
            browser = p.chromium.launch(**launch)
            results['browser_execution'] = 'real_chromium'
            page = browser.new_page(viewport={'width': 1440, 'height': 1050}, device_scale_factor=1)
            page.on('pageerror', lambda error: results['page_errors'].append(str(error)))
            page.on('console', lambda msg: results['console_errors'].append(msg.text) if msg.type == 'error' else None)
            requests = []
            page.on('request', lambda r: requests.append({'url': r.url, 'method': r.method}))

            def no_overflow():
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), page.url

            def screenshot(name):
                target = args.output_dir / name
                for quality in (82, 68, 52, 40):
                    page.screenshot(path=str(target), type='jpeg', quality=quality, full_page=True)
                    if target.stat().st_size < 400_000:
                        results['screenshots'].append(str(target))
                        break
                else:
                    raise AssertionError('Screenshot exceeds 400 KB cap')

            def assert_stage(trial, index):
                expect(page.locator('#agent-workspace')).to_be_visible()
                expect(page.locator('#agent-error')).to_be_hidden()
                expect(page.locator(f'[data-trial="{trial}"]')).to_have_attribute('aria-pressed', 'true')
                expect(page.locator(f'[data-step="{index}"]')).to_have_attribute('aria-current', 'step')
                expect(page.locator('#agent-progress')).to_have_text(f'{index+1:02d} / 06')
                expect(page.locator('#agent-status')).to_contain_text('真实执行记录回放')
                expect(page.locator('#agent-title')).not_to_be_empty()
                assert page.url.endswith(f'#{trial}/{index}'), page.url
                no_overflow()

            page.goto(url + '/agent')
            expect(page.locator('#agent-export')).to_be_enabled(timeout=30000)
            assert_stage('development', 0)
            screenshot('ui-agent-development-start.jpg')
            results['flows'].append('one entry loads verified recorded evidence without live model or compute')

            for trial in ('development', 'heldout'):
                page.locator(f'[data-trial="{trial}"]').click()
                run = expected['runs'][trial]
                for index in range(6):
                    assert_stage(trial, index)
                    text = page.locator('#agent-stage').inner_text()
                    if index == 0:
                        assert str(run['task']['max_fin_mass_g']) in text
                        assert str(run['task']['max_base_temperature_C']) in text
                    if index == 1:
                        assert '质量不满足' in text
                        rejected = next(e for e in run['evaluations'] if e['design_id'] != run['final']['selected_design_id'])
                        assert f"{rejected['fin_only_mass_g']:.2f}" in text
                        assert f"{rejected['required_uniform_base_temperature_C']:.2f}" in text
                    if index == 2:
                        page.locator('.trace-details summary').click()
                        expect(page.locator('.event-list li')).to_have_count(len(run['events']))
                        for row in run['events']:
                            response = page.request.get(url + row['result_href'])
                            assert response.status == 200
                            assert hashlib.sha256(response.body()).hexdigest() == row['result_sha256']
                        page.locator('.trace-details summary').click()
                        screenshot(f'ui-agent-{trial}-tools.jpg')
                    if index == 3:
                        for row in run['final']['case_verification']:
                            assert f"{row['worst_mesh_temperature_C']:.2f}" in text
                        screenshot(f'ui-agent-{trial}-design.jpg')
                    if index == 4:
                        img = page.locator('#agent-stage img')
                        expect(img).to_be_visible()
                        assert img.evaluate('img => img.complete && img.naturalWidth > 0')
                        for kind in ('step', 'stl'):
                            with page.expect_download() as info:
                                page.locator(f'#agent-{kind}-download').click()
                            download = info.value
                            actual = Path(download.path()).read_bytes()
                            identity = run['cad']['downloads'][kind]
                            assert len(actual) == identity['bytes']
                            assert hashlib.sha256(actual).hexdigest() == identity['sha256']
                        screenshot(f'ui-agent-{trial}-cad.jpg')
                    if index == 5:
                        assert '23 / 23' in text
                        assert '一个质量合格候选' in text
                        assert '广泛工程泛化' in text
                        screenshot(f'ui-agent-{trial}-heldout.jpg')
                    if index < 5:
                        page.locator('#agent-next').click()
                results['flows'].append(f'{trial}: all six stages, actual source identities, CAD downloads and scope checked')

            with page.expect_download() as info:
                page.locator('#agent-export').click()
            export = json.loads(Path(info.value.path()).read_text())
            assert export['execution'] == 'recorded_native_assistant_trial'
            assert export['live_computation'] is False
            assert export['selection'] == {'trial': 'heldout', 'step': 5}
            assert export['run']['task'] == expected['runs']['heldout']['task']
            assert export['run']['final'] == expected['runs']['heldout']['final']
            results['flows'].append('export preserves selected trial, exact requirements and terminal evidence')

            page.locator('#agent-reset').click()
            assert_stage('heldout', 0)
            page.locator('[data-step="2"]').click()
            page.locator('[data-step="4"]').click()
            page.go_back()
            assert_stage('heldout', 2)
            page.go_back()
            assert_stage('heldout', 0)
            page.go_forward()
            assert_stage('heldout', 2)
            for _ in range(3):
                page.locator('[data-step="2"]').click()
            assert_stage('heldout', 2)
            page.go_back()
            assert_stage('heldout', 0)  # Repeated clicks must not duplicate history.
            page.locator('[data-step="5"]').click()
            page.locator('#agent-next').click()
            assert_stage('heldout', 0)
            page.locator('[data-trial="development"]').click()
            page.locator('[data-step="5"]').click()
            page.locator('#agent-next').click()
            assert_stage('heldout', 0)
            page.reload()
            assert_stage('heldout', 0)
            results['flows'].append('history, reload, repeated step clicks, reset and heldout handoff')

            for target in ('/nacelle', '/physics', '/experiments#fin'):
                page.locator(f'.site-header a[href="{target}"]').click()
                expect(page.locator('a[href="/agent"]').first).to_be_visible()
                page.go_back()
                assert_stage('heldout', 0)
            results['flows'].append('supporting workspaces have a return path and browser Back retains trial')

            report = expected['links']['report']
            page.goto(url + report)
            expect(page.locator('body')).to_contain_text('原生')
            assert page.evaluate('getComputedStyle(document.body).fontFamily') != '"Times New Roman"'
            page.goto(url + '/agent#development/0')
            expect(page.locator('#agent-export')).to_be_enabled()
            for size in ({'width': 390, 'height': 844}, {'width': 768, 'height': 1024}):
                page.set_viewport_size(size)
                for index in range(6):
                    page.locator(f'[data-step="{index}"]').click()
                    assert_stage('development', index)
                screenshot(f"ui-agent-mobile-{size['width']}.jpg")
            results['flows'].append('real responsive pixels at 390 px and 768 px; six stages no horizontal overflow')

            # Network failures must not show stale results or pretend a solver ran.
            page.route('**/api/agent/replay', lambda route: route.fulfill(status=503, content_type='application/json', body='{"error":"test unavailable"}'))
            page.reload()
            expect(page.locator('#agent-error')).to_be_visible()
            expect(page.locator('#agent-workspace')).to_be_hidden()
            expect(page.locator('#agent-export')).to_be_disabled()
            page.unroute('**/api/agent/replay')
            page.locator('#agent-retry').click()
            expect(page.locator('#agent-export')).to_be_enabled()
            assert_stage('development', 5)
            results['flows'].append('503 failure hides stale results; retry restores verified evidence')

            page.route('**/api/agent/replay', lambda route: route.fulfill(status=200, content_type='application/json', body='{"execution":"live","live_computation":true}'))
            page.reload()
            expect(page.locator('#agent-error')).to_be_visible()
            expect(page.locator('#agent-workspace')).to_be_hidden()
            page.unroute('**/api/agent/replay')
            page.locator('#agent-retry').click()
            expect(page.locator('#agent-export')).to_be_enabled()
            results['flows'].append('wrong execution contract fails closed')

            assert not [r for r in requests if '/api/agent/' in r['url'] and r['method'] != 'GET'], requests
            assert not [r for r in requests if '/api/' in r['url'] and '/agent/' in r['url'] and '/api/agent/replay' not in r['url']], requests
            assert not results['page_errors'], results['page_errors']
            unexpected_console = [e for e in results['console_errors'] if '503' not in e and 'favicon' not in e and '404' not in e]
            assert not unexpected_console, unexpected_console
            results['flows'].append('no JavaScript errors, CSP errors, external services or mutable agent requests')
            results['status'] = 'PASS'
            browser.close()
    except Exception as error:
        results['status'] = 'FAIL'
        results['error'] = str(error)
        results['traceback'] = traceback.format_exc()
        raise
    finally:
        if server:
            server.shutdown()
            server.server_close()
        if thread:
            thread.join(timeout=3)
        (args.output_dir / 'ui-agent-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
