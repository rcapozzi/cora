# Gap Analysis: Documentation vs Implementation

**Last Updated:** 2025-07-01  
**Analyst:** AI Assistant  
**Scope:** All design documents in `docs/designs/` vs actual implementation in `cora/`

---

## Executive Summary

| Category | Status | Notes |
|----------|--------|-------|
| **Core Application API** | ✅ **Complete** | `/application` family (list, new, detail, create, release, takeover) fully implemented |
| **Status Endpoint** | ✅ **Complete** | `/status/` implemented per PRD |
| **Lock Management** | ✅ **Complete** | Lock acquisition, release, sweep, takeover all implemented |
| **OCR Worker** | ❌ **Missing** | Design complete, **no implementation** |
| **Authentication/Authorization** | ❌ **Missing** | Documented as "if enabled", not implemented |
| **Rate Limiting** | ❌ **Missing** | Documented as gap, not implemented |
| **Tests** | ⚠️ **Minimal** | Only `utils.test_ids` exists |
| **PATCH /application/{id}** | ❌ **Missing** | Documented as gap |
| **OCR Provider Integration** | ❌ **Missing** | Design references Google Vision, no implementation |

---

## Detailed Gap Analysis

### 1. OCR Worker Implementation ❌ **CRITICAL**

| Document | Design Status | Implementation Status | Gap |
|----------|---------------|----------------------|-----|
| `04-OCR-Worker.md` | ✅ High-level design | ❌ No worker process | Complete missing implementation |
| `04-OCR-Worker-design.md` | ✅ Detailed design | ❌ No worker process | Complete missing implementation |
| `04-OCR-Worker.md` | Google Vision API specified | ❌ No OCR provider | No provider integration |

**Missing Components:**
- `scripts/run_ocr_worker.py` - standalone worker process
- `cora/tasks.py` - `process_ocr_job()` implementation (currently stub)
- OCR provider integration (Google Vision API or PaddleOCR alternative)
- Async worker pool with bounded concurrency (`OCR_WORKERS`)
- PGMQ async read/delete helpers in `cora/pgmq.py`
- Visibility timeout handling, retry logic, backoff
- Graceful shutdown (SIGINT/SIGTERM handling)
- Config: `OCR_WORKERS`, `OCR_QUEUE_NAME`, `OCR_VISIBILITY_TIMEOUT`, `OCR_EMPTY_QUEUE_BACKOFF`, `OCR_PROVIDER`

**Dependencies:** `cora/pgmq.py` (partial), `cora/tasks.py` (stub only)

---

### 2. Authentication & Authorization ❌ **HIGH**

| Document | Requirement | Implementation |
|----------|-------------|----------------|
| `02-Route-application.md` §10 | "Authorization (if enabled) | 401/403" | ❌ Not implemented |
| `02-Route-application.md` §10 | "Authentication \| Django auth (login_required / permission_required)" | ❌ Not implemented |
| All views | Should require auth | All views use `@csrf_exempt` only |

**Missing:**
- No `login_required` / `permission_required` decorators on views
- No authentication middleware configured
- No user permissions model for reviewers
- No API key / token authentication for programmatic access

---

### 3. Rate Limiting ❌ **HIGH**

| Document | Requirement | Implementation |
|----------|-------------|----------------|
| `02-Route-application.md` §10 | "Rate limiting \| Not yet implemented (gap — see gaps doc)" | ❌ Not implemented |

**Missing:**
- No rate limiting middleware (e.g., `django-ratelimit`)
- No per-user/IP rate limits on API endpoints
- No burst/rate configuration

---

### 4. Test Coverage ❌ **HIGH**

| Area | Current State | Required |
|------|---------------|----------|
| Unit tests | Only `cora/utils/test_ids.py` | Comprehensive unit tests for all views, models, utilities |
| Integration tests | None | API endpoint tests, lock workflow tests |
| OCR worker tests | None | Worker process tests, retry logic tests |
| Management command tests | None | Sweep command tests |
| HTMX partial rendering | None | Template fragment tests |
| Lock workflow tests | None | Lock acquisition, release, sweep, takeover |

---

### 5. Missing API Endpoints ❌ **MEDIUM**

