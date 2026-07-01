
import json
import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand

from cora.tests.fixtures.loader import FIXTURE_PATH, load_fixtures


class Command(BaseCommand):
    help = 'Load application and label image fixtures from cora/tests/fixtures/fixtures.json.'

    def handle(self, *args, **options):
        load_fixtures(FIXTURE_PATH)
        self.stdout.write(self.style.SUCCESS('Loaded application fixtures.'))
