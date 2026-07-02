# CORA `/application` Endpoint — Consolidated Design Document

This document consolidates all behavior specification describes the complete `/application` endpoint family:
- **GET** `/application` — List, search, filter, paginate application records (collection)
- **GET** `/application/new` — Returns form for creating a new application
- **POST** `/application` — Create a new COLA application (with label images)
- **GET** `/application/{id}` — Detail view with review lock acquisition
- **POST** `/application/{id}/release` — Release review lock on unload/abandon
- **GET** `/application/import` — Alias for HTML form (legacy route, consider removing)

All routes share a single URL pattern (`/application`) with method/content-type dispatch.

---

## 1. Route Map

```mermaid
graph TD
    CLIENT[Client Request] --> A{HTTP Method}

    A -->|GET /application| B{Accept Header}
    B -->|application/json| C[Return JSON List]
    B -->|text/html| D[Render Application List HTML]

    A -->|GET /application/new| E[Render Import Form]

    A -->|POST /application| F{Content-Type}
    F -->|multipart/form-data| G[Create Application]
    F -->|other| H[415 Unsupported Media Type]

    A -->|GET /application?params| I{Accept Header}
    I -->|application/json| J[Filtered JSON List]
    I -->|text/html + HX-Request| K[HTMX Partial: Table Rows]
    I -->|text/html| L[Full Application List HTML]

    A -->|"GET /application/{id}"| M{"Accept Header"}
    M -->|application/json| N[JSON Detail + Nested Images]
    M -->|text/html| O[Side-by-Side Verification Screen]

    A -->|"POST /application/{id}/release"| P[Release Lock - 204 No Content]
```

---

## 2. GET `/application` — List / Search / Filter / Paginate

### 2.1 Query Parameters

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `q` | string | — | Search `brand_name`, `fanciful_name`, `applicant_name`, `ttb_id` (icontains, max 200 chars) |
| `status` | string | — | Must be in `ALLOWED_STATUSES` |
| `product_type` | string | — | Must be in `ALLOWED_PRODUCT_TYPES` |
| `page` | int ≥ 1 | 1 | — |
| `limit` | int [1, 100] | 20 | — |
| `sort_by` | string | `date_of_application` | Must be in `ALLOWED_SORT_FIELDS` |
| `order` | string | `desc` | `asc` or `desc` |

`ALLOWED_STATUSES`: `RECEIVED`, `APPROVED`, `VERIFIED`, `IN_REVIEW`, `CONDITIONALLY_APPROVED`, `NEEDS_CORRECTION`, `REJECTED`, `SURRENDERED`, `WITHDRAWN`

`ALLOWED_PRODUCT_TYPES`: `WINE`, `DISTILLED_SPIRITS`, `MALT_BEVERAGES`

`ALLOWED_SORT_FIELDS`: `date_of_application`, `created_at`, `brand_name`

### 2.2 Default Behavior (Collection)

By default, `GET /application` returns a list of application records (the collection), not a form.

### 2.3 Form Retrieval

To get the application creation form, use `GET /application/new` which returns the HTML form for creating a new application.

### 2.4 Lock Handling in List Query

Expired `IN_REVIEW` locks (older than **15 minutes**) are **excluded** from the default queryset but remain visible in the DB so the next agent can see and take them over.

```python
lock_cutoff = now() - timedelta(minutes=15)
queryset = ColaApplication.objects.exclude(
    status='IN_REVIEW', review_started_at__lt=lock_cutoff
).all()
```

### 2.5 Content Negotiation

| Accept / HX-Request | Response |
|---------------------|----------|
| `Accept: application/json` | JSON list |
| `Accept: application/json` + `?schema=1` | JSON Schema for create payload |
| `HX-Request: true` (HTMX) | Partial HTML — table rows + pagination strip |
| Default (`text/html`) | Full application list HTML |

### 2.6 JSON Response Envelope

```json
{
  "success": true,
  "count": 142,
  "next": "/application?page=2&q=blue",
  "previous": null,
  "results": [
    {
      "id": "uuid-v7",
      "cola_application_id": 102548,
      "ttb_id": "COLA-2026-004587",
      "applicant_name": "Blue Ridge Cellars LLC",
      "product_type": "WINE",
      "brand_name": "Blue Ridge Reserve",
      "fanciful_name": "Moonlit Harvest",
      "status": "RECEIVED",
      "date_of_application": "2026-03-12"
    }
  ]
}
```

### 2.7 HTMX Wiring (Application List)

```html
<!-- Search input -->
<input id="search-input"
       name="q"
       hx-get="/application"
       hx-target="#results-body"
       hx-trigger="keyup changed delay:300ms"
       hx-include="#filter-form">

<!-- Status filter -->
<select name="status"
        hx-get="/application"
        hx-target="#results-body"
        hx-trigger="change"
        hx-include="#filter-form">
```

