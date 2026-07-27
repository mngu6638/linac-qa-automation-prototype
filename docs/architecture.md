# Architecture

## Overview

This public edition is a **Django** monolith with server-rendered templates and vanilla JavaScript. It is packaged conceptually as a research prototype for LINAC monthly QA informatics.

```text
Browser (templates + JS wizards)
        |
        v
Django URLs / Views / Services
   |            |              |
QA/Schedule  Film analysis   Dose APIs / Statistics / Reports
   |            |              |
SQLite DB   uploads/ (local)  PhysicsParameters + analysis helpers
```

## Django layout

| Path | Role |
|------|------|
| `QA_Manager/` | Project settings, URLs, WSGI |
| `QAID_Manager/` | Domain app: models, views, templates, static JS/CSS |
| `QAID_Manager/analysis/` | Pure helpers for film geometry + dose formulas (testable without views) |
| `scripts/` | Demo DB init + synthetic film generation |
| `sample_data/` | Synthetic seed metadata and films |
| `tests/` | Synthetic regression tests |

## Database model overview (high level)

- **Linac** — machine inventory + optional commissioning-style reference fields (demo values only in public seed)
- **Dosimeter** — ion chamber inventory
- **QATest / QAStatus / QARecord / QASchedule** — monthly QA documentation and planning
- **Film upload models** — temporary film artifacts for analysis wizards
- **DoseCalculation** — stored dose-calc results linked to a QA record
- **PhysicsParameters** — lookup tables (Ks, kQ-style, film analysis parameters)
- **OrganizationSettings** — branding/templates (generic demo org in public edition)
- **LinacServiceReport / Device** — equipment service documentation

## Film analysis workflow

1. User uploads a raster image and confirms DPI.
2. User crops the region of interest.
3. User provides geometric guidance (lines for field size; centre+radius for star-shot).
4. Server-side analysis (views + `QAID_Manager.analysis`) measures intensity/geometry heuristics.
5. Metrics populate QA entry fields; annotated overlay images may be stored.

Public tests exercise **pure analysis helpers** on synthetic images under `sample_data/films/`.

## Dose calculation workflow

1. User enters chamber readings, temperature/pressure, polarity and recombination inputs.
2. Front-end / API helpers apply TRS-398-style corrections (Ktp, Kpol, Ks, kQ, Dw,Q).
3. Relative checks (symmetry, flatness, output, MU linearity) compare against stored baselines.
4. Confirmed results attach to the QA record.

Educational formula implementations live in `QAID_Manager/analysis/dose_formulas.py`.

## Reporting workflow

QA and service reports are generated primarily as DOCX (with optional PDF conversion hooks). Public edition excludes hospital-branded templates; users may supply their own non-clinical demo templates locally (ignored by git).

## Synthetic demo data flow

```text
scripts/generate_synthetic_films.py → sample_data/films/*.png + expected_geometry.json
scripts/init_demo_db.py → migrate + synthetic org/linacs/chambers/users/schedule
pytest tests/ → regression against synthetic ground truth
```
