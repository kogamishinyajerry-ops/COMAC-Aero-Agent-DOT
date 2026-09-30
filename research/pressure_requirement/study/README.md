# Conditional pressure requirement study

Research-only inverse design of a synthetic available mechanical pressure-loss budget. This directory is ignored by Git and is the only study write location. The original checkpoint and all accepted packages are inputs only.

Read `RESULTS.md` for outcomes, `SCOPE_AND_MEASUREMENT.md` for the physical meaning and measurement needs, and the independent review under `review/` before using a root conclusion. A successful root is zero-headroom within this model and is not a hardware margin.

## Frozen scope

- Two geometries: 16 fins at 0.86 mm and 0.60 mm
- Three uniform illustrative end-loss scenarios: K=0,1,2
- Fixed 60 W, 25°C inlet, 85°C required uniform base and 40 g fin-only mass ceiling
- Root variable: nominal budget P, with combined state 0.6P and branch 1 sealed
- Existing raw Poisson conductance and full-array finite-fin thermal operator imported read-only
- Three fixed meshes per scenario: 48×144×800, 64×192×800 and 48×144×1600
- Frozen plan and a pre-numerics clarification retained with SHA256 records

## Reproduction

Existing Python, NumPy and SciPy are the only optional research dependencies. No dependency installation is needed or performed. The original source location is resolved relative to this directory's position under `output/physics-campaign/`.

To reproduce in a separate ignored sibling study directory, copy the scripts, frozen `plan.json`, `plan.sha256`, `pre_numerics_clarification.json` and its `.sha256` to a new directory at the same nesting depth, leaving the original evidence intact. Run the two geometry commands below from the repository root, changing only the sibling directory component if used. Do not run more than two numerical processes concurrently.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -B output/physics-campaign/pressure-requirement-study/pressure_requirement.py n16_t860
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -B output/physics-campaign/pressure-requirement-study/pressure_requirement.py n16_t600
```

The commands write detailed `runs/` and aggregate `results/` below their own script directory. Re-running them in this evidence directory overwrites their same-named study outputs, so use a sibling copy if preserving the supplied run is important. They never write to imported accepted sources.

After both finish, assemble and audit:

```sh
python -B output/physics-campaign/pressure-requirement-study/summarize.py
python -B output/physics-campaign/pressure-requirement-study/audit_study.py
```

The numerical runner uses at most 90 full thermal solves per geometry, preserving the global predeclared 180-solve cap, and saves failure reasons when a bracket or numerical/resource gate cannot be met. Its primary result status explicitly awaits independent review. Runtime is dominated by repeated conservative sparse full-array marches; refined evaluations are approximately 40 seconds on the current execution machine with two single-thread workers.

## Evidence

`runs/` contains every executed thermal evaluation, including domain checks at nominal and combined conditions, per-branch constitutive pressure balance, normalized maximum-principle diagnostics, mass and enthalpy closure, dissipation decomposition, sealed-branch zero enthalpy and sampled finite-fin temperatures. `results/` contains all six cases, all three mesh roots and their directly evaluated sign brackets. `summary.json` and `RESULTS.md` are derivative readouts, not replacement source data. `audit.json` aggregates the declared gates; independent review remains a separate acceptance step.

Every JSON must remain below 100,000 bytes and every binary below 250,000 bytes. The fine numerical pressure brackets are not physical uncertainty bounds. Electrical power, actual fan/feeder coupling, installed end geometry, measured coefficients, hotspot limits and aircraft transfer remain outside scope.

## Completed verification and preserved first phase

The completed evidence contains 18 mesh-root brackets and six independent main-root reproductions. The original 180-solve phase exhausted its bound with two K=2 axial brackets unfinished. Its results, readout and gate outcomes are preserved by `phase1_manifest.json` and `phase1_readout/`; they were not relabeled as a successful original phase. A separately frozen continuation added 5 primary evaluations and 6 independent reproductions, within its 14-solve and 20-minute limits. The resulting total is 191 thermal evaluations across both phases.

Read the completed six-case records in `continuation/results/`, the combined readout in `RESULTS.md` and `summary.json`, and independent acceptance in `review/final_review_gate.json`. That acceptance applies only to conditional model-pressure root reporting. It retains the process-cap exception, the pre-thermal/root clarification chronology, and the original whole-checkout gate failures caused by concurrent authorized integration. The separate dependency audit establishes that all 13 consumed accepted input files remain identical to the original checkpoint.

These commands audit the existing completed evidence without new thermal solves:

```sh
python -B output/physics-campaign/pressure-requirement-study/audit_dependencies.py
python -B output/physics-campaign/pressure-requirement-study/audit_final.py
python -B output/physics-campaign/pressure-requirement-study/build_manifest.py
```

`audit_study.py` intentionally audits only the original limited phase and retains its incomplete/whole-checkout failures. `audit_final.py` audits the completed scientific evidence while keeping those original failure results separate and unchanged. No final audit can convert the roots into physical validation or an engineering margin.

For a fresh numerical reproduction, use a separate sibling directory. The archived continuation plan has a fixed historical execution window and input-hash ledger; preserve it. After re-running the original bounded phase, freeze a new equivalent verification-only continuation record for the new run window and fresh first-phase hashes before executing the same cached-root workflow. Do not expand the six-scenario scope or change the numerical gates.

`manifest_index.json` links small manifest chunks under `manifest/`. They retain all scientific records and exclude bytecode and incomplete temporary writes. No publication or repository integration is performed by these scripts.