---

## 3. GET `/application/new` — Application Creation Form

Returns the HTML form for creating a new COLA application. Equivalent to the legacy `/application/import/` endpoint.

**Response**: HTML form (`cora/import.html`)

---

## 4. POST `/application` — Create Application

### 4.1 Request

| Aspect | Requirement |
|--------|-------------|
| Content-Type | `multipart/form-data` (required) |
| Form field `payload` | JSON string matching `IMPORT_PAYLOAD_SCHEMA` |
| Files | One per `label_images[].file_name` in payload |

### 4.2 Payload Schema (abridged)

```json
{
  "cola_application": {
    "ttb_id": "COLA-2026-000001",          // required, unique
    "applicant_name": "Example Winery",     // required
    "product_type": "WINE",                  // required: WINE|DISTILLED_SPIRITS|MALT_BEVERAGES
    "brand_name": "VINEYARD RESERVE",        // required
    "fanciful_name": "Estate Select",        // optional
    "grape_varietals": ["Cabernet Sauvignon"],
    "wine_appellation": "California",
    "distinctive_bottle_capacity": "750 mL",
    "date_of_application": "2026-07-01",
    "date_issued": "2026-07-02",
    "label_images": [                         // optional, max 4
      { "label_type": "BRAND", "file_name": "front.jpg" },
      { "label_type": "BACK",  "file_name": "back.jpg" }
    ]
  }
}
```

Allowed `label_type`: `BRAND`, `BACK`, `NECK`, `OTHER`.

### 4.3 Validation & Business Rules

| Rule | Check | On Fail |
|------|-------|---------|
| BR-001 | `ttb_id` unique | 409 Conflict (unless idempotent) |
| BR-002 | ≤ 4 label images | 422 |
| BR-003 | Atomic transaction | — (enforced by `transaction.atomic()`) |
| BR-004 | `label_type` in allowed set | 422 |
| BR-005/009 | Idempotent retry on duplicate `ttb_id` | Exact match → 200; mismatch → 409 |
| BR-006 | Strip server fields (`id`, timestamps) | Silently ignored |
| BR-007/013 | Structured audit log on success | — |
| BR-008 | Content negotiation | JSON or HTML response |
| BR-010 | Stream uploads via `TemporaryFileUploadHandler` | — |
| BR-011 | Max 1.5 MB/image; PNG/JPG only | 413/422 |
| BR-012 | Authorization (if enabled) | 401/403 |

### 4.4 Idempotency Flow

```mermaid
graph TD
    POST[POST /application] --> TTB{ttb_id exists?}
    TTB -->|No| VALIDATE[Validate Business Rules]
    TTB -->|Yes| COMPARE[Compare all fields + image metadata]
    COMPARE -->|Exact match| IDEM[200 OK - Existing Resource]
    COMPARE -->|Mismatch| CONFLICT[409 Conflict]
    VALIDATE -->|Pass| TX["transaction.atomic()"]
    TX --> SAVE_APP[Save ColaApplication]
    SAVE_APP --> SAVE_IMG[Save LabelImages + Files]
    SAVE_IMG --> AUDIT[Audit Log Entry]
    AUDIT --> ENQUEUE[Enqueue OCR Task]
    ENQUEUE --> NEG{Accept: application/json?}
    NEG -->|Yes| JSON_201[201 Created + JSON]
    NEG -->|No| HTML_201[201 Created + HTML]
```

### 4.5 Responses

| Status | Trigger | JSON Body |
|--------|---------|-----------|
| 201 | New application created | `{ "success": true, "id": 123, "message": "Application created." }` |
| 200 | Idempotent duplicate | `{ "success": true, "id": 123, "message": "Application created (idempotent)." }` |
| 400 | Invalid JSON / missing payload | `{ "success": false, "reason": "missing_payload", ... }` |
| 409 | Duplicate `ttb_id` with differing data | `{ "success": false, "reason": "duplicate", "failing_field": "ttb_id", ... }` |
| 413 | File too large | `{ "success": false, "reason": "file_too_large", ... }` |
| 415 | Not `multipart/form-data` | `{ "success": false, "reason": "unsupported_media_type", ... }` |
| 422 | Validation failed (schema, types, sizes) | `{ "success": false, "reason": "validation_failed", "failing_field": "...", ... }` |
| 500 | Unexpected server error | `{ "success": false, "reason": "server_error", ... }` |

---

## 5. GET `/application/{id}` — Detail View with Lock Acquisition

### 5.1 Lock Logic (inside `transaction.atomic()`)

