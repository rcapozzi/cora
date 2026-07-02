from functools import wraps

from django.conf import settings
from django.http import JsonResponse

from .authentication import ApiTokenAuthentication


def auth_required(view_func):
    """Combined session + token auth decorator for function views.

    When CORA_AUTH_REQUIRED is False, requests pass through without auth check
    but user is still attached if present.
    """

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
            {
                'success': False,
                'reason': 'authentication_required',
                'detail': 'Valid session or Bearer token required',
            },
            status=401,
        )

    return wrapper


def require_review_permission(view_func):
    """Ensure user has cora.review_application or token review scope.

    When CORA_AUTH_REQUIRED is False, requests pass through.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(settings, 'CORA_AUTH_REQUIRED', False):
            return view_func(request, *args, **kwargs)

        has_perm = (
            request.user.is_authenticated
            and request.user.has_perm('cora.review_application')
        )
        has_scope = getattr(request, 'token_scope', None) == 'review'

        if not (has_perm or has_scope):
            return JsonResponse(
                {
                    'success': False,
                    'reason': 'permission_denied',
                    'detail': 'Review permission required',
                },
                status=403,
            )
        return view_func(request, *args, **kwargs)

    return wrapper


def require_write_permission(view_func):
    """Ensure user has write access (authenticated session or token write scope).

    When CORA_AUTH_REQUIRED is False, requests pass through.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(settings, 'CORA_AUTH_REQUIRED', False):
            return view_func(request, *args, **kwargs)

        # Session auth: authenticated users have write access
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)

        # Token auth: must have write scope
        has_scope = 'write' in getattr(request, 'token_scopes', []) or getattr(request, 'token_scope', None) == 'write'

        if not has_scope:
            return JsonResponse(
                {
                    'success': False,
                    'reason': 'permission_denied',
                    'detail': 'Write permission required',
                },
                status=403,
            )
        return view_func(request, *args, **kwargs)

    return wrapper