"""
Vacuum the file and folder tables once 2% of their rows are updated or deleted and analyze
them once 1% are inserted, updated or deleted, instead of PostgreSQL's default 20% and 10%.
Inserts alone still trigger a vacuum at the default 20%
(autovacuum_vacuum_insert_scale_factor).

Registering and deleting feeds churns these tables by millions of rows so at the
defaults a table of a few million files carries hundreds of thousands of dead rows after a
deletion and stale planner statistics after a registration. Django has no field or Meta option for table
storage parameters. A migration applies them wherever CUBE runs.

ALTER TABLE ... SET takes a SHARE UPDATE EXCLUSIVE lock: reads and writes go on but the
migration waits for a manual VACUUM or ANALYZE, or an anti-wraparound autovacuum, running
on the table to finish (an ordinary autovacuum gives way).
"""
from django.db import migrations


TABLES = ('core_chrisfile', 'core_chrisfolder')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_chrisfolder_deletion_error_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[f'ALTER TABLE {table} SET (autovacuum_vacuum_scale_factor = 0.02, '
                 f'autovacuum_analyze_scale_factor = 0.01);' for table in TABLES],
            reverse_sql=[f'ALTER TABLE {table} RESET (autovacuum_vacuum_scale_factor, '
                         f'autovacuum_analyze_scale_factor);' for table in TABLES],
        ),
    ]
