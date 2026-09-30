"""Thin standard-library reader for the pinned, untuned plate-fin study.

The research package's audit imports only the standard library and executes no
solver. The original experiment/freeze remain separate from packaging replay.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'examples/plate_fin_experiment/'
MANIFEST_PATH = PREFIX + 'package_manifest.json'
EXPECTED_MANIFEST_SHA256 = 'b56204f3ac3f6cbc7536869e5aa77f8a0cba3474297e3f0bc459a79f55f021c3'
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def read_fin_experimental_evidence(root=ROOT):
    """Audit original source/solver/projection chains, then build a bounded view."""
    try:
        from research.plate_fin.audit_package import audit, strict_json
        root = Path(root).resolve()
        accepted, records, manifest_sha = audit(root, expected_manifest_sha256=EXPECTED_MANIFEST_SHA256, return_verified_records=True)
        def data(name):
            return strict_json(records[PREFIX + name])
        report = data('plate_fin_report.json')
        verification = data('verification.json')
        rows = []
        for row in report['rows']:
            observed = row['observed']
            primary, alternative = row['predictions']['fd'], row['predictions']['plug']
            graphical = row['graphical_readout_allowance_separate']
            rows.append({
                'marker_index': row['marker_index'],
                'V_m_s': observed['V_channel_inferred_m_s'],
                'Re_nominal': row['scope']['Re_nominal'],
                'observed_Rth_K_W': observed['Rth_K_W'],
                'fd_Rth_K_W': primary['Rth_K_W'],
                'plug_Rth_K_W': alternative['Rth_K_W'],
                'relative_Rth_discrepancy': primary['relative_Rth_discrepancy'],
                'scope': row['scope']['scope'],
                'graphical_Rth_allowance_K_W': graphical['Rth_K_W'],
                'graphical_V_allowance_m_s': graphical['V_m_s'],
                'author_Rth_absolute_uncertainty_K_W': row['author_uncertainty_separate']['Rth_absolute_K_W'],
            })
        nominal = [r for r in report['rows'] if r['scope']['Re_nominal'] <= report['laminar_cutoff_Re']]
        def value_range(key):
            values = [r['predictions']['fd'][key] for r in nominal]
            return [min(values), max(values)]
        result = {
            'schema': 'aerolab-fin-experiment-replay-v1',
            'execution': 'verified_research_replay', 'live_computation': False,
            'physical_validation_pass': None, 'aircraft_transfer_authorized': False,
            'calibration_records': 0, 'source': report['source'], 'rows': rows,
            'scope_boundary_speed_m_s': report['laminar_cutoff_Re'] * report['nominal_properties']['nu_m2_s'] / report['geometry']['hydraulic_diameter_m'],
            'side_channel_heat_fraction_range': value_range('side_channels_G_fraction'),
            'naive_channel_G_bias_range': value_range('naive_17_central_channels_relative_G_bias'),
            'topology_range_scope': 'four nominally laminar points, including one boundary-uncertain point',
            'numerical': {'all_passed': True, 'gates': verification['gates'],
                          'summary': report['verification_summary'],
                          'notice': 'Numerical verification, not uncertainty-backed physical validation'},
            'research_report': report,
            'provenance': {
                'reader_source_sha256': SOURCE_SHA256,
                'package_manifest_sha256': manifest_sha,
                'verified_file_count': accepted['listed_file_count'],
                'original_numerical_freeze_sha256': report['provenance']['original_precomparison_freeze_sha256'],
                'original_comparison_sha256': report['provenance']['original_comparison_sha256'],
                'solver_sha256': report['provenance']['solver_sha256'],
                'chronology': report['chronology'],
            },
        }
        if len(json.dumps(result, allow_nan=False).encode()) >= 100_000:
            raise ValueError('Plate-fin evidence exceeds bounded response contract')
        return result
    except (ImportError, OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        raise RuntimeError('Plate-fin research evidence is missing, stale or inconsistent; audit the pinned package before showing the replay') from exc
