import json
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
from cora.models import ColaApplication, LabelImage

# A valid 1x1 transparent pixel PNG image bytes
PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
    b'\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`0\x00\x00\x00\x02\x00'
    b'\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
)

@override_settings(ROOT_URLCONF='cora.urls')
class PingEndpointTests(TestCase):
    def test_ping_returns_json(self):
        response = self.client.get(reverse("ping"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_ping_payload_contains_date_and_time(self):
        response = self.client.get(reverse("ping"))
        payload = json.loads(response.content.decode())
        self.assertIn("current_date", payload)
        self.assertIn("current_time", payload)


@override_settings(ROOT_URLCONF='cora.urls')
class ApplicationImportEndpointTests(TestCase):
    def setUp(self):
        self.import_url = reverse("application_import")
        self.valid_payload = {
            "cola_application": {
                "ttb_id": "COLA-2026-004587",
                "cola_application_id": 102548,
                "applicant_name": "Blue Ridge Cellars LLC",
                "product_type": "WINE",
                "brand_name": "Blue Ridge Reserve",
                "fanciful_name": "Moonlit Harvest",
                "grape_varietals": ["Cabernet Sauvignon", "Merlot"],
                "wine_appellation": "Virginia",
                "distinctive_bottle_capacity": "750 mL",
                "cola_status": "RECEIVED",
                "date_of_application": "2026-03-12",
                "date_issued": "2026-04-02",
                "ttb_authorized_signature": "J. Anderson",
                "label_images": [
                    {
                        "label_type": "BRAND",
                        "file_name": "front_label.png"
                    }
                ]
            }
        }

    def test_get_html_form(self):
        response = self.client.get(self.import_url, HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CORA APPLICATION PORTAL")
        self.assertContains(response, "<form")

    def test_get_json_schema(self):
        response = self.client.get(self.import_url, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        schema = json.loads(response.content.decode())
        self.assertEqual(schema["title"], "ColaApplicationImportPayload")

    def test_post_success_json(self):
        image = SimpleUploadedFile("front_label.png", PNG_BYTES, content_type="image/png")
        data = {
            "payload": json.dumps(self.valid_payload),
            "front_label.png": image
        }
        
        response = self.client.post(self.import_url, data, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 201)
        res_data = json.loads(response.content.decode())
        self.assertTrue(res_data["success"])
        
        # Verify db records exist
        self.assertEqual(ColaApplication.objects.count(), 1)
        self.assertEqual(LabelImage.objects.count(), 1)
        app = ColaApplication.objects.first()
        self.assertEqual(app.ttb_id, "COLA-2026-004587")
        self.assertEqual(app.brand_name, "Blue Ridge Reserve")
        
        # Verify Image file metadata properties were calculated
        lbl_img = app.label_images.first()
        self.assertEqual(lbl_img.label_type, "BRAND")
        self.assertEqual(lbl_img.width_px, 1)
        self.assertEqual(lbl_img.height_px, 1)
        self.assertEqual(lbl_img.image_format, "PNG")

    def test_post_success_html(self):
        image = SimpleUploadedFile("front_label.png", PNG_BYTES, content_type="image/png")
        data = {
            "payload": json.dumps(self.valid_payload),
            "front_label.png": image
        }
        
        response = self.client.post(self.import_url, data, HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import Successful")
        self.assertContains(response, "COLA-2026-004587")

    def test_post_idempotent_retry(self):
        # 1st upload
        image = SimpleUploadedFile("front_label.png", PNG_BYTES, content_type="image/png")
        data = {
            "payload": json.dumps(self.valid_payload),
            "front_label.png": image
        }
        self.client.post(self.import_url, data, HTTP_ACCEPT="application/json")
        
        # 2nd upload (identical retry)
        image_retry = SimpleUploadedFile("front_label.png", PNG_BYTES, content_type="image/png")
        data_retry = {
            "payload": json.dumps(self.valid_payload),
            "front_label.png": image_retry
        }
        response = self.client.post(self.import_url, data_retry, HTTP_ACCEPT="application/json")
        
        self.assertEqual(response.status_code, 200)
        res_data = json.loads(response.content.decode())
        self.assertTrue(res_data["success"])
        self.assertIn("idempotent", res_data["message"])
        
        # No extra records created
        self.assertEqual(ColaApplication.objects.count(), 1)
        self.assertEqual(LabelImage.objects.count(), 1)

    def test_post_conflict(self):
        # 1st upload
        image = SimpleUploadedFile("front_label.png", PNG_BYTES, content_type="image/png")
        data = {
            "payload": json.dumps(self.valid_payload),
            "front_label.png": image
        }
        self.client.post(self.import_url, data, HTTP_ACCEPT="application/json")
        
        # Modify some values in payload (different brand name)
        modified_payload = dict(self.valid_payload)
        modified_payload["cola_application"] = dict(self.valid_payload["cola_application"])
        modified_payload["cola_application"]["brand_name"] = "Different Brand"
        
        image_conflict = SimpleUploadedFile("front_label.png", PNG_BYTES, content_type="image/png")
        data_conflict = {
            "payload": json.dumps(modified_payload),
            "front_label.png": image_conflict
        }
        response = self.client.post(self.import_url, data_conflict, HTTP_ACCEPT="application/json")
        
        self.assertEqual(response.status_code, 409)
        res_data = json.loads(response.content.decode())
        self.assertFalse(res_data["success"])
        self.assertEqual(res_data["reason"], "duplicate")

    def test_post_too_many_images(self):
        payload = dict(self.valid_payload)
        payload["cola_application"] = dict(self.valid_payload["cola_application"])
        payload["cola_application"]["label_images"] = [
            {"label_type": "BRAND", "file_name": "front_label.png"},
            {"label_type": "BACK", "file_name": "back_label.png"},
            {"label_type": "NECK", "file_name": "neck_label.png"},
            {"label_type": "OTHER", "file_name": "other_label.png"},
            {"label_type": "OTHER", "file_name": "extra_label.png"},
        ]
        
        data = {
            "payload": json.dumps(payload),
            "front_label.png": SimpleUploadedFile("front_label.png", PNG_BYTES, content_type="image/png"),
            "back_label.png": SimpleUploadedFile("back_label.png", PNG_BYTES, content_type="image/png"),
            "neck_label.png": SimpleUploadedFile("neck_label.png", PNG_BYTES, content_type="image/png"),
            "other_label.png": SimpleUploadedFile("other_label.png", PNG_BYTES, content_type="image/png"),
            "extra_label.png": SimpleUploadedFile("extra_label.png", PNG_BYTES, content_type="image/png"),
        }
        response = self.client.post(self.import_url, data, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 422)

    def test_post_image_too_large(self):
        # 1.6MB file
        large_bytes = b"\x00" * int(1.6 * 1024 * 1024)
        image = SimpleUploadedFile("front_label.png", large_bytes, content_type="image/png")
        data = {
            "payload": json.dumps(self.valid_payload),
            "front_label.png": image
        }
        response = self.client.post(self.import_url, data, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 413)

    def test_post_invalid_image_type(self):
        # Text file instead of image
        image = SimpleUploadedFile("front_label.png", b"not-a-valid-image-content", content_type="text/plain")
        data = {
            "payload": json.dumps(self.valid_payload),
            "front_label.png": image
        }
        response = self.client.post(self.import_url, data, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 422)
        res_data = json.loads(response.content.decode())
        self.assertEqual(res_data["reason"], "invalid_image")


@override_settings(ROOT_URLCONF='cora.urls')
class ApplicationImportValidationTests(TestCase):
    def setUp(self):
        self.import_url = reverse("application_import")

    def test_missing_payload(self):
        response = self.client.post(self.import_url, {}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 400)

    def test_malformed_payload(self):
        data = {"payload": "not-json"}
        response = self.client.post(self.import_url, data, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 400)

    def test_schema_validation_failure_missing_required(self):
        payload = {"cola_application": {}}
        data = {"payload": json.dumps(payload)}
        response = self.client.post(self.import_url, data, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 422)

    def test_invalid_product_type(self):
        payload = {
            "cola_application": {
                "ttb_id": "COLA-2026-9999",
                "product_type": "UNKNOWN",
                "brand_name": "Brand",
                "applicant_name": "Applicant",
                "label_images": []
            }
        }
        data = {"payload": json.dumps(payload)}
        response = self.client.post(self.import_url, data, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 422)


@override_settings(ROOT_URLCONF='cora.urls')
class ApplicationListEndpointTests(TestCase):
    def setUp(self):
        for index in range(35):
            ColaApplication.objects.create(
                ttb_id=f"COLA-2026-{index:05d}",
                applicant_name="Acme Wines",
                product_type="WINE",
                brand_name=f"Brand {index}"
            )

    def test_default_list_returns_results(self):
        response = self.client.get(reverse("application_list"), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content.decode())
        self.assertIn("applications", body)
        self.assertTrue(body["total"] >= 35)

    def test_search_filters_results(self):
        response = self.client.get(
            reverse("application_list") + "?q=Brand%2010",
            HTTP_ACCEPT="application/json"
        )
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content.decode())
        self.assertTrue(any("Brand 10" in entry["brand_name"] for entry in body["applications"]))

    def test_sorting_and_pagination(self):
        response = self.client.get(
            reverse("application_list") + "?sort=brand_name&dir=asc&page=1",
            HTTP_ACCEPT="application/json"
        )
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content.decode())
        self.assertIn("page", body)
        self.assertIn("num_pages", body)


@override_settings(ROOT_URLCONF='cora.urls')
class ApplicationDetailReleaseTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="agent",
            password="secret"
        )
        self.client.force_login(self.user)
        self.app = ColaApplication.objects.create(
            ttb_id="COLA-2026-0001",
            applicant_name="Acme Wines",
            product_type="WINE",
            brand_name="Reserve",
            status="RECEIVED"
        )
        LabelImage.objects.create(
            cola_application=self.app,
            label_type="BRAND",
            file_name="front.png",
            file_path=f"cola/{self.app.ttb_id}/front.png",
            file_size_bytes=10,
            width_px=1,
            height_px=1,
            image_format="PNG"
        )

    def test_detail_view_can_lock_record(self):
        response = self.client.get(reverse("application_detail", kwargs={"id": str(self.app.id)}))
        self.assertEqual(response.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "IN_REVIEW")
        self.assertEqual(self.app.review_by, self.user)

    def test_detail_view_refresh_lease(self):
        self.app.status = "IN_REVIEW"
        self.app.review_by = self.user
        self.app.prior_status = "RECEIVED"
        self.app.review_started_at = timezone.now() - timedelta(minutes=20)
        self.app.save()

        response = self.client.get(reverse("application_detail", kwargs={"id": str(self.app.id)}))
        self.assertEqual(response.status_code, 200)
