# Rectangular-duct research replay

Research-only conservative finite-volume solver for a hydrodynamically developed, constant-property, laminar rectangular duct with all four walls at one common temperature. This package reproduces an untuned historical experimental comparison; it does not validate an aircraft model or authorize coefficient transfer.

## What changed during packaging

The original solver, preregistered numerical plans, rejected first trial, accepted verification, frozen response and experimental comparison are preserved verbatim in `original_freeze/`. `packaging_provenance.json` records their original hashes. The original precomparison solver SHA-256 is `efe82dc9d96dc5bb6ff4c19216d6ac84e083c6c482bab090d21f7ff48b2f488c`.

Historical scripts under `original_freeze/` are archival evidence, not supported execution entry points. Use the current top-level `reproduce.sh`; it replaces the original PDF-dependent research workflow with an offline transcription-based replay.

This packaging work occurred **after** the original 32-row experimental comparison. The new runs are explicitly labeled post-comparison replay. They test reproducibility and packaging drift; they do not pretend to repeat an unseen or blinded experiment.

The sole numerical-domain change is an explicit error for fewer than two cells per direction, protecting an unsupported one-cell edge. Accepted equations, grids, discretization, numerical tolerances and all measurement rows are unchanged. The marching-method syntax is unchanged. Supported-grid operators, velocities, short marches and the complete accepted numerical evidence are checked for exact equality with the preserved original.

Other changes concern paths/provenance, optional source-PDF checking, and display-only field export. The original mathematical acceptance still uses the complete unrounded grids. The downsampled fields do not participate in acceptance or residual calculations.

## Offline reproduction

Use Python 3.11 or compatible Python with NumPy, SciPy and Matplotlib already installed. `requirements-research.txt` lists the exact versions used. These are **research dependencies only**. Do not add them to application/runtime dependencies or import this module into the standard-library application. A UI replay can load the saved JSON and images without these packages.

