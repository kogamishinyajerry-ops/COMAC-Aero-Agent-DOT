# Packaging-only evidence

These records were created after the original axial study and its independent scientific acceptance. They do not replace any file in `../study/` or recalculate the experiment's residuals.

- `replay_input_manifest.json` pins the 41-file numerical-replay input snapshot. Its SHA256 is d9cc9323dbe3dec35b8c72fa086ce000bf56108b1305199de664de7ff09c0fd8. The final appendix adds packaging records and a larger outer manifest; every file in this input snapshot remains byte-identical.
- `final_replay/replay_report.json` records both final 48×144×480 cases run from a fresh relocated root using the delivered wrapper, plus all 15 mathematical gates. Its case-file references are relative to `final_replay/`; the regenerated mathematical record is saved alongside them. Timing/resource metadata belong to this replay, not the original acceptance.
- `independent_packaging_checks.json` records 17 independently checked boundaries and a separate actual two-case quick numerical replay. Its temporary fixture paths describe the historical packaging test location; fixtures and logs are not delivered.
- `packaging_tests.json` and `independent_stdlib_contract_tests.json` record separate executions of the 22 standard-library contract tests. Some orchestration tests mock subprocess output and are explicitly not numerical replays. Repeat with `python -S research/axial_fin/test_package.py --output <new-test-report.json>` from the package root. The output filename must be new; disposable test directories are created only below `output/`.
- `source_preservation_check.json` and the original study manifest document exact byte preservation. `FINAL_PACKAGING_REVIEW.md` closes the packaging review; it does not repeat or broaden the scientific claim.

The original final-pair grid result is unchanged: conductance decreases by about 0.01685% and 0.01305% at the two probes. Stable cancellation supports the paired effect; absolute conductance is less precise, and entrance development remains unresolved.
