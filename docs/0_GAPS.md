# Gap Analysis
Last updated: 2026-06-28

## Scope
This document lists gaps between the current code and a stable, reviewable employer-grade delivery.

---

## Critical
1. Database config mismatch
- `cora/settings.py` switches to Postgres only when `POSTGRES_HOST` is set; `docker-compose.yml` uses `DATABASE_URL`.
- Result: team members can end up on SQLite vs Postgres without realizing it, causing schema drift.

2. Schema/model migration drift
- `models.py` defines lifecycle timestamps; applied DB state can still miss them if migrations are not authoritative.
- This produces runtime `OperationalError` on `/application`.

---

## High
3. Application isolation / auth in tests
- `cora/tests.py` creates real `auth.User` records but does not isolate app state or permission behavior.
- Risk: review locks and `review_by` ownership are not actually enforced.

4. View error contract
- `views.py` uses broad `except Exception` for request parsing and returns `server_error` with the exception string.
- Risk: stack traces leak out of JSON responses during pilot runs.

5. Missing label-image metadata enforcement
- `LabelImage` stores width/height/image_format, but `application_import` skips image metadata extraction on invalid image uploads.
- Risk: bad files can pass through with incomplete metadata.

---

## Medium
6. Media/upload hygiene
- `get_label_upload_path` derives path from `ttb_id` before the app is saved or validated.
- Risk: filesystem paths depend on untrusted payload content.

7. Test route coverage
- `/application/import` is tested; `/submission/import` alias is not independently tested.
- Risk: alias regression can go unnoticed.

8. No CI or quality gate docs
- README doesn’t yet define `ruff`/`mypy`/`pytest` policy, so review acceptance is subjective.

---

## Low
9. Duplicate timezone import
- `cora/views.py` imports `timezone` twice.
- Risk: maintainability noise only.

10. Missing `exists()` check before label-image operations
- `views.py` assumes `label_images` relation is available; no empty-state annotation or no-image fallback.
