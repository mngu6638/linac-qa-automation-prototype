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

## Demo Walkthrough

The screenshots below show the prototype running with synthetic demo data. For a standalone step-by-step guide see [examples/demo_walkthrough.md](examples/demo_walkthrough.md).

### Homepage

![Homepage](screenshots/Homepage.png)

The homepage is the entry point to the QA management workflow. It shows the current organization identity, application version, and navigation to all major modules.

- Provides quick access to QA Schedule, Equipment Management, Statistics, Settings, and Help.
- Displays the organization name and branding area (configurable in Settings).
- Shows a feature summary so new users can orient themselves.
- Links to the About page for methodology references and the Help page for detailed usage guidance.

This matters because a centralized dashboard reduces context-switching between paper forms, spreadsheets, and standalone tools during monthly LINAC QA.

### QA Schedule

![QA Schedule](screenshots/QA_Schedule.png)

The QA Schedule view manages monthly and ad-hoc QA planning across multiple LINACs. Each card represents one machine's scheduled QA session for the selected month.

- Assign up to two QA performers per session for dual-review workflows.
- Set expected QA dates and track status (Scheduled, In Progress, Completed, Passed, Failed).
- Create bulk monthly schedules or non-scheduled (ad-hoc) QA sessions.
- Navigate between months to review past and upcoming QA commitments.
- Supports workflow traceability from schedule assignment through to final QA record.

Structured scheduling with status tracking addresses a common gap in radiotherapy departments where QA task assignment and completion are tracked informally.

### Film Analysis

![Film Analysis](screenshots/Film_Analysis.png)

The Film Analysis panel shows results from the prototype's three film-based geometric checks: field-size mismatch estimation, collimator star-shot-style analysis, and gantry star-shot-style analysis. All analysis is **grayscale / image-intensity heuristic** — not OD-calibrated Gafchromic dose conversion.

- **Field size:** Compares light-field and radiation-field edges; reports per-side shifts (A, B, G, T) in millimetres with automatic axis-rotation correction.
- **Collimator isocenter:** Detects radiation spoke bands along a user-defined circle, pairs opposite spokes, and computes a minimum enclosing circle to estimate displacement from the mechanical centre.
- **Gantry isocenter:** Uses the same star-shot-style geometric analysis pipeline for gantry rotation geometry.
- Results populate QA record fields automatically; annotated overlay images are stored for review.
- Analysis parameters (detection threshold, band width) are configurable in Settings → Physics Parameters.

Film-based geometric QA is a routine part of monthly LINAC checks; this prototype demonstrates how guided analysis and structured result storage can improve reproducibility and traceability compared to manual film reading.

### TRS-398-Oriented Dose Calculator

![Dose Calculator](screenshots/Dose_Calculator_TRS398.png)

The Dose Calculator implements an educational/prototype workflow for TRS-398-style absolute dosimetry corrections. It is **not** a substitute for independent dosimetry worksheets or accredited clinical software.

- Applies temperature–pressure correction (K_tp), polarity correction (K_pol), and ion recombination correction (K_s) using documented TRS-398 formulas.
- Calculates corrected charge (M_Q), beam quality (TPR_20,10), and absorbed dose at reference depth (D_w,Q).
- Supports relative dose checks: symmetry, flatness, output factor, wedge factor, and MU linearity.
- Compares measured values against stored commissioning (CAT) baselines per LINAC and energy.
- Formula references are shown inline so users can verify each calculation step.

Encoding the dosimetry calculation chain in software demonstrates how protocol-oriented workflows can reduce transcription errors, though independent verification remains mandatory.

### Equipment Management

![Equipment Management](screenshots/Equipment_management.png)

The Equipment Management module tracks LINACs, ancillary devices, and service/maintenance history with structured reports and downtime logging.

- Dashboard cards summarize total reports, completion status, and cumulative downtime per machine.
- Service reports capture issue descriptions, actions taken, status (Completed, Pending, Temporary, Breakdown), and downtime hours.
- Filtering by equipment, type, status, keyword, and date range supports audit review.
- Batch PDF/DOCX export enables periodic reporting to management or regulators.
- Dosimeter and device inventories are managed through the same equipment infrastructure.

Structured equipment tracking supports regulatory compliance and provides data for uptime/reliability analysis across a LINAC fleet.

### Settings and Configuration

![Settings](screenshots/Settings.png)

The Settings page provides centralized configuration for the entire QA workflow: machines, detectors, test definitions, physics parameters, users, and organization branding.

- **Dosimeters / LINACs / Devices:** Manage hardware inventory and commissioning reference data.
- **Physics Parameters:** Configure Ks coefficients, kQ tables, film analysis thresholds, and other protocol-specific constants.
- **QA Tests:** Define test names, types (mechanical / beam / film / isocenter), tolerance values, and units.
- **User Accounts:** Role-based access (administrator, medical physicist, radiation therapist).
- **Organization Settings:** Customize homepage branding and report templates.

Configurable tolerances and physics parameters mean the prototype can be adapted to different departmental protocols without code changes, which is important for workflow standardization across sites.

### Suggested demo flow

1. Start from the **Homepage** and review the navigation structure.
2. Open **QA Schedule** and review or create a monthly QA session.
3. Open or create a **QA Record** for a scheduled session.
4. Run the **film-analysis workflow** using synthetic images from `sample_data/films/`.
5. Review the **TRS-398-oriented Dose Calculator** panel and its inline formula references.
6. Check **Equipment Management** for service reports and downtime tracking.
7. Explore **Settings** to see configurable QA tests, physics parameters, and user roles.
8. Run synthetic regression tests from the command line:

```bash
python -m pytest tests -q
```

> This walkthrough uses synthetic demo data only. The screenshots do not represent a clinical deployment.

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
