"""
Enable pg_trgm extension and add GIN trigram indexes for QIDO-RS wildcard search.

pg_trgm is a standard PostgreSQL contrib module (available in all Postgres
installations). Enabling it allows GIN indexes to accelerate arbitrary substring
ILIKE queries — necessary for QIDO wildcard matching at scale (PS3.18 §F.7).

This migration depends only on dicomweb.0001_initial and is independent of B-1
(PACSStudy). Once B-1 merges, this migration will be renumbered to 0003 and its
dependency updated to reference the PACSStudy migration.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dicomweb', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql='CREATE EXTENSION IF NOT EXISTS pg_trgm;',
            reverse_sql='DROP EXTENSION IF EXISTS pg_trgm;',
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS pacsseries_patientname_trgm_idx
                    ON pacsfiles_pacsseries USING GIN ("PatientName" gin_trgm_ops);
                CREATE INDEX IF NOT EXISTS pacsseries_patientid_trgm_idx
                    ON pacsfiles_pacsseries USING GIN ("PatientID" gin_trgm_ops);
                CREATE INDEX IF NOT EXISTS pacsseries_studydescription_trgm_idx
                    ON pacsfiles_pacsseries USING GIN ("StudyDescription" gin_trgm_ops);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS pacsseries_patientname_trgm_idx;
                DROP INDEX IF EXISTS pacsseries_patientid_trgm_idx;
                DROP INDEX IF EXISTS pacsseries_studydescription_trgm_idx;
            """,
        ),
    ]
