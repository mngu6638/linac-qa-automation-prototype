# Public Release Audit (Final)

**Audited directory:** `linac-qa-automation-prototype-public`  
**Audit date:** 2026-07-27 (final pre-publish cleanup)  
**Scope:** Public repository only. The original private QAID Manager project was not modified.

## 1. Root README completeness

| Check | Result |
|-------|--------|
| Root `README.md` is a full project landing page (not a docs index) | **PASS** |
| Title / Overview / Clinical Motivation | **PASS** |
| Implemented features + Explicit non-features | **PASS** |
| Architecture + link to `docs/architecture.md` | **PASS** |
| Installation (venv, requirements, `.env`, migrate, demo DB, server, tests) | **PASS** |
| Demo data / Validation / Limitations | **PASS** |
| AI disclosure + non-clinical disclaimer | **PASS** |
| Contact / citation placeholders | **PASS** |
| Documentation index kept in `docs/README.md` | **PASS** |

## 2. Sensitive-string search

Search covered application source, templates, docs, configs, and DOCX XML (excluding binary PNGs).

| Pattern / concern | Result in public app tree | Notes |
|-------------------|---------------------------|-------|
| Hospital / site names (e.g. Cho Ray / Chợ Rẫy) | **PASS (none in app/docs/templates)** | Historical scrub complete |
| Site packaging labels (BVCR tokens in code) | **PASS** | Removed from `port_config.py` during final cleanup |
| `bvcr2025` | **PASS** | Not present |
| `Cancer Center` / `Oncology Center` | **PASS** | Not present |
| Real staff names / emails | **PASS** | Demo email only: `demo_admin@example.com` |
| Real LINAC / chamber serials | **PASS** | `DEMO-*` only |
| Hardcoded Django secret (`django-insecure-…`) | **PASS** | `DJANGO_SECRET_KEY` required from environment |
| Packaged update / dist trees | **PASS** | No `update_packages/`, `dist/`, or `build/` directories |

**Acceptable mentions (not secrets):**

- `SECRET_KEY = os.environ.get(...)` in settings (env-required)
- README install examples setting `DJANGO_SECRET_KEY`
- Runtime path names `uploads` / `media` / `db.sqlite3` in Django settings (directories are gitignored and **not present** in the published tree)
- This audit file may mention scrubbed terms when describing exclusions

## 3. Risky files remaining?

| Item | Present in public tree? |
|------|-------------------------|
| `db.sqlite3` | **No** |
| `data/`, `uploads/`, `media/` directories | **No** |
| `dist/`, `build/`, `update_packages/` | **No** |
| `.env` | **No** (only `.env.example`) |
| `*.zip` / `*.exe` | **No** |
| Hospital-branded DOCX | **No** (generic demo templates only) |
| Synthetic PNGs under `sample_data/films/` | **Yes (intended)** |
| Generic `static/images/logo.png` | **Yes (intended)** |

## 4. Tests

```text
pytest tests -q
16 passed
```

(Run during this final audit with a temporary local `DJANGO_SECRET_KEY`.)

## 5. Synthetic data only?

**Yes.** Demo organization, linacs, chambers, schedules, and films are synthetic (`sample_data/demo_seed.json`, `sample_data/films/`). No patient data and no real departmental commissioning tables are included.

## 6. Limitations clearly documented?

**Yes** — root README, `DISCLAIMER.md`, `docs/algorithms.md`, and `docs/validation-plan.md` state heuristic analysis, missing OD/Gafchromic calibration, absent EPID/DICOM/Winston–Lutz modules, incomplete phantom validation, and non-clinical-use restrictions.

## 7. Residual risks (acceptable for public research release)

1. Demo password `change-me-before-use` is intentionally public documentation.
2. `scripts/init_demo_db.py` may set a temporary local-only insecure secret via `setdefault` if unset — documented; do not reuse for shared hosts.
3. Vietnamese clinical UI wording remains in some templates (protocol language, not hospital identifiers).
4. Human should run `git status` after `git init` and confirm ignored runtime paths are not force-added.

## Final judgment

**SAFE FOR PUBLIC GITHUB: YES**

Do not initialize a remote or push from this automation step. After a final human skim, `git init` locally, commit, then create the GitHub remote manually if desired.
