# A complete, bounded engineering story

Open `/nacelle`, wait for the current assembly calculation, then choose **六步设计讲解**. Every entry recomputes the declared cases locally. The story shares the actual mesh/thermal renderer but keeps the workbench's inputs, evidence, view and camera separate. Returning to the workbench restores them. No LLM, remote model, paid API, search optimizer or aircraft-control connection is used.

## One question per screen

1. **What was reconstructed?** The full-load baseline assembly identifies the Mod II motor, two controllers and separate LV intakes. Source-supported topology and inferred dimensions stay distinct
2. **Can full load be interpreted as a temperature prediction?** A separate full-load case uses the paper's pressure increments with explicit approximations. Its total motor flow can approach the published analysis while the gap/slot split and thermal budget remain substantially different. Out-of-domain temperatures are suppressed in the normal visual layer
3. **What happens when ambient temperature rises?** The teaching baseline deliberately uses `heat_scale=0.25`. A synthetic +10 C ambient perturbation holds density, pressures, geometry and heat fixed. It is not a complete weather model or one-quarter motor power
4. **Does adding fins cool the entire system?** Increase each CMC from 24 to 36 fins at the same hot-day boundaries. It cools the HV proxy but increases backpressure, decreases motor flow, raises the winding proxy and adds mass
5. **What does a different design exchange?** A second candidate combines 12 fins per CMC with a 16000 mm² upper motor exhaust (baseline 9000 mm²), under exactly the same boundary/load assumptions. It improves the nominal winding proxy and lowers mass while warming the HV side and increasing passive hydraulic dissipation. Both its thermal benefits and penalties are calculated, not scored with an invented optimum label
6. **Can the design be approved?** Compare nominal temperatures, mass, reference margins and assumption-corner diagnostics. The decision remains to retain research candidates and obtain missing physical evidence, not approve an aircraft design

The full published heat case is never silently replaced by a favorable teaching case. The reduced-heat banner remains visible on every design-comparison page. Source-informed pressure and inferred freestream-pressure modes are labeled separately.

## Reproduction and evidence

```bash
python3 scripts/generate_nacelle_story.py --output output/nacelle-story.json
python3 -m unittest discover -s tests -p test_nacelle_story.py -v
python3 -m aerolab serve
```

`POST /api/nacelle/story` accepts only an empty JSON object and computes the fixed, bounded sequence. It returns each canonical geometry and boundary, whole-file model/source identities, input hashes, geometric fingerprints, full pressure/thermal results, uncertainty scenarios, summaries and candidate-minus-hot-baseline deltas. It accepts no user-supplied target temperature or executable action. The UI can download this exact response on the final screen.

A separate monotonically increasing request token and abort controller guard story computation and mesh fetches. Switching back to the workbench cancels pending requests; late responses cannot reopen the story or replace workbench evidence. Mesh/result fingerprints are checked before displaying each case. The browser test exercises all six screens, actual computed values, exports, mobile layout, Back navigation, cancellation, state restoration and an intentionally wrong mesh fingerprint.

## Audited candidate STEP

The baseline and the exact 12-fin/16000-mm² candidate each passed an independent kernel/interference/contact/STEP audit. Only the baseline is bundled for no-kernel download; CI publishes the two ordinary STEP files and their audit manifests together as `cad-regeneration-evidence`.

```bash
python3 scripts/generate_nacelle.py --out output/nacelle-redesign --params '{"hv_fin_count":12,"motor_exhaust_area_mm2":16000}'
python3 scripts/export_nacelle_step.py --manifest output/nacelle-redesign/manifest.json --output output/nacelle-redesign.step
```

A geometry audit establishes the modeled solids/contacts and lack of unexpected modeled intersections, not manufacturing tolerances, structural adequacy or thermal validity. Other arbitrary custom geometries need their own audit.

## Interpretation

- Software conservation and independent analytical benchmarks verify equations, not hardware accuracy
- The source is itself an analysis reference; its authors lacked nacelle airflow measurements for experimental validation
- Passing the chosen temperature/Mach/Reynolds pressure guards is insufficient to validate rotating and developing passages
- Scenario corners are selected sensitivity assumptions, not confidence intervals, global extrema or certification margins; out-of-domain corner values are explicitly diagnostics
- Reported hydraulic power is passive pressure dissipation, not blower electrical energy, total cooling drag or propulsion penalty
- Component dimensions, materials, flow losses and contacts remain uncertain; manufacturing, strength and aircraft performance have not been established

See [thermal credibility](NACELLE_MODEL.md), [source traceability](NACELLE_SOURCES.md) and the machine-readable `examples/nacelle_credibility.json` for the unfitted multi-condition discrepancy evidence.
