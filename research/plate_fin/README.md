# Offline plate-fin research package

This is a saved, source-conditioned comparison with the plate-fin experiment of Pires-Fonseca and Carrasco-Altemani, DOI10.17533/udea.redin.20230417. Mathematical verification and integrity checks are not experimental or aircraft validation.

## Separation of responsibilities

- The application only integrity-checks and displays saved JSON. It requires Python’s standard library, with no NumPy, SciPy, Matplotlib, PyMuPDF, source PDF, network access or live solver execution
- `audit_package.py` is the portable standard-library audit. An application should pin the delivered manifest SHA256 and pass it as its expected identity
- `replay_numerics.py` is optional research work. It uses existing NumPy/SciPy to recompute the unchanged40 cases and independent mathematical checks, then verifies numerical equivalence to the retained original results
- `original_freeze/` preserves the original plan, rejected grid, accepted mathematical freeze, independent review, original comparison, exact small field samples and source extractor/readout byte-for-byte
- Packaging was performed after residuals were observed. `packaging_replay.json` records that chronology. It does not masquerade as a fresh precomparison experiment
- The physical solver bytes are unchanged. Only path handling, publication projection, a separate replay wrapper and labeled seven-decimal display samples were added

## Run from any relocated checkout

Quick audit, standard library only:

`python -S research/plate_fin/audit_package.py`

Optional numeric replay, using the existing research dependencies:

`bash research/plate_fin/reproduce.sh`

The default command creates a new `output/plate-fin-replays/run_<unique-id>/` directory. It writes the audit, replay results and run metadata there, then verifies that every pinned publication file is unchanged. It never overwrites accepted examples or changes the pinned manifest. An explicit `--output-dir` must be fresh and outside both publication directories. `--audit-only` tests the same fresh-output path without scientific dependencies. No existing output README, field array or PDF is needed.

New outputs are not automatically promoted. Changing or replacing pinned evidence requires a separate explicit promotion step and a new manifest identity.

The code accepts only the original frozen48×144 cross-section and1600-step backward-Euler case set in the supported replay. The optional BDF2 branch inherited in the archived/core solver remains outside accepted evidence. Material167/205/237W/(m K), source numerical air properties, prescribed FD/plug cases and property/area-mapping sensitivities are unchanged.

## Optional source-byte audit

The paper PDF is not redistributed and is not required for any numeric replay or display audit. To verify a separately supplied copy explicitly:

`python research/plate_fin/source_audit.py --source-pdf /path/to/paper.pdf`

Add `--extract-figure8` to check all12 vector markers using an existing PyMuPDF installation. The command accepts only the documented source hash and does not download a PDF or install software. `optional_source_audit_record.json` records the packaging-time audit against the original bytes. The preserved extractor includes Figure7 for historical provenance; Figure7 and fitted curves are explicitly excluded from the offline numeric targets.

## Display contract and interpretation

The stable front-end record is `examples/plate_fin_experiment/plate_fin_report.json`; `replay_index.json` names stable keys and paths. It preserves12 distinct measured markers,24 model-form predictions, three robustly laminar points, one nominally laminar boundary-uncertain point, and eight out-of-scope points. Author uncertainty and graphical allowances remain separate. The joint-corner regime screen is not a statistical confidence interval.

The isothermal base heats15 interior-channel floors. The two side floors lie outside the base and are adiabatic, with only one fin face per side channel. `side_channel_counterexample.json` shows how incorrectly multiplying a central heated channel by17 masks disagreement; it is explicitly not an accepted model.

Source Rth is a graphical, loss-corrected reduction rather than raw run temperatures. Source air properties are numerical assumptions, not measured per-run conditions. The tested aluminum conductivity is unidentified. Unresolved entrance development, axial solid conduction and other limitations remain attached to every report. No model coefficient, geometry or cutoff was fitted to agreement.

All published JSON files are below100KB, and each PNG is below250KB. Full-resolution arrays, logs, caches and the PDF are excluded. Exact raw-run replication still requires original run rows, loss corrections, material/tolerance information and the missing13th-marker explanation.

`build_display_records.py` is a publication-authoring utility, not a replay command. Running it intentionally rewrites derived display files and invalidates a pinned manifest until an explicit new package is audited and promoted.

Field consumers must use `display_fields.json.channel_domains`: index0 is a full side-clearance channel, index1 a full interior channel, and index8 the central half-channel with `modeled_width_fraction=0.5` and an explicit symmetry boundary. Coordinates are actual local millimetres, not stretched full-channel coordinates.

Optional plot regeneration writes to a separate fresh directory: `python research/plate_fin/render_saved_results.py --output-dir output/plate-fin-plots/fresh_name`. Saved PNGs were reproduced byte-for-byte in the packaging environment; Matplotlib remains optional.

For an application reader, `audit(root, expected_manifest_sha256=PIN, return_verified_records=True)` returns `(summary, records, manifest_sha256)`, where `records` maps proposed repository paths to the exact immutable bytes already checked by that call. Construct the response from these bytes; do not audit and then reread files. The default API/CLI still returns only the compact JSON audit summary. Both manifest and artifact stat sizes are checked before bounded reads.

Archived original scripts are immutable historical records, including their original path conventions. They are not the relocated entry points. Use the top-level audit, reproduction and optional source-audit commands above. Only the two proposed `research/plate_fin/` and `examples/plate_fin_experiment/` trees belong to the publication; staging helpers, relocation fixtures, temporary tests and logs are excluded.
