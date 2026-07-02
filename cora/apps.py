from django.apps import AppConfig


class CoraConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'  # type: ignore[assignment]
    name = 'cora'

    def ready(self):
        """Create custom permissions on app startup."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        # Only create permissions if they don't exist (safe to run on every startup)
        try:
            ct = ContentType.objects.get_for_model('cora.ColaApplication')
            Permission.objects.get_or_create(
                codename='review_application',
                content_type=ct,
                defaults={'name': 'Can review COLA applications'},
            )
            Permission.objects.get_or_create(
                codename='import_application',
                content_type=ct,
                defaults={'name': 'Can import COLA applications'},
            )
        except Exception:
            # During migrations, ContentType may not exist yet
            pass