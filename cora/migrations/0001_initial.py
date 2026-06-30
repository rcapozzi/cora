import cora.utils.ids
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ColaApplication',
            fields=[
                ('id', models.CharField(default=cora.utils.ids.generate_uuid7, max_length=36, primary_key=True)),
                ('cola_application_id', models.BigIntegerField(blank=True, null=True)),
                ('ttb_id', models.CharField(db_index=True, max_length=50, unique=True)),
                ('applicant_name', models.CharField(max_length=255)),
                ('product_type', models.CharField(db_index=True, max_length=30)),
                ('brand_name', models.CharField(db_index=True, max_length=255)),
                ('fanciful_name', models.CharField(blank=True, max_length=255, null=True)),
                ('grape_varietals', models.JSONField(blank=True, null=True)),
                ('wine_appellation', models.CharField(blank=True, max_length=255, null=True)),
                ('distinctive_bottle_capacity', models.CharField(blank=True, max_length=50, null=True)),
                ('status', models.CharField(db_index=True, default='RECEIVED', max_length=30)),
                ('date_of_application', models.DateField(blank=True, db_index=True, null=True)),
                ('date_issued', models.DateField(blank=True, null=True)),
                ('ttb_authorized_signature', models.CharField(blank=True, max_length=255, null=True)),
                ('review_started_at', models.DateTimeField(blank=True, null=True)),
                ('prior_status', models.CharField(blank=True, max_length=30, null=True)),
                ('review_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviews', to='auth.user')),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('conditionally_approved_at', models.DateTimeField(blank=True, null=True)),
                ('needs_correction_at', models.DateTimeField(blank=True, null=True)),
                ('rejected_at', models.DateTimeField(blank=True, null=True)),
                ('archived_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'cola_applications',
            },
        ),
        migrations.CreateModel(
            name='LabelImage',
            fields=[
                ('id', models.CharField(default=cora.utils.ids.generate_uuid7, max_length=36, primary_key=True)),
                ('label_type', models.CharField(max_length=30)),
                ('file_name', models.CharField(max_length=255)),
                ('file_path', models.CharField(max_length=1024)),
                ('file_size_bytes', models.BigIntegerField()),
                ('width_px', models.IntegerField(blank=True, null=True)),
                ('height_px', models.IntegerField(blank=True, null=True)),
                ('image_format', models.CharField(max_length=10)),
                ('image', models.ImageField(upload_to='cola/label_images/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('cola_application', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='label_images', to='cora.colaapplication')),
            ],
            options={
                'db_table': 'label_images',
            },
        ),
    ]