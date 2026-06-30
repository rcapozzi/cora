"""PGMQ-backed task helpers for cora."""

from django.conf import settings
from django.db import connection


def ensure_queue(queue_name: str = 'cora_ocr_jobs') -> None:
    with connection.cursor() as cursor:
        cursor.execute('SELECT pgmq.create(%s)', [queue_name])


def enqueue_application(application_id, *, queue_name: str = 'cora_ocr_jobs') -> None:
    """
    Enqueue an application processing task.
    Best-effort: falls back to returning when PGMQ is unavailable.
    """
    try:
        ensure_queue(queue_name)
    except Exception as exc:
        raise RuntimeError('PGMQ is unavailable: %s' % exc) from exc

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT pgmq.send(%s, %s, %s)',
            [queue_name, str(application_id), 'application_id'],
        )