```mermaid
flowchart TD
    FETCH[Fetch ColaApplication by id] --> STATUS{Current status?}

    STATUS -->|RECEIVED or VERIFIED| ACQUIRE[Acquire lock: status=IN_REVIEW, review_started_at=now, review_by=user, prior_status=old]
    STATUS -->|IN_REVIEW| AGE{lock age > 15 min?}
    AGE -->|Yes| ACQUIRE
    AGE -->|No| OWNER{review_by == current user?}
    OWNER -->|Yes| REFRESH[Refresh lease: review_started_at=now]
    OWNER -->|No| WARN[Return 200 with takeover_warning=true]
    STATUS -->|APPROVED, REJECTED, etc.| READONLY[Read-only view, no lock mutation]

    ACQUIRE --> SERIALIZE[Serialize full app + label_images]
    REFRESH --> SERIALIZE
    READONLY --> SERIALIZE
    WARN --> SERIALIZE

    SERIALIZE --> NEG{Accept: application/json?}
    NEG -->|Yes| JSON_DETAIL[200 JSON Detail]
    NEG -->|No| HTML_DETAIL[200 Side-by-Side Verification Screen]
```

### 5.2 JSON Detail Response

```json
{
  "success": true,
  "application": {
    "id": "uuid-v7",
    "cola_application_id": 102548,
    "ttb_id": "COLA-2026-004587",
    "applicant_name": "Blue Ridge Cellars LLC",
    "product_type": "WINE",
    "brand_name": "Blue Ridge Reserve",
    "fanciful_name": "Moonlit Harvest",
    "grape_varietals": ["Cabernet Sauvignon", "Merlot"],
    "wine_appellation": "Virginia",
    "distinctive_bottle_capacity": "750 mL",
    "status": "IN_REVIEW",
    "date_of_application": "2026-03-12",
    "date_issued": "2026-04-02",
    "ttb_authorized_signature": "J. Anderson",
    "created_at": "2026-03-12T14:22:11Z",
    "updated_at": "2026-04-02T09:15:44Z",
    "review_started_at": "2026-07-01T14:30:00Z",
    "review_by": "agent@example.com",
    "prior_status": "RECEIVED",
    "take_over_warning": false
  },
  "take_over_warning": false
}
```

### 5.3 HTML Verification Screen

Side-by-side layout:
- **Left**: Label images (click to enlarge)
- **Right**: Extracted OCR text blocks mapped to label regions
- **Bottom**: Status transition form (`APPROVED`, `REJECTED`, `NEEDS_CORRECTION` + notes)
- **Audit Trail**: Status history with timestamps and agents

---

## 6. POST `/application/{id}/release` — Release Review Lock

### 6.1 Invocation

Called by `navigator.sendBeacon` on `window.beforeunload`. Also callable explicitly.

```javascript
window.addEventListener('beforeunload', () => {
    navigator.sendBeacon('/application/${application.id}/release');
});
```

### 6.2 Logic (inside `transaction.atomic()`)

```python
with transaction.atomic():
    app = ColaApplication.objects.select_for_update().get(id=id)
    if (app.status == 'IN_REVIEW' and app.review_by == request.user):
        app.status = app.prior_status or 'RECEIVED'
        app.prior_status = None
        app.review_started_at = None
        app.review_by = None
        app.save()
```

### 6.3 Response

| Status | Condition |
|--------|-----------|
| 204 | Lock released (or no-op if not owner/not locked) |
| 404 | Application not found |

Idempotent: safe to call multiple times.

---

## 7. GET `/application/import` — Legacy Import Form Alias

| Route | View | Purpose |
|-------|------|---------|
| `GET /application/import` | `application_create` | Renders `cora/import.html` (same as `GET /application/new`) |

> [!IMPORTANT]
> The `/application/import` route is retained for backward compatibility and explicit bookmarking.
> For new development, use `GET /application/new` instead.
> If the `/application/import` route is kept, it should be redirected to `/application/new` in future versions.

---

## 8. Database Model Summary (Relevant Fields)

