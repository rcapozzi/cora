# Gaps & Open Questions — `/application` Endpoint Consolidation

Source documents reviewed:
- `02-Route-application-import.md`
- `02-Route-application-import-plan.md`
- `03-Route-application-list-search.md`
- `03-Route-application_list_detail_plan.md`

---

## 1. Route Conflicts & URL Ordering

| Gap | Detail | Resolution Needed |
|-----|--------|-------------------|
| Import route vs Detail route | Both use `/application/...`. The detail route uses regex `r'^application/(?P<id>[0-9a-f-]{36}|\\d+)'` which could capture `import` if UUID pattern weren't strict. | Confirm UUID pattern excludes literal `import`. Current pattern `([0-9a-f-]{36})` is safe. |
| Dual list routes | `application_list` handles both `GET /application` (list) and `GET /application?schema=1` (schema). This mixes concerns. | Consider separate `application_schema` view or keep as-is with clear docs. |

---

## 2. Payload Schema Inconsistencies

| Gap | Source A | Source B | Resolution |
|-----|----------|----------|------------|
| `PUT` vs `POST` | `02-Route-application-import.md` line 95: *"example payload for `PUT application/import`"* | All other docs and code use `POST /application` | Typo in import doc — should be `POST`. |
| `cola_application_id` required? | Import doc example includes it; schema marks it optional (integer, not required) | Plan doc doesn't mention it | Keep optional — server-assigned. |
| `id` in payload | Example includes `"id": 102`; schema marks `id` as integer type (not explicitly required) | Plan doc BR-006 says "strip server fields" | Document: client may send but server ignores. |
| `label_images.id` | Example includes `id` fields; schema has `id` as integer | Plan doc BR-006 says strip server fields | Same — server ignores. |

---

## 3. Status Code Discrepancies

| Scenario | Import Doc | Plan Doc | Consolidated Doc | Notes |
|----------|------------|----------|------------------|-------|
| Success new | 201 | 201 | 201 | Agreed |
| Idempotent duplicate | 200 | 200 | 200 | Agreed |
| Conflict | 409 | 409 | 409 | Agreed |
| File too large | 413 | 413/422 | 413/422 | Plan says both; need decision |
| Invalid format | 415 | 415/422 | 415/422 | Plan says both; need decision |
| Too many images | 400/422 | 422/400 | 422 | Prefer 422 for semantic validation failure |
| Validation error | 400/422 | 422 | 422 | Standardize on 422 |

**Decision needed**: Pick one code per error class and document rationale.

---

## 4. Missing/Incomplete Specifications

| Gap | Description | Priority |
|-----|-------------|----------|
| Rate limiting | Not specified in any doc (BR-012 mentions auth but not rate limits) | Medium |
| `prior_status` field | Detail plan Phase 5 adds it; not in import docs or model | High — needed for lock release |
| `review_by` field type | Plan uses `CharField` for user identifier; no auth integration specified | Medium |
| OCR task contract | Plan mentions "Enqueue Background OCR Task" but no queue schema defined | Medium |
| Pagination style | List doc discusses offset vs cursor but no final decision recorded | Low |
| DELETE `/application/{id}` | Not specified — is deletion allowed? | Medium |
| PATCH `/application/{id}` | Not specified — partial updates for status transitions? | High — needed for approve/reject |
| HTMX `hx-push-url` | Not addressed — browser history for filter state | Low |
| CORS / API versioning | Not mentioned | Low |

---

## 5. Lock & Concurrency Gaps

| Gap | Current State | Risk |
|-----|---------------|------|
| Lock acquisition race | `GET /application/{id}` uses `select_for_update()` but no explicit ordering on concurrent requests | Two agents could both pass the `review_by != current_user` check before either commits |
| Lock expiration sweep | No background job to auto-revert stale `IN_REVIEW` locks; only filtered out of list query | Orphaned locks persist indefinitely in DB |
| `prior_status` persistence | Added in detail plan but not in import plan or model migrations | Release endpoint will fail without it |
| Takeover UX | Warning returned but no `POST /application/{id}/takeover` endpoint defined | Agent B cannot actually take over — only warned |

---

## 6. Content Negotiation Edge Cases

| Scenario | Specified? | Gap |
|----------|------------|-----|
| `GET /application` with `Accept: application/json` + `?list=1` | Yes (plan) | What if both `?schema=1` and `?list=1`? |
| `POST /application` with `Accept: text/html` but client sends JSON (not multipart) | Import doc says form submits as multipart; plan says browser gets HTML | What if API client sends `Accept: text/html` with multipart? |
| `GET /application/{id}` with `Accept: application/json` on HTML-originated session | Detail plan handles both | No gap — covered |

