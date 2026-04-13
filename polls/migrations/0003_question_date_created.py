from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("polls", "0002_auto_20221205_2153"),
    ]

    operations = [
        migrations.AddField(
            model_name="question",
            name="date_created",
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        ),
    ]
