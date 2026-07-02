import json
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from cora.models import ColaApplication


@override_settings(ROOT_URLCONF='cora.urls')
class HTMXPartialResponseTests(TestCase):
    """Test HTMX partial rendering behavior for application list endpoint."""

    def setUp(self):
        """Create test applications with various statuses and product types."""
        self.list_url = reverse("application_list")
        
        # Create applications for testing
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0001",
            applicant_name="Acme Wines",
            product_type="WINE",
            brand_name="Brand Alpha",
            status="RECEIVED",
        )
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0002",
            applicant_name="Beta Spirits",
            product_type="DISTILLED_SPIRITS",
            brand_name="Brand Beta",
            status="APPROVED",
        )
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0003",
            applicant_name="Gamma Brewing",
            product_type="MALT_BEVERAGES",
            brand_name="Brand Gamma",
            status="IN_REVIEW",
        )
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0004",
            applicant_name="Delta Winery",
            product_type="WINE",
            brand_name="Brand Delta",
            status="REJECTED",
        )

    # -----------------------------------------------------------------------
    # Test 1: Full page vs partial vs JSON response based on Accept/HX-Request
    # -----------------------------------------------------------------------
    def test_full_page_render_without_htmx(self):
        """Test full HTML page is returned for regular HTML requests."""
        response = self.client.get(self.list_url, HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        # Full page should have HTML structure
        self.assertContains(response, "<!DOCTYPE html>")
        self.assertContains(response, "<html")
        self.assertContains(response, "<head>")
        self.assertContains(response, "<body")
        self.assertContains(response, '<title>CORA — Applications</title>')
        # Full page should contain filter form
        self.assertContains(response, '<form id="filter-form"')
        self.assertContains(response, 'id="q"')

    def test_partial_render_with_htmx_header(self):
        """Test partial HTML fragment is returned for HTMX requests."""
        response = self.client.get(
            self.list_url,
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        # Partial should NOT have full HTML wrapper
        self.assertNotContains(response, "<!DOCTYPE html>")
        self.assertNotContains(response, "<html")
        self.assertNotContains(response, "<head")
        self.assertNotContains(response, "<body")
        self.assertNotContains(response, '<title>CORA — Applications</title>')
        # Partial should have the results table
        self.assertContains(response, '<div class="results-card">')
        self.assertContains(response, "<table>")

    def test_json_response_with_accept_json(self):
        """Test JSON response for Accept: application/json requests."""
        response = self.client.get(self.list_url, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        body = json.loads(response.content.decode())
        self.assertTrue(body["success"])
        self.assertIn("count", body)
        self.assertIn("results", body)
        self.assertGreaterEqual(body["count"], 4)


@override_settings(ROOT_URLCONF='cora.urls')
class HTMXSearchFilterTests(TestCase):
    """Test search filtering via HTMX (search input with keyup trigger)."""

    def setUp(self):
        self.list_url = reverse("application_list")
        # Create multiple applications
        for i in range(5):
            ColaApplication.objects.create(
                ttb_id=f"COLA-2026-{i:05d}",
                applicant_name=f"Test Applicant {i}",
                product_type="WINE",
                brand_name=f"UniqueBrand{i}",
                status="RECEIVED",
            )

    def test_search_filter_returns_partial_via_htmx(self):
        """Test search query parameter filtering with HTMX header returns partial."""
        response = self.client.get(
            self.list_url + "?q=UniqueBrand1",
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        # Should be a partial, not full page
        self.assertNotContains(response, "<!DOCTYPE html>")
        self.assertContains(response, '<span class="badge badge-RECEIVED">')

    def test_search_filter_matches_brand_name(self):
        """Test search actually filters by brand name."""
        response = self.client.get(
            self.list_url + "?q=UniqueBrand1",
            HTTP_ACCEPT="application/json"
        )
        body = json.loads(response.content.decode())
        results = body["results"]
        self.assertEqual(len(results), 1)
        self.assertIn("UniqueBrand1", results[0]["brand_name"])

    def test_search_filter_does_not_match_other_fields(self):
        """Test search finds results across multiple fields."""
        # Create app with matching ttb_id
        ColaApplication.objects.create(
            ttb_id="COLA-2026-99999",
            applicant_name="Other Applicant",
            product_type="WINE",
            brand_name="Different Brand",
            status="RECEIVED",
        )
        
        response = self.client.get(
            self.list_url + "?q=COLA-2026-99999",
            HTTP_ACCEPT="application/json"
        )
        body = json.loads(response.content.decode())
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["results"][0]["ttb_id"], "COLA-2026-99999")


@override_settings(ROOT_URLCONF='cora.urls')
class HTMXStatusFilterTests(TestCase):
    """Test status filter HTMX partial rendering."""

    def setUp(self):
        self.list_url = reverse("application_list")
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0001",
            applicant_name="Wines Inc",
            product_type="WINE",
            brand_name="Wine Brand",
            status="RECEIVED",
        )
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0002",
            applicant_name="Spirits Inc",
            product_type="DISTILLED_SPIRITS",
            brand_name="Spirit Brand",
            status="APPROVED",
        )

    def test_status_filter_returns_partial_with_htmx(self):
        """Test status filter with HTMX header returns partial response."""
        response = self.client.get(
            self.list_url + "?status=RECEIVED",
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertNotContains(response, "<!DOCTYPE html>")
        self.assertContains(response, "Wine Brand")
        self.assertNotContains(response, "Spirit Brand")

    def test_status_filter_json_response(self):
        """Test status filter works correctly in JSON response."""
        response = self.client.get(
            self.list_url + "?status=APPROVED",
            HTTP_ACCEPT="application/json"
        )
        body = json.loads(response.content.decode())
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["results"][0]["status"], "APPROVED")

    def test_status_filter_invalid_returns_all(self):
        """Test invalid status value returns all applications (no filter applied)."""
        response = self.client.get(
            self.list_url + "?status=INVALID_STATUS",
            HTTP_ACCEPT="application/json"
        )
        body = json.loads(response.content.decode())
        # Should return all since invalid status is ignored
        self.assertEqual(body["count"], 2)


@override_settings(ROOT_URLCONF='cora.urls')
class HTMXProductTypeFilterTests(TestCase):
    """Test product type filter HTMX partial rendering."""

    def setUp(self):
        self.list_url = reverse("application_list")
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0001",
            applicant_name="Wine Co",
            product_type="WINE",
            brand_name="Wine Brand",
            status="RECEIVED",
        )
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0002",
            applicant_name="Spirits Co",
            product_type="DISTILLED_SPIRITS",
            brand_name="Spirit Brand",
            status="RECEIVED",
        )
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0003",
            applicant_name="Beer Co",
            product_type="MALT_BEVERAGES",
            brand_name="Beer Brand",
            status="RECEIVED",
        )

    def test_product_type_filter_returns_partial_with_htmx(self):
        """Test product type filter with HTMX header returns partial."""
        response = self.client.get(
            self.list_url + "?product_type=WINE",
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertNotContains(response, "<!DOCTYPE html>")
        self.assertContains(response, "Wine Brand")
        self.assertNotContains(response, "Spirit Brand")
        self.assertNotContains(response, "Beer Brand")

    def test_product_type_filter_json_response(self):
        """Test product type filter in JSON response."""
        response = self.client.get(
            self.list_url + "?product_type=DISTILLED_SPIRITS",
            HTTP_ACCEPT="application/json"
        )
        body = json.loads(response.content.decode())
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["results"][0]["product_type"], "DISTILLED_SPIRITS")

    def test_product_type_filter_invalid_returns_all(self):
        """Test invalid product type returns all applications."""
        response = self.client.get(
            self.list_url + "?product_type=INVALID_TYPE",
            HTTP_ACCEPT="application/json"
        )
        body = json.loads(response.content.decode())
        # Invalid product type should be ignored
        self.assertEqual(body["count"], 3)


