"""Optional browser QA; Playwright is test-only, never a runtime dependency.

    python -m pip install playwright
    python -m playwright install chromium
    python tests/ui_smoke.py --output-dir output

Starts the real stdlib server in-process, then verifies the real UI and solver.
Run in a browser-capable environment. A blocked browser launch is not a UI pass.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import threading
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aerolab.server import Handler  # noqa: E402


def set_range(page, selector, value):
    """Range inputs use the same input/change events as pointer or keyboard edits."""
    page.locator(selector).evaluate("""(element, value) => {
        element.value = String(value);
        element.dispatchEvent(new Event('input', {bubbles: true}));
        element.dispatchEvent(new Event('change', {bubbles: true}));
    }""", value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import expect, sync_playwright
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
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
            # Leadership view is the default: one question and visual, no workbench.
            expect(page.locator('#guided-view')).to_be_visible()
            expect(page.locator('.app-layout')).to_be_hidden()
            expect(page.locator('#guide-provenance')).to_contain_text('回放')
            assert page.locator('[data-guide-step]').count() == 6
            for step in range(6):
                page.locator(f'[data-guide-step="{step}"]').click()
                expect(page.locator('#guide-question')).not_to_be_empty()
                expect(page.locator('#guide-visual')).to_be_visible()
                expect(page.locator('.app-layout')).to_be_hidden()
                if step == 4:
                    expect(page.locator('#guide-compute-lv')).to_be_visible()
                    page.locator('#guide-compute-lv').click()
                    expect(page.locator('#guide-provenance')).to_contain_text('本次', timeout=120000)
                    evidence = json.loads(page.locator('#guide-evidence-json').text_content())
                    assert 'command_loss' in json.dumps(evidence)
                    assert 'input_hash' in json.dumps(evidence)
                elif step == 5:
                    expect(page.locator('#guide-compute-sweep')).to_be_visible()
                    page.locator('#guide-compute-sweep').click()
                    expect(page.locator('#guide-provenance')).to_contain_text('本次', timeout=120000)
                    evidence = json.loads(page.locator('#guide-evidence-json').text_content())
                    assert 'command_loss' in json.dumps(evidence)
                    assert 'results' in evidence
                    assert len(evidence['results']) == 4
                else:
                    expect(page.locator('#guide-provenance')).to_contain_text('回放')
                page.screenshot(path=str(args.output_dir / f'ui-guide-{step + 1:02d}.png'), full_page=True)
            results['flows'].append('Default six-step guide shows one visual, hides expert workbench and uses authentic evidence')
            results['flows'].append('Guide LV and equal-mass design examples require explicit fresh solver computations')
            page.set_viewport_size({'width': 390, 'height': 844})
            page.locator('[data-guide-step="0"]').click()
            page.screenshot(path=str(args.output_dir / 'ui-guide-mobile.png'), full_page=True)
            assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
            page.set_viewport_size({'width': 1440, 'height': 1100})
            page.locator('#expert-mode-button').click()
            expect(page.locator('.app-layout')).to_be_visible()
            expect(page.locator('#guided-view')).to_be_hidden()
            expect(page.locator('#provenance')).to_have_text('已存结果回放')
            assert page.locator('#scenario').input_value() == 'cooling_fault'
            results['flows'].append('Expert mode restores unchanged replay and preserves its inputs after guided computations')
            results['flows'].append('Authentic replay explicitly labeled; solver-derived comparison rendered')
            assert page.locator('#trace-chart svg').count() == 1
            assert '两种策略都未满足' in page.locator('.comparison-conclusion').inner_text()
            assert '不能据此宣称节能优化成功' in page.locator('.comparison-conclusion').inner_text()
            page.screenshot(path=str(args.output_dir / 'ui-desktop.png'), full_page=True)
            for chart in ('power', 'electrical', 'energy', 'thermal'):
                page.locator(f'[data-chart="{chart}"]').click()
                assert page.locator('#trace-chart svg').count() == 1
            results['flows'].append('Four actual-timeseries chart modes render')
            set_range(page, '#time-scrubber', 200)
            assert page.locator('#current-time').inner_text() == '06:42'
            page.locator('#play-button').click()
            expect(page.locator('#current-time')).not_to_have_text('06:42')
            page.locator('#play-button').click()
            assert page.locator('#play-button').get_attribute('aria-label') == '播放轨迹'
            results['flows'].append('Trace scrubber and play/pause update actual frame')
            page.locator('input[value="baseline"]').check(force=True)
            assert '热感知固定规则' in page.locator('#evidence-caption').inner_text()
            page.locator('input[value="planner"]').check(force=True)
            assert '确定性有界预测搜索' in page.locator('#evidence-caption').inner_text()
            results['flows'].append('Policy selector swaps matching comparison evidence')
            old_caption = page.locator('#evidence-caption').inner_text()
            set_range(page, '#ambient', 39)
            assert page.locator('#input-dirty').is_visible()
            assert page.locator('#evidence-caption').inner_text() == old_caption
            page.locator('#run-button').click()
            expect(page.locator('#loading-overlay')).to_be_hidden(timeout=120000)
            assert page.locator('#provenance').inner_text() == '本次实际计算'
            assert not page.locator('#input-dirty').is_visible()
            assert '39 °C' in page.locator('#evidence-caption').inner_text()
            results['flows'].append('Edited input marks old evidence stale; fresh computation updates identity')
            page.locator('#scenario').select_option('nominal')
            page.locator('#compare-button').click()
            expect(page.locator('#loading-overlay')).to_be_hidden(timeout=120000)
            assert '两种策略都满足' in page.locator('.comparison-conclusion').inner_text()
            results['flows'].append('Fresh fair nominal comparison reports both policies feasible')
            page.locator('#scenario').select_option('bus_cooling')
            page.locator('#run-button').click()
            expect(page.locator('#loading-overlay')).to_be_hidden(timeout=120000)
            set_range(page, '#time-scrubber', 200)
            assert 'failed' in page.locator('#source-a-node').get_attribute('class')
            assert 'failed' in page.locator('#route-a').get_attribute('class')
            results['flows'].append('Explicit pack isolation marks A source and route')
            page.locator('#scenario').select_option('inverter_loss')
            page.locator('#run-button').click()
            expect(page.locator('#loading-overlay')).to_be_hidden(timeout=120000)
            set_range(page, '#time-scrubber', 200)
            assert 'failed' in page.locator('#motor-right-node').get_attribute('class')
            results['flows'].append('Explicit inverter isolation marks right channel')
            page.locator('[data-view="design"]').click()
            page.locator('#sweep-button').click()
            expect(page.locator('#loading-overlay')).to_be_hidden(timeout=120000)
            assert page.locator('.sweep-card').count() == 4
            assert page.locator('#tradeoff-chart svg').count() == 1
            page.screenshot(path=str(args.output_dir / 'ui-design.png'), full_page=True)
            results['flows'].append('Offline sweep displays four separately calculated fixed-hardware designs')
            page.locator('.choose-design').first.click()
            expect(page.locator('#loading-overlay')).to_be_hidden(timeout=120000)
            assert page.locator('#control-view').is_visible()
            results['flows'].append('Choosing hardware returns to control and computes a new run')
            page.locator('#model-details-link').click()
            evidence = json.loads(page.locator('#evidence-details').inner_text())
            assert len(evidence['meta']['model_sha256']) == 64
            assert len(evidence['meta']['input_hash']) == 64
            assert evidence['validation']['fixed_hardware'] is True
            results['flows'].append('Expert evidence exposes model hash, input hash and fixed-hardware validation')
            with page.expect_download() as download_info:
                page.locator('#export-button').click()
            download_info.value.save_as(str(args.output_dir / 'ui-evidence.json'))
            exported = json.loads((args.output_dir / 'ui-evidence.json').read_text(encoding='utf-8'))
            assert exported['trace'] and exported['meta']['input_hash'] == evidence['meta']['input_hash']
            results['flows'].append('Export contains complete authentic trace and matching evidence identity')
            page.set_viewport_size({'width': 390, 'height': 844})
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(args.output_dir / 'ui-mobile.png'), full_page=True)
            assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
            results['flows'].append('390px layout has no document-level horizontal overflow')
            assert not page.locator('#error-banner').is_visible()
            assert not results['errors'], results['errors']
            # Favicon 404 is irrelevant to application correctness; CSP errors are not.
            meaningful_console = [item for item in results['console_errors'] if '404' not in item]
            assert not meaningful_console, meaningful_console
            browser.close()
            results['status'] = 'passed'
    except Exception as error:
        results['status'] = 'failed'
        results['failure'] = str(error)
        raise
    finally:
        server.shutdown()
        server.server_close()
        (args.output_dir / 'ui-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