```python
class ColaApplication(models.Model):
    id = UUIDField(default=uuid7, primary_key=True)
    cola_application_id = BigIntegerField(null=True, blank=True)
    ttb_id = CharField(max_length=50, unique=True, db_index=True)
    applicant_name = CharField(max_length=255)
    product_type = CharField(max_length=30, db_index=True)  # WINE, DISTILLED_SPIRITS, MALT_BEVERAGES
    brand_name = CharField(max_length=255, db_index=True)
    fanciful_name = CharField(max_length=255, null=True, blank=True)
    grape_varietals = JSONField(null=True, blank=True)
    wine_appellation = CharField(max_length=255, null=True, blank=True)
    distinctive_bottle_capacity = CharField(max_length=50, null=True, blank=True)
    status = CharField(max_length=30, default='RECEIVED', db_index=True)
    date_of_application = DateField(null=True, blank=True, db_index=True)
    date_issued = DateField(null=True, blank=True)
    ttb_authorized_signature = CharField(max_length=255, null=True, blank=True)
    review_started_at = DateTimeField(null=True, blank=True)
    review_by = CharField(max_length=255, null=True, blank=True)
    prior_status = CharField(max_length=30, null=True, blank=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    archived_at = DateTimeField(null=True, blank=True)

class LabelImage(models.Model):
    cola_application = ForeignKey(ColaApplication, on_delete=CASCADE, related_name='label_images')
    label_type = CharField(max_length=30)  # BRAND, BACK, NECK, OTHER
    file_name = CharField(max_length=255)
    file_path = CharField(max_length=1024)
    file_size_bytes = BigIntegerField()
    width_px = IntegerField(null=True, blank=True)
    height_px = IntegerField(null=True, blank=True)
    image_format = CharField(max_length=10)  # PNG, JPG
    image = ImageField(upload_to='cola/{ttb_id}/')
    created_at = DateTimeField(auto_now_add=True)
```

---

## 9. URL Routing (cora/urls.py)

```python
urlpatterns = [
    path('', views.landing, name='landing'),
    path('admin/', admin.site.urls),
    re_path(r'^application/(?P<id>[0-9a-f-]{36}|\d+)/?$', views.application_detail, name='application_detail'),
    re_path(r'^application/(?P<id>[0-9a-f-]{36}|\d+)/release/?$', views.application_release, name='application_release'),
    re_path(r'^ping/?$', views.ping, name='ping'),
    re_path(r'^application/?$', views.application_list, name='application_list'),
    path('application/new/', views.application_create, name='application_new'),
    path('application/import/', views.application_create, name='application_import'),  # Legacy
    path('status/', views.status, name='status'),
]

> **Note**: UUID pattern `([0-9a-f-]{36}|\d+)` supports both UUID and numeric IDs for backward compatibility.
> The `/application/import/` route is legacy and should be redirected to `/application/new/` in future versions.
```

---

## 10. Security & Observability

| Concern | Implementation |
|---------|----------------|
| Authentication | Django auth (`login_required` / `permission_required` on views) |
| CSRF | `@csrf_exempt` on API endpoints (stateless); form uses `{% csrf_token %}` |
| File validation | MIME type check, 1.5 MB limit, Pillow header parse for dimensions |
| Audit logging | Structured JSON to `cora.audit` logger on every import/review action |
| Rate limiting | Not yet implemented (gap — see gaps doc) |

---

## 11. Test Matrix (Acceptance Criteria)

| # | Scenario | Expected |
|---|----------|----------|
| 1 | `POST /application` valid new app + images | 201 JSON/HTML |
| 2 | `POST /application` same payload again | 200 (idempotent) |
| 3 | `POST /application` same `ttb_id`, different data | 409 |
| 4 | `POST /application` missing payload field | 400 |
| 5 | `POST /application` image > 1.5 MB | 422 |
| 6 | `POST /application` 5 images | 422 |
| 7 | `POST /application` invalid `label_type` | 422 |
| 8 | `GET /application` `Accept: application/json` | 200 paginated JSON |
| 9 | `GET /application?schema=1` `Accept: application/json` | 200 JSON Schema |
| 10 | `GET /application` `Accept: text/html` | 200 application list HTML |
| 11 | `GET /application?q=blue` | 200 filtered |
| 12 | `GET /application?status=RECEIVED` | 200 filtered |
| 13 | `GET /application?page=2&limit=5` | 200 correct slice |
| 14 | `GET /application` `HX-Request` | 200 partial HTML |
| 15 | `GET /application/new` | 200 import form HTML |
| 16 | `GET /application/{id}` status=RECEIVED | 200, lock acquired, status=IN_REVIEW |
| 17 | `GET /application/{id}` expired lock | 200, lock re-acquired |
| 18 | `GET /application/{id}` active foreign lock | 200, `takeover_warning=true` |
| 19 | `GET /application/{id}` same agent returns | 200, lease refreshed |
| 20 | `GET /application/9999` | 404 |
| 21 | `POST /application/{id}/release` by owner | 204, status reverted |
| 22 | `POST /application/{id}/release` by non-owner | 204 (no-op) |
| 23 | `GET /application/import` | 200 import form HTML (legacy) |

---

## 12. Future Enhancements (Out of Scope)

- Cursor-based pagination for very large datasets
- WebSocket / SSE for real-time status updates
- Bulk import endpoint (`POST /application/bulk`)
- Full-text search (PostgreSQL `tsvector`) on label OCR text
- RBAC for reviewer assignment