From the repository root, or any working directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 bash research/rectangular_duct/reproduce.sh
```

The shell script resolves its own location. By default it creates a fresh ignored `output/rectangular-replay-*` directory. It never overwrites the accepted application evidence under `examples/rectangular_experiment/`; attempts to use that directory are rejected. To choose another separate output location:

```sh
RECTANGULAR_OUTPUT_DIR=/absolute/path/to/results bash research/rectangular_duct/reproduce.sh
```

No network calls, installation, accounts, credentials or PDF downloads occur. The default replay uses the numeric transcription in `inputs/experimental_source.json`. The source PDF is neither redistributed nor required. If the user separately has the original PDF, they can request an explicit optional byte audit:

```sh
python research/rectangular_duct/compare_experiment.py --audit-source-pdf /path/to/388313.pdf
```

That flag verifies the original SHA-256 locally. It performs no download. With an alternative results directory, set the same `RECTANGULAR_OUTPUT_DIR`. The optional audit changes provenance only; run it against the separate replay output, then re-run `compare_accepted_evidence.py` and `audit_package.py` with that same output variable to refresh its dependent hashes. Individual research commands write to their selected output and are not the protected replay entry point.

A complete replay takes approximately ten minutes for refined FV verification on the original executor, plus response generation, independent modes and comparison. The scientific results are deterministic on the recorded environment; elapsed time and content hashes of metadata change on a fresh run. The package records exact same-environment numerical identity rather than claiming cross-platform bitwise identity.

## Equations and numerical method

Coordinates span x/H in [0,2], y/H in [0,1]. Dh/H=4/3.

- Solve −laplacian(w)=1, with w=0 on all four walls; normalize v=w/area_mean(w)
- Set theta=(Tw−T)/(Tw−Tin), tau=alpha*z/(Umean*H²)
- Solve diag(v) dtheta/dtau=−K theta, with theta=0 at the walls and theta=1 at the thermal inlet
- Mixed outlet theta=sum(v theta)/sum(v)
- For reported Gz=Re Pr Dh/L, tau_out=16/(9Gz)

Uniform, cell-centered square finite volumes use explicit half-cell wall Dirichlet conductances. Backward Euler solves (M+dt K) theta_new=M theta_old with sparse LU. This is second-order spatial and first-order axial discretization. Mass normalization, every-step heat balance, every-cell positivity and monotonicity, sampled solve residuals, inlet/long-duct limits, exact-series momentum, an independent plug-flow heat series, mesh refinement and time refinement are checked.

The accepted production mesh has 256×128 cells. The first doubling intervals use 512 steps, with dt capped at 0.0000625. Verification includes a 512×256 mesh and doubled time-step counts. Step-halving differences are not total error or uncertainty bounds.

Independent sine-Galerkin continuum thermal calculations use analytical Poiseuille velocity and exact axial exponential propagation of numerically converged modes. They are an independent numerical thermal reference, not an exact analytical thermal solution. Further derivation and the original study narrative are preserved in `original_freeze/README.md`.

Omissions include buoyancy/secondary flow, velocity development, turbulence/transition, temperature-dependent properties, axial fluid/solid conduction, conjugate wall spreading, radiation and viscous heating.

## Evidence and experimental interpretation

The 32 measurements are from P. Wibulswas, *Laminar-flow heat-transfer in non-circular ducts*, UCL 1966, Appendix 7.6, printed pp 124–125. Primary PDF: https://discovery.ucl.ac.uk/1381757/1/388313.pdf. Original audited PDF SHA-256: `8fac58915fcb924f0fb0095f01e15c85de9af85b1f8a39405e71837e889c03ba`.

The target is `(Tw−Tout)/(Tw−Tin)`, computed from printed temperatures. Source Gz is a reduced flow/property input whose precise per-run property evaluation was not recovered. Printed Nu does not exactly reproduce from printed Gz/temperatures and is retained only for traceability. Blank Re cells remain null. No fitted coefficient, heat-transfer multiplier, flow correction, temperature offset or residual-based filtering is used.

The original numerical run passed all 11 mathematical gates. The maximum independent continuum-reference difference was 0.06361% relative. Experimental attenuation mean absolute errors were 2.62 percentage points for 24-inch tests, 4.61 for 13 inches, and 8.82 for 7.5 inches. All 32 rows remain in the replay.

The source has incomplete uncertainty and unresolved applicability concerns involving transition, opposing buoyancy, nonconstant properties and approximate wall/velocity conditions. A source temperature-circuit precision figure is not a complete uncertainty budget. The comparison therefore stores `physical_validation_pass: null`. No actual-aircraft validation or transfer to a device-temperature model follows.

## Integration contract

Recommended repository destinations:

- `research/rectangular_duct/`: these scripts, research requirements, exact input transcription/plans, original freeze, and packaging provenance
- `examples/rectangular_experiment/`: accepted packaged replay JSON, plots, display samples and package manifest

The manifest supplies each proposed destination, exact SHA-256 and byte size. Exclude all logs, caches, `__pycache__`, PDFs and full-resolution NPZ files. Every JSON is below 100 kB; each PNG is below 250 kB. The original historical manifest lists some omitted working artifacts; it is preserved as provenance, not as the package's distribution manifest.

For a physics-page replay, label the panel “Recorded experimental-comparison replay.” Read `experimental_comparison.json` for the 32 fixed cases and `frozen_response.json` for the recorded curve. Read `replay_index.json` for labels/provenance and `display_fields.json` only for visual fields. Residual values are raw attenuation differences; multiply by 100 to display attenuation percentage points. Larger predicted theta means less predicted heat pickup.

Keep this separate from live subproblem computation. Do not present the records as a live CFD solve, an uncertainty-backed validation pass, a new blinded holdout, or aircraft-prediction evidence.

## Promoting a new evidence package

A replay is a separate research result, not an automatic update of the UI. Compare its complete numerical payload and source identities with the accepted package first. Any deliberate promotion requires a reviewed package manifest, an explicit update of the application reader's manifest pin, regression tests, and fresh browser evidence. Elapsed times and metadata hashes can change even when all numerical values agree. The standard-library command `python -S research/rectangular_duct/audit_package.py` audits the current accepted package without scientific dependencies; it does not rerun the solver.
