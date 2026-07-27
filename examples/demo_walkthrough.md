# Demo Walkthrough (Synthetic Data Only)

Prerequisites: virtualenv, dependencies, `DJANGO_SECRET_KEY` set.

## 1. Initialize demo database

```bash
python manage.py migrate
python scripts/init_demo_db.py
python manage.py runserver
```

Login:

- user: `demo_admin`
- password: `change-me-before-use`

## 2. Confirm organization

Open **Settings → Organization**. You should see **Demo Radiotherapy Physics Department**.

## 3. Inspect demo machines

Open LINAC settings. Expected:

- Demo Linac A — `DEMO-LINAC-001`
- Demo Linac B — `DEMO-LINAC-002`

All CAT/beam numbers are **fake**.

## 4. Film analysis demo (optional UI)

1. Open QA Entry for a demo schedule/machine.
2. Use film wizard upload with files from `sample_data/films/`.
3. Follow crop → centre/lines → analyze.
4. Compare order-of-magnitude results to `sample_data/films/expected_geometry.json`.

For automated checks instead of UI:

```bash
python -m pytest tests/test_field_size_synthetic.py tests/test_starshot_synthetic.py -q
```

## 5. Dose formula checks

```bash
python -m pytest tests/test_dose_formulas.py -q
```

## 6. Reminder

This walkthrough is educational. Do not use results for clinical QA release decisions.
