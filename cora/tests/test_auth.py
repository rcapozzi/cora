"""Authentication system tests for CORA."""

import json
from datetime import timedelta
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone
from cora.models import ColaApplication, ApiToken
from rest_framework.test import APIClient

from cora.authentication import generate_token


@override_settings(ROOT_URLCONF='cora.urls', CORA_AUTH_REQUIRED=True)
class ApiTokenAuthenticationTests(TestCase):
    """Test API token authentication."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename='review_application')
        )
        
        # Create API token
        full_token, prefix, token_hash = generate_token()
        self.token = ApiToken.objects.create(
            name='test-token',
            token_hash=token_hash,
            prefix=prefix,
            scopes=['review', 'read'],
            created_by=self.user,
        )
        self.full_token = full_token

    def test_token_auth_success(self):
        """Test valid token authenticates successfully."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.full_token}')
        
        response = client.get(reverse('application_list'), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)

    def test_token_auth_invalid(self):
        """Test invalid token is rejected."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token')
        
        response = client.get(reverse('application_list'), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 401)

    def test_token_auth_missing(self):
        """Test missing auth header returns 401 when auth required."""
        client = APIClient()
        response = client.get(reverse('application_list'), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 401)

    def test_token_revoked(self):
        """Test revoked token is rejected."""
        self.token.revoked_at = timezone.now()
        self.token.save()
        
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.full_token}')
        
        response = client.get(reverse('application_list'), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 401)

    def test_token_expired(self):
        """Test expired token is rejected."""
        from django.utils import timezone
        from datetime import timedelta
        
        self.token.expires_at = timezone.now() - timedelta(days=1)
        self.token.save()
        
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.full_token}')
        
        response = client.get(reverse('application_list'), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 401)


@override_settings(ROOT_URLCONF='cora.urls', CORA_AUTH_REQUIRED=True)
class SessionAuthenticationTests(TestCase):
    """Test session-based authentication."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename='review_application')
        )
        self.client.login(username='testuser', password='testpass')

    def test_session_auth_success(self):
        """Test authenticated session works."""
        response = self.client.get(reverse('application_list'), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)

    def test_session_auth_no_perm(self):
        """Test user without review permission gets 403 on protected endpoint."""
        self.user.user_permissions.clear()
        self.user.save()
        
        response = self.client.post(
            reverse('application_list'),
            HTTP_ACCEPT='application/json',
            data={}
        )
        # Should be 403 or 401 depending on implementation
        self.assertIn(response.status_code, [401, 403])


@override_settings(ROOT_URLCONF='cora.urls', CORA_AUTH_REQUIRED=False)
class AuthDisabledTests(TestCase):
    """Test endpoints work when CORA_AUTH_REQUIRED=False."""

    def test_no_auth_required(self):
        """Test all endpoints accessible without auth when disabled."""
        response = self.client.get(reverse('application_list'), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse('application_list'),
            HTTP_ACCEPT='application/json',
            data={}
        )
        self.assertEqual(response.status_code, 400)  # Invalid data, but not auth error


@override_settings(ROOT_URLCONF='cora.urls', CORA_AUTH_REQUIRED=True)
class PermissionDecoratorsTests(TestCase):
    """Test permission decorators on views."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='reviewer',
            password='testpass'
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename='review_application')
        )
        self.client.login(username='reviewer', password='testpass')
        
        self.app = ColaApplication.objects.create(
            ttb_id='COLA-2026-0001',
            applicant_name='Test Winery',
            product_type='WINE',
            brand_name='Test Brand',
            status='IN_REVIEW',
            review_by=self.user,
        )

    def test_takeover_requires_review_perm(self):
        """Test takeover endpoint requires review permission."""
        self.user.user_permissions.clear()
        self.user.save()
        
        response = self.client.post(
            reverse('application_takeover', kwargs={'id': self.app.id}),
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(response.status_code, 403)

    def test_takeover_with_review_perm(self):
        """Test takeover works with review permission."""
        response = self.client.post(
            reverse('application_takeover', kwargs={'id': self.app.id}),
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

    def test_release_requires_review_perm(self):
        """Test release endpoint requires review permission."""
        self.user.user_permissions.clear()
        self.user.save()
        
        response = self.client.post(
            reverse('application_release', kwargs={'id': self.app.id}),
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(response.status_code, 403)

    def test_import_requires_write_perm(self):
        """Test import endpoint requires import permission."""
        self.user.user_permissions.clear()
        self.user.save()
        
        response = self.client.post(
            reverse('application_list'),
            HTTP_ACCEPT='application/json',
            data={}
        )
        self.assertEqual(response.status_code, 403)


@override_settings(ROOT_URLCONF='cora.urls', CORA_AUTH_REQUIRED=True)
class TokenScopeTests(TestCase):
    """Test token scopes for different operations."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='apiuser',
            password='testpass'
        )
        
        self.full_token, prefix, token_hash = generate_token()
        self.token = ApiToken.objects.create(
            name='api-token',
            token_hash=token_hash,
            prefix=prefix,
            scopes=['read'],  # Only read scope
            created_by=self.user,
        )
        
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.full_token}')

    def test_read_scope_allows_list(self):
        """Test read scope allows GET /application."""
        response = self.client.get(reverse('application_list'), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)

    def test_read_scope_denies_create(self):
        """Test read scope denies POST /application."""
        response = self.client.post(
            reverse('application_list'),
            HTTP_ACCEPT='application/json',
            data={}
        )
        self.assertEqual(response.status_code, 403)

    def test_review_scope_allows_takeover(self):
        """Test review scope allows takeover."""
        # Create token with review scope
        full_token, prefix, token_hash = generate_token()
        token = ApiToken.objects.create(
            name='review-token',
            token_hash=token_hash,
            prefix=prefix,
            scopes=['review', 'read'],
            created_by=self.user,
        )
        
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {full_token}')
        
        app = ColaApplication.objects.create(
            ttb_id='COLA-2026-0002',
            applicant_name='Test',
            product_type='WINE',
            brand_name='Brand',
            status='IN_REVIEW',
            review_by=self.user,
        )
        
        response = client.post(
            reverse('application_takeover', kwargs={'id': app.id}),
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(response.status_code, 200)