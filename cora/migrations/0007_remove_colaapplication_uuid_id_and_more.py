from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cora', '0006_rename_uuid_to_pk'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='colaapplication',
                    name='approved_at',
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='colaapplication',
                    name='conditionally_approved_at',
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='colaapplication',
                    name='needs_correction_at',
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='colaapplication',
                    name='rejected_at',
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
        ),
    ]
