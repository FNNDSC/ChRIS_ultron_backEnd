# Generated by Django 4.2.5 on 2024-01-31 04:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_remove_chrisfolder_size'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='chrislinkfile',
            name='is_folder',
        ),
        migrations.AlterField(
            model_name='chrislinkfile',
            name='path',
            field=models.CharField(db_index=True, max_length=1024),
        ),
    ]
