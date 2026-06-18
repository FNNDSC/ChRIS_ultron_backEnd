"""
Add nullable study FK to PACSSeries → PACSStudy.

The FK is nullable so existing rows continue to work unchanged.
The D-1 backfill (reindex_pacs_instances management command) populates it
for pre-existing series after B-1 deploys.

Adding a nullable column on Postgres 11+ is a metadata-only operation —
no row rewrite, safe to apply on a live table of any size.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pacsfiles', '0009_pacsseries_qido_fields'),
        ('dicomweb', '0002_pacsstudy'),
    ]

    operations = [
        migrations.AddField(
            model_name='pacsseries',
            name='study',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='series',
                to='dicomweb.pacsstudy',
            ),
        ),
    ]
