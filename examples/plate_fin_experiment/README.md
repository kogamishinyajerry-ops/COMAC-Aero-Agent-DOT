# Saved plate-fin experimental comparison

Read `plate_fin_report.json` or `RESULTS.md`. The default view must say this is a saved conditional comparison, not live computation or a physical-validation pass.

- Untuned FD-model Rth discrepancies at three robustly laminar points: +0.51%, +2.97%, +5.13%
- A fourth nominally laminar point is boundary-uncertain and differs by +8.63%; eight further points are outside laminar scope
- All12 graphical markers are retained, including separate author and graphical allowances
- Side-channel ownership matters: the wrong17-interior-channel shortcut inflates conductance by about6.0–6.4% in the nominally laminar cases
- Unknown material and source properties remain scenarios; entrance development and axial fin conduction are not solved

`experimental_comparison.json`, `verification.json` and `frozen_numerics.json` are exact copies of original saved evidence. `packaging_replay.json` is a separately labeled post-comparison numerical-equivalence run. `display_fields.json` contains small normalized samples rounded to seven decimals, never recovered absolute temperatures.

The application should pin `package_manifest.json`, verify file hashes and saved arithmetic, and retain the qualifications in `replay_index.json`. It must not import or execute the research solver. The source PDF is neither required nor included.

Run optional research reproduction through `research/plate_fin/reproduce.sh`; it creates a fresh ignored output directory and never overwrites these pinned accepted files. Promotion is separate and explicit.
