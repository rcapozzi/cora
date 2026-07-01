# tasks.py
import os

from django.db import transaction
from django.utils import timezone

from .models import ColaApplication, LabelImage
from .pgmq import delete_message, read_queue


def process_ocr_job(application_id, image_id):
    try:
        with transaction.atomic():
            app = ColaApplication.objects.get(id=application_id)
            label_image = LabelImage.objects.get(id=image_id)

            if not label_image.image:
                raise RuntimeError('Label image file not attached')

            path = label_image.image.path
            if not os.path.exists(path):
                raise RuntimeError(f'File missing on disk: {path}')

            with open(path, 'rb') as handle:
                data = handle.read()

            ocr_result = _run_ocr_provider(data)

            label_image.ocr_text = ocr_result.get('text')
            label_image.ocr_status = 'COMPLETE'
            label_image.save(update_fields=['ocr_text', 'ocr_status'])

            app.status = 'VERIFIED'
            app.save(update_fields=['status'])

        return label_image
    except Exception as exc:
        raise RuntimeError(f'Failed OCR for {application_id}: {image_id}') from exc


def _run_ocr_provider(image_bytes):
    # Stubbed caller used by the worker implementation.
    # Replace with a real provider call when available.
    return {'text': '', 'provider': 'stub'}


def process_application(application_id):
    # Legacy compatibility; OCR is now queue-driven.
    pass