@override_settings(ROOT_URLCONF='cora.urls')
class HTMXPaginationTests(TestCase):
    """Test pagination via HTMX links."""

    def setUp(self):
        self.list_url = reverse("application_list")
        # Create more than limit (default 20) applications
        for i in range(25):
            ColaApplication.objects.create(
                ttb_id=f"COLA-2026-{i:05d}",
                applicant_name=f"Applicant {i}",
                product_type="WINE",
                brand_name=f"Brand {i}",
                status="RECEIVED",
            )

    def test_pagination_with_htmx_returns_partial(self):
        """Test pagination links with HTMX header return partial."""
        response = self.client.get(
            self.list_url + "?page=2",
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertNotContains(response, "<!DOCTYPE html>")

    def test_pagination_links_have_htmx_attributes(self):
        """Test pagination links include correct HTMX attributes."""
        response = self.client.get(
            self.list_url + "?page=1",
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        # Check for hx-get on pagination links
        self.assertContains(response, 'hx-get=')
        self.assertContains(response, 'hx-target="#results-section"')
        self.assertContains(response, 'hx-indicator="#spinner"')

    def test_next_url_in_partial_response(self):
        """Test next_url is present when there are more results."""
        response = self.client.get(
            self.list_url + "?page=1&limit=10",
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        # Should have Next link
        self.assertContains(response, "Next</a>")

    def test_previous_url_in_partial_response(self):
        """Test previous_url is present when not on first page."""
        response = self.client.get(
            self.list_url + "?page=2&limit=10",
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        # Should have Previous link
        self.assertContains(response, "Previous</a>")

    def test_json_pagination_links(self):
        """Test JSON response includes pagination URLs."""
        response = self.client.get(
            self.list_url + "?page=2&limit=10",
            HTTP_ACCEPT="application/json"
        )
        body = json.loads(response.content.decode())
        self.assertIn("next", body)
        self.assertIn("previous", body)


@override_settings(ROOT_URLCONF='cora.urls')
class HTXEmptyStateTests(TestCase):
    """Test empty state rendering in partial."""

    def setUp(self):
        self.list_url = reverse("application_list")

    def test_empty_state_with_htmx(self):
        """Test empty state renders correctly in HTMX partial."""
        response = self.client.get(
            self.list_url + "?q=nonexistent",
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        # Should have empty state message
        self.assertContains(response, "No applications match your current filters")
        self.assertContains(response, '<div class="empty-state">')

    def test_empty_state_json_response(self):
        """Test empty search returns empty results in JSON."""
        response = self.client.get(
            self.list_url + "?q=doesnotexist12345",
            HTTP_ACCEPT="application/json"
        )
        body = json.loads(response.content.decode())
        self.assertEqual(len(body["results"]), 0)
        self.assertEqual(body["count"], 0)


@override_settings(ROOT_URLCONF='cora.urls')
class HTMXStaleLockBadgeTests(TestCase):
    """Test stale lock badge rendering in partial."""

    def setUp(self):
        self.list_url = reverse("application_list")

    def test_stale_lock_badge_in_partial(self):
        """Test stale IN_REVIEW lock shows (stale) badge in HTMX partial."""
        # Create application with stale lock
        stale_time = timezone.now() - timedelta(minutes=20)
        app = ColaApplication.objects.create(
            ttb_id="COLA-2026-0001",
            applicant_name="Test Winery",
            product_type="WINE",
            brand_name="Stale Brand",
            status="IN_REVIEW",
            review_started_at=stale_time,
        )
        
        response = self.client.get(
            self.list_url,
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        # Should show stale indicator
        self.assertContains(response, "stale")
        self.assertContains(response, "IN_REVIEW (stale)")

    def test_active_lock_no_stale_badge(self):
        """Test active IN_REVIEW lock does not show stale badge."""
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0002",
            applicant_name="Active Winery",
            product_type="WINE",
            brand_name="Active Brand",
            status="IN_REVIEW",
            review_started_at=timezone.now(),
        )
        
        response = self.client.get(
            self.list_url,
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        # Should show "In Review" without stale
        self.assertContains(response, "badge-IN_REVIEW")
        # Count occurrences - should not have "(stale)" text
        self.assertNotContains(response, "IN_REVIEW (stale)")


@override_settings(ROOT_URLCONF='cora.urls')
class HTMXPartialWrapperTests(TestCase):
    """Test that partial response doesn't include full HTML wrapper."""

    def setUp(self):
        self.list_url = reverse("application_list")
        for i in range(3):
            ColaApplication.objects.create(
                ttb_id=f"COLA-2026-{i:05d}",
                applicant_name=f"Test {i}",
                product_type="WINE",
                brand_name=f"Brand {i}",
                status="RECEIVED",
            )

    def test_partial_no_full_html_wrapper(self):
        """Test HTMX partial doesn't include html, head, body tags."""
        response = self.client.get(
            self.list_url,
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        content = response.content.decode()
        
        # Should NOT have full page wrapper elements
        self.assertNotIn("<html", content.lower())
        self.assertNotIn("</html>", content.lower())
        self.assertNotIn("<head", content.lower())
        self.assertNotIn("</head>", content.lower())
        self.assertNotIn("<body", content.lower())
        self.assertNotIn("</body>", content.lower())

    def test_partial_returns_only_table_fragment(self):
        """Test HX-Request: true returns only the table fragment (application_table.html)."""
        response = self.client.get(
            self.list_url,
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        content = response.content.decode()
        
        # Should have the results-card div (main partial container)
        self.assertIn('<div class="results-card">', content)
        # Should have table structure
        self.assertIn("<thead>", content)
        self.assertIn("<tbody>", content)
        # Should NOT have page-level elements
        self.assertNotIn('class="page-header"', content)
        self.assertNotIn('<form id="filter-form"', content)


@override_settings(ROOT_URLCONF='cora.urls')
class HTMXCombinedFilterTests(TestCase):
    """Test combined HTMX filtering scenarios."""

    def setUp(self):
        self.list_url = reverse("application_list")

    def test_combined_search_and_status_filter(self):
        """Test combining search and status filter with HTMX."""
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0001",
            applicant_name="Test Wines",
            product_type="WINE",
            brand_name="SearchBrand",
            status="RECEIVED",
        )
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0002",
            applicant_name="Test Spirits",
            product_type="DISTILLED_SPIRITS",
            brand_name="SearchBrand2",
            status="APPROVED",
        )
        
        response = self.client.get(
            self.list_url + "?q=SearchBrand&status=RECEIVED",
            HTTP_ACCEPT="text/html",
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SearchBrand")
        self.assertNotContains(response, "SearchBrand2")

    def test_combined_filters_with_invalid_values(self):
        """Test that invalid filter values are ignored but valid ones still apply."""
        ColaApplication.objects.create(
            ttb_id="COLA-2026-0001",
            applicant_name="Test Wines",
            product_type="WINE",
            brand_name="TargetBrand",
            status="RECEIVED",
        )
        
        response = self.client.get(
            self.list_url + "?q=TargetBrand&status=INVALID&type=INVALID",
            HTTP_ACCEPT="application/json"
        )
        body = json.loads(response.content.decode())
        # Search should still work
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["brand_name"], "TargetBrand")