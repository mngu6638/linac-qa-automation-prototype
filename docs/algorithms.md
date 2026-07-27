# Algorithms

Educational documentation of prototype analysis methods. These are **heuristics**, not certified metrology.

## Field-size analysis (light vs radiation)

### Intent
Estimate side-wise mismatch between light-field guides and radiation-field edges on a scanned film (or synthetic raster).

### Method (prototype)
- User draws 4 light-field and 4 radiation-guide lines.
- Image may be rotated toward an axis-aligned frame from light lines.
- Parallel intensity profiles are sampled in a band around each radiation guide.
- Edge location uses a relative intensity threshold (default ~30% of profile min→max after smoothing).
- Edge points are fit (TLS/PCA); side shifts A/B/G/T are converted to millimetres using DPI.
- Aggregate metric often uses `match_mm = max(A,B,G,T)`.

### Assumptions
- Adequate contrast; irradiated region darker than background in typical setups.
- Correct DPI metadata.
- User guides near true borders.

### Limitations / failure modes
- No optical-density calibration.
- Threshold choice is heuristic.
- Bad guides, DPI errors, low contrast, or non-rectangular fields degrade results.

## Star-shot-style isocentre analysis (collimator / gantry)

### Intent
From a star-shot-like spoke pattern, estimate radiation isocentre location relative to a user-chosen mechanical centre and a spoke-intersection “circle” diameter.

### Method (prototype)
- User sets centre and sampling radius.
- Extract circular intensity profile.
- Detect dark valleys (spokes) with mid-range intensity heuristics; prefer ~8 spokes at 45° spacing.
- Pair opposite spokes → central lines → intersections.
- Approximate radiation isocentre (e.g. enclosing circle of intersections) and displacement from mechanical centre.
- Convert to mm via DPI.

### Assumptions
- Approximately 8-spoke geometry; dark spokes on brighter background.
- User radius intersects spokes cleanly.

### Limitations / failure modes
- Non-8-spoke patterns; wrong radius; inverted contrast; approximate MEC.
- Hard-coded acceptability checks in some view paths are prototype conveniences only.

## Dose calculation workflow (TRS-398-oriented)

Educational helpers implement:

- \(K_{tp}\), \(K_{pol}\), \(K_s\)
- \(TPR_{20,10} = 1.2661 \times PDD_{20,10} - 0.0595\)
- \(k_Q\) table interpolation
- \(D_{w,Q}(z_{ref})\) from \(M_Q \times N_{D,w} \times k_Q\)
- Relative symmetry/flatness indices

See `QAID_Manager/analysis/dose_formulas.py`.

### Limitations
- Not a substitute for accredited dosimetry software or independent worksheets.
- Table content and chamber factors in any demo DB are synthetic unless replaced by the user from public protocol tables.

## Explicit non-features

- **No OD calibration**
- **No calibrated Gafchromic dose conversion**
- Analysis is **grayscale / image-intensity heuristic** with **user-guided geometry**
- **Validation still required** before any quantitative research claim
