# Gap Analysis
Last updated: 2026-06-30

## Scope
This document lists gaps between the current code and a stable, reviewable employer-grade delivery.

---

## Resolved (This Session)
1. ✅ **Database config mismatch** - Fixed `docker-compose.yml` to set `POSTGRES_HOST=postgres` so web service connects to postgres container.
2. ✅ **Schema/model migration drift** - Replaced 12 stale migrations with single authoritative `0001_initial.py` containing all model fields.
3. ✅ **Missing `application_detail.html` template** - Created template to fix 500 error on detail view.
4. ✅ **Test assertion mismatches** - Fixed tests to expect `results`/`count` instead of `applications`/`total`.

---

## High Priority (Remaining)
1. **Application isolation / auth in tests** - Tests create real `auth.User` records but do not isolate app state or permission behavior.
   - Risk: review locks and `review_by` ownership are not actually enforced end-to-end.

2. **View error contract** - `views.py` uses broad `except Exception` for request parsing and returns `server_error` with the exception string.
   - Risk: stack traces leak out of JSON responses during pilot runs.

3. **Missing label-image metadata enforcement** - `LabelImage` stores width/height/image_format, but `application_import` skips image metadata extraction on invalid image uploads.
   - Risk: bad files can pass through with incomplete metadata.

---

## Medium Priority
4. **Media/upload hygiene** - `get_label_upload_path` derives path from `ttb_id` before the app is saved or validated.
   - Risk: filesystem paths depend on untrusted payload content.

5. **No CI or quality gate docs** - README doesn't define `ruff`/`mypy`/`pytest` policy.

---

## Low Priority
6. **Duplicate timezone import** - `cora/views.py` imports `timezone` twice (minor maintainability noise).

7. **Missing `exists()` check before label-image operations** - No empty-state annotation or no-image fallback.