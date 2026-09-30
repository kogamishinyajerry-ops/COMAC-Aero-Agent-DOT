# Conditional cooling-pressure appendix

The independently reviewed model requires the following nominal mechanical pressure-loss budgets to reject 60 W at an 85°C uniform base, with a 25°C inlet, 40% loss of available pressure and the same internal branch sealed:

| Geometry | K=0 | K=1 | K=2 | Fin-only mass |
|---|---:|---:|---:|---:|
| 16 fins × 0.86 mm | 41.77 Pa | 57.07 Pa | 72.36 Pa | 37.78 g |
| 16 fins × 0.60 mm | 33.18 Pa | 49.05 Pa | 64.88 Pa | 26.36 g |

The combined condition receives 0.6 times each listed pressure. Both original 25 Pa nominal cases pass; both original 15 Pa combined cases still fail. K=0 reproduces the accepted model. K=1 and K=2 are illustrative loss scenarios, not measured uncertainty or fitted hardware coefficients. Each root has zero model headroom. These are conditional uniform-base requirements, not hot-spot limits, an installed-system optimum, electrical fan-power requirements or physical/aircraft validation.

Read `study/RESULTS.md` for numerical brackets, domain checks, passive dissipation and original failures; `study/SCOPE_AND_MEASUREMENT.md` for equations and falsification needs; and `study/review/final_review_gate.json` for independent acceptance with retained procedural exceptions.

## Read-only pinned audit

This appendix is independent of the main UI. From the repository/package root, using the separate SHA256 pin supplied with the handoff:

```sh
python -I -S -B research/pressure_requirement/audit_package.py --expected-manifest-sha256 TRUSTED_SHA256
```

The audit uses only the standard library, writes nothing, and works after relocation without Git or the original workspace. The manifest is a bounded, split allowlist. A caller must provide a separately trusted pin; computing a new hash from an untrusted local manifest does not establish identity. `audit(root, pin, return_verified_records=True)` returns a summary and exact verified bytes for snapshot consumers.

The original inventory has 251 entries. This package physically distributes 248 byte-identical non-log artifacts, plus the unchanged original manifest/index files. Three runtime logs are excluded with exact path/size/hash records in `packaging_disposition.json`. None overlaps the 192-file exhausted-phase snapshot, which is preserved completely. All 13 consumed scientific dependencies are unchanged. Their allowlist role is `existing_repository_dependency_compare_only`: consolidation must compare them with the repository, never overwrite a mismatch. The existing `.gitignore` is also a compare-only dependency because it already ignores `output/`.

The original 180-solve phase stopped with two axial brackets unfinished. A separately frozen 11-solve continuation completed verification. Original incomplete outcomes, failed whole-checkout checks, the brief parallel-process deviation and their independent dispositions remain intact. The final evidence contains 18 mesh-root brackets, 185 primary evaluations and six independent reproductions.

## Optional numerical replay

With the existing NumPy/SciPy installation, run:

```sh
python -I -B research/pressure_requirement/replay_roots.py --expected-manifest-sha256 TRUSTED_SHA256
```

This entry runs exactly the six reviewed main-root points. It performs no root search, new sweep or rerun of the 191-evaluation research campaign. It uses the unchanged numerical source from a byte-verified snapshot and reports the expected/replayed values and exact signed scalar differences for every case. It rechecks both the source package and snapshot before reporting success. Numerical agreement is verification of the archived computation, not new independent physical validation.

Replay is supported on Linux, where the tested no-follow descriptor staging and process resource limits apply. It uses one numerical process, one BLAS thread, a 600-second CPU limit, 4 GiB address-space limit, strict 100,000-byte per-file bound and 900-second subprocess wall limit. It never installs software. Audit/reading do not import scientific dependencies.

Every invocation creates a fresh direct child of the verified root's ignored `output/`. An optional `--output output/NEW_NAME` must name a new direct child. Existing files/directories, protected trees, traversal, nested destinations, symlinked roots/parents/leaves and broken symlinks are rejected. No accepted evidence is modified. Failed replay diagnostics remain only in the new output directory.

Packaging tests, with a new report path, run without numerical solves:

```sh
python -I -S -B research/pressure_requirement/test_package.py --expected-manifest-sha256 TRUSTED_SHA256 --report output/NEW_TEST_REPORT.json
```

The package manifest excludes runtime logs, bytecode, PDFs and full arrays. Each JSON is below 100,000 bytes. Source evidence under `study/` was copied unchanged; these wrappers do not rewrite historical labels, paths, source or numerical records.
