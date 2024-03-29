# Generated by Django 4.2.5 on 2023-12-19 04:41

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0003_alter_chrisinstance_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChrisFolder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creation_date', models.DateTimeField(auto_now_add=True)),
                ('path', models.CharField(max_length=1024, unique=True)),
                ('size', models.BigIntegerField(default=0)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('parent', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='core.chrisfolder')),
            ],
            options={
                'ordering': ('-path',),
            },
        ),
        migrations.CreateModel(
            name='ChrisLinkFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creation_date', models.DateTimeField(auto_now_add=True)),
                ('path', models.CharField(max_length=1024)),
                ('is_folder', models.BooleanField()),
                ('fname', models.FileField(max_length=1024, unique=True, upload_to='')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('parent_folder', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chris_link_files', to='core.chrisfolder')),
            ],
        ),
    ]
