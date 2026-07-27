# Validation Protocol (Outline)

## Purpose
Define how future phantom/reference studies should be recorded for this research prototype.

## Scope
Geometric film heuristics and TRS-398-style educational dose formulas only. No patient data.

## Materials
- Synthetic films in `sample_data/films/` (baseline)
- Optional: phantom films acquired without PHI
- Independent dosimetry spreadsheet

## Procedure (future)
1. Register expected offsets before analysis.
2. Run software analysis blinded to expected values when possible.
3. Tabulate bias = measured − expected.
4. Store CSV summaries in `validation/results/` (no PHI).

## Acceptance
See `docs/validation-plan.md`. Passing synthetic tests is necessary but not sufficient for research claims beyond software correctness.
