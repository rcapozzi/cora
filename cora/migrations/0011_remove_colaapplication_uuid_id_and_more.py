import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cora', '0010_remove_colaapplication_uuid_id_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='labelimage',
                    name='cola_application',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='label_images', to='cora.colaapplication'),
                ),
            ],
        ),
    ]
