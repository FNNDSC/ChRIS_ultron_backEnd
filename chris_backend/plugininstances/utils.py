
from plugininstances.tasks import run_plugin_instance
from plugininstances.models import PluginInstance


def run_if_ready(plg_inst, previous):
    """
    Set the status of ``plg_inst`` accordingly depending on the status of its previous
    plugin instance. Plugin instances of type 'ts' also consider the status of each of
    its possibly multiple parents.
    """
    parent_ids = []
    if plg_inst.plugin.meta.type == 'ts':
        param = plg_inst.string_param.filter(plugin_param__name='plugininstances').first()
        if param and param.value:
            parent_ids = [int(parent_id) for parent_id in param.value.split(',')]

    if parent_ids:
        parents = PluginInstance.objects.filter(pk__in=parent_ids)
        all_parents_finished = True

        for parent in parents:
            if parent.status in ('created', 'waiting', 'scheduled',
                                 'registeringFiles', 'started'):
                plg_inst.set_status('waiting')
                all_parents_finished = False
                break
            if parent.status in ('finishedWithError', 'cancelled'):
                plg_inst.set_status('cancelled')
                all_parents_finished = False
                break

        if all_parents_finished:
            plg_inst.set_status('scheduled')
            run_plugin_instance.delay(plg_inst.id)  # call async task

    elif previous is None or previous.status == 'finishedSuccessfully':
        plg_inst.set_status('scheduled') # changes to 'scheduled' right away
        run_plugin_instance.delay(plg_inst.id)  # call async task

    elif previous.status in ('created', 'waiting', 'scheduled',
                             'registeringFiles', 'started'):
        plg_inst.set_status('waiting')

    elif previous.status in ('finishedWithError', 'cancelled'):
        plg_inst.set_status('cancelled')
