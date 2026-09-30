"""Real-browser acceptance for qualified, integrity-checked experiment replays.

Only run in an environment authorized for Chromium (the repository CI).
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
from aerolab.experimental_evidence import read_experimental_evidence
from aerolab.fin_experimental_evidence import read_fin_experimental_evidence
from tests.ui_nacelle_smoke import wait_for_held_route


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import expect, sync_playwright
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = {'status': 'running', 'flows': [], 'page_errors': [], 'screenshots': []}
    url = f'http://127.0.0.1:{server.server_port}'
    expected = read_experimental_evidence()
    expected_fin = read_fin_experimental_evidence()
    try:
        with sync_playwright() as p:
            launch = {'headless': True}
            if os.environ.get('AEROLAB_CHROMIUM'):
                launch['executable_path'] = os.environ['AEROLAB_CHROMIUM']
            browser = p.chromium.launch(**launch)
            page = browser.new_page(viewport={'width': 1440, 'height': 1050}, device_scale_factor=1)
            page.on('pageerror', lambda error: results['page_errors'].append(str(error)))
            def screenshot(name):
                page.screenshot(path=str(args.output_dir / name), full_page=True)
                results['screenshots'].append(name)
            page.goto(url + '/physics', wait_until='networkidle')
            expect(page.locator("a[href='/experiments']")).to_be_visible(timeout=60000)
            page.locator("a[href='/experiments']").click()
            expect(page.locator('#experiment-status')).to_contain_text('已核对的研究回放', timeout=60000)
            expect(page.locator('#run-count')).to_have_text('32')
            expect(page.locator('#fitted-count')).to_have_text('0')
            expect(page.locator('#mean-residual')).to_have_text(f"{expected['comparison']['all_rows_mean_absolute_residual_theta'] * 100:.2f}")
            expect(page.locator('#max-residual')).to_have_text(f"{expected['comparison']['all_rows_maximum_absolute_residual_theta'] * 100:.2f}")
            expect(page.locator('#comparison-chart circle')).to_have_count(32)
            expect(page.locator('#source-rows tr')).to_have_count(32)
            expect(page.locator('#source-rows td', has_text='未给出')).to_have_count(8)
            expect(page.locator('#residual-meaning')).to_contain_text('31 / 32')
            expect(page.locator('#numerical-summary')).to_contain_text('11 / 11')
            expect(page.locator('.scope')).to_contain_text('不能判为物理验证通过')
            expect(page.locator('#experiment-status')).to_contain_text('此页没有重新求解')
            expect(page.locator('#experiment-error')).to_be_hidden()
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            screenshot('ui-experiments-rectangular-desktop.png')
            results['flows'].append('Physics journey reaches all32 untuned experimental rows with missing Re and numerical/physical/replay boundaries intact')

            for length, count in [('24', 12), ('13', 11), ('7.5', 9), ('all', 32)]:
                page.locator('#length-filter').select_option(length)
                expect(page.locator('#comparison-chart circle')).to_have_count(count)
                expect(page.locator('#comparison-legend')).to_contain_text(f'{count} / 32')
                expect(page.locator('#source-rows tr')).to_have_count(32)
                expect(page.locator('#run-count')).to_have_text('32')
            results['flows'].append('Length filter changes only the plot; all32 rows and global discrepancy statistics remain intact')

            page.locator('.source-table summary').click()
            expect(page.locator('#source-rows')).to_be_visible()
            first = expected['comparison']['rows'][0]
            expect(page.locator('#source-rows tr').first).to_contain_text(f"{first['observed_bulk_theta'] * 100:.2f}")
            expect(page.locator('#source-rows tr').first).to_contain_text(f"{first['predicted_bulk_theta'] * 100:.2f}")
            page.locator('.source-table summary').click()
            with page.expect_download() as download:
                page.locator('#export-record').click()
            target = args.output_dir / 'ui-experiments-rectangular-evidence.json'
            download.value.save_as(str(target))
            exported = json.loads(target.read_text(encoding='utf-8'))
            assert exported == expected
            assert target.stat().st_size < 100_000
            results['flows'].append('Full source table and native export reproduce the exact integrity-checked server record below100KB')

            held = []
            page.route('**/api/physics/experiment', lambda route: held.append(route))
            with page.expect_request('**/api/physics/experiment'):
                page.locator('#verify-record').click()
            pending = wait_for_held_route(page, held, 'experimental cancellation')
            expect(page.locator('#verify-record')).to_be_disabled()
            expect(page.locator('#export-record')).to_be_disabled()
            expect(page.locator('#length-filter')).to_be_disabled()
            page.locator('#cancel-record').click()
            expect(page.locator('#experiment-status')).to_contain_text('已取消核对')
            expect(page.locator('#run-count')).to_have_text('32')
            expect(page.locator('#export-record')).to_be_disabled()
            pending.abort()
            page.unroute('**/api/physics/experiment')
            page.locator('#verify-record').click()
            expect(page.locator('#experiment-status')).to_contain_text('已核对的研究回放')
            results['flows'].append('Cancellation guards repeated actions and retains explicitly old evidence with export disabled until verified')

            def fail(route):
                route.fulfill(status=503, content_type='application/json', body=json.dumps({'error': 'research evidence deliberately stale in test'}))
            page.route('**/api/physics/experiment', fail)
            page.locator('#verify-record').click()
            expect(page.locator('#experiment-error')).to_contain_text('stale')
            expect(page.locator('#experiment-status')).to_contain_text('显示上次回放')
            expect(page.locator('#export-record')).to_be_disabled()
            page.unroute('**/api/physics/experiment')
            page.locator('#verify-record').click()
            expect(page.locator('#experiment-error')).to_be_hidden()
            expect(page.locator('#export-record')).to_be_enabled()
            results['flows'].append('Missing/stale package error is visible, preserves prior values honestly and recovers without reload')

            def invalid_claim(route):
                data = route.fetch().json()
                data['comparison']['physical_validation_pass'] = True
                route.fulfill(status=200, content_type='application/json', body=json.dumps(data))
            page.route('**/api/physics/experiment', invalid_claim)
            page.locator('#verify-record').click()
            expect(page.locator('#experiment-error')).to_contain_text('验证声明')
            expect(page.locator('#export-record')).to_be_disabled()
            page.unroute('**/api/physics/experiment')
            page.locator('#verify-record').click()
            expect(page.locator('#export-record')).to_be_enabled()
            results['flows'].append('Response with an unauthorized physical-validation claim is rejected before display/export')

            held = []
            page.route('**/api/physics/experiment', lambda route: held.append(route))
            with page.expect_request('**/api/physics/experiment'):
                page.locator('#verify-record').click()
            pending = wait_for_held_route(page, held, 'experimental navigation')
            page.locator(".site-header nav a[href='/']").click()
            try:
                pending.abort()
            except Exception:
                pass
            page.unroute('**/api/physics/experiment')
            page.go_back(wait_until='networkidle')
            expect(page.locator('#verify-record')).to_be_enabled(timeout=60000)
            if not page.locator('#export-record').is_enabled():
                page.locator('#verify-record').click()
            expect(page.locator('#export-record')).to_be_enabled(timeout=60000)
            results['flows'].append('Navigate away during pending audit and browser Back restores an enabled replay page')

            page.locator('#experiment-tab-fin').click()
            expect(page.locator('#benchmark-fin')).to_be_visible()
            expect(page.locator('#fin-status')).to_contain_text('已核对的板翅研究回放', timeout=60000)
            expect(page.locator('#fin-point-count')).to_have_text('12')
            expect(page.locator('#fin-scope-count')).to_have_text('3 / 12')
            expect(page.locator('#fin-gates-count')).to_have_text('17 / 17')
            expect(page.locator('#fin-comparison-chart [data-marker-index]')).to_have_count(12)
            expect(page.locator('#fin-source-rows tr')).to_have_count(12)
            expect(page.locator('#fin-source-rows .robust')).to_have_count(3)
            expect(page.locator('#fin-source-rows .boundary')).to_have_count(1)
            expect(page.locator('#fin-source-rows .outside')).to_have_count(8)
            expect(page.locator('#fin-topology-metrics')).to_contain_text('6.02–6.37')
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            screenshot('ui-experiments-fin-desktop.png')
            results['flows'].append('All12 plate-fin markers and both model forms render with3 robust,1 boundary-uncertain and8 out-of-scope cases')

            page.locator('#fin-allowance').select_option('graphical')
            expect(page.locator('#fin-comparison-chart [data-allowance="graphical"]')).to_have_count(12)
            expect(page.locator('#fin-allowance-explanation')).to_contain_text('不是测量置信区间')
            page.locator('#fin-allowance').select_option('author')
            expect(page.locator('#fin-comparison-chart [data-allowance="author"]')).to_have_count(12)
            expect(page.locator('#fin-comparison-chart [data-allowance="graphical"]')).to_have_count(0)
            expect(page.locator('#fin-allowance-explanation')).to_contain_text('未合并为总误差棒')
            page.locator('#fin-allowance').select_option('none')
            expect(page.locator('#fin-comparison-chart [data-allowance]')).to_have_count(0)
            results['flows'].append('Graphical-readout and author-uncertainty displays remain separate, explicitly noncombined components')

            with page.expect_download() as download:
                page.locator('#export-fin').click()
            target = args.output_dir / 'ui-experiments-fin-evidence.json'
            download.value.save_as(str(target))
            exported = json.loads(target.read_text(encoding='utf-8'))
            assert exported == expected_fin
            assert target.stat().st_size < 100_000
            results['flows'].append('Plate-fin export equals the audited snapshot with original-freeze provenance and all12 retained measurements')

            page.go_back()
            expect(page.locator('#benchmark-rectangular')).to_be_visible()
            page.go_forward()
            expect(page.locator('#benchmark-fin')).to_be_visible()
            page.locator('#experiment-tab-fin').focus()
            page.keyboard.press('Home')
            expect(page.locator('#experiment-tab-rectangular')).to_be_focused()
            expect(page.locator('#benchmark-rectangular')).to_be_visible()
            page.keyboard.press('End')
            expect(page.locator('#benchmark-fin')).to_be_visible()
            results['flows'].append('The two experimental benchmarks support keyboard tab selection and browser history without recomputing or dropping records')

            held = []
            page.route('**/api/physics/fin-experiment', lambda route: held.append(route))
            with page.expect_request('**/api/physics/fin-experiment'):
                page.locator('#verify-fin').click()
            pending = wait_for_held_route(page, held, 'plate-fin cancellation')
            expect(page.locator('#verify-fin')).to_be_disabled()
            expect(page.locator('#export-fin')).to_be_disabled()
            expect(page.locator('#fin-allowance')).to_be_disabled()
            page.locator('#cancel-fin').click()
            expect(page.locator('#fin-status')).to_contain_text('已取消核对')
            expect(page.locator('#export-fin')).to_be_disabled()
            pending.abort()
            page.unroute('**/api/physics/fin-experiment')
            page.locator('#verify-fin').click()
            expect(page.locator('#export-fin')).to_be_enabled()
            results['flows'].append('Plate-fin cancellation preserves old labeled data and only verified evidence can be exported')

            page.route('**/api/physics/fin-experiment', fail)
            page.locator('#verify-fin').click()
            expect(page.locator('#fin-error')).to_contain_text('stale')
            expect(page.locator('#fin-status')).to_contain_text('显示上次板翅回放')
            expect(page.locator('#export-fin')).to_be_disabled()
            page.unroute('**/api/physics/fin-experiment')
            page.locator('#verify-fin').click()
            expect(page.locator('#export-fin')).to_be_enabled()
            def invalid_fin_scope(route):
                data = route.fetch().json()
                data['rows'][0]['scope'] = 'nominally_outside_laminar_scope'
                route.fulfill(status=200, content_type='application/json', body=json.dumps(data))
            page.route('**/api/physics/fin-experiment', invalid_fin_scope)
            page.locator('#verify-fin').click()
            expect(page.locator('#fin-error')).to_contain_text('适用性分组')
            expect(page.locator('#export-fin')).to_be_disabled()
            page.unroute('**/api/physics/fin-experiment')
            page.locator('#verify-fin').click()
            expect(page.locator('#export-fin')).to_be_enabled()
            results['flows'].append('Stale plate-fin evidence and mismatched applicability are rejected before display/export and recover cleanly')

            page.set_viewport_size({'width': 390, 'height': 844})
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            for chart in ('#fin-comparison-chart', '#fin-channel-diagram'):
                sizes = page.locator(chart + ' svg text').evaluate_all('''nodes => nodes.map(n => {
                    const m=n.getScreenCTM(),size=parseFloat(getComputedStyle(n).fontSize);
                    return {text:n.textContent,px:size*Math.min(Math.hypot(m.a,m.b),Math.hypot(m.c,m.d))};
                })''')
                assert sizes and min(row['px'] for row in sizes) >= 9.5, sizes
                results.setdefault('fin_mobile_svg_rendered_font_sizes', {})[chart] = sizes
            screenshot('ui-experiments-fin-mobile.png')
            page.locator('.fin-source-table summary').click()
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            assert page.locator('.fin-source-table .table-scroll').evaluate('n=>n.scrollWidth > n.clientWidth')
            screenshot('ui-experiments-fin-table-mobile.png')
            page.locator('.fin-source-table summary').click()
            results['flows'].append('390px plate-fin plots and topology retain native-size labels; all12 table rows scroll locally without page overflow')
            page.locator('#experiment-tab-rectangular').click()
            page.set_viewport_size({'width': 390, 'height': 844})
            page.locator('#length-filter').select_option('all')
            expect(page.locator('#comparison-chart circle')).to_have_count(32)
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            sizes = page.locator('#comparison-chart svg text').evaluate_all('''nodes => nodes.map(n => {
                const m=n.getScreenCTM(),size=parseFloat(getComputedStyle(n).fontSize);
                return {text:n.textContent,px:size*Math.min(Math.hypot(m.a,m.b),Math.hypot(m.c,m.d))};
            })''')
            assert sizes and min(row['px'] for row in sizes) >= 9.5, sizes
            results['mobile_svg_rendered_font_sizes'] = sizes
            screenshot('ui-experiments-rectangular-mobile.png')
            page.locator('.source-table summary').click()
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            assert page.locator('.source-table .table-scroll').evaluate('n=>n.scrollWidth > n.clientWidth')
            screenshot('ui-experiments-rectangular-table-mobile.png')
            results['flows'].append('390px mobile preserves native-size plot labels and contains table overflow within its own scroll region')
            assert not results['page_errors'], results['page_errors']
            results['status'] = 'passed'
            browser.close()
    except Exception:
        results['status'] = 'failed'
        results['traceback'] = traceback.format_exc()
        raise
    finally:
        (args.output_dir / 'ui-experiments-results.json').write_text(json.dumps(results, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        server.shutdown()
        server.server_close()
        thread.join()
        print(json.dumps(results, ensure_ascii=False))


if __name__ == '__main__':
    main()
