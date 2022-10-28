from plugininstances.tasks import run_plugin_instance


def run_if_ready(plg_inst, previous):
    """
    Set the status of ``plg_inst`` accordingly depending on the state of its previous
    plugin instance.
    """

    if previous is None or previous.status == 'finishedSuccessfully':
        # schedule the plugin's app to run
        plg_inst.status = 'scheduled'  # status changes to 'scheduled' right away
        plg_inst.save()
        run_plugin_instance.delay(plg_inst.id)  # call async task
    elif previous.status in ('created', 'waiting', 'scheduled',
                             'registeringFiles', 'started'):
        plg_inst.status = 'waiting'
        plg_inst.save()
    elif previous.status in ('finishedWithError', 'cancelled'):
        plg_inst.status = 'cancelled'
        plg_inst.save()
