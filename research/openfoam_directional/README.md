# Directional pressure-error diagnosis

This is a new, preregistered, momentum-only follow-up to the synthetic three-dimensional cooling duct. It separates directional mesh sensitivity, fully developed transverse finite-volume bias, and mesh-dependent inlet/end effects. It does not replace the original validation or its failed pressure-grid gate. All five new directional cases passed their execution checks; the separate inlet-isolation control failed its frozen residual gate at 1500 iterations. Its unconverged field is excluded from accepted comparisons and causal conclusions. The finest directional case also retains unresolved near-inlet pressure-gradient oscillations outside the primary interior fit.

## Frozen scientific scope

The original 30 × 4 × 2 mm duct, air properties, 3 m/s physical area-mean inlet speed, pressure and no-slip wall conditions, Gmsh meshing, OpenFOAM v1912 SIMPLEC solver and numerical operators are retained. Thermal transport is not re-solved. The original scalar corner singularity and limitations remain.

Six new serial flow runs are registered in `plan.json`, together with reporting limits, hypotheses and a 2700 s aggregate solver budget. Four historical cases are analyzed read-only and identified by their original content hashes. `evidence/run_lock.json` records the plan and solver-script hashes before the first new solve.

- Axial ladder: (40,32,16), existing B=(80,32,16), (160,32,16)
- Transverse ladder: (80,16,8), existing B, (80,64,32), (80,128,64)
- Cross-check: existing F=(160,64,32) closes the combined refinement decomposition
- Supplementary inlet: B mesh with the independent discrete fully developed profile prescribed at the inlet; this changes only the inlet shape and is excluded from the matched-BC ladders

The finer transverse case was chosen before solver execution, not conditional on getting a desired result. New cases use a fresh output namespace. No mesh, threshold or physical parameter is tuned after viewing results.

## What the reference means

The rectangular continuum Poiseuille series at fixed physical area mean 3 m/s is a fully developed target. It is not the exact finite-duct solution of the mesh-dependent sampled inlet plus zero-gradient inlet pressure closure. This distinction matters because the original sampled inlet is normalized to exactly the same discrete physical volume flow on every grid, while its corresponding continuous-profile amplitude is slightly grid-dependent.

We keep both original continuum point-value L2 and exact cross-sectional cell-average L2, always labeling the definition. The cell-average series is integrated analytically; its physical mean remains 3 m/s. No value is silently re-normalized to improve agreement.

An independent sparse 2D cell-centered operator solves −laplacian(v)=1 on the same uniform rectangular cross section. An interior face contributes 1/h² and a zero-Dirichlet wall at half-cell distance contributes 2/h². This gives a discrete fully developed profile and gradient. It isolates a known transverse finite-volume bias, but it is not an independent validation of the complete 3D solver. The residual difference can contain inlet, end, axial and coupling effects.

## Measurements and interpretation

The primary gradient uses a least-squares fit to cross-sectional mean pressure on x/L=0.25–0.75, exactly the original definition. Extra symmetric windows 0.10–0.90 and 0.40–0.60 and a downstream asymmetric window 0.60–0.90 expose finite-length development. The inlet-owner to outlet pressure drop is separately labeled.

Mass is checked with the actual pressure-corrected OpenFOAM phi on every streamwise face. Arithmetic section means of cell-centered velocity are not substituted for conserved flux. Nonzero transverse velocity or section-mean velocity variation is not automatically mass loss.

The combined refinement difference decomposes as:

F − B = (A − B) + (T − B) + (F − A − T + B)

A changes only nx; T changes only ny,nz. A transverse-dominant result requires at least 90% of the sum of separate absolute changes and an interaction no greater than 10% of the combined change. The independent transverse operator is called sufficient alone only if its remainder is at most 10% of total continuum-target bias at both B and T. These hypotheses may fail even when every run meets execution checks.

Observed order and Richardson estimates require same-sign contracting differences, positive observed order and changes above the preregistered noise floor. They are conditional trend diagnostics, not a GCI or uncertainty bound. An axial-only extrapolation with fixed transverse resolution does not estimate continuum truth. A successful fixed-axial transverse doubling does not pass the original all-direction gate.

## Evidence and reproduction

Publication note: [repository publication scope and clean-clone checks](../COOLING_RESEARCH_PUBLICATION.md). This directory contains numerical evidence, including failed checks. Historical reports predate repository publication.

- `REPORT_ZH.md`: concise findings and retained failure
- `evidence/report.json`: all measurements, tested hypotheses, orders and limitations
- `evidence/directional_comparison.png`: actual pressure results, directional ladders and source-separated bias
- `evidence/actual_velocity_difference.png`: actual saved mid-duct OpenFOAM velocity data relative to the discrete developed target, with separately labeled color scales
- `evidence/*_profiles.json`: full pressure stations, volume flux stations and actual middle-plane data behind the figures; four large profiles are stored as exact-byte gzip parts listed in `evidence/storage.json`
- The original `directional_comparison.png` is also stored in exact-byte gzip parts. `storage.py --extract-to output/directional-evidence` reconstructs it without changing any pixels. `storage.read_json` transparently reads archived profiles.
- `evidence/source_artifacts.json`: new mesh, dictionaries, initial conditions, solved fields and logs, including exact SHA-256 records
- `evidence/manifest.json`: compact package integrity
- `REVIEW.md`: independent scientific and source audit

Run from the repository root, using the already-installed isolated Gmsh 4.15.2 and OpenFOAM v1912 tools at `/workspace/shared/cfd-tools`:

```
PYTHONDONTWRITEBYTECODE=1 bash research/openfoam_directional/reproduce.sh
python -m unittest discover -s research/openfoam_directional -p 'test_*.py' -v
python -S research/openfoam_directional/audit_package.py --full-source
python -S research/openfoam_3d/audit_package.py --full-source
```

This exact registered replay requires the unchanged retained original source fields at `output/openfoam-3d-v2`. Freshly regenerated original cases have new runtime/log hashes and must be registered as a new baseline; they cannot silently substitute for the frozen historical cases. Large native fields are intentionally not included in the compact delivery. The compact package can be audited without `--full-source`; it is not a claim that a small attachment contains all full-resolution CFD fields. `package_results.py` may regenerate compact evidence from a completed fresh run; its default evidence destination is this new study namespace, never the original package.

The original numerical study used no external solver/API, MPI or new installation. Repository publication does not add application integration, deployment or physical validation.
