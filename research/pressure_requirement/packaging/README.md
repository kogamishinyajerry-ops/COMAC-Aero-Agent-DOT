# Package verification and delivery boundary

The inner scientific/replay-input manifest is `research/pressure_requirement/package_manifest.json`. Its separately trusted SHA256 pin is:

`384a5816d373a7344c569322fb789eb642583e296c105a493d68c6187240aa1a`

The read-only CI command checks that exact inner snapshot:

```sh
python -I -S -B research/pressure_requirement/audit_package.py --expected-manifest-sha256 384a5816d373a7344c569322fb789eb642583e296c105a493d68c6187240aa1a
```

The inner snapshot has 273 payload files plus its four manifest chunks and index: 278 verified files. It includes the unchanged scientific appendix and replay code, 13 scientific dependencies and the existing `.gitignore`. Its audit does not claim to pin the later packaging receipts in this directory.

The outer `integration_allowlist.json`, delivered with its own separate expected SHA256, covers every proposed integration file, including these later review/test/replay receipts. Its entries distinguish new appendix files from 14 existing compare-only dependencies. Consolidation must compare all existing dependency bytes, reject mismatches and never overwrite them. Copy only allowlisted new files into absent destinations; do not copy the whole staging workspace or its temporary replay snapshots.

Package verification is a separate chronology from the accepted 191-solve scientific campaign. The initial package replay completed one thermal solve but failed while serializing an inherited NumPy boolean; no accepted case JSON was produced. That failed receipt, old worker and old pin are retained under `failed_attempt_01/`. Only the numerical wrapper serializer changed. The final replay must independently reproduce all six main-root points from a new relocated package and report typed scalar differences. None of these packaging evaluations is inserted into or used to rewrite the scientific campaign's original phase records.

The original 251-entry scientific inventory remains unchanged in `study/manifest_index.json` and its chunks. Exactly 248 non-log inventory artifacts are physically distributed. Three logs are omitted with their paths, sizes and hashes retained in `packaging_disposition.json`; they have no overlap with the 192 preserved exhausted-phase files. No numerical source or historical scientific evidence was rewritten for packaging.
