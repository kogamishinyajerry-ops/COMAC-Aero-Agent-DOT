# Portable pressure-driven fin tradeoff evidence

This is a declared synthetic component-scale screening exercise, not aircraft validation. Its most important result is a failure: **none of the nine tested designs meets the fixed 60 W combined-fault screen**. The sole mass/combined-temperature Pareto point within the declared Reynolds scope has 16 fins × 0.60 mm, 26.36 g of fin-only aluminum and a required uniform-base temperature of 93.56°C under the combined fault. The synthetic ceiling is 85°C. Pareto status does not mean feasibility or a global optimum.

The original accepted study, experimental benchmark and source checkpoint `14d72777b434d025c87f560b9e3e9c24fd786865` are unchanged. The exact source, plan, 36 design cases, 18 sensitivity cases, numerical verification and independent review are preserved under `research/pressure_fin/original_freeze/`. The frozen upstream `study/manifest.json` is a historical inventory and may name transient files intentionally excluded here. `examples/pressure_fin_tradeoff/package_manifest.json` is the authoritative portable inventory. No caches, bytecode, logs, NPZ or PDF are included in that inventory.

## Safe default reproduction, Python standard library only

Run `python -S research/pressure_fin/reproduce.py` from the package directory, or run `research/pressure_fin/reproduce.sh`. The default:

1. Checks the immutable manifest, scientific hashes and final review
2. Independently checks saved residuals, mass/geometry/temperature arithmetic, flow-network identities, exact rectangular-series conductance, continuum plug-flow limits, convergence differences, scope flags and Pareto dominance
3. Rebuilds display records into a new `output/replay-.../display/` and compares their bytes with the accepted examples
4. Writes a selected-view JSON comparing baseline and selected candidate with exact absolute branch-flow bars and flow fractions

Export, selected-view construction, and optional scientific source staging consume the exact verified-byte snapshot. A second audit checks every pinned identity before reproduction reports that examples were unchanged. It does not import NumPy/SciPy or rerun the thermal PDE by default. Every invocation creates a fresh ignored output directory. `--output` is accepted only for a new child of `package/output/`; existing paths and paths to pinned examples are rejected.

Example: `python -S research/pressure_fin/reproduce.py --design n16_t600 --case combined_fault --heat-load 40`

The 40/60/80 W selector changes the displayed linear constant-property temperature. **It never changes the fixed 60 W combined-fault design criterion.** Raw mass/temperature criterion flags and Reynolds-qualified conditional flags are distinct. Material/property/profile sensitivities stay separate from these flags and are not confidence bounds.

## Optional scientific rerun

With the existing NumPy/SciPy installation, `python research/pressure_fin/reproduce.py --scientific baseline` reruns the selected design/case at the frozen 48 × 144 × 800 mesh in fresh ignored output and checks conductance against the accepted value. It defaults to the baseline geometry and combined fault. It does not install software.

`--scientific full` reruns the original verification, all 36 design cases, all 18 sensitivity cases, the post-screen selected-point check, and internal artifact audit in a fresh staged copy. This takes several minutes. The numerical rerun is not a new independent scientific review or experimental/aircraft validation. Scientific source files remain byte-identical; only copies inside the new output folder execute and write results.

## Display interface

`examples/pressure_fin_tradeoff/ui_contract.json` defines the bounded interface. `catalog.json` contains all nine scatter points. Each `candidates/{design_id}.json` has geometry, fin-only mass, all four scenarios, temperatures for 40/60/80 W, separate raw/conditional flags and absolute/fractional branch flows. Two candidates with nominal flow above the Reynolds cutoff are also listed separately in `out_of_scope_candidates.json`, with their per-case flags retained.

For equal-pressure comparisons, sealing channel 1 reduces total flow and changes flow fractions while open-channel absolute flows remain unchanged. Compare nominal with blockage-only, or pressure-loss with combined. Nominal 25 Pa versus combined 15 Pa also reduces every open-channel flow to 0.6 times nominal. Show the selected pressure with branch bars.

The branch display is an algebraically lossless expansion of the accepted hydraulic symmetry classes: both invariant side-channel conductances are taken from the accepted baseline record, and the remaining accepted total flow is divided among identical active interior channels. There is no fitted coefficient, new pressure model, or inferred fan curve. Independent analytic conductance and saved maximum-Reynolds checks validate this expansion.

## Mandatory scientific limits

- The 85°C base ceiling, 40 g fin-only budget and 60 W design load are synthetic choices, not aircraft or certification requirements
- Required **uniform-base** temperature is `25 + Q/G`, not a local hotspot; high failed-case values are constant-property extrapolations
- The ideal fixed pressure covers fully developed straight-channel friction. Hydrodynamic development and inlet/exit losses are omitted; thermal development is marched
- Fin-only aluminum mass excludes base, duct, fan, motor and aircraft. `deltaP × volume_flow` is hydraulic dissipation, not electrical fan power
- The sealed branch retains transverse fluid conduction but has no advected inlet state. Obstruction conduction, recirculation and axial fluid conduction are not solved
- Contact resistance, base spreading/conduction and axial solid conduction are omitted. Viscous heating is omitted and its reported maximum is 0.171% of the 60 W load
- All failures, dominated points and out-of-scope candidates remain. This is a finite nine-point screen, with baseline-only uncertainty scenarios, not a robust optimized design

For application readers, `audit(root, expected_manifest_sha256=PIN, return_verified_records=True)` returns `(summary, records, manifest_sha256)`. `records` maps proposed repository paths to the exact verified byte snapshot. Build responses from those bytes; never audit and then reopen files. Manifest/snapshot keys are POSIX-style on all operating systems. Set `sys.dont_write_bytecode=True` before dynamically importing the auditor so the immutable research tree remains cache-free. The manifest path is `examples/pressure_fin_tradeoff/package_manifest.json`.

Every published JSON is below 100 kB and every binary below 250 kB. The package contains no binary assets.
