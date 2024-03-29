# Generated by Django 4.0 on 2023-04-21 03:41

from django.db import migrations, models
import django.db.models.deletion
import pipelines.models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('pipelines', '0009_alter_defaultpipingstrparameter_value'),
    ]

    operations = [
        migrations.CreateModel(
            name='PipelineSourceFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creation_date', models.DateTimeField(auto_now_add=True)),
                ('fname', models.FileField(max_length=512, unique=True, upload_to=pipelines.models.source_file_path)),
                ('owner', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
                ('pipeline', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='source_file', to='pipelines.pipeline')),
            ],
            options={
                'ordering': ('-fname',),
            },
        ),
    ]
