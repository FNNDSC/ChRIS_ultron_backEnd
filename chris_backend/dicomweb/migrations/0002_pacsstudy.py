"""
Add PACSStudy model — study-level entity for the DICOM hierarchy.

This migration is additive only. Existing PACSSeries rows are unaffected;
the FK (pacsfiles migration 0010) is nullable and populated by D-1 backfill.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dicomweb', '0001_initial'),
        ('pacsfiles', '0009_pacsseries_qido_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='PACSStudy',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('StudyInstanceUID', models.CharField(db_index=True, max_length=100)),
                ('StudyDate', models.DateField(blank=True, db_index=True, null=True)),
                ('StudyTime', models.TimeField(blank=True, null=True)),
                ('AccessionNumber', models.CharField(blank=True, db_index=True, max_length=100)),
                ('StudyDescription', models.CharField(blank=True, max_length=400)),
                ('PatientName', models.CharField(blank=True, db_index=True, max_length=400)),
                ('PatientID', models.CharField(blank=True, db_index=True, max_length=100)),
                ('PatientBirthDate', models.DateField(blank=True, null=True)),
                ('PatientSex', models.CharField(blank=True, max_length=1)),
                ('NumberOfStudyRelatedSeries', models.PositiveIntegerField(default=0)),
                ('NumberOfStudyRelatedInstances', models.PositiveIntegerField(default=0)),
                ('pacs', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='studies',
                    to='pacsfiles.pacs',
                )),
            ],
            options={
                'unique_together': {('pacs', 'StudyInstanceUID')},
            },
        ),
        migrations.AddIndex(
            model_name='pacsstudy',
            index=models.Index(fields=['pacs', 'StudyDate'], name='pacsstudy_pacs_date_idx'),
        ),
    ]
