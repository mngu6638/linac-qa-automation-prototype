# Validation Plan

This prototype currently has **software / synthetic regression tests** only. Formal clinical or phantom validation is **not** complete.

## Current status

| Layer | Status |
|-------|--------|
| Unit tests for dose formulas | Present (`tests/test_dose_formulas.py`) |
| Synthetic field-size regression | Present (`tests/test_field_size_synthetic.py`) |
| Synthetic star-shot regression | Present (`tests/test_starshot_synthetic.py`) |
| Phantom film comparison | Planned |
| Commercial film-tool comparison | Planned |
| Independent TRS-398 spreadsheet comparison | Planned |
| Clinical deployment validation | Out of scope / not claimed |

## Roadmap

1. **Synthetic regression (done in public repo)**  
   Known-geometry PNGs under `sample_data/films/` with `expected_geometry.json`.

2. **Manual measurement comparison**  
   Print or display synthetic films; measure with ruler/caliper overlays; compare to software.

3. **Scanner / DPI sensitivity**  
   Resample images at multiple DPI values; quantify mm bias.

4. **Phantom film comparison**  
   Acquire non-patient phantom films under controlled offsets; compare to manual and commercial tools.

5. **Commercial film tools (if available)**  
   Side-by-side metrics; report bias and precision.

6. **Independent TRS-398 spreadsheet comparison**  
   Fixed synthetic chamber inputs vs spreadsheet gold values for Ktp/Kpol/Ks/kQ/Dw,Q.

## Suggested acceptance criteria (research, not clinical release)

| Check | Suggested research gate |
|-------|-------------------------|
| Synthetic field-size sides | Within ±0.5 mm of ground truth at stated DPI |
| Synthetic star-shot displacement | Within ±0.5 mm |
| Dose formula unit tests | Exact/near-exact agreement with analytic expectations |
| Phantom study (future) | Pre-registered protocol with bias/precision tables in `validation/results/` |

## Limitations

- Passing synthetic tests does **not** imply clinical accuracy.
- Heuristic intensity methods can fail on real films with poor contrast or atypical geometry.
- No patient images should ever enter this repository.

Record future results under `validation/results/` (keep PHI-free).
