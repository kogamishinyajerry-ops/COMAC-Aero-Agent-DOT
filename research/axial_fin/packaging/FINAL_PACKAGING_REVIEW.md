# Independent axial-appendix packaging review

The packaging checks pass for the stable tooling below. Final assembled-inventory acceptance is recorded after the replay evidence and this review are added; the enclosing manifest is intentionally not embedded here, to avoid a circular hash dependency.

All 34 accepted scientific/review records and the original study manifest are byte-identical. The original manifest identity remains `4d283fbb2dc3171e97dca0094053929c481da375c8f2970b8e1b69d9bd7a3413`. The transverse core remains `bdf9998a7f20cdd5d75fef2f5f0e49c9344ebc1e6f31a5ac955bff366d6c9d4c`, and the axial scalar-run source remains `29174c5a2a3e0549541ac498e8cfc26387e3f54d94b5ddca5b12b76e949e5c4f`.

The standard-library audit performs bounded reads, verifies fixed scientific identities and saved arithmetic, rejects duplicate/nonfinite JSON and returns the exact verified byte snapshot. Independent relocated checks pass all 22 portable contract tests and 17 additional checks. The latter include actual Linux quick numerical replays at both speeds with zero difference in every compared scalar, plus a real post-audit mutation test. Staging used the good snapshot; the final identity check rejected the changed originals before emitting a passing report. No source package bytes were changed by this review.

Three wrapper issues found during review are resolved: post-run source identity is checked, a symlinked output root cannot redirect writes, and unsupported suite values fail before output creation. Existing outputs, protected paths, redirected destination parents and destinations outside the allowed output tree are rejected. Mocked orchestration tests are explicitly distinguished from actual numerical replay.

The current-wrapper final-pair replay is accepted. Both 48×144×480 cases match all eight declared scalar keys exactly; all 15 mathematical gates pass. The case and regenerated-mathematics hashes were independently checked. Times were 94.89 and 92.15 seconds, with process peaks of 925.69 and 927.29 MiB. All 41 files from the tested input manifest `d9cc9323dbe3dec35b8c72fa086ce000bf56108b1305199de664de7ff09c0fd8` remain exact. The accepted replay report hash is `0231dab6b863c54e3db7c72118385feeba0aeb32ef136e3ecf881ee118c83bc6`.

The numerical wrapper uses fresh disposable snapshots, unchanged scientific code and one BLAS thread. Linux-only numerical execution and `ru_maxrss` KiB accounting are disclosed; the audit has no scientific dependencies. Resource limits are numerical-code checks, not an OS containment guarantee. The README separates supported entry points from preserved historical helper scripts. No PDF, network access, installation or full field arrays are required.

Reviewed tooling SHA256:

| File | SHA256 |
|---|---|
| audit_package.py | a804c9d5688685d62759c716c438fedb4cd9d7623aa155f55c349bef17993e0b |
| reproduce.py | b56d124f34e931e42fd55a682c29f73fad3cd2fdc0cada6f0b60412c38549a94 |
| replay_case.py | 7b5a7e2cd661234b1eaf1b32ea8474fdcc1b85c6ad34542a19422e9705aa5d5c |
| test_package.py | 6fa5f688f12f8eb9c65eb90aeee729f276d2cb1313dc4968dc0c4f0bf2485979 |

The scientific finding remains the two conditional matched-grid effects. Packaging does not improve absolute-conductance accuracy, resolve entrance development or other physical omissions, recompute experimental residuals, or establish experimental or aircraft validation. This review adds no rendered browser/UI or actual Windows-execution claim.
