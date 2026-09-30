# Recorded rectangular-duct experimental-comparison replay

Static research evidence for an untuned comparison with 32 historical isothermal rectangular-duct measurements. This directory is separate from live application calculations. The model's mathematical verification is not a physical-validation or aircraft-validation pass.

Read `replay_index.json` for the recommended UI label, artifact paths and immutable-source provenance; `experimental_comparison.json` for all 32 measurements and predictions; and `frozen_response.json` for the recorded dimensionless response. The mean absolute attenuation differences by source length are 2.62, 4.61 and 8.82 percentage points (24, 13 and 7.5 in). Eight source Re cells remain null.

`display_fields.json` contains 17×33 samples selected from the accepted 256×128 cell-centered fields and rounded to six decimals. They are display-only point samples, not cell averages, boundary nodes, or numerical-acceptance evidence. Original cell-center coordinates and sampling indices are retained. Declared rounding error is at most 0.5×10^-6, apart from machine floating-point roundoff. Acceptance and comparison use unrounded full-grid calculations.

`packaging_replay.json` records exact numerical identity between the original accepted research run and the guarded packaged replay. `verification.json` and `independent_continuum_comparison.json` contain the full mathematical checks. `package_manifest.json` supplies proposed repository destinations, file sizes and exact hashes.

This packaging replay was produced after the original experimental discrepancy was known. The original precomparison code, freeze, rejected trial and hashes remain preserved under `research/rectangular_duct/original_freeze/`. No new unseen ordering is claimed.

The accepted files in this directory are pinned by the application. The supported replay creates a separate ignored output directory and does not replace these files. Reproduce offline using `bash research/rectangular_duct/reproduce.sh` from the repository root. NumPy/SciPy/Matplotlib are research-only dependencies. The application can serve these static files while retaining its standard-library dependency set. No PDF, network, credentials, API spend or publication is required.
