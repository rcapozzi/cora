# Gap Analysis: Documentation vs Implementation

**Last Updated:** 2025-07-02

**Scope:** All design documents in `docs/designs/` vs actual implementation in `cora/`

---

## Executive Summary

| Category | Status | Notes |
|----------|--------|-------|
| **Core Application API** | ✅ Complete | `/application` family: list, create, detail, release, takeover |
| **Status Endpoint** | ✅ Complete | `/status/` implemented |
| **Lock Management** | ✅ Complete | Acquisition, refresh, release, sweep, takeover implemented |
| **OCR Worker** | ⚠️ Partial | Worker command exists; uses sync helpers via `asyncio.to_thread`; **no real OCR provider** |
| **Authentication/Authorization** | ✅ Implemented (flagged off) | `cora/authentication.py`, `decorators.py`, `permissions.py`, `ApiToken` model, tests all exist; `CORA_AUTH_REQUIRED` feature flag controls enforcement |
| **Rate Limiting** | ❌ Missing | Documented as gap, not implemented |
| **Tests** | ✅ Good | Import, list, detail/release, status, HTMX partials, auth covered |
| **PATCH Endpoint** | ❌ Missing | Status transitions via detail/HTML flow; no dedicated PATCH route |
| **Legacy Route** | ✅ Resolved | `/application/import` **kept** in `urls.py` for backward compatibility (doc drift fixed) |

---

## Detailed Gap Analysis

### 1. OCR Worker ❌ Critical — End-to-End Processing Blocked

| Doc | Spec | Actual |
|-----|------|--------|
| `04-OCR-Worker.md` | Async worker pool, bounded concurrency | `cora/management/commands/ocr_worker.py` exists; uses `asyncio.to_thread()` for sync `pgmq` helpers |
| `04-OCR-Worker-design.md` | Provider abstraction + async queue handshake | `cora/tasks.py` has stubs only; `_run_ocr_provider` returns empty text |
| `01-Workflow.md` | Message broker ingress | Not implemented in app |

**Blockers:**
- Worker runs but `process_ocr_job` marks `VERIFIED` per-image (FIXME in code); **no all-label completion logic**
- `_run_ocr_provider` is a stub — no real OCR backend (Google Vision, PaddleOCR, etc.)
- **Env/config gap:** No settings for `OCR_WORKERS`, queue names, provider selection in `cora/settings.py`
- Queue name inconsistency: `qr_label_images` in status view vs `q_label_images` in worker

---

### 2. Authentication & Authorization ✅ Implemented (Feature-Flagged Off)

**Design doc:** `06-auth_model_design.md` (Priority 2.1)

**What's implemented in code:**
- `cora/models.py` — `ApiToken` model with PBKDF2 hash, prefix lookup, scopes, expiry, revocation
- `cora/authentication.py` — `ApiTokenAuthentication` (DRF `BaseAuthentication`); `generate_token()` helper
- `cora/permissions.py` — `HasReviewPermission`, `IsLockOwnerOrAdmin` (DRF permission classes)
- `cora/decorators.py` — `auth_required`, `require_review_permission`, `require_write_permission`
- `cora/admin.py` — `ApiTokenAdmin` (read-only for non-superusers)
- `cora/tests/test_auth.py` — 10 test cases covering token auth, session auth, scopes, flag toggle
- `cora/settings.py` — `CORA_AUTH_REQUIRED`, `CORA_TOKEN_PBKDF2_ITERATIONS`, `REST_FRAMEWORK` config
- **Views decorated:**
  - `application_list` (POST) — `@auth_required` + `@require_write_permission`
  - `application_release` — `@auth_required` + `@require_review_permission`
  - `application_takeover` — `@auth_required` + `@require_review_permission`

**Current state:** All decorators check `CORA_AUTH_REQUIRED` flag (default `False`). When `False`, requests pass through. **Auth is implemented but not enforced in dev.**

---

### 3. Rate Limiting ❌ High

- No middleware/config for endpoint throttling
- Would pair naturally with auth (per-user limits) and anonymous IP limits

---

### 4. Test Coverage ✅ Good (Growing)

**Existing:**
- `cora/tests.py`: POST import, idempotency, conflict, validation, list JSON, detail/release, status
- `cora/tests/test_htmx_partials.py`: HTMX content negotiation, search/status/product filters, pagination, empty state, stale/active lock badges
- `cora/utils/test_ids.py`: UUID v7 generation/validation
- `cora/tests/test_auth.py`: Auth enforcement, token scopes, flag behavior

