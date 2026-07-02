# Gap Analysis: Documentation vs Implementation

**Last Updated:** 2025-07-01

**Scope:** All design documents in `docs/designs/` vs actual implementation in `cora/`

---

## Executive Summary

| Category | Status | Notes |
|----------|--------|-------|
| **Core Application API** | ✅ Complete | `/application` family: list, create, detail, release, takeover |
| **Status Endpoint** | ✅ Complete | `/status/` implemented |
| **Lock Management** | ✅ Complete | Acquisition, refresh, release, sweep, takeover implemented |
| **OCR Worker** | ⚠️ Partial | Worker command exists but uses sync helpers via `asyncio.to_thread`; no OCR provider |
| **Authentication/Authorization** | 📐 Designed | Design doc created (`06-auth_model_design.md`); not yet implemented |
| **Rate Limiting** | ❌ Missing | Documented as gap, not implemented |
| **Tests** | ⚠️ Growing | Import, list, detail/release, status, HTMX partials covered |
| **PATCH Endpoint** | ❌ Missing | Status transitions via detail/HTML flow; no dedicated PATCH route |
| **Legacy Route** | ⚠️ Drift | `/application/import` removed from `urls.py` but still in docs |

---

## Detailed Gap Analysis

### 1. OCR Worker ❌ Critical

| Doc | Spec | Actual |
|-----|------|--------|
| `04-OCR-Worker.md` | Async worker pool, bounded concurrency | `cora/management/commands/ocr_worker.py` exists; uses `asyncio.to_thread()` for sync `pgmq` helpers |
| `04-OCR-Worker-design.md` | Provider abstraction + async queue handshake | `cora/tasks.py` has stubs only; `_run_ocr_provider` returns empty text |
| `01-Workflow.md` | Message broker ingress | Not implemented in app |

- **Blocker:** Worker runs but `process_ocr_job` marks `VERIFIED` per-image (FIXME in code); no all-label completion logic
- **Blocker:** `_run_ocr_provider` is a stub — no real OCR backend (Google Vision, PaddleOCR, etc.)
- **Env/config gap:** No settings for `OCR_WORKERS`, queue names, provider selection in `cora/settings.py`

### 2. Authentication & Authorization 📐 Designed (Priority 2.1)

**New:** `docs/designs/06-auth_model_design.md` specifies:
- Feature-flagged enforcement via `CORA_AUTH_REQUIRED`
- Django `auth.User` + `rest_framework.authtoken` for token auth
- Permission classes: `IsReviewer`, `IsImporter`, `IsOCROperator`, `OwnsLockOrSuperuser`
- Conditional `@auth_required` decorator
- View protection matrix covering all mutating endpoints
- Rollout phases: flag off → staging on → production on

**Current state:** All views `@csrf_exempt`; `review_by` is `ForeignKey('auth.User')` but never enforced.

### 3. Rate Limiting ❌ High

- No middleware/config for endpoint throttling
- Would pair naturally with auth (per-user limits) and anonymous IP limits

### 4. Test Coverage ⚠️ High

**Existing:**
- `cora/tests.py`: POST import, idempotency, conflict, validation, list JSON, detail/release, status
- `cora/tests/test_htmx_partials.py`: HTMX content negotiation, search/status/product filters, pagination, empty state, stale/active lock badges
- `cora/utils/test_ids.py`: UUID v7 generation/validation

**Remaining gaps:**
- Worker command coverage
- Sweep command unit tests
- Auth/rate-limit behavior (once implemented)
- Template snapshot/render regression tests

### 5. Missing API Endpoints ❌ Medium

| Endpoint | Document Reference | Status |
|----------|-------------------|--------|
| `PATCH /application/{id}` | `02-Route-application.md`, `03-Route-application_list_detail_plan.md` | ❌ Missing |
| `POST /application/bulk` | `02-Route-application.md` §12 | Future |
| Full-text search (`tsvector`) | `02-Route-application.md` §12 | Future |
| RBAC for reviewer assignment | `02-Route-application.md` §12 | Future |
| Cursor-based pagination | `03-Route-application-list-search.md` | Future |
| WebSocket/SSE real-time updates | `02-Route-application.md`, `01-Workflow.md` | Future |

### 6. Documentation Drift ⚠️ Medium

| Doc | Issue |
|-----|-------|
| `02-Route-application.md` | Lists `/application/import/` as legacy route; removed from `cora/urls.py` |
| `02-Route-application.md` §8 | `review_by` documented as `CharField`; model uses `ForeignKey('auth.User')` |
| `02-Route-application.md` | `/application/{id}/takeover` absent; now implemented |
| `03-Route-application-list-search.md` §C.3 | Mentions takeover warning UI, not endpoint behavior contract |
| `03-Route-application_list_detail_plan.md` | Still flags `PATCH /application/{id}` as gap |
| `03-Route-application-list-search.md` | Date-range filter mentioned in §1, not implemented in view |
| `04-OCR-Worker-design.md` | **FIXED** — now reflects actual `ocr_worker.py` concurrency model |
| `04-OCR-Worker.md` | Still references `scripts/demo_ocr_async.py`; real entrypoint is management command |