| Endpoint | Document Reference | Status |
|----------|-------------------|--------|
| `PATCH /application/{id}` | `03-Route-application_list_detail_plan.md` gap review §10 | ❌ Missing |
| `POST /application/bulk` | `02-Route-application.md` §12 | ❌ Future enhancement |
| Full-text search (`tsvector`) | `02-Route-application.md` §12 | ❌ Future enhancement |
| RBAC for reviewer assignment | `02-Route-application.md` §12 | ❌ Future enhancement |
| WebSocket/SSE real-time updates | `02-Route-application.md` §12 | ❌ Future enhancement |
| Cursor-based pagination | `02-Route-application.md` §12 | ❌ Future enhancement |

---

### 6. OCR Provider Integration ❌ **CRITICAL**

| Document | Specification | Implementation |
|----------|---------------|----------------|
| `04-OCR-Worker.md` | Google Vision API | ❌ No implementation |
| `04-OCR-Worker-design.md` | Google Vision API | ❌ No implementation |
| `cora/tasks.py` | `process_application` stub | ❌ Stub only |

**Missing:**
- OCR provider abstraction layer
- Google Vision API client (or PaddleOCR alternative)
- Image bytes → OCR text extraction
- OCR result persistence to `LabelImage.ocr_text`, `ocr_status`
- Provider timeout/error handling

---

### 7. Documentation Gaps ⚠️ **MEDIUM**

| Document | Issue |
|----------|-------|
| `03-Route-application-list-search.md` §C.3 | Describes "Takeover Warning" UI but doesn't document the separate `/takeover` endpoint implementation |
| `03-Route-application_list_detail_plan.md` | Gap review mentions missing `PATCH /application/{id}` but not in main design doc |
| `02-Route-application.md` | Doesn't document `/application/{id}/takeover` endpoint |
| `01-Workflow.md` | Mentions message broker interaction but not implemented |
| `04-OCR-Worker.md` | References `scripts/demo_ocr_async.py` which doesn't exist in repo |
| `04-OCR-Worker-design.md` | References `scripts/run_ocr_worker.py`, `scripts/demo_ocr_async.py` which don't exist |

---

### 8. Implemented but Undocumented Features ✅

| Feature | Implementation | Documentation Status |
|---------|----------------|---------------------|
| `POST /application/{id}/takeover` | ✅ Implemented (views.py:540) | ⚠️ Partially in 03-Route-application-list-search.md §C.3 |
| `GET /status/` | ✅ Implemented (views.py:107) | ✅ Documented in 05-Route-status-PRD.md |
| `sweep_review_locks` command | ✅ Implemented | ⚠️ Not in design docs |
| `application_takeover` view | ✅ Implemented (views.py:540) | ⚠️ Partial in 03-Route-application-list-search.md |
| `sweep_expired_locks` command | ✅ Implemented | ⚠️ Not in design docs |
| LabelImage OCR fields | ✅ Model has `ocr_text`, `ocr_status` | ✅ Documented |

---

### 9. Model/Schema Gaps ⚠️ **MEDIUM**

| Document | Specification | Implementation | Gap |
|----------|---------------|----------------|-----|
| `02-Route-application.md` §8 | `review_by = CharField(max_length=255)` | `review_by = ForeignKey('auth.User', ...)` | Type mismatch |
| `02-Route-application.md` §8 | Missing `approved_at`, `conditionally_approved_at`, etc. | ✅ Present in model | Doc outdated |
| `02-Route-application.md` §8 | `archived_at = DateTimeField(...)` | ✅ Present in model | OK |

---

## Prioritized Action Plan

### 🔴 PRIORITY 1: CRITICAL - Blocking Production Readiness

| # | Task | Effort | Owner | Dependencies |
|---|------|--------|-------|--------------|
| 1.1 | **Implement OCR Worker Process** | 3-5 days | Backend | `cora/pgmq.py`, config |
| 1.2 | **Implement OCR Provider Integration** | 2-3 days | Backend | Google Vision API key or PaddleOCR |
| 1.3 | **Add Authentication/Authorization** | 2-3 days | Backend | Django auth setup |
| 1.4 | **Add Rate Limiting** | 1-2 days | Backend | `django-ratelimit` |

---

### 🟠 PRIORITY 2: HIGH - Required for Production Quality

