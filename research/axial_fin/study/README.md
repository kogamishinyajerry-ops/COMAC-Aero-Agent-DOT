# Bounded axial-fin study

Start with `RESULTS.md` and `study_summary.json`. This is a post-comparison, axial-solid-conduction-only investigation. It is not published application evidence, a blind holdout, an experimental-validation pass, or an aircraft result. The accepted plate-fin package stays frozen.

## Outcome

At the declared4 and10m/s probes, including axial fin conduction decreases conductance by approximately0.01685% and0.01305% under prescribed FD flow and insulated axial fin ends. The matched-grid paired changes are stable under refinement and independent checks. Absolute conductance is less precise: its grid changes are larger than this small paired effect. See the numerical diagnostics, not just the outer acceptance threshold.

No experimental residuals were recomputed. The original12 measurements, source interpretation, material/property scenarios and published package are unchanged.

## Reproduce an exact scalar-run case

Existing NumPy/SciPy are research dependencies. Nothing is installed automatically. The code imports the unchanged `research/plate_fin/conjugate_fin.py` and rejects a different SHA256.

From repository root, choose a new output filename:

`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python output/physics-campaign/axial-fin-study/axial_fin_numerical_run.py --nx 48 --ny 144 --nz 480 --speed 4 --lambda-z 1 --output output/physics-campaign/axial-fin-study/new_probe_V04.json`

The solver reports the axial result and the accepted slice baseline on the identical grid. The command recomputes one case, typically about1–2minutes on the measured environment. It does not overwrite the source package or need the paper PDF. The10m/s case uses the same frozen settings with `--speed 10`.

`axial_fin_numerical_run.py` is the exact full-refinement source. The current `axial_fin.py` is numerically identical and corrects only a full-array sample ownership notice. `verify_label_patch.py` proves that single-value AST difference and exercises both full/half labels. `axial_fin_first_probe.py` retains the exact preliminary tiny-probe version; it predates the tighter-tolerance API and is not the final scalar-run identity.

`verify_math.py` and `run_refinement.py` are the verification/refinement workflows used for this investigation. Their saved outputs preserve the original run hashes. Running them again regenerates this exploratory folder’s evidence under the imported current source; do not mistake such regenerated hashes for the original recorded run. The scientific comparison itself is the matched-grid calculation, not byte-identical elapsed-time metadata.

## Evidence

- `PLAN.md`, `plan.json`: declared equations, domain, resource limits and gates before substantial numerics
- `mathematical_verification.json`:15 mathematical checks, including exact zero-axial recovery, analytic and manufactured limits
- `review/`: independent global direct solution, symmetry and tolerance checks, including the retained too-strict-tolerance failure
- `refinement_plan.json`, `refinement.json`: staged paired-effect convergence; final48×144×480 mesh
- `fields_V04.json`, `fields_V10.json`: labeled moderate-grid illustrative temperature/baseline/difference and signed axial-flux samples; no full-resolution arrays
- `label_patch_verification.json`: unchanged numerical AST and exact scalar source identity
- `accepted_package_immutability.json`: pinned standard-library audit of the unchanged accepted package
- `manifest.json`: compact artifact identities; logs, caches and transient progress files are excluded from the deliverable index

The reported95.8million-equivalent-unknown estimate for48×144×1600 refers to the mirrored computational half-domain representing the full device. The actual study eliminates fluid slices and solves only the global solid temperatures. The largest executed solid system has552,960 unknowns, about934MiB observed peak process memory, and a96s maximum case time.
