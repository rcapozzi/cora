import hashlib
import secrets

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiToken


class ApiTokenAuthentication(BaseAuthentication):
    """Token authentication for API clients.

    Looks for `Authorization: Bearer ***` header.
    Tokens are validated via prefix lookup + PBKDF2 hash comparison.
    """

    keyword = 'Bearer'

    def authenticate(self, request):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith(self.keyword + ' '):
            return None

        token = auth[len(self.keyword) + 1:]
        return self._validate_token(token, request)

    def _validate_token(self, token, request):
        # Malformed tokens (too short, no dot) -> return None to let other backends try
        if len(token) < 17 or '.' not in token:
            return None

        # Token format: <prefix>.<suffix> where prefix is 16 chars
        prefix = token[:16]
        try:
            api_token = ApiToken.objects.get(prefix=prefix, revoked_at__isnull=True)
        except ApiToken.DoesNotExist:
            return None

        # Check expiry
        if api_token.expires_at and api_token.expires_at < timezone.now():
            raise AuthenticationFailed('Token expired')

        # Constant-time compare of token hash
        salt = getattr(settings, 'CORA_TOKEN_SALT', b'cora-token-salt')
        iterations = getattr(settings, 'CORA_TOKEN_PBKDF2_ITERATIONS', 100000)
        expected_hash = hashlib.pbkdf2_hmac('sha256', token.encode(), salt, iterations).hex()

        if not secrets.compare_digest(api_token.token_hash, expected_hash):
            raise AuthenticationFailed('Invalid token')

        # Update last used timestamp
        api_token.last_used_at = timezone.now()
        api_token.save(update_fields=['last_used_at'])

        # Attach scope to request for permission checks
        request.token_scopes = api_token.scopes
        request.token_scope = 'review' if 'review' in api_token.scopes else 'read'

        return (api_token.created_by, api_token)


def generate_token() -> tuple[str, str, str]:
    """
    Generate a new API token.
    
    Returns:
        (full_token, prefix, token_hash)
    """
    prefix = 'cora_' + secrets.token_urlsafe(11)[:11]  # 5 + 11 = 16 chars
    suffix = secrets.token_urlsafe(32)
    full_token = f"{prefix}.{suffix}"
    
    token_hash = hashlib.pbkdf2_hmac(
        'sha256',
        full_token.encode(),
        b'cora-token-salt',
        100000
    ).hex()
    
    return full_token, prefix, token_hash