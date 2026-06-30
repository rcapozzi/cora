# Project Review: CORA
Last updated: 2026-06-28

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

### 3.2 Gaps / Risks
- **Schema drift / missing migration coverage:** Model fields can outpace migration files.
- **DB config split:** `docker-compose.yml` and `cora/settings.py` use different env mechanisms.
- **Test coverage gaps:** Broad import/validation coverage but no shared fixtures/setup and no clear lint/type gate in README.

## 4. Step-by-Step Implementation Plan

### Phase 0 — Stabilize the DB config and migrations
1. Unify DB config -> one env flag, update README with exact `.env` names.
2. Make migration history authoritative.
3. Establish DB runbook.

### Phase 1 — Entrypoint coverage
4. GET `/application` returns filtered list, HTMX + JSON.
5. GET `/application/<id>` returns detail and lease/lock logic.
6. POST `/application/import` accepts structured payload and multipart images.
7. Error contracts: `400`, `409`, `421`, `422`, `413` with JSON schema.

### Phase 2 — Label image pipeline
8. Validate image size, dimensions, format (PNG/JPIF/PDF).
9. Store with path derived from `ttb_id`.
10. Backfill/store OCR metadata via PaddleOCR wrapper.

### Phase 3 — Lock, SLA, and operational tooling
11. Lease expiration, lock heartbeat, and safe release.
12. Expose lifecycle timestamps for reporting.
13. Management commands for queue health checks and retry logic.

### Phase 4 — Quality gates
14. Add `ruff` or `pylint` checks.
15. Require `pytest` and `make check` green before PRs.
16. Document gates in README.

## 5. Security & Compliance Notes
- No secrets in code; `.env` remains uncommitted.
- Release workflow must be tied to reviewer identity and lock acquisition.
- No public GitHub policy unless employer explicitly open-sources.

## 6. Prioritized Backlog

### P0 — Fix runtime schema error on GET /application
- Broken command: `uv run python manage.py test cora.tests --noinput`
- Broken runtime path: `OperationalError: no such column: cola_applications.approved_at`
- Fix path:
  1. Confirm `models.py` reflects intended schema.
  2. Ensure migration applies `approved_at`/`conditionally_approved_at`/`needs_correction_at`/`rejected_at`.
  3. Run `uv run python manage.py migrate --run-syncdb --noinput` and confirm exit 0.

## 7. Test Commands
- Setup: `python3.14 -m venv .venv && source .venv/bin/activate`
- Run tests: `uv run python -m pytest`
- Django check: `uv run python manage.py check`
- Migrate: `uv run python manage.py migrate --run-syncdb --noinput`