| # | Task | Effort | Owner | Dependencies |
|---|------|--------|-------|--------------|
| 2.1 | **Write Comprehensive Test Suite** | 3-5 days | QA/Backend | Test framework |
| 2.2 | **Implement `PATCH /application/{id}`** | 1-2 days | Backend | Status transition logic |
| 2.4 | **Fix Model Documentation Gaps** | 0.5 days | Docs | - |
| 2.5 | **Document Implemented Features** | 1 day | Docs | - |

---

### 🟡 PRIORITY 3: MEDIUM - Important Features

| # | Task | Effort | Owner | Dependencies |
|---|------|--------|-------|--------------|
| 3.1 | **Implement `PATCH /application/{id}` for Status Transitions** | 1-2 days | Backend | 2.3 |
| 3.2 | **Add Full-Text Search (tsvector)** | 2-3 days | Backend | PostgreSQL |
| 3.3 | **Implement Cursor-Based Pagination** | 1-2 days | Backend | - |
| 3.4 | **Add OCR Provider Abstraction** | 1-2 days | Backend | 1.2 |

---

### 🟢 PRIORITY 4: LOW - Future Enhancements

| # | Task | Effort | Owner | Notes |
|---|------|--------|-------|-------|
| 4.1 | **Bulk Import Endpoint (`POST /application/bulk`)** | 2-3 days | Backend | - |
| 4.2 | **WebSocket/SSE Real-Time Updates** | 3-5 days | Fullstack | WebSocket infra |
| 4.3 | **RBAC for Reviewer Assignment** | 2-3 days | Backend | Auth system |
| 4.4 | **WebSocket/SSE for Real-Time Status Updates** | 3-5 days | Fullstack | - |
| 4.5 | **Cursor-Based Pagination** | 1-2 days | Backend | - |

---

## Detailed Task Specifications

### 1.1 Implement OCR Worker Process

**Files to Create/Modify:**
- `scripts/run_ocr_worker.py` - Main worker entry point
- `cora/pgmq.py` - Add async read/delete helpers
- `cora/tasks.py` - Implement `process_ocr_job(app_id, image_id)`
- `scripts/demo_ocr_async.py` - Reference implementation (optional)