**Remaining gaps:**
- Worker command coverage (no tests for `ocr_worker.py`)
- Sweep command unit tests (no tests for `sweep_review_locks.py` / `sweep_expired_locks.py`)
- Template snapshot/render regression tests

---

### 5. Missing API Endpoints ❌ Medium

| Endpoint | Document Reference | Status |
|----------|-------------------|--------|
| `PATCH /application/{id}` | `02-Route-application.md`, `03-Route-application_list_detail_plan.md` | ❌ Missing |
| `POST /application/bulk` | `02-Route-application.md` §12 | Future |
| Full-text search (`tsvector`) | `02-Route-application.md` §12 | Future |
| RBAC for reviewer assignment | `02-Route-application.md` §12 | Future |
| Cursor-based pagination | `03-Route-application-list-search.md` | Future |
| WebSocket/SSE real-time updates | `02-Route-application.md`, `01-Workflow.md` | Future |

---

### 6. Documentation Drift ⚠️ Medium

| Doc | Issue | Status |
|-----|-------|--------|
| `02-Route-application.md` | Lists `/application/import/` as legacy route **removed** from `urls.py` | **FIXED** — route is kept in `urls.py` |
| `02-Route-application.md` §8 | `review_by` documented as `CharField`; model uses `ForeignKey('auth.User')` | ❌ Open |
| `02-Route-application.md` | `/application/{id}/takeover` absent; **now implemented** | ❌ Open |
| `03-Route-application-list-search.md` §C.3 | Mentions takeover warning UI, not endpoint behavior contract | ❌ Open |
| `03-Route-application_list_detail_plan.md` | Still flags `PATCH /application/{id}` as gap | ✅ Accurate |
| `03-Route-application-list-search.md` | Date-range filter mentioned in §1, not implemented in view | ❌ Open |
| `04-OCR-Worker.md` | References `scripts/demo_ocr_async.py`; real entrypoint is management command | ❌ Open |
| `04-OCR-Worker-design.md` | ✅ Updated to match `ocr_worker.py` concurrency model | ✅ Current |
| `05-Route-status-PRD.md` | ✅ Implemented as designed | ✅ Current |

---

### 7. Implemented but Undocumented Features

- `POST /application/{id}/takeover`: view + URL implemented; docs don't describe response format or 409 behavior
- `GET /ping/` content negotiation (HTML + JSON): not in design docs
- Sweep management commands: `sweep_review_locks` + `sweep_expired_locks` exist; no design doc section
- HTMX partials/partial JSON envelope evolution: no design doc update
- `application_list` now excludes expired `IN_REVIEW` locks from queryset (not just displays stale badge)

---

## Prioritized Action Plan

### 🔴 Priority 1 — Critical (Blocking Production Readiness)

| # | Task | Effort | Dependency |
|---|------|--------|------------|
| 1.1 | **Fix OCR worker path** — `process_ocr_job` needs all-label completion logic; `_run_ocr_provider` needs real backend or functional stub | 1-2 days | OCR provider choice |
| 1.2 | **Provide OCR provider stub** — implement `fallback_text` or PaddleOCR so task path is end-to-end runnable | 1 day | 1.1 |
| 1.3 | **Wire OCR config** — add queue/provider settings to Django config / `.env`-driven defaults | 0.5 day | 1.1 |
| 1.4 | **Document takeover semantics** — in `02-Route-application.md`, add response format, 409 conditions, client behavior | 0.5 day | docs parity |

---

### 🟠 Priority 2 — High (Required for Production Quality)

| # | Task | Effort | Dependency |
|---|------|--------|------------|
| 2.1 | **Enable auth enforcement** — flip `CORA_AUTH_REQUIRED=True` in staging/prod; verify all decorators work | 0.5 day | `06-auth_model_design.md` |
| 2.2 | **Add rate limiting config path** — IP/user limits with feature flag | 1-2 days | middleware |
| 2.3 | **Add `PATCH /application/{id}`** for explicit status transitions | 1-2 days | business rules |
| 2.4 | **Fix docs drift** — update `review_by` to ForeignKey, record takeover endpoint, worker command location | 0.5 day | docs |

---

### 🟡 Priority 3 — Medium (Important Features)

