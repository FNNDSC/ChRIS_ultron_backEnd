# Generated by Django 4.0 on 2022-10-19 23:14
from django.db import migrations, models


# MANUALLY ADDED WORKAROUND
def set_default_piping_title(apps, schema_editor):
    """
    In this migration, there is a new constraint introduced where piping titles
    must be unique within a pipeline. Hence empty piping titles become problematic.

    For every piping without a title, assign a unique title which is comprised
    of their ID number and their plugin's title.
    """
    PluginPiping = apps.get_model('pipelines', 'PluginPiping')

    pipings = PluginPiping.objects.all().iterator()
    pipings_wo_title = filter(lambda p: not p.title, pipings)

    for piping in pipings_wo_title:
        plugin_title = piping.plugin.meta.title
        piping.title = f'{piping.id}: {plugin_title}'[:100]
        print('SETTING PIPING TITLE: ' + piping.title)
        piping.save()


def undo_piping_title_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('pipelines', '0007_pluginpiping_title'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pluginpiping',
            name='title',
            field=models.CharField(max_length=100),
        ),
        # MANUALLY ADDED WORKAROUND
        migrations.RunPython(set_default_piping_title, undo_piping_title_noop),
        migrations.AlterUniqueTogether(
            name='pluginpiping',
            unique_together={('title', 'pipeline')},
        ),
    ]