**Key Requirements:**
- Long-running async process with `OCR_WORKERS` coroutines
- `pgmq.read(queue, vt=OCR_VISIBILITY_TIMEOUT, qty=1)`
- Retry on failure (don't delete message)
- Backoff on empty queue (`OCR_EMPTY_QUEUE_BACKOFF`)
- Graceful shutdown on SIGINT/SIGTERM
- Config via env: `OCR_WORKERS`, `OCR_QUEUE_NAME`, `OCR_VISIBILITY_TIMEOUT`, `OCR_EMPTY_QUEUE_BACKOFF`, `OCR_PROVIDER`

**Verification:** Ad-hoc script enqueues message → worker updates DB; simulate failure → message not deleted

---

### 1.2 Implement OCR Provider Integration

**Options:**
- **Google Vision API** (per design docs) - Requires GCP credentials, billing
- **PaddleOCR** (open-source alternative) - Self-hosted, no API costs
- **Tesseract** (lightweight) - Lower accuracy

**Implementation:**
- Abstract `OCRProvider` base class
- Implement `GoogleVisionProvider` / `PaddleOCRProvider`
- Config via `OCR_PROVIDER` env var
- Timeout guard on OCR calls
- Error handling → log, don't delete message

---

### 1.3 Add Authentication/Authorization

**Implementation:**
- Add `LoginRequiredMixin` or `@login_required` to all views
- Add `@permission_required('cora.review_application')` for review actions
- Configure Django auth middleware
- Create `Reviewer` permission group
- Add API token authentication for programmatic access (`Authorization: Bearer <token>`)

---

### 1.4 Add Rate Limiting

**Implementation:**
- Add `django-ratelimit` to requirements
- Apply `@ratelimit(key='ip', rate='100/m', method='POST')` to `/application`
- Apply `@ratelimit(key='user', rate='1000/h')` to authenticated endpoints
- Configurable via settings

---

### 2.1 Comprehensive Test Suite

**Test Coverage Targets:**
| Module | Target Coverage |
|--------|-----------------|
| `views.py` | 90%+ |
| `models.py` | 95%+ |
| `tasks.py` | 80%+ |
| `management/commands/` | 90%+ |
| `utils/ids.py` | 100% (already done) |

**Test Types:**
- Unit tests for each view function
- Integration tests for lock workflow (acquire → detail → release)
- Integration tests for takeover tests for takeover flow
- Management command tests (sweep, dry-run)
- HTMX partial rendering tests
- OCR worker process tests (mock PGMQ and OCR provider)

---

### 2.2 Implement `PATCH /application/{id}`

**Specification:**
- Endpoint: `PATCH /application/{id}`
- Purpose: Status transitions (APPROVE, REJECT, NEEDS_CORRECTION)
- Request: `{ "status": "APPROVED", "notes": "Optional correction notes" }`
- Response: Updated application JSON
- Permissions: Reviewer who holds lock or admin
- Side effects: Clear lock fields, set lifecycle timestamps (`approved_at`, `rejected_at`, etc.), enqueue status change message

---

## Quick Wins (Can Do Today)

| Task | Time | Impact |
|------|------|--------|
| Fix model documentation in 02-Route-application.md | 30 min | High |
| Document `/application/{id}/takeover` endpoint in design docs | 30 min | High |
| Document `sweep_review_locks` command in design docs | 30 min | Medium |
| Remove `application/import/` legacy route reference from 02-Route-application.md | 15 min | Low |
| Add `review_by` as ForeignKey in design doc | 15 min | Low |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OCR provider API changes | Medium | High | Abstract provider interface |
| Google Vision API costs | High | Medium | Implement PaddleOCR fallback |
| PGMQ async support missing | Low | High | Use sync helpers in thread pool |
| Auth breaks existing integrations | Medium | High | Phase rollout with feature flag |
| Rate limiting breaks legitimate traffic | Low | Medium | Generous limits, monitoring |

---

## Success Criteria

| Milestone | Criteria |
|-----------|----------|
| **MVP OCR Worker** | Worker process runs, processes queue, updates DB on success, retries on failure |
| **Auth + Rate Limiting** | All endpoints require auth; rate limits enforced; 401/429 responses correct |
| **Test Coverage** | >85% overall; all critical paths tested |
| **Documentation Parity** | All implemented features documented; all documented features implemented |
| **Production Ready** | All Priority 1 & 2 items complete; load tested; monitoring in place |

---

## Appendix: File Inventory

### Implementation Files (cora/)
```
cora/
├── models.py              ✅ Complete
├── views.py               ✅ Complete (missing PATCH, auth)
├── urls.py                ✅ Complete
├── pgmq.py                ⚠️ Sync only (need async)
├── tasks.py               ⚠️ Stub only (need OCR impl)
├── management/commands/
│   ├── sweep_review_locks.py  ✅ Complete
│   ├── sweep_expired_locks.py  ✅ Complete
│   └── load_fixtures.py        ✅ Complete
├── pgmq.py                ⚠️ Sync helpers only
├── utils/
│   ├── ids.py             ✅ Complete
│   └── test_ids.py        ✅ Complete
├── templates/
│   └── cora/              ✅ All templates exist
└── tests/
    └── fixtures/          ✅ Fixtures exist
```

### Design Documents (docs/designs/)
```
docs/designs/
├── 00_GAPS.md                 ← THIS FILE (to be updated)
├── 01-Workflow.md             ✅ Current
├── 02-Route-application.md    ✅ Current (minor doc gaps)
├── 03-Route-application-list-search.md  ✅ Current
├── 03-Route-application_list_detail_plan.md  ✅ Current
├── 04-OCR-Worker.md           ⚠️ Design only, no impl
├── 04-OCR-Worker-design.md    ⚠️ Design only, no impl
├── 05-Route-status-PRD.md     ✅ Implemented
└── 00_GAPS.md                 ← REPLACE THIS FILE
```

---

## Next Steps

1. **Immediate:** Fix documentation gaps (30 min)
2. **Week 1:** Implement OCR Worker + Provider + Auth + Rate Limiting (Priority 1)
3. **Week 2:** Test Suite + PATCH endpoint (Priority 2)
4. **Week 3:** Documentation parity + medium features (Priority 3)
5. **Ongoing:** Future enhancements as capacity allows

---

*This document should be updated as gaps are closed and new ones discovered.*