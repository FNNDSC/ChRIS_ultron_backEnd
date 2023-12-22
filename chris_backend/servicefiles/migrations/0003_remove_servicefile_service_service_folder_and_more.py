# Generated by Django 4.2.5 on 2023-12-19 04:41

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0004_chrisfolder_chrislinkfile'),
        ('servicefiles', '0002_alter_service_id_alter_servicefile_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='servicefile',
            name='service',
        ),
        migrations.AddField(
            model_name='service',
            name='folder',
            field=models.OneToOneField(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='service', to='core.chrisfolder'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='servicefile',
            name='owner',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='servicefile',
            name='parent_folder',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='service_files', to='core.chrisfolder'),
            preserve_default=False,
        ),
    ]
