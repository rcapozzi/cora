# CORA Authentication & Authorization Design

**Document ID:** 06-auth_model_design.md  
**Status:** DESIGN — ready for implementation  
**Priority:** High (Priority 2.1 per `00_GAPS.md`)  
**Target:** Phase 2 — Auth enforcement on mutating endpoints  

---

## 1. Problem Statement

Currently all CORA views are `@csrf_exempt` with no authentication enforcement. Tests exercise auth-state effects (e.g., `review_by = request.user`), but production endpoints accept requests from any caller.

**Goals:**
- Enforce authentication on mutating endpoints (POST/import, takeover, release, future PATCH)
- Support two auth modes: session auth (browser/HTMX) + token auth (API clients)
- Feature-flag rollout so existing integrations don't break
- Minimal schema changes — leverage existing `ForeignKey('auth.User')` on `ColaApplication.review_by`

---

## 2. Auth Model

### 2.1 User Model
Use Django's built-in `auth.User` — no custom user model needed.

| Requirement | Decision |
|-------------|----------|
| Reviewer identity | `request.user` (session) or `Authorization: Bearer <token>` |
| Permissions | `cora.review_application` permission (custom) |
| Groups | `Reviewers` group with `cora.review_application` |

### 2.2 Token Auth (API Clients)

| Aspect | Spec |
|--------|------|
| Header | `Authorization: Bearer <token>` |
| Token model | `cora.models.ApiToken` (new) — hashed storage, prefix + random suffix |
| Scopes | `read`, `write`, `review` (initial: `review` covers mutating endpoints) |
| Expiry | Optional `expires_at`; default none (revocable) |
| Rotation | Admin can regenerate; old token revoked immediately |

```python
# cora/models.py addition
class ApiToken(models.Model):
    name = models.CharField(max_length=100)           # human label
    token_hash = models.CharField(max_length=128)     # pbkdf2_sha256 hash
    prefix = models.CharField(max_length=8)           # first 8 chars for lookup
    scopes = models.JSONField(default=list)           # ["review", "read"]
    created_by = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'cora_api_tokens'
```

### 2.3 Permission Matrix

| Endpoint | Session Auth Required | Token Scope Required | Notes |
|----------|----------------------|----------------------|-------|
| `GET /application` | ❌ (flagged) | `read` | List is read-only |
| `GET /application/new` | ❌ (flagged) | `read` | Form display |
| `POST /application` | ✅ | `write` | Create + enqueue OCR |
| `GET /application/{id}` | ❌ (flagged) | `read` | Lock acquisition advisory |
| `POST /application/{id}/release` | ✅ | `review` | Must own lock or be admin |
| `POST /application/{id}/takeover` | ✅ | `review` | Requires expired lock |
| `PATCH /application/{id}` | ✅ | `review` | Status transitions |
| `GET /status/` | ❌ | `read` | Observability |
| `GET /ping/` | ❌ | — | Health check |

> **Feature flag:** `CORA_AUTH_REQUIRED` (default `False` in dev, `True` in prod). When `False`, auth checks are skipped but user is still attached if present.

---

## 3. Implementation Plan

### 3.1 New Files

```
cora/
├── permissions.py        # Custom permission classes
├── decorators.py         # View decorators (auth_required, token_auth)
├── authentication.py     # DRF-style token authentication backend
├── models.py             # + ApiToken model
├── management/commands/
│   └── create_api_token.py   # Admin helper
└── tests/
    └── test_auth.py      # Auth enforcement tests
```

### 3.2 Modified Files

| File | Change |
|------|--------|
| `cora/views.py` | Apply decorators to mutating views |
| `cora/urls.py` | No change (decorators on views) |
| `cora/settings.py` | Add `CORA_AUTH_REQUIRED`, `REST_FRAMEWORK` if using DRF auth |
| `cora/admin.py` | Register `ApiToken` (read-only for non-superusers) |

### 3.3 Core Components

#### `cora/permissions.py`
```python
from rest_framework import permissions

class HasReviewPermission(permissions.BasePermission):
    """Check user has cora.review_application perm or token scope 'review'."""
    def has_permission(self, request, view):
        if not getattr(settings, 'CORA_AUTH_REQUIRED', False):
            return True
        # Session auth
        if request.user and request.user.is_authenticated:
            return request.user.has_perm('cora.review_application')
        # Token auth — attached by authentication class
        return getattr(request, 'token_scope', None) == 'review'

class IsLockOwnerOrAdmin(permissions.BasePermission):
    """For release/takeover — user must own the lock or be superuser."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        return obj.review_by_id == request.user.id
```

