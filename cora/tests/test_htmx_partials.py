"""Tests for HTMX partial rendering behavior on the application list endpoint.

Covers:
- Full-page HTML vs HTMX partial vs JSON response branching
- HTMX search, status, product_type filtering for partial + JSON
- Pagination links with HTMX attributes
- Empty-state rendering without a full HTML wrapper
- Stale lock badge rendering in partials
"""

import time
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from cora.models import ColaApplication
from django.utils import timezone


def _create_app(**overrides):
    defaults = {
        "brand_name": "Default Brand",
        "ttb_id": "TTB-TEST-001",
        "applicant_name": "Default Applicant",
        "product_type": "WINE",
        "status": "RECEIVED",
        "fanciful_name": None,
        "grape_varietals": [],
        "wine_appellation": "",
        "distinctive_bottle_capacity": "",
        "date_of_application": None,
        "date_issued": None,
        "ttb_authorized_signature": "",
    }
    defaults.update(overrides)
    return ColaApplication.objects.create(**defaults)


class HTMXContentNegotiationTests(TestCase):
    def setUp(self):
        self.url = reverse("application_list")

    def test_full_page_html_without_htmx(self):
        _create_app(brand_name="Alpha", ttb_id="TTB-ALPHA-001")
        response = self.client.get(self.url, HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("<html", content)
        self.assertIn("Alpha", content)

    def test_partial_html_with_htmx_request(self):
        _create_app(brand_name="Beta", ttb_id="TTB-BETA-001")
        response = self.client.get(
            self.url,
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn("<html", content)
        self.assertNotIn("<body>", content)
        self.assertIn("Beta", content)

    def test_json_with_json_accept(self):
        _create_app(brand_name="Gamma", ttb_id="TTB-GAMMA-001")
        response = self.client.get(self.url, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        import json
        payload = json.loads(response.content.decode())
        self.assertIn("results", payload)
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["brand_name"], "Gamma")


class HTMXSearchFilterTests(TestCase):
    def setUp(self):
        self.url = reverse("application_list")
        _create_app(brand_name="Valley Reserve", ttb_id="TTB-VALLEY-001", applicant_name="Valley Craft")
        _create_app(brand_name="Summit Lager", ttb_id="TTB-SUMMIT-001", applicant_name="Summit Brewing")

    def _htmx(self, params=None):
        return self.client.get(
            self.url,
            params or {},
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true",
        )

    def test_search_returns_partial(self):
        response = self._htmx({"q": "Valley"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Valley Reserve", content)
        self.assertNotIn("Summit Lager", content)
        self.assertNotIn("<html", content)

    def test_search_matches_brand_name(self):
        response = self._htmx({"q": "Summit"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Summit Lager", content)

    def test_search_matches_cross_fields_json(self):
        response = self.client.get(
            self.url,
            {"q": "Valley"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        import json
        payload = json.loads(response.content.decode())
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["ttb_id"], "TTB-VALLEY-001")


class HTMXStatusFilterTests(TestCase):
    def setUp(self):
        self.url = reverse("application_list")
        _create_app(brand_name="Received App", ttb_id="TTB-REC-001", status="RECEIVED")
        _create_app(brand_name="Review App", ttb_id="TTB-REV-001", status="IN_REVIEW")

    def _htmx(self, params=None):
        return self.client.get(
            self.url,
            params or {},
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true",
        )

    def test_status_filter_returns_partial(self):
        response = self._htmx({"status": "RECEIVED"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Received App", content)
        self.assertNotIn("Review App", content)
        self.assertNotIn("<html", content)

    def test_status_filter_json(self):
        response = self.client.get(
            self.url,
            {"status": "RECEIVED"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        import json
        payload = json.loads(response.content.decode())
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["ttb_id"], "TTB-REC-001")

    def test_invalid_status_returns_all(self):
        response = self._htmx({"status": "INVALID_STATUS"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Received App", content)
        self.assertIn("Review App", content)


class HTMXProductTypeFilterTests(TestCase):
    def setUp(self):
        self.url = reverse("application_list")
        _create_app(brand_name="Wine App", ttb_id="TTB-WINE-001", product_type="WINE")
        _create_app(brand_name="Spirits App", ttb_id="TTB-SPIRITS-001", product_type="DISTILLED_SPIRITS")

    def _htmx(self, params=None):
        return self.client.get(
            self.url,
            params or {},
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true",
        )

    def test_product_type_filter_returns_partial(self):
        response = self._htmx({"product_type": "WINE"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Wine App", content)
        self.assertNotIn("Spirits App", content)
        self.assertNotIn("<html", content)

    def test_product_type_filter_json(self):
        response = self.client.get(
            self.url,
            {"product_type": "DISTILLED_SPIRITS"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        import json
        payload = json.loads(response.content.decode())
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["ttb_id"], "TTB-SPIRITS-001")

    def test_invalid_product_type_returns_all(self):
        response = self._htmx({"product_type": "INVALID_TYPE"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Wine App", content)
        self.assertIn("Spirits App", content)


class HTMXPaginationTests(TestCase):
    def setUp(self):
        self.url = reverse("application_list")
        for idx in range(25):
            _create_app(
                brand_name=f"App {idx:02d}",
                ttb_id=f"TTB-PAGE-{idx:03d}",
                product_type="WINE" if idx < 13 else "BEER",
            )

    def _htmx(self, params=None):
        return self.client.get(
            self.url,
            params or {},
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true",
        )

    def test_pagination_returns_partial(self):
        response = self._htmx({"page": 2, "limit": 10})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("App 10", content)
        self.assertNotIn("App 00", content)
        self.assertNotIn("<html", content)

    def test_pagination_links_have_htmx_attributes(self):
        response = self._htmx({"page": 1, "limit": 10})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('hx-get=', content)
        self.assertIn('hx-target="#results-section"', content)
        self.assertIn('hx-indicator="#spinner"', content)

    def test_next_url_present_when_more_results(self):
        response = self._htmx({"page": 1, "limit": 10})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('>Next<', content)

    def test_previous_url_present_on_later_page(self):
        response = self._htmx({"page": 2, "limit": 10})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('>Previous<', content)

    def test_json_pagination_links(self):
        response = self.client.get(
            self.url,
            {"page": 2, "limit": 10},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        import json
        payload = json.loads(response.content.decode())
        self.assertIn("next", payload)
        self.assertIn("previous", payload)
        self.assertIsNotNone(payload["next"])
        self.assertIsNotNone(payload["previous"])


class HTMXEmptyStateTests(TestCase):
    def setUp(self):
        self.url = reverse("application_list")

    def test_empty_state_renders_in_partial(self):
        response = self.client.get(
            self.url,
            {"q": "NO-MATCH"},
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("No applications match your current filters", content)
        self.assertNotIn("<html", content)

    def test_empty_state_json_response(self):
        response = self.client.get(
            self.url,
            {"q": "NO-MATCH"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        import json
        payload = json.loads(response.content.decode())
        self.assertEqual(payload["count"], 0)
        self.assertEqual(len(payload["results"]), 0)


class HTMXStaleLockBadgeTests(TestCase):
    def setUp(self):
        self.url = reverse("application_list")
        self.recent_lock_app = _create_app(
            brand_name="Active Lock App",
            ttb_id="TTB-LOCK-RECENT",
            status="IN_REVIEW",
            review_started_at=timezone.now() - timedelta(minutes=5),
        )
        self.stale_lock_app = _create_app(
            brand_name="Stale Lock App",
            ttb_id="TTB-LOCK-STALE",
            status="IN_REVIEW",
            review_started_at=timezone.now() - timedelta(minutes=20),
        )

    def test_stale_lock_badge_in_partial(self):
        response = self.client.get(
            self.url,
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Stale Lock App", content)
        self.assertIn("IN_REVIEW (stale)", content)
        self.assertNotIn("<html", content)

    def test_active_lock_badge_in_partial(self):
        response = self.client.get(
            self.url,
            {"q": "Active Lock App"},
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Active Lock App", content)
        self.assertIn("In Review", content)
        self.assertNotIn("Stale Lock App", content)
        self.assertNotIn("IN_REVIEW (stale)", content)
