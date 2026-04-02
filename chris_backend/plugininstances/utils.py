
from .tasks import run_plugin_instance_job
from .models import PluginInstance, ACTIVE_STATUSES


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
            if parent.status in ACTIVE_STATUSES:
                plg_inst.set_status('waiting')
                all_parents_finished = False
                break
            if parent.status in ('finishedWithError', 'cancelled'):
                plg_inst.set_status('cancelled')
                all_parents_finished = False
                break

        if all_parents_finished:
            if plg_inst.compute_resource.compute_requires_copy_job:
                plg_inst.set_status('copying')
                run_plugin_instance_job.delay(plg_inst.id, 'PluginInstanceCopyJob')
            else:
                plg_inst.set_status('scheduled')
                run_plugin_instance_job.delay(plg_inst.id, 'PluginInstanceAppJob')

    elif previous is None or previous.status == 'finishedSuccessfully':
        if plg_inst.compute_resource.compute_requires_copy_job:
            plg_inst.set_status('copying')
            run_plugin_instance_job.delay(plg_inst.id, 'PluginInstanceCopyJob')
        else:
            plg_inst.set_status('scheduled')
            run_plugin_instance_job.delay(plg_inst.id, 'PluginInstanceAppJob')

    elif previous.status in ACTIVE_STATUSES:
        plg_inst.set_status('waiting')

    elif previous.status in ('finishedWithError', 'cancelled'):
        plg_inst.set_status('cancelled')