#### `cora/authentication.py`
```python
import hashlib
import secrets
from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import ApiToken

class ApiTokenAuthentication(BaseAuthentication):
    keyword = 'Bearer'

    def authenticate(self, request):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith(self.keyword + ' '):
            return None
        token = auth[len(self.keyword) + 1:]
        return self._validate_token(token)

    def _validate_token(self, token):
        prefix = token[:8]
        try:
            api_token = ApiToken.objects.get(prefix=prefix, revoked_at__isnull=True)
        except ApiToken.DoesNotExist:
            raise AuthenticationFailed('Invalid token')

        if api_token.expires_at and api_token.expires_at < timezone.now():
            raise AuthenticationFailed('Token expired')

        # Constant-time compare
        expected_hash = hashlib.pbkdf2_hmac('sha256', token.encode(), b'salt', 100000).hex()
        if not secrets.compare_digest(api_token.token_hash, expected_hash):
            raise AuthenticationFailed('Invalid token')

        api_token.last_used_at = timezone.now()
        api_token.save(update_fields=['last_used_at'])

        # Attach scope to request for permission checks
        request.token_scope = 'review' if 'review' in api_token.scopes else 'read'
        return (api_token.created_by, api_token)
```

#### `cora/decorators.py`
```python
from functools import wraps
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from .authentication import ApiTokenAuthentication

def auth_required(view_func):
    """Combined session + token auth decorator for function views."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(settings, 'CORA_AUTH_REQUIRED', False):
            return view_func(request, *args, **kwargs)

        # Try token auth first
        auth = ApiTokenAuthentication()
        auth_result = auth.authenticate(request)
        if auth_result:
            request.user, request.auth = auth_result
            return view_func(request, *args, **kwargs)

        # Fall back to session auth
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)

        return JsonResponse(
            {'success': False, 'reason': 'authentication_required', 'detail': 'Valid session or Bearer token required'},
            status=401
        )
    return wrapper

def require_review_permission(view_func):
    """Ensure user has cora.review_application or token review scope."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(settings, 'CORA_AUTH_REQUIRED', False):
            return view_func(request, *args, **kwargs)

        has_perm = (
            request.user.is_authenticated and
            request.user.has_perm('cora.review_application')
        )
        has_scope = getattr(request, 'token_scope', None) == 'review'

        if not (has_perm or has_scope):
            return JsonResponse(
                {'success': False, 'reason': 'permission_denied', 'detail': 'Review permission required'},
                status=403
            )
        return view_func(request, *args, **kwargs)
    return wrapper
```

### 3.4 View Application (cora/views.py)

```python
# Imports
from .decorators import auth_required, require_review_permission

# POST /application — create
@csrf_exempt
@auth_required
def application_list(request):
    ...

# POST /application/{id}/release
@csrf_exempt
@require_POST
@auth_required
@require_review_permission
def application_release(request, id):
    ...

# POST /application/{id}/takeover
@require_POST
@csrf_exempt
@auth_required
@require_review_permission
def application_takeover(request, id):
    ...

# Future PATCH /application/{id}
@csrf_exempt
@auth_required
@require_review_permission
def application_update(request, id):
    ...
```

> **Note:** `GET /application` and `GET /application/{id}` remain unprotected by default; they can be wrapped with `@auth_required` when `CORA_AUTH_REQUIRED=True` and read-access control is desired.

### 3.5 Management Command: Create API Token

```python
# cora/management/commands/create_api_token.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from cora.models import ApiToken
import hashlib, secrets

class Command(BaseCommand):
    help = 'Create an API token for a user'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--scope', action='append', default=['review'], choices=['read', 'write', 'review'])
        parser.add_argument('--name', default='api-token')
        parser.add_argument('--days', type=int, help='Expiry in days')

    def handle(self, *args, **opts):
        User = get_user_model()
        user = User.objects.get(username=opts['username'])
        raw_token = 'cora_' + secrets.token_urlsafe(32)
        token_hash = hashlib.pbkdf2_hmac('sha256', raw_token.encode(), b'salt', 100000).hex()
        prefix = raw_token[:8]

        expires_at = None
        if opts['days']:
            from django.utils import timezone
            from datetime import timedelta
            expires_at = timezone.now() + timedelta(days=opts['days'])

        token = ApiToken.objects.create(
            name=opts['name'],
            token_hash=token_hash,
            prefix=prefix,
            scopes=opts['scope'],
            created_by=user,
            expires_at=expires_at,
        )
        self.stdout.write(f'Token: {raw_token}')
        self.stdout.write(f'Prefix: {prefix}')
        self.stdout.write('SAVE THE TOKEN — it cannot be shown again.')
```

