# LINAC QA Automation Prototype

## Overview

This repository is an **AI-assisted Django-based research/educational prototype** for **LINAC monthly quality assurance (QA) informatics**. It demonstrates structured QA workflow design, film-based geometric analysis helpers, TRS-398-oriented dose calculation tooling, reporting hooks, and trend monitoring—framed as a portfolio/research prototype, **not** as clinically approved software.

Related documents: [DISCLAIMER.md](DISCLAIMER.md) · [AI_DEVELOPMENT_DISCLOSURE.md](AI_DEVELOPMENT_DISCLOSURE.md) · [docs/](docs/README.md)

## Clinical Motivation

Monthly LINAC QA is often fragmented across paper forms, spreadsheets, film viewers, and dosimetry worksheets. This prototype explores how a single informatics workflow can support:

- monthly LINAC QA documentation and scheduling,
- film-based geometric QA (field size; collimator/gantry star-shot-style checks),
- TRS-398-oriented absolute and relative dose calculation worksheets,
- structured reporting and equipment/service documentation,
- QA traceability (records, notes, status),
- departmental trend monitoring.

The goal is to show clinical medical physics **workflow design and automation thinking**, not to replace institutionally validated clinical systems.

## Implemented Features

- QA scheduling and documentation (monthly / ad-hoc sessions, status tracking)
- Field-size film analysis (light vs radiation geometry helpers)
- Collimator / gantry star-shot-style geometric analysis
- TRS-398-oriented dose calculation workflow
- DOCX/PDF-style reporting workflow
- QA trend / statistics dashboard
- Synthetic demo data and regression tests

## Explicit Non-Features

- No EPID module
- No DICOM module
- No Winston–Lutz module
- No OD calibration
- No calibrated Gafchromic dose conversion
- No clinical validation
- Not for patient-care or clinical QA release decisions

## Architecture

Django monolith with server-rendered templates and vanilla JavaScript:

- `QA_Manager/` — project settings and URLs
- `QAID_Manager/` — domain models, views, templates, film/dose workflows
- `QAID_Manager/analysis/` — pure helpers for geometry and dose formulas (testable without views)
- `scripts/` — demo DB init and synthetic film generation
- `sample_data/` — synthetic seed metadata and films

See [docs/architecture.md](docs/architecture.md) for details.

## Installation

```bash
# 1) Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
# source .venv/bin/activate

# 2) Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 3) Configure environment
copy .env.example .env          # Windows
# cp .env.example .env          # Linux / macOS
# Edit .env and set a unique DJANGO_SECRET_KEY

# 4) Set SECRET_KEY for the current shell (example)
set DJANGO_SECRET_KEY=dev-only-change-me-to-a-long-random-string
# export DJANGO_SECRET_KEY=dev-only-change-me-to-a-long-random-string

# 5) Migrate and initialize synthetic demo data
python manage.py migrate
python scripts/init_demo_db.py

# 6) Run the development server
python manage.py runserver

# 7) Run tests
python -m pytest tests -q
```

Demo login (change before any shared use):

- username: `demo_admin`
- password: `change-me-before-use`

## Demo Data

All included demonstration data are **synthetic**:

- Organization: **Demo Radiotherapy Physics Department**
- Machines: **Demo Linac A** / **Demo Linac B** (`DEMO-LINAC-001`, `DEMO-LINAC-002`)
- Chambers: **Demo Chamber 001** / **002**
- Synthetic QA schedules and fake CAT/reference numbers
- Synthetic field-size and star-shot PNGs under `sample_data/films/`
- Ground truth: `sample_data/films/expected_geometry.json`

Regenerate films:

```bash
python scripts/generate_synthetic_films.py
```

## Validation Status

- Synthetic regression tests exist (`tests/`)
- Formal phantom validation is **not** complete
- Commercial film-tool comparison is **planned**
- Independent TRS-398 spreadsheet comparison is **planned**
- Clinical deployment validation is **out of scope**

See [docs/validation-plan.md](docs/validation-plan.md) and [validation/](validation/).

## Limitations

- Heuristic image analysis (grayscale / intensity-based)
- User-guided geometry (lines / centre / radius)
- Sensitivity to DPI metadata and film contrast
- No OD calibration and no calibrated Gafchromic dose conversion
- No real clinical / patient / departmental data in this public tree
- No clinical approval; not a medical device

## AI-Assisted Development Disclosure

This prototype was developed with **AI-assisted coding in Cursor**. Clinical QA workflow design, measurement intent, acceptance/validation logic direction, and testing priorities were defined by the author based on clinical medical physics practice. AI assistance accelerated software implementation; the author reviewed and iterated on the system as a research/engineering prototype.

Full text: [AI_DEVELOPMENT_DISCLOSURE.md](AI_DEVELOPMENT_DISCLOSURE.md)

## Non-Clinical-Use Disclaimer

**This repository is a research and educational prototype. It is not a medical device, not clinically validated, and must not be used for clinical QA release decisions.**

See also [DISCLAIMER.md](DISCLAIMER.md).

## Contact / Citation

- **Author:** Mai Dang Khoa Nguyen
- **GitHub:** https://github.com/mngu6638

If you reference this prototype in academic work, cite the repository URL and version in `VERSION.txt`, and state clearly that it is a research/educational prototype (not clinically validated).

## License

MIT — see [LICENSE](LICENSE).
