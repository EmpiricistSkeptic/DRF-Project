# Generated by Django 5.1.3 on 2025-03-20 15:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0031_rename_fat_consumedcalories_fats_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="profile",
            old_name="exp",
            new_name="points",
        ),
        migrations.RemoveField(
            model_name="task",
            name="exp",
        ),
        migrations.AddField(
            model_name="task",
            name="points",
            field=models.IntegerField(default=0),
        ),
    ]
