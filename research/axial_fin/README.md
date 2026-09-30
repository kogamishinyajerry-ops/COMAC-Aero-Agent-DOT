# Axial fin conduction: compact research appendix

The defined model's conductance decreases by **0.01685% at 4 m/s** and **0.01305% at 10 m/s** when axial fin conduction is added. These are matched-grid paired effects for prescribed fully developed flow, aluminum conductivity 205 W/(m K), and insulated fin ends. The differences are stable at the two probes. Absolute conductance has larger grid changes, so its accuracy must not be inferred from cancellation in the paired difference.

Read [study/RESULTS.md](study/RESULTS.md) for the finding and limitations, or [study/study_summary.json](study/study_summary.json) for compact numbers. This is a post-comparison model-form investigation. Hydrodynamic entrance development, frontal/end convection, base spreading, actual material/air properties and actual flow partition remain unresolved. No experimental residuals were recalculated and this appendix makes no experimental-validation or aircraft-transfer claim.

## Preserved evidence

All 34 scientific/review records and their original manifest are byte-identical to the accepted research study. This includes the original numerical-run source, preliminary source, label-only revision/proof, 15 mathematical gates, paired refinement, independent direct/limiting checks, retained strict-tolerance failure and illustrative field samples. The field samples use 24×72×240; the final scalar result uses 48×144×480. The sample locations explicitly distinguish slab-centered solid temperatures from numerical outgoing-face fluid states.

The dependency `research/plate_fin/conjugate_fin.py` is the exact accepted core, SHA256 bdf9998a7f20cdd5d75fef2f5f0e49c9344ebc1e6f31a5ac955bff366d6c9d4c. It is included for standalone offline replay; in an existing project it already has these bytes and must not be replaced by different bytes. The original plan and source imports retain their original repository-relative locations because `research/axial_fin/study/` preserves their directory depth.

The immutable files preserve historical paths and chronology. `study/README.md` describes the original scratch workflow. **Use the supported entry points below**, rather than running historical writers in the accepted study directory. In particular, historical finalize/review convenience scripts can depend on the original surrounding experiment package; they are preserved as provenance, not advertised as standalone commands. The safe wrapper runs `verify_math.py` only inside a disposable snapshot and runs scalar cases using the exact `axial_fin_numerical_run.py`.

## Offline integrity check, no scientific dependencies

From the repository or relocated package root:

    python -S research/axial_fin/audit_package.py --expected-manifest-sha256 <delivered-manifest-sha256>

The manifest is `research/axial_fin/package_manifest.json`. Trust requires a separately obtained expected manifest hash. The audit uses only the Python standard library, stat-preflights and bounds every read, verifies all original identities and saved arithmetic, and does not execute the model. An unpinned audit checks internal consistency only.

Python API: `audit(root, expected_manifest_sha256=None, return_verified_records=False)`. With `True`, it returns `(summary, records, manifest_sha256)`, with canonical repository paths mapped to the exact immutable bytes verified in that call. Consumers must use those bytes rather than reopen files after auditing.

## Safe numerical reproduction

Requires **Linux**, Python 3.10+, NumPy and SciPy already installed. No installation, network, PDF, logs, full arrays or caches are required. Audit/reading works without Linux; numerical replay rejects other platforms explicitly because the unchanged source interprets `resource.getrusage().ru_maxrss` as KiB. Linux peak RSS includes Python/libraries. Each scalar case gets a fresh subprocess, so its high-water figure is not inherited from a previous case. This packaging choice changes resource metadata, not equations or numerical inputs.

    python research/axial_fin/reproduce.py --expected-manifest-sha256 <delivered-manifest-sha256>

Default `--suite final` reruns all 15 compact mathematical gates and both final 48×144×480 cases, typically a few minutes on the measured environment. `--suite quick` substitutes the two 12×36×120 pilot cases; `--suite refinement` repeats all 14 declared grid cases and retains the original staged resource guard. None recomputes experimental residuals. BLAS thread counts are fixed to one. Original per-case limits remain 300 seconds, 350 fluid sweeps and 1.5 GiB process peak memory, with a 30-minute total replay cap. These are numerical-code checks rather than an OS-enforced sandbox limit.

Outputs go to a fresh `output/axial-fin-replays/run_<random-id>/`. The project ignores `output/`; a standalone snapshot has no Git metadata. Optional `--output` must name a new directory inside the selected root's `output/`. Existing directories and protected destinations are refused. Every source byte copied into the disposable workspace comes from the single verified audit snapshot. New elapsed/resource metadata and verification hashes are labeled packaging replay. They are never promoted over accepted evidence. A completed run records case differences, the compared scalar keys and a conservative absolute equivalence tolerance of 1e-9; inspect the actual differences, rather than treating this tolerance as an uncertainty bound.

The original accepted numerical finding relies on the original verification/refinement/review records. Packaging replays test relocation and reproducibility; they do not reset its pre-comparison chronology or establish a new physical-validation pass.
