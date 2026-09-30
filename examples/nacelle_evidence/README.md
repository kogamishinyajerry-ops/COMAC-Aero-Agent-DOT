# Bounded nacelle evidence

Each JSON file is one complete scenario, including inputs, model/geometry identities, pressure and heat balances, diagnostics, uncertainty corners and source comparisons. No result fields were dropped. The former 703136-byte `examples/nacelle_evidence.json` has been replaced by this directory.

`manifest.json` records ordered case names, file sizes and SHA-256 hashes, plus the canonical SHA-256 of the entire reconstructed evidence object. Every case file is limited to 200000 bytes; current files are approximately 73–81 KB. The index is 2113 bytes.

Reproduce and check all values from the repository root:

```bash
python3 scripts/generate_nacelle_evidence.py --check
python3 -m unittest discover -s tests -p test_nacelle_evidence.py -v
```

To regenerate, omit `--check`. A custom `--output path/manifest.json` writes an index and complete case files beside it. Consumers can call `read_evidence(path)` from `scripts.generate_nacelle_evidence` to recover the original complete object after hash, size and filename validation.

The storage-only follow-up passed the complete 144-test suite, including eight new integrity/reproduction tests, and an independent exact-object review.

This changes storage only. Geometry, thermal equations, all numerical results and their source/input fingerprints remain identical to the pre-split evidence. Software reproducibility is not physical validation or aircraft design approval. Browser CI status is independent and must be checked for the published commit.
