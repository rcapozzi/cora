from django.db import models  # type: ignore[reportMissingModuleSource]

from cora.utils.ids import generate_uuid7


def get_label_upload_path(instance, filename):
    return f"cola/{instance.cola_application.ttb_id}/{filename}"


class ColaApplication(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid7)
    cola_application_id = models.BigIntegerField(null=True, blank=True)
    ttb_id = models.CharField(max_length=50, unique=True, db_index=True)
    applicant_name = models.CharField(max_length=255)
    product_type = models.CharField(max_length=30, db_index=True)
    brand_name = models.CharField(max_length=255, db_index=True)
    fanciful_name = models.CharField(max_length=255, null=True, blank=True)
    grape_varietals = models.JSONField(null=True, blank=True)
    wine_appellation = models.CharField(max_length=255, null=True, blank=True)
    distinctive_bottle_capacity = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=30, default='RECEIVED', db_index=True)
    date_of_application = models.DateField(null=True, blank=True, db_index=True)
    date_issued = models.DateField(null=True, blank=True)
    ttb_authorized_signature = models.CharField(max_length=255, null=True, blank=True)

    # Review locking fields
    review_started_at = models.DateTimeField(null=True, blank=True)
    prior_status = models.CharField(max_length=30, null=True, blank=True)
    review_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
    )

    # Lifecycle timestamps for reporting/SLA
    approved_at = models.DateTimeField(null=True, blank=True)
    conditionally_approved_at = models.DateTimeField(null=True, blank=True)
    needs_correction_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cola_applications'

    def __str__(self):
        return f"{self.brand_name} - {self.ttb_id} ({self.status})"


class LabelImage(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid7)
    cola_application = models.ForeignKey(
        ColaApplication,
        on_delete=models.CASCADE,
        related_name='label_images',
    )
    label_type = models.CharField(max_length=30)
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=1024)
    file_size_bytes = models.BigIntegerField()
    width_px = models.IntegerField(null=True, blank=True)
    height_px = models.IntegerField(null=True, blank=True)
    image_format = models.CharField(max_length=10)

    image = models.ImageField(upload_to=get_label_upload_path)
    ocr_text = models.TextField(null=True, blank=True)
    ocr_status = models.CharField(max_length=30, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'label_images'

    def __str__(self):
        return f"{self.id} {self.ocr_status} {self.label_type} {self.file_name}"
