from django.db import migrations, models
import cora.utils.ids


class Migration(migrations.Migration):

    dependencies = [
        ("cora", "0007_remove_colaapplication_uuid_id_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="colaapplication",
            name="id",
            field=models.CharField(default=cora.utils.ids.generate_uuid7, max_length=36, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="labelimage",
            name="id",
            field=models.CharField(default=cora.utils.ids.generate_uuid7, max_length=36, primary_key=True, serialize=False),
        ),
    ]
