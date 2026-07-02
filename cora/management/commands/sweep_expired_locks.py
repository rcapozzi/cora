#!/usr/bin/env python
"""Management command to sweep and release expired IN_REVIEW locks.

This command finds ColaApplication records stuck in IN_REVIEW status
where the review_started_at timestamp is older than the configured
timeout (default 15 minutes) and reverts them to their prior_status
or RECEIVED if prior_status is not set.

Can be run manually or scheduled via cron:
    uv run manage.py sweep_expired_locks [--timeout-minutes 15] [--dry-run]
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from cora.models import ColaApplication

logger = logging.getLogger(__name__)

LOCK_TIMEOUT_MINUTES = 15


class Command(BaseCommand):
    help = 'Release expired IN_REVIEW locks on ColaApplication records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout-minutes',
            type=int,
            default=LOCK_TIMEOUT_MINUTES,
            help=f'Lock timeout in minutes (default: {LOCK_TIMEOUT_MINUTES})',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        timeout_minutes = options['timeout_minutes']
        dry_run = options['dry_run']

        cutoff = timezone.now() - timedelta(minutes=timeout_minutes)

        # Find expired locks
        expired = ColaApplication.objects.filter(
            status='IN_REVIEW',
            review_started_at__lt=cutoff,
        )

        count = expired.count()

        if dry_run:
            self.stdout.write(f'DRY RUN: Would process {count} expired lock(s)')
            return

        cleaned = 0
        for app in expired:
            try:
                with transaction.atomic():
                    # Re-fetch with lock to avoid race
                    app = ColaApplication.objects.select_for_update().get(pk=app.pk)

                    # Double-check it's still expired and locked
                    if app.status != 'IN_REVIEW' or app.review_started_at >= cutoff:
                        continue

                    # Revert status to prior_status or RECEIVED
                    app.status = app.prior_status or 'RECEIVED'
                    app.review_started_at = None
                    app.review_by = None
                    app.prior_status = None
                    app.save()

                    cleaned += 1
                    logger.info(
                        'Expired lock cleaned',
                        extra={
                            'event': 'expired_lock_swept',
                            'ttb_id': app.ttb_id,
                            'brand_name': app.brand_name,
                        }
                    )
            except ColaApplication.DoesNotExist:
                # Already processed by another worker
                continue
            except Exception as exc:
                logger.error(
                    f'Error processing expired lock for {app.ttb_id}: {exc}',
                    extra={
                        'event': 'lock_sweep_failed',
                        'ttb_id': app.ttb_id,
                        'error': str(exc),
                    }
                )

        self.stdout.write(f'Cleaned {cleaned} expired lock(s)')
        logger.info(f'Sweep completed: {cleaned} locks cleaned')