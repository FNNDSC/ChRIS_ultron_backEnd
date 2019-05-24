# Generated by Django 2.1.4 on 2019-05-24 17:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('plugins', '0029_auto_20190423_1448'),
        ('plugininstances', '0007_auto_20190222_1532'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='boolparameter',
            unique_together={('plugin_inst', 'plugin_param')},
        ),
        migrations.AlterUniqueTogether(
            name='floatparameter',
            unique_together={('plugin_inst', 'plugin_param')},
        ),
        migrations.AlterUniqueTogether(
            name='intparameter',
            unique_together={('plugin_inst', 'plugin_param')},
        ),
        migrations.AlterUniqueTogether(
            name='pathparameter',
            unique_together={('plugin_inst', 'plugin_param')},
        ),
        migrations.AlterUniqueTogether(
            name='strparameter',
            unique_together={('plugin_inst', 'plugin_param')},
        ),
    ]
