# Generated by Django 4.0 on 2022-10-18 12:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pacsfiles', '0006_alter_pacs_id_alter_pacsfile_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pacsfile',
            name='PatientSex',
            field=models.CharField(blank=True, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], max_length=2),
        ),
    ]