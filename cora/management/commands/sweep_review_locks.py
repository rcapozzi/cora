#!/usr/bin/env python
"""
Management command to sweep and release expired IN_REVIEW locks.

This command finds ColaApplication records stuck in IN_REVIEW status
where the review_started_at timestamp is older than the configured
timeout (default 15 minutes) and reverts them to their prior_status
or RECEIVED if prior_status is not set.

Can be run manually or scheduled via cron:
    uv run manage.py sweep_review_locks [--timeout-minutes 15] [--dry-run]
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from cora.models import ColaApplication

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Release expired IN_REVIEW locks on ColaApplication records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout-minutes',
            type=int,
            default=15,
            help='Lock timeout in minutes (default: 15)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of locks to process per run (default: 100)',
        )

    def handle(self, *args, **options):
        timeout_minutes = options['timeout_minutes']
        dry_run = options['dry_run']
        limit = options['limit']

        cutoff = timezone.now() - timedelta(minutes=timeout_minutes)

        # Find expired locks
        expired = ColaApplication.objects.filter(
            status='IN_REVIEW',
            review_started_at__lt=cutoff,
        ).order_by('review_started_at')[:limit]

        count = expired.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('No expired locks found.')
            )
            return

        self.stdout.write(f'Found {count} expired lock(s) (timeout: {timeout_minutes} min)')

        if dry_run:
            for app in expired:
                self.stdout.write(
                    f'  Would release: {app.ttb_id} ({app.brand_name}) '
                    f'locked since {app.review_started_at} by {app.review_by_id}'
                )
            return

        released = 0
        for app in expired:
            try:
                with transaction.atomic():
                    # Re-fetch with lock to avoid race
                    app = ColaApplication.objects.select_for_update().get(pk=app.pk)

                    # Double-check it's still expired and locked
                    if app.status != 'IN_REVIEW' or app.review_started_at >= cutoff:
                        continue

                    prior = app.prior_status or 'RECEIVED'
                    reviewer = app.review_by_id

                    app.status = prior
                    app.review_started_at = None
                    app.review_by = None
                    app.prior_status = None
                    app.save(update_fields=[
                        'status', 'review_started_at', 'review_by', 'prior_status', 'updated_at'
                    ])

                    released += 1
                    self.stdout.write(
                        f'  Released: {app.ttb_id} ({app.brand_name}) '
                        f'→ {prior} (was locked by user {reviewer})'
                    )

                    logger.info(
                        'Lock released',
                        extra={
                            'event': 'lock_released',
                            'ttb_id': app.ttb_id,
                            'applicant_name': app.applicant_name,
                            'brand_name': app.brand_name,
                            'prior_status': prior,
                            'locked_by_user_id': reviewer,
                            'lock_age_minutes': int((timezone.now() - app.review_started_at).total_seconds() / 60) if app.review_started_at else None,
                        }
                    )

            except ColaApplication.DoesNotExist:
                # Already processed by another worker
                continue
            except Exception as exc:
                self.stderr.write(
                    f'  ERROR releasing {app.ttb_id}: {exc}'
                )
                logger.error(
                    'Failed to release lock',
                    extra={
                        'event': 'lock_release_failed',
                        'ttb_id': app.ttb_id,
                        'error': str(exc),
                    }
                )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully released {released} lock(s).')
        )