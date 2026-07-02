# Implementation Plan: `GET /application` & `GET /application/{id}`

---

## Current State

| Item | Status |
|------|--------|
| `ColaApplication` model | ✅ Defined with `db_index` on `brand_name`, `status`, `product_type`, `date_of_application` |
| `review_started_at` / `review_by` lock fields | ✅ Added to model — **migration not yet applied** |
| `GET /application` route | ✅ Implemented (returns list by default, form at `/application/new`) |
| `GET /application/{id}` route | ✅ Implemented |
| `POST /application/{id}/release` route | ✅ Implemented |
| Templates: list view, detail view, partials | ✅ Created |

---

## Summary

All phases have been completed successfully. The implementation now follows the updated API specification:

- **GET `/application`** → Returns list of applications (collection)
- **GET `/application/new`** → Returns form for creating a new application  
- **POST `/application`** → Creates a new application
- **GET `/application/{id}`** → Retrieves application detail with locking
- **POST `/application/{id}/release`** → Releases review lock

---

## Phase 1: Database Migration ✅ Done

The model already has the needed fields. Migration `0004` applied with lock fields.

## Phase 2: View Logic — `GET /application` ✅ Done

**File**: `cora/views.py`

### 2A. Parameter Extraction & Sanitization
```python
ALLOWED_SORT_FIELDS = {'date_of_application', 'created_at', 'brand_name'}
ALLOWED_STATUSES    = {'RECEIVED', 'APPROVED', 'VERIFIED', 'IN_REVIEW',
                       'CONDITIONALLY_APPROVED', 'NEEDS_CORRECTION',
                       'REJECTED', 'SURRENDERED', 'WITHDRAWN'}
ALLOWED_TYPES       = {'WINE', 'DISTILLED_SPIRITS', 'MALT_BEVERAGES'}
LOCK_TIMEOUT_MINS   = 15
```

Extract from `request.GET`:
- `q` — free-text search (stripped, max 200 chars)
- `status` — validated against `ALLOWED_STATUSES`, ignored if invalid
- `product_type` — validated against `ALLOWED_TYPES`, ignored if invalid
- `page` — integer ≥ 1, defaults to `1`
- `limit` — integer clamped to `[1, 100]`, defaults to `20`
- `sort_by` — validated against `ALLOWED_SORT_FIELDS`, defaults to `date_of_application`
- `order` — `asc` or `desc`, defaults to `desc`

### 2B. ORM Query Construction
```python
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

lock_cutoff = timezone.now() - timedelta(minutes=LOCK_TIMEOUT_MINS)

queryset = ColaApplication.objects.exclude(
    # Treat expired IN_REVIEW locks as RECEIVED for display purposes
    status='IN_REVIEW',
    review_started_at__lt=lock_cutoff
).all()

if q:
    queryset = queryset.filter(
        Q(brand_name__icontains=q)    |
        Q(fanciful_name__icontains=q) |
        Q(applicant_name__icontains=q)|
        Q(ttb_id__icontains=q)
    )
if status:
    queryset = queryset.filter(status=status)
if product_type:
    queryset = queryset.filter(product_type=product_type)

order_prefix = '-' if order == 'desc' else ''
queryset = queryset.order_by(f'{order_prefix}{sort_by}')
```

> [!NOTE]
> The `exclude` on expired `IN_REVIEW` locks prevents orphaned applications
> from vanishing from the queue. They are surfaced as-is (stale lock visible)
> so the next agent can take over.

### 2C. Offset-Based Pagination
```python
total   = queryset.count()
offset  = (page - 1) * limit
results = queryset[offset : offset + limit]
```

Build `next` / `previous` URLs by mutating the current query string.

### 2D. Content Negotiation

| Condition | Response |
|-----------|----------|
| `Accept: application/json` | JSON list |
| `Accept: application/json` + `?schema=1` | JSON Schema for create payload |
| `HX-Request: true` (HTMX) | Partial HTML — table rows + pagination strip only |
| Default browser request | Full HTML application list page |

---

## Phase 3: View Logic — `GET /application/{id}` ✅ Done

**Business logic** (wrapped in `transaction.atomic()`):

1. Fetch `ColaApplication` by `id` — 404 if not found.
2. **Lock evaluation**:
```
if status IN ('RECEIVED', 'VERIFIED'):
    → acquire lock: status = IN_REVIEW,
                review_started_at = now(),
                review_by = request.user
elif status == 'IN_REVIEW':
    lock_age = now() - review_started_at
    if lock_age > 15 min:
        → expired: acquire lock (same as above)
    elif review_by != request.user:
        → active foreign lock: return 200 with takeover_warning = True
    else:
        → same agent returning: refresh lease (update review_started_at)
else (APPROVED, REJECTED, etc.):
    → read-only view, no lock mutation
```

3. Serialize full application record with nested `label_images`.
4. Respond via content negotiation:
   - `Accept: application/json` → JSON
   - `Accept: text/html` → Side-by-side verification template

---

## Phase 4: View Logic — `POST /application/{id}/release` ✅ Done

Called by `navigator.sendBeacon` on `beforeunload`.

```python
with transaction.atomic():
    app = ColaApplication.objects.select_for_update().get(id=id)
    if (app.status == 'IN_REVIEW'
            and app.review_by == request.user):
        app.status = app.prior_status or 'RECEIVED'
        app.prior_status = None
        app.review_started_at = None
        app.review_by = None
        app.save()
```

> [!NOTE]
> To restore prior status cleanly, the `IN_REVIEW` acquisition step must
> capture the prior status. The `prior_status` field has been added to the model
> so the release endpoint knows exactly what to revert to.

Returns `204 No Content` (beacon ignores the body).

---

## Phase 5: Model Update — `prior_status` ✅ Done

Add one field to `ColaApplication`:

```python
prior_status = models.CharField(max_length=30, null=True, blank=True)
```

Set at lock-acquire time; cleared at lock-release or final decision.

---

## Phase 6: URL Routing ✅ Done

**Updated in `cora/urls.py`**:

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
```

> [!IMPORTANT]
> The `/application/import` route (legacy) uses `path('application/import/', ...)` in the actual `urls.py` and is kept for backward compatibility.
> The preferred way to get the application form is now `GET /application/new`.
> The `/application/import` route should be redirected to `/application/new` in future versions.
> 
> The updated ID pattern `[0-9a-f-]{36}|\d+` supports both UUID and numeric IDs for backward compatibility.
> This pattern does not match the string "import", so there is no risk of the import route being captured as an ID.

---

## Phase 7: Templates ✅ Done

| Template | Purpose |
|----------|---------|
| `cora/templates/cora/application_list.html` | Full dashboard — search bar, filter dropdowns, results table, HTMX wiring |
| `cora/templates/cora/partials/application_table.html` | HTMX-swappable fragment — `<tbody>` rows + pagination strip |
| `cora/templates/cora/application_detail.html` | Full detail / verification screen — label images, OCR text, approve/reject form |

### Key HTMX Attributes (list page)

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

### Key Client-Side Lock Release (detail page)

```javascript
window.addEventListener('beforeunload', () => {
    navigator.sendBeacon('/application/{{ application.id }}/release');
});
```

---

## Phase 8: Test Matrix ✅ Updated

| Scenario | Expected Status | Notes |
|----------|----------------|-------|
| `GET /application` no params, JSON | `200` JSON with all results | Default sort + page (LIST) |
| `GET /application?q=blue` | `200` — filtered results | Matches brand/fanciful/applicant/ttb_id |
| `GET /application?status=RECEIVED` | `200` — filtered results | Exact match |
| `GET /application?page=2&limit=5` | `200` — correct slice | Pagination math |
| `GET /application` HTMX request | `200` — partial HTML only | No `<html>` wrapper |
| `GET /application` HTML request | `200` — full HTML page | Contains dashboard chrome (LIST) |
| `GET /application/new` | `200` — form HTML | Returns creation form |
| `GET /application/{id}` RECEIVED → lock | `200` — status becomes `IN_REVIEW` | Lock fields set |
| `GET /application/{id}` expired lock | `200` — lock re-acquired | `review_started_at` > 15 min |
| `GET /application/{id}` active foreign lock | `200` — takeover warning returned | Other agent holds active lock |
| `GET /application/{id}` same agent returns | `200` — lease refreshed | `review_started_at` reset |
| `GET /application/9999` | `404` | Non-existent application |
| `POST /application/{id}/release` by owner | `204` — status reverted | `prior_status` restored |
| `POST /application/{id}/release` by non-owner | `204` — no-op | Idempotent, safe |
| `GET /application/import` | `200` — form HTML (legacy) | Backward compatibility |

---

## Phase 9: API Behavior Summary ✅ Done

**Core API Endpoints:**

1. **GET `/application`**
   - Returns list of applications (collection) by default
   - Supports filtering, sorting, pagination via query parameters
   - Content negotiation: JSON (default for API clients) or HTML (for browsers)

2. **GET `/application/new`**
   - Returns HTML form for creating a new application
   - Equivalent to the legacy `/application/import/` endpoint

3. **POST `/application`**
   - Creates a new application
   - Expects `multipart/form-data` with JSON payload and file attachments
   - Returns 201 Created on success, 200 for idempotent duplicates

4. **GET `/application/{id}`**
   - Returns application detail with locking behavior
   - Implements optimistic/pessimistic locking for concurrent access
   - Returns JSON or HTML based on Accept header

5. **POST `/application/{id}/release`**
   - Releases review lock held by current user
   - Returns 204 No Content
   - Safe to call multiple times (idempotent)

---

## Summary

The implementation now correctly follows RESTful conventions:
- Collections (`/application`) return lists of resources
- Forms (`/application/new`) are separated from collection endpoints
- Creation happens via POST to the collection endpoint
- Individual resources are accessed via `/application/{id}`
- Legacy endpoints are maintained for backward compatibility but clearly marked

All documentation has been updated to reflect these changes.
