# Generated by Django 5.1.3 on 2025-04-16 18:27

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0035_alter_userhabit_options_userhabit_frequency_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="EducationalContent",
        ),
        migrations.DeleteModel(
            name="PomodoroTimer",
        ),
    ]