### 7. Implemented but Undocumented Features

- `POST /application/{id}/takeover`: view + URL implemented; docs don't describe response format or 409 behavior
- `GET /ping/` content negotiation: not in design docs
- Sweep management commands: `sweep_review_locks` + `sweep_expired_locks` exist; no design doc section
- HTMX partials/partial JSON envelope evolution: no design doc update

---

## Prioritized Action Plan

### 🔴 Priority 1 — Critical (Blocking Production Readiness)

| # | Task | Effort | Dependency |
|---|------|--------|------------|
| 1.1 | **Fix OCR worker path** — `process_ocr_job` needs all-label completion logic; `_run_ocr_provider` needs real backend or functional stub | 1-2 days | OCR provider choice |
| 1.2 | **Provide OCR provider stub** — implement `fallback_text` or PaddleOCR so task path is end-to-end runnable | 1 day | 1.1 |
| 1.3 | **Wire OCR config** — add queue/provider settings to Django config / `.env`-driven defaults | 0.5 day | 1.1 |
| 1.4 | **Document takeover semantics** — in `02-Route-application.md`, add response format, 409 conditions, client behavior | 0.5 day | docs parity |

### 🟠 Priority 2 — High (Required for Production Quality)

| # | Task | Effort | Dependency |
|---|------|--------|------------|
| 2.1 | **Implement auth enforcement** per `06-auth_model_design.md` — feature-flagged `login_required` + token auth on mutating views | 2 days | `06-auth_model_design.md` |
| 2.2 | **Add rate limiting config path** — IP/user limits with feature flag | 1-2 days | middleware |
| 2.3 | **Add `PATCH /application/{id}`** for explicit status transitions | 1-2 days | business rules |
| 2.4 | **Fix docs drift** — remove `/application/import` refs, update `review_by` to ForeignKey, record worker command location | 0.5 day | docs |

### 🟡 Priority 3 — Medium (Important Features)

| # | Task | Effort | Dependency |
|---|------|--------|------------|
| 3.1 | **Implement date-range filter** in `application_list` if required by `03-Route-application-list-search.md` §1 | 1 day | view + tests |
| 3.2 | **Finish OCR provider abstraction** and persistence invariants (per-image vs full-application advance) | 1-2 days | 1.1/1.2 |
| 3.3 | **Add worker and sweep command tests** with fake queue/provider | 1-2 days | test infra |
| 3.4 | **Implement auth tests** once enforcement is added | 0.5 day | 2.1 |

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
├── models.py                      ✅ Complete
├── views.py                       ✅ Complete (missing PATCH, auth)
├── urls.py                        ✅ Complete
├── pgmq.py                        ⚠️ Sync helpers only (used via to_thread)
├── tasks.py                       ⚠️ Stub OCR provider
├── permissions.py                 📐 Designed (06-auth_model_design.md)
├── decorators.py                  📐 Designed (06-auth_model_design.md)
├── management/commands/
│   ├── sweep_review_locks.py      ✅ Complete
│   ├── sweep_expired_locks.py     ✅ Complete
│   ├── ocr_worker.py              ⚠️ Runs; needs provider
│   └── load_fixtures.py           ✅ Complete
├── utils/
│   ├── ids.py                     ✅ Complete
│   └── test_ids.py                ✅ Complete
├── templates/cora/                ✅ All templates exist
├── tests/                         ✅ Fixtures exist
└── tests.py + test_htmx_partials.py  ✅ Core + HTMX tests
```

### Design Documents (`docs/designs/`)
```
docs/designs/
├── 00_GAPS.md                     ← THIS FILE (updated)
├── 01-Workflow.md                 ✅ Current
├── 02-Route-application.md        ⚠️ Drift: import route, review_by type, missing takeover
├── 03-Route-application-list-search.md  ⚠️ Drift: date-range filter, takeover contract
├── 03-Route-application_list_detail_plan.md  ⚠️ Flags PATCH as gap
├── 04-OCR-Worker.md               ⚠️ References demo script; worker is management command
├── 04-OCR-Worker-design.md        ✅ Updated to match ocr_worker.py
├── 05-Route-status-PRD.md         ✅ Implemented
└── 06-auth_model_design.md        📐 NEW — Priority 2.1 design
```

---

## Next Steps

1. **Immediate:** Fix OCR worker path (Priority 1.1–1.3) — unblocks end-to-end processing
2. **Week 1:** Implement auth per `06-auth_model_design.md` (Priority 2.1) + rate limiting (2.2)
3. **Week 2:** Add `PATCH /application/{id}` (Priority 2.3) + docs drift fixes (2.4)
4. **Week 3:** OCR provider abstraction (3.2) + worker/sweep tests (3.3)
5. **Ongoing:** Future enhancements as capacity allows

---

*This document should be updated as gaps are closed and new ones discovered.*