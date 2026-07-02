"""Management command to create API tokens for programmatic access."""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from cora.models import ApiToken
import hashlib
import secrets


class Command(BaseCommand):
    help = 'Create an API token for a user'

    def add_arguments(self, parser):
        parser.add_argument('username', help='Username to create token for')
        parser.add_argument(
            '--scope',
            action='append',
            default=['review'],
            choices=['read', 'write', 'review'],
            help='Scope for the token (can be specified multiple times)',
        )
        parser.add_argument('--name', default='api-token', help='Human-readable name for the token')
        parser.add_argument('--days', type=int, help='Expiry in days')

    def handle(self, *args, **opts):
        User = get_user_model()
        try:
            user = User.objects.get(username=opts['username'])
        except User.DoesNotExist:
            self.stderr.write(f'User "{opts["username"]}" not found')
            return

        # Generate token: cora_<random> and extract 8-char prefix
        raw_token = 'cora_' + secrets.token_urlsafe(32)
        prefix = raw_token[:8]

        # Hash with PBKDF2 (using salt from settings or default)
        salt = getattr(settings, 'CORA_TOKEN_SALT', b'salt')
        iterations = getattr(settings, 'CORA_TOKEN_PBKDF2_ITERATIONS', 100000)
        token_hash = hashlib.pbkdf2_hmac('sha256', raw_token.encode(), salt, iterations).hex()

        expires_at = None
        if opts.get('days'):
            expires_at = timezone.now() + timedelta(days=opts['days'])

        token = ApiToken.objects.create(
            name=opts['name'],
            token_hash=token_hash,
            prefix=prefix,
            scopes=opts['scope'],
            created_by=user,
            expires_at=expires_at,
        )

        self.stdout.write(self.style.SUCCESS('Token created successfully:'))
        self.stdout.write(f'  Name: {token.name}')
        self.stdout.write(f'  Prefix: {token.prefix}')
        self.stdout.write(f'  Scopes: {", ".join(token.scopes)}')
        self.stdout.write(f'  Expires: {token.expires_at or "Never"}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('SAVE THIS TOKEN — IT CANNOT BE SHOWN AGAIN:'))
        self.stdout.write(f'  {raw_token}')
        self.stdout.write('')
        self.stdout.write('Usage:')
        self.stdout.write('  curl -H "Authorization: Bearer <token>" ...')