---

## 7. File Storage & Naming

| Gap | Detail |
|-----|--------|
| `get_label_upload_path` uses `ttb_id` | What if `ttb_id` contains filesystem-unsafe chars? (Currently alphanumeric + dash) |
| Max 1.5 MB per image | Plan says 1.5 MB; import doc doesn't specify exact limit |
| Allowed formats: PNG, JPG | What about HEIC, WEBP, TIFF? Explicit reject list needed. |
| Width/height extraction | Plan says use Pillow headers only — not implemented in any code yet |

---

## 8. Audit Logging

| Field | Import Doc | Plan Doc | Missing |
|-------|------------|----------|---------|
| `timestamp` | ✅ | ✅ | — |
| `event` | ✅ | ✅ | — |
| `ttb_id` | ✅ | ✅ | — |
| `applicant_name` | ✅ | ✅ | — |
| `fanciful_name` | ✅ | ✅ | — |
| `cola_application_id` | ✅ | ✅ | — |
| `client_ip` | ❌ | ✅ | Add to import doc |
| `user_agent` | ❌ | ❌ | Consider adding |
| `request_id` (trace) | ❌ | ❌ | Consider for distributed tracing |

---

## 9. Testing Gaps

| Test Case | Covered in Plan? | Notes |
|-----------|------------------|-------|
| Concurrent lock acquisition | ❌ | Race condition test needed |
| Lock expiry background sweep | ❌ | No sweep job designed |
| File streaming memory usage | ❌ | Load test with 4×1.5MB uploads |
| Idempotency with partial image match | ❌ | What if metadata matches but file bytes differ? |
| HTML form CSRF token handling | ❌ | `@csrf_exempt` on import; form needs `{% csrf_token %}` |
| Pagination boundary (last page, empty results) | ✅ | Covered in matrix |
| HTMX partial without filter form | ❌ | `hx-include="#filter-form"` assumes form exists |

---

## 10. Migration & Deployment Gaps

| Item | Status | Blocker |
|------|--------|---------|
| `review_started_at`, `review_by`, `prior_status` fields | Added to model per detail plan | Migration not applied (`makemigrations` not run) |
| Database indexes on `status`, `brand_name`, `product_type`, `date_of_application` | Defined in model | Same — needs migration |
| `ColaApplication` / `LabelImage` tables | Defined in plan | Old `ApplicationSubmit` / `ApplicationImage` still in DB? |
| Static files for import form CSS/JS | Referenced in plan | Not created yet |

---

## 11. Open Decisions Requiring Input

| Decision | Options | Recommendation |
|----------|---------|----------------|
| File too large: 413 vs 422 | 413 (HTTP semantic) vs 422 (validation semantic) | 413 — it's a payload size limit |
| Invalid format: 415 vs 422 | 415 (media type) vs 422 (business rule) | 415 — it's a Content-Type mismatch |
| Cursor vs offset pagination | Offset (simple) vs Cursor (scale) | Offset for MVP; cursor if >100k rows |
| Auth model | Session + CSRF vs Token vs API Key | Session for browser; token for API |
| Background lock sweeper | Celery beat / cron / pg_cron | Cron job calling management command |

---

## 12. Document Hygiene

| Issue | Files Affected |
|-------|----------------|
| Duplicate `02-Route-application-import.md` listed twice in review prompt | — |
| Import doc references `PUT` instead of `POST` | `02-Route-application-import.md` line 95 |
| Plan doc references `docs/use_cases/02-Route-application-import.md` which doesn't exist in provided set | `02-Route-application-import-plan.md` line 3 |
| List detail plan references `cora/tests.py` but no test file shown in workspace | `03-Route-application_list_detail_plan.md` line 187 |
| Mermaid diagrams render in GitHub but not all Markdown viewers | All docs with diagrams |

---

## Summary of Action Items

1. **Apply migrations** for lock fields and indexes
2. **Add `prior_status` field** to model and migration
3. **Implement `POST /application/{id}/takeover`** endpoint
4. **Create background lock sweeper** (cron/management command)
5. **Standardize HTTP status codes** (413 for size, 415 for type, 422 for validation)
6. **Define OCR queue message schema** and enqueue logic
7. **Add rate limiting** middleware/config
8. **Implement `DELETE` and `PATCH /application/{id}`** for full CRUD
9. **Write unit tests** covering race conditions and edge cases
10. **Clean up legacy `ApplicationSubmit`/`ApplicationImage`** if no longer used