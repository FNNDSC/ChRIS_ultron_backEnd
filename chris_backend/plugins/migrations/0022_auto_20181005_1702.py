# Generated by Django 2.0.7 on 2018-10-05 17:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('plugins', '0021_auto_20180504_1608'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='plugininstance',
            options={'ordering': ('-start_date',)},
        ),
    ]