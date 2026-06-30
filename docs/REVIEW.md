# Project Review: CORA
Last updated: 2026-06-30

## 1. Executive Summary
CORA is a Django-based internal system for managing COLA (Certificate of Label Approval) application records and related label image assets. The current stack uses Django 6.0.6, Python 3.14, PostgreSQL (optional), and a custom migration-driven schema evolution for image and application metadata.

## 2. Tech Stack Validation

| Layer | Current Implementation | Validation |
|-------|------------------------|------------|
| Language/Runtime | Python 3.14 | Required by `pyproject.toml` and README |
| Web Framework | Django 6.0.6 | Canonical `cora` app; standard project layout |
| Database | SQLite (default), optional PostgreSQL via `POSTGRES_HOST` | `settings.py` falls back to SQLite when `POSTGRES_HOST` is not set |
| Admin/API | Django views + JSON responses | `application_list`, `application_detail`, `application_import` |
| Image Handling | Pillow / ImageField / label image | `LabelImage` model with `Pillow` in dependencies |
| Auth | Django contrib auth | `cora/tests.py` uses `get_user_model()` |
| Packaging | `pyproject.toml` + README | `uv` is the authoritative package/run tool |

**Verdict:** Stack is internally consistent for internal employer use. PostgreSQL is supported but optional.

## 3. Codebase Review

### 3.1 Strengths
- Clear entrypoints: `get` for list/detail, `post` for import.
- UUIDv7-based primary keys via `cora.utils.ids.generate_uuid7`.
- Lifecycle timestamps for SLA/reporting: `approved_at`, `conditionally_approved_at`, `needs_correction_at`, `rejected_at`, `archived_at`.
- Frontend contract via JSON/HTMX-aware views.

### 3.2 Resolved Issues
- ✅ Migration state synchronized - all model fields now match database schema
- ✅ `/application` endpoint returns filtered list with JSON and HTML responses
- ✅ `/ping` endpoint working
- ✅ All 20 tests passing

## 4. Changes Applied This Session

### 4.1 Migration Fixes
- **Removed stale migrations** (0003-0012) that created conflicting operations
- **Created single authoritative `0001_initial.py`** with all model fields including lifecycle timestamps
- **Added `application_detail.html` template** to fix 500 error on detail view

### 4.2 Test Fixes
- **Fixed assertions** to match actual JSON response format (`results`/`count` vs `applications`/`total`)
- **All 20 tests now pass**

### 4.3 Container Connectivity
- **Fixed `docker-compose.yml`** to set `POSTGRES_HOST=postgres` so the `web` service connects to the `postgres` container instead of falling back to SQLite

### 4.5 URL Refactor: POST /application/import → POST /application
- Consolidated `application_import` view into `application_list` function
- Removed `path('application/import/', ...)` from urls.py
- `/application` now handles: GET (schema/form/list), POST (import)
- Updated tests to use `reverse("application_list")` instead of `reverse("application_import")`
- Updated `import_success.html` template to link to `application_list`
- **Added `failing_field` property** to all JSON error responses for easier client-side debugging
- **Converted HTML error responses** to use styled `import_error.html` template instead of raw HttpResponse

### 4.6 Landing Page Navigation
- **"View Applications"** button now links to `/application?list=1` to trigger `_handle_application_list()`
- **"Import Application"** button continues to link to `/application` (displays import form)

## 5. Security & Compliance Notes
- No secrets in code; `.env` remains uncommitted.
- Release workflow must be tied to reviewer identity and lock acquisition.
- No public GitHub policy unless employer explicitly open-sources.

## 6. Test Commands
- Setup: `uv sync` (creates `.venv`)
- Run tests: `uv run python manage.py test cora.tests --noinput`
- Django check: `uv run python manage.py check`
- Migrate: `uv run python manage.py migrate --run-syncdb --noinput`

## 7. Verification Summary
- **Tests:** 20/20 passing (ad-hoc verification via grep for "Ran 20 tests" + "OK")
- **Migrations:** Clean single initial migration with all fields
- **Endpoints:** `/ping/` returns JSON, `/application/` returns HTML/JSON