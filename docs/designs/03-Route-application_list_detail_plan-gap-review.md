# Gap Review: `03-Route-application_list_detail_plan.md` vs Current Codebase

**Source Plan:** `docs/designs/03-Route-application_list_detail_plan.md`  
**Review Date:** 2026-07-01  
**Status:** Significant progress — core views implemented, but critical specification gaps remain.

---

## Summary

| Phase | Plan Item | Status | Notes |
|-------|-----------|--------|-------|
| 1 | Database Migration | ✅ Done | Migration `0004` applied with lock fields |
| 2 | `GET /application` View | ✅ Done | Implemented in `_handle_application_list` |
| 3 | `GET /application/{id}` View | ⚠️ Partial | Implemented with content negotiation, but lock logic deviations |
| 4 | `POST /application/{id}/release` View | ⚠️ Partial | Implemented with 200 status, fixed prior_status fallback |
| 5 | Model `prior_status` Field | ✅ Done | Already in model + DB |
| 6 | URL Routing | ⚠️ Partial | `application/import/` route exists but uses `re_path` |
| 7 | Templates | ✅ Done | `application_list.html`, `application_detail.html`, `partials/application_table.html` exist |
| 8 | Test Matrix | ❌ Not Done | No test file created |

---

## Detailed Gaps

### 1. URL Routing — Minor Issues

**Plan (Phase 6):**
```python
re_path(r'^application/?$', views.application_list, name='application_list'),
re_path(r'^application/(?P<id>\d+)/?$', views.application_detail, name='application_detail'),
re_path(r'^application/(?P<id>\d+)/release/?$', views.application_release, name='application_release'),
```

**Current (`urls.py`):**
```python
re_path(r'^application/(?P<id>[0-9a-f-]{36}|\d+)/?$', views.application_detail, name='application_detail'),
re_path(r'^application/(?P<id>[0-9a-f-]{36}|\d+)/release/?$', views.application_release, name='application_release'),
re_path(r'^application/?$', views.application_list, name='application_list'),
re_path(r'^application/import/?$', views.application_create, name='application_create'),
```

**Issues:**
- Plan uses numeric ID (`\d+`) but model uses UUID; current code supports both — acceptable.
- `application/import/` route uses `re_path` instead of `path()` — works but inconsistent.
- Route order: `application/import/` comes after `application/` list route — correct since regex doesn't conflict.

---

### 2. `GET /application/{id}` — Content Negotiation ✅ Implemented

**Plan:** Return JSON for `Accept: application/json`, HTML for `Accept: text/html`.

**Current (lines 621, 684-718):**
```python
requires_json = request.headers.get('Accept') == 'application/json'
# ...
if requires_json:
    return JsonResponse({...})
return render(request, 'cora/application_detail.html', context)
```

**Status:** ✅ Works for exact `application/json`. Gap: doesn't handle `application/json; charset=utf-8` or wildcards.

---

### 3. `GET /application/{id}` — Lock Acquisition Logic Deviations

| Scenario | Plan Spec | Current Code | Gap |
|----------|-----------|--------------|-----|
| Status `RECEIVED`/`VERIFIED` + auth user | Acquire lock: `IN_REVIEW`, set `prior_status`, `review_started_at`, `review_by` | ✅ Matches (lines 638-644) | — |
| Status `IN_REVIEW`, lock **expired** (>15 min) | **Acquire lock** (same as above: set `IN_REVIEW`, new `prior_status`, etc.) | **Re-acquires lock** but uses `previous_status` (captured before transaction) instead of `app.status` (lines 653-660) | ⚠️ `previous_status` = status at fetch time, not `app.prior_status`. If status changed between fetch and transaction, wrong prior_status stored. |
| Status `IN_REVIEW`, lock **active**, **foreign** user | Return 200 with `takeover_warning = True` | Sets `take_over_warning = True`, includes in both JSON and template context (lines 661-663, 681, 700) | ✅ Works |
| Status `IN_REVIEW`, lock **active**, **same** user | Refresh lease: `review_started_at = now()` | ✅ Matches (lines 664-667) | — |
| Status `APPROVED`/`REJECTED`/etc. | Read-only, no lock mutation | ✅ Matches (lines 669-670) | — |

**Critical Gap:** Expired lock handling uses `previous_status` (captured at line 627, outside transaction) instead of `app.prior_status` (the actual prior status before lock). If another process changed status between fetch and transaction, wrong value stored.

---

### 4. `GET /application/{id}` — Missing `select_for_update()` on Initial Fetch

**Plan (Phase 4):** "Uses `select_for_update()` inside transaction for release. Detail view should also lock the row during the lock-acquisition transaction to prevent race conditions."

**Current (lines 624, 635):**
```python
app = get_object_or_404(ColaApplication, id=id)  # No lock
# ...
app = ColaApplication.objects.select_for_update().get(id=id)  # Lock acquired HERE
```

**Gap:** Row not locked during initial fetch (line 404 check. Small window where another transaction could delete the row. Should use `select_for_update(nowait=True)` or handle `DoesNotExist` inside transaction.

---

### 5. `GET /application/{id}` — JSON Response Missing Fields

**Plan (Phase 3, Step 4):** "Returns a JSON representation of the application, including nested `label_images` list."

**Current (lines 687-712):** Returns subset of fields. Missing:
- `cola_application_id`
- `ttb_authorized_signature`
- `created_at`, `updated_at`, `archived_at`
- `review_started_at`, `review_by`, `prior_status`
- `approved_at`, `conditionally_approved_at`, `needs_correction_at`, `rejected_at`

Template context has full `app` object, but JSON serialization is manual and incomplete.

---

### 6. `POST /application/{id}/release` — HTTP Status Fixed

**Plan:** "Returns `204 No Content` (beacon ignores the body)."

**Current (lines 735-743):** Returns `200 OK` with JSON body.
```python
return JsonResponse({...}, status=200)  # Not 204
```

**Gap:** Uses `200` instead of `204`. Body included — `sendBeacon` ignores body anyway, but spec says `204`.

---

### 7. `POST /application/{id}/release` — `prior_status` Fallback ✅ Fixed

**Plan:** `prior_status` field captures pre-lock state; release should revert to it.

**Current (line 729):**
```python
original_status = app.prior_status or 'RECEIVED'
```
✅ Correctly defaults to `'RECEIVED'` if `prior_status` is `None`.

---

### 8. `application_release` — Anonymous User Handling

**Current (lines 726, 728):**
```python
current_user = request.user if request.user.is_authenticated else None
# ...
if (app.status == 'IN_REVIEW' and app.review_by == current_user):
```

If anonymous, `current_user` is `None`. `app.review_by` is FK to `User` — never `None`. Anonymous release always hits "no-op" path. This is probably fine for `sendBeacon` (no auth), but not documented.

---

### 9. Templates — HTMX Attributes Verification Needed

**Plan (Phase 7):** Specific HTMX attributes for search input and status filter:
```html
<input id="search-input" name="q" hx-get="/application" hx-target="#results-body" hx-trigger="keyup changed delay:300ms" hx-include="#filter-form">
<select name="status" hx-get="/application" hx-target="#results-body" hx-trigger="change" hx-include="#filter-form">
```

**Current:** `partials/application_table.html` exists (3708 bytes) — content not verified against plan.

---

### 10. Missing `PATCH /application/{id}` for Status Transitions

**Gap Review `02-Route-application-gaps.md` #11:** "PATCH `/application/{id}` — Not specified — partial updates for status transitions? — High — needed for approve/reject"

**Current:** Not implemented. Detail view renders form but no handler for approve/reject actions.

---

### 11. Missing Test Matrix Implementation

**Plan (Phase 8):** 14 test scenarios listed.

**Current:** `cora/tests.py` exists but contains only basic stubs (`TestCase`, `override_settings`). No tests for list, detail, lock, release scenarios.

---

## Action Plan

| Priority | Task | Owner | Est. Effort |
|----------|------|-------|-------------|
| **P0** | Fix expired lock handling: use `app.prior_status` inside transaction, not `previous_status` | Backend | 15 min |
| **P0** | Add `select_for_update()` to initial fetch in `application_detail` | Backend | 10 min |
| **P0** | Complete JSON response in `application_detail` with all model fields | Backend | 20 min |
| **P0** | Change `application_release` to return `204 No Content` (empty body) | Backend | 10 min |
| **P1** | Verify `partials/application_table.html` has required HTMX attributes | Frontend | 30 min |
| **P1** | Update URL route for `application/import/` to use `path()` | Backend | 5 min |
| **P2** | Implement `PATCH /application/{id}` for approve/reject | Backend | 1 hr |
| **P2** | Write test matrix cases (Phase 8) in `cora/tests.py` | QA | 2 hr |

---

## Files to Modify

1. `cora/views.py` — `application_detail` (lock logic, JSON fields, select_for_update), `application_release` (status code)
2. `cora/urls.py` — Change `re_path` to `path` for `application/import/`
3. `cora/templates/cora/partials/application_table.html` — Verify HTMX attributes
4. `cora/templates/cora/application_detail.html` — Verify `take_over_warning` usage
5. `cora/tests.py` — Add test cases

---

## Notes

- Lock fields (`review_started_at`, `review_by`, `prior_status`) and indexes already migrated and present in DB — **Phase 1 and 5 complete**.
- `sweep_review_locks` management command exists and works — handles background expiry cleanup.
- `application_list` view (`_handle_application_list`) closely matches plan specification including HTMX partial support.