---

## 4. Settings & Configuration

### `cora/settings.py` additions
```python
# Auth feature flag
CORA_AUTH_REQUIRED = os.environ.get('CORA_AUTH_REQUIRED', 'False').lower() == 'true'

# Token hashing cost (adjust for perf/security balance)
CORA_TOKEN_PBKDF2_ITERATIONS = int(os.environ.get('CORA_TOKEN_PBKDF2_ITERATIONS', '100000'))

# Optional: DRF config if using DRF permissions globally
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'cora.authentication.ApiTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

### Environment Variables
| Var | Default | Purpose |
|-----|---------|---------|
| `CORA_AUTH_REQUIRED` | `False` | Global auth enforcement toggle |
| `CORA_TOKEN_PBKDF2_ITERATIONS` | `100000` | Hash cost for token storage |

---

## 5. Migration Plan

### Phase A — Model & Infra (Day 1)
1. Add `ApiToken` model to `cora/models.py`
2. Create & run migration
3. Add `cora/permissions.py`, `cora/authentication.py`, `cora/decorators.py`
4. Add `create_api_token` management command
5. Register `ApiToken` in `cora/admin.py` (read-only for non-superusers)

### Phase B — View Decoration (Day 1–2)
1. Apply `@auth_required` + `@require_review_permission` to mutating views
2. Keep `CORA_AUTH_REQUIRED=False` in dev settings
3. Run test suite — all existing tests should pass (auth skipped)

### Phase C — Enable & Test (Day 2)
1. Flip `CORA_AUTH_REQUIRED=True` in staging
2. Write auth enforcement tests:
   - `POST /application` without auth → 401
   - `POST /application` with valid session → 201
   - `POST /application` with valid token → 201
   - `POST /application/{id}/takeover` with expired lock → 200
   - `POST /application/{id}/takeover` with active foreign lock → 409
   - Token revocation → 401
2. Load-test token auth path

### Phase D — Docs & Rollout (Day 2–3)
1. Update `02-Route-application.md` §10 with auth matrix
2. Document token creation workflow for API consumers
3. Deploy to prod with flag on

---

## 6. Test Plan

| Test | Description |
|------|-------------|
| `test_create_app_requires_auth` | POST without session/token → 401 |
| `test_create_app_with_session` | Logged-in user with `cora.review_application` → 201 |
| `test_create_app_with_token` | Bearer token with `write` scope → 201 |
| `test_takeover_requires_review_perm` | User without perm → 403 |
| `test_takeover_lock_owner_can_release` | Owner releases → 204 |
| `test_takeover_non_owner_cannot_release` | Non-owner → 204 no-op (current behavior) |
| `test_token_revoked` | Revoked token → 401 |
| `test_token_expired` | Expired token → 401 |
| `test_flag_off_allows_unauth` | `CORA_AUTH_REQUIRED=False` → all requests pass |

---

## 7. Security Considerations

| Concern | Mitigation |
|---------|------------|
| Token leakage | Prefix-only lookup; hash stored with PBKDF2; constant-time compare |
| Token replay | HTTPS only; short expiry recommended for high-value tokens |
| Session fixation | Django's built-in session rotation |
| Brute force | Rate limiting (Priority 2.2) on auth endpoints |
| Privilege escalation | `review` scope required for mutating endpoints; `IsLockOwnerOrAdmin` on object-level actions |

---

## 8. Future Extensions

- **OAuth2/OIDC** — swap `ApiTokenAuthentication` for `OAuth2Authentication` if SSO needed
- **Scoped tokens per application** — add `application` FK to `ApiToken` for multi-tenant
- **Audit log on auth events** — log token creation/use/revocation to `cora.audit` logger

---

## 9. References

- `00_GAPS.md` Priority 2.1
- `02-Route-application.md` §10 (to be updated)
- Django auth docs: https://docs.djangoproject.com/en/6.0/topics/auth/
- DRF token auth pattern: https://www.django-rest-framework.org/api-guide/authentication/#tokenauthentication