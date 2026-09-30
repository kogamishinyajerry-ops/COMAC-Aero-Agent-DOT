# Modern plate-fin experiment: figure-data feasibility audit

## Outcome

**An approximate independent whole-sink thermal-resistance comparison is feasible. Exact raw-run replication is not yet supported.** Prefer the plate-fin experimental symbols in **Figure 8, printed p94 / PDF page9**, rather than the fitted correlations or the model-reduced Nusselt number in Figure7. This would require a conjugate, developing-flow fin/channel model; the fully developed bare-duct Graetz solver is not the same physical problem.

Source: Pires-Fonseca & Carrasco-Altemani, [journal page](https://revistas.udea.edu.co/index.php/ingenieria/article/view/343222), DOI [10.17533/udea.redin.20230417](https://doi.org/10.17533/udea.redin.20230417). Published online 2023, issue Jan–Mar2024. The [publisher PDF endpoint](https://revistas.udea.edu.co/index.php/ingenieria/article/download/343222/20810985/294727) was identified but returned HTTP403 to the downloader. The publisher-version PDF was retrieved from its [Zenodo record](https://zenodo.org/records/10975619), which lists the same DOI, publisher and authors. No raw spreadsheet supplement is listed there.

## What the plotted quantities mean

- Heat is supplied by a plate resistor; the base is maintained near40°C. Per-run heater power and inlet/base temperatures are not tabulated
- `qcv = electrical power − estimated losses`; loss estimates include radiation, insulation and wire conduction, collectively stated below3% of electrical power. The reported `Rth=(Tb−Tin)/qcv` is therefore a **loss-corrected experimental reduction**, not a raw thermocouple reading
- `V` is **inferred channel-average speed**. Nozzle mass flow is divided equally among17 channels. Two side channels lie between an outer fin and a Plexiglas sidewall; they are not thermally identical to interior channels
- Figure7's `Nu=h* Dh/k` uses inlet-referenced `h*`, obtained by iteratively applying an adiabatic-tip fin-efficiency model to Rth. It must not be treated as an independently measured local convection coefficient
- The numerical section assumes inlet18°C and properties near20°C: rho1.204kg/m³, nu1.516e−5m²/s, k0.02514W/(m K), cp1007J/(kg K), Pr0.7. These are **numerical assumptions, not recovered per-run experimental conditions**. A numerical value for the tested aluminum conductivity was not located
- The source reports experimental uncertainties: Rth1.2%, V3.7–4.6%, Re4.6–5.2%, Nu2.9–3.0%. Do not replace them with digitization precision or call them confidence intervals without identifying their coverage convention

## Vector extraction, including its limits

The PDF contains no raster images on pages8–9. Figures6–8 contain actual vector symbols and axes. Using existing PyMuPDF, the research script reads black filled-square centers, maps them linearly from labeled major axis ticks, and **explicitly excludes fitted curve paths**.

Working artifacts, excluded from the checkpoint:

- PDF `/tmp/fonseca2024_zenodo.pdf`,564,988bytes, SHA-256 `c14571f635c5767ae3fc57f90fb18514595a54dc53918bc7454da084839c5a01`
- Extractor `output/physics-campaign/figure-readout/read_fonseca_vectors.py`
- Readout `output/physics-campaign/figure-readout/fonseca2024_vector_readout.json`, including original PDF-coordinate centers, path indices, source/extractor hashes, figure identities and caveats

Reproduce with `python output/physics-campaign/figure-readout/read_fonseca_vectors.py /tmp/fonseca2024_zenodo.pdf`.

The graph contains **12 recoverable plate-fin square symbols**, although the methods state13 tests per sink. A missing or overlapping test is not invented. Coordinate readout is deterministic for these PDF bytes; it is still a **figure-derived approximation**, not the author's measurement array.

| Figure8 inferred V, m/s | Figure8 Rth, K/W |
| ---: | ---: |
| 4.370 | 0.8830 |
| 6.355 | 0.7293 |
| 8.356 | 0.6398 |
| 10.323 | 0.5711 |
| 12.274 | 0.5216 |
| 13.988 | 0.4707 |
| 14.510 | 0.4621 |
| 16.216 | 0.4266 |
| 17.322 | 0.3980 |
| 18.367 | 0.3730 |
| 19.237 | 0.3620 |
| 20.673 | 0.3311 |

For a conservative independent graphical-readout allowance, retain **half the plotted symbol dimensions**, approximately ±0.257m/s and ±0.0134K/W, separately from experimental uncertainty. These are adopted graphical envelopes, not author uncertainty or confidence intervals. The vector-center computation is much more precise, but pretending that this recovers equally precise underlying measurements is unjustified. A more ambitious, tighter readout allowance would require a separately documented axis/coordinate audit.

## Applicability audit before comparison

1. Use the actual16-fin,90mm-long,11.3mm-tall,0.86mm-thick geometry, with approximately1.86mm gaps and the stated side clearances. The experimental duct is45.2×11.3mm and170mm long; the heat sink begins10mm downstream of its entrance. This is not an imposed fully developed velocity inlet
2. Preserve geometric rounding: `16×0.86 + 17×1.86 = 45.38mm`, not the printed duct width45.2mm. The numerical section instead uses1.85mm for one channel width. Do not conceal this mismatch by claiming exact CAD recovery
3. Freeze a low-Re laminar comparison domain based on a source-supported regime threshold **before evaluating errors**. Report all recoverable points separately, including transition/turbulent cases that the model cannot claim to predict
4. If working with one interior channel, quantify side-channel/finite-array sensitivity; multiplying one heated interior cell by17 silently changes the experiment
5. Compare predicted total `Qconv/(Tbase−Tin)` with `1/Rth`. Fix material/property and heat-loss assumptions independently. Because per-run power/temperature are absent, label the result a linearized conductance/Rth comparison, not replicated raw temperatures. Do not tune aluminum k, inlet shape, fin efficiency or bypass to match the graph
6. Figure6's legend places strip-fin pressure above plate-fin pressure, while the printed Eq13/Eq14 labels assign the larger fit to plate fins. The symbol series can be inspected directly; the fit labels cannot be silently adopted or corrected as measured truth

**Stopping condition for an exact benchmark:** obtain original run rows (nozzle flow, properties/reference temperature, heater power, loss corrections, three base readings, inlet temperature), geometry tolerances/material conductivity, and the missing13th-point explanation. Until then, report the approximate comparison and its limitations. The public figures can test an untuned model; they cannot certify an aircraft design.
