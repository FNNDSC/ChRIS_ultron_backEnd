# Generated by Django 2.2.24 on 2021-12-30 23:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plugins', '0044_auto_20210126_1615'),
    ]

    operations = [
        migrations.AddField(
            model_name='computeresource',
            name='max_job_exec_seconds',
            field=models.IntegerField(blank=True, default=86400),
        ),
    ]
