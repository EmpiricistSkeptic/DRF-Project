# Generated by Django 5.1.3 on 2024-12-12 17:34

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0022_alter_task_deadline"),
    ]

    operations = [
        migrations.AlterField(
            model_name="task",
            name="deadline",
            field=models.DateTimeField(
                default=datetime.datetime(2024, 12, 13, 17, 34, 17, 85283)
            ),
        ),
    ]
