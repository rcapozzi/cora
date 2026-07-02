from django.conf import settings
from rest_framework import permissions


class HasReviewPermission(permissions.BasePermission):
    """Check user has cora.review_application perm or token scope 'review'.

    When CORA_AUTH_REQUIRED is False, all requests pass (feature flag off).
    """

    def has_permission(self, request, view):
        if not getattr(settings, 'CORA_AUTH_REQUIRED', False):
            return True

        # Session auth: check user permission
        if request.user and request.user.is_authenticated:
            return request.user.has_perm('cora.review_application')

        # Token auth: attached by authentication class
        return getattr(request, 'token_scope', None) == 'review'


class IsLockOwnerOrAdmin(permissions.BasePermission):
    """For release/takeover — user must own the lock or be superuser."""

    def has_object_permission(self, request, view, obj):
        # Superusers can always access
        if request.user.is_superuser:
            return True

        # Check if user owns the lock (via review_by)
        if hasattr(obj, 'review_by_id') and obj.review_by_id:
            return obj.review_by_id == request.user.id

        # For token-authenticated requests, check the user from token
        if hasattr(request, 'auth') and request.auth:
            return obj.review_by_id == request.auth.created_by_id

        return False