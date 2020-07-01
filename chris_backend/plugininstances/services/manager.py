"""
Plugin app manager module that provides functionality to run and check the execution
status of a plugin app.
"""

from .charm import Charm


class PluginAppManager(object):

    @staticmethod
    def run_plugin_app(plugin_inst, parameter_dict):
        """
        Run a plugin's app.
        """
        # hardcode mounting points for the input and outputdir in the app's container
        app_container_inputdir = '/share/incoming'
        app_container_outputdir = '/share/outgoing'
        # get input dir
        inputdir = plugin_inst.previous.get_output_path() if plugin_inst.previous else ''
        # get output dir
        outputdir = plugin_inst.get_output_path()
        app_args = []
        # append app's container input dir to app's argument list (only for ds plugins)
        if plugin_inst.plugin.meta.type == 'ds':
            app_args.append(app_container_inputdir)
        # append app's container output dir to app's argument list
        app_args.append(app_container_outputdir)
        # append flag to save input meta data (passed options)
        app_args.append("--saveinputmeta")
        # append flag to save output meta data (output description)
        app_args.append("--saveoutputmeta")
        # append the parameters to app's argument list
        db_parameters = plugin_inst.plugin.parameters.all()
        for param_name in parameter_dict:
            param_value = parameter_dict[param_name]
            for db_param in db_parameters:
                if db_param.name == param_name:
                    if db_param.action == 'store':
                        app_args.append(db_param.flag)
                        app_args.append(param_value)
                    if db_param.action == 'store_true' and param_value:
                        app_args.append(db_param.flag)
                    if db_param.action == 'store_false' and not param_value:
                        app_args.append(db_param.flag)
                    break
        # run the app via an external REST service...
        str_IOPhost = plugin_inst.compute_resource.name
        chris_service = Charm(app_args=app_args,
                              d_args=parameter_dict,
                              plugin_inst=plugin_inst,
                              inputdir=inputdir,
                              outputdir=outputdir,
                              IOPhost=str_IOPhost)

        chris_service.app_manage(method='pfcon', IOPhost=str_IOPhost)

    @staticmethod
    def check_plugin_app_exec_status(plugin_inst):
        """
        Check a plugin's app execution status. It connects to the remote
        service to determine job status.
        """
        chris_service = Charm(plugin_inst=plugin_inst)
        chris_service.app_statusCheckAndRegister()

    @staticmethod
    def cancel_plugin_app_exec(plugin_inst):
        """
        Cancel a plugin's app execution. It connects to the remote service to cancel job.
        """
        pass