| # | Task | Effort | Dependency |
|---|------|--------|------------|
| 3.1 | **Implement date-range filter** in `application_list` if required by `03-Route-application-list-search.md` §1 | 1 day | view + tests |
| 3.2 | **Finish OCR provider abstraction** and persistence invariants (per-image vs full-application advance) | 1-2 days | 1.1/1.2 |
| 3.3 | **Add worker and sweep command tests** with fake queue/provider | 1-2 days | test infra |
| 3.4 | **Implement auth tests** once enforcement is added (already written, need to run with flag on) | 0.5 day | 2.1 |

---

### 🟢 Priority 4 — Low / Future

- Cursor-based pagination
- Bulk import endpoint (`POST /application/bulk`)
- WebSocket/SSE real-time updates
- RBAC for reviewer assignment

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OCR worker rewrites break queue semantics | Medium | High | Sync-first worker with bounded threads; `asyncio.to_thread` pattern |
| Auth rollout breaks existing integrations | Medium | High | Phase with `CORA_AUTH_REQUIRED` flag; default off |
| OCR provider cost/availability | Medium | Medium | Provider abstraction + fallback stub |
| Docs drift hides broken paths | Low | Medium | CI doc lint / grep checks |

---

## Success Criteria

| Milestone | Criteria |
|-----------|----------|
| **Worker Runs** | Worker command processes a queued message end-to-end with a non-stub provider |
| **Auth + Rate Limiting** | Mutating endpoints reject unauthenticated requests; limit headers/config exist |
| **Test Coverage** | Core API paths have regression tests; worker path covered with fakes |
| **Documentation Parity** | Every implemented route/behavior reflected in `docs/designs/`; all stated routes exist in `urls.py` |
| **Production Ready** | Priority 1 and 2 items complete; no documented required behavior left unimplemented |

---

## Appendix: File Inventory

### Implementation Files (`cora/`)

```
cora/
├── models.py                      ✅ Complete (ApiToken, ColaApplication, LabelImage)
├── views.py                       ✅ Complete (missing PATCH, auth flagged off)
├── urls.py                        ✅ Complete (all routes incl. legacy /import)
├── pgmq.py                        ⚠️ Sync helpers only (used via to_thread)
├── tasks.py                       ⚠️ Stub OCR provider; per-image VERIFIED FIXME
├── authentication.py              ✅ Complete (ApiTokenAuthentication)
├── permissions.py                 ✅ Complete (HasReviewPermission, IsLockOwnerOrAdmin)
├── decorators.py                  ✅ Complete (auth_required, require_review_permission, require_write_permission)
├── admin.py                       ✅ Complete (ApiTokenAdmin read-only for non-superusers)
├── settings.py                    ✅ Complete (CORA_AUTH_REQUIRED, REST_FRAMEWORK config)
├── management/commands/
│   ├── sweep_review_locks.py      ✅ Complete
│   ├── sweep_expired_locks.py     ✅ Complete
│   ├── ocr_worker.py              ⚠️ Runs; needs provider
│   ├── create_api_token.py        ✅ Complete
│   └── load_fixtures.py           ✅ Complete
├── utils/
│   ├── ids.py                     ✅ Complete
│   └── test_ids.py                ✅ Complete
├── templates/cora/                ✅ All templates exist
├── tests/                         ✅ Fixtures exist
└── tests.py + test_htmx_partials.py + test_auth.py  ✅ Core + HTMX + Auth tests
```

### Design Documents (`docs/designs/`)

```
docs/designs/
├── 00_GAPS.md                     ← THIS FILE (updated)
├── 01-Workflow.md                 ✅ Current
├── 02-Route-application.md        ⚠️ Drift: review_by type, missing takeover, legacy import route status
├── 03-Route-application-list-search.md  ⚠️ Drift: date-range filter, takeover contract
├── 03-Route-application_list_detail_plan.md  ⚠️ Flags PATCH as gap
├── 04-OCR-Worker.md               ⚠️ References demo script; worker is management command
├── 04-OCR-Worker-design.md        ✅ Updated to match ocr_worker.py
├── 05-Route-status-PRD.md         ✅ Implemented
└── 06-auth_model_design.md        ✅ Implemented (feature-flagged)
```

---

## Next Steps

1. **Immediate:** Fix OCR worker path (Priority 1.1–1.3) — unblocks end-to-end processing
2. **Week 1:** Enable auth enforcement (Priority 2.1) + rate limiting (2.2)
3. **Week 2:** Add `PATCH /application/{id}` (Priority 2.3) + docs drift fixes (2.4)
4. **Week 3:** OCR provider abstraction (3.2) + worker/sweep tests (3.3)
5. **Ongoing:** Future enhancements as capacity allows

---

*This document should be updated as gaps are closed and new ones discovered.*