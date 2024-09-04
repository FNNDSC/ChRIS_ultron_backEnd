"""
Pipeline manager module that provides functionality to add, modify and delete pipelines.
"""

import os
import sys
from argparse import ArgumentParser

if __name__ == '__main__':
    # django needs to be loaded when this script is run standalone from the command line
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django
    django.setup()

from django.contrib.auth.models import User
from pipelines.models import Pipeline
from pipelines.serializers import PipelineSerializer


class PipelineManager(object):

    def __init__(self):
        parser = ArgumentParser(description='Manage pipelines')
        subparsers = parser.add_subparsers(dest='subparser_name', title='subcommands',
                                           description='valid subcommands',
                                           help='sub-command help')

        # create the parser for the "add" command
        parser_add = subparsers.add_parser('add', help='Add a new pipeline')
        parser_add.add_argument('name', help="Pipeline's name")
        parser_add.add_argument('owner', help="Pipeline's owner username")
        parser_add.add_argument('plugintree',
                           help="A json string with the plugin tree for the pipeline")
        parser_add.add_argument('--authors', help="Pipeline's authors string")
        parser_add.add_argument('--category', help="Pipeline's category")
        parser_add.add_argument('--description', help="Pipeline's description")
        parser_add.add_argument('--unlock', action='store_true',
                                help="Unlock pipeline to make it immutable and visible "
                                     "to other users")

        # create the parser for the "modify" command
        parser_modify = subparsers.add_parser('modify', help='Modify existing pipeline')
        parser_modify.add_argument('id', type=int, help="Plugin's id")
        parser_modify.add_argument('--name', help="Pipeline's name")
        parser_modify.add_argument('--authors', help="Pipeline's authors string")
        parser_modify.add_argument('--category', help="Pipeline's category")
        parser_modify.add_argument('--description', help="Pipeline's description")
        parser_modify.add_argument('--unlock', action='store_true',
                                help="Unlock pipeline to make it immutable and visible "
                                     "to other users")

        # create the parser for the "remove" command
        parser_remove = subparsers.add_parser('remove', help='Remove an existing pipeline')
        parser_remove.add_argument('id', type=int, help="Plugin's id")

        self.parser = parser

    def add_pipeline(self, args):
        """
        Add a new pipeline to the system.
        """
        data = {'name': args.name, 'plugin_tree': args.plugintree}
        if args.authors:
            data['authors'] = args.authors
        if args.category:
            data['category'] = args.category
        if args.description:
            data['description'] = args.description
        if args.unlock:
            data['locked'] = False
        pipeline_serializer = PipelineSerializer(data=data)
        pipeline_serializer.is_valid(raise_exception=True)
        owner = User.objects.get(username=args.owner)
        pipeline_serializer.save(owner=owner)

    def modify_pipeline(self, args):
        """
        Modify an existing pipeline.
        """
        pipeline = self.get_pipeline(args.id)
        data = {}
        if args.name:
            data['name'] = args.name
        if args.authors:
            data['authors'] = args.authors
        if args.category:
            data['category'] = args.category
        if args.description:
            data['description'] = args.description
        if args.unlock:
            data['locked'] = False
        pipeline_serializer = PipelineSerializer(pipeline, data=data)
        pipeline_serializer.is_valid(raise_exception=True)
        pipeline_serializer.save()

    def remove_pipeline(self, args):
        """
        Remove an existing pipeline from the system.
        """
        pipeline = self.get_pipeline(args.id)
        pipeline.delete()

    def run(self, args=None):
        """
        Parse the arguments passed to the manager and perform the appropriate action.
        """
        options = self.parser.parse_args(args)
        if options.subparser_name == 'add':
            self.add_pipeline(options)
        elif options.subparser_name == 'modify':
            self.modify_pipeline(options)
        elif options.subparser_name == 'remove':
            self.remove_pipeline(options)

    @staticmethod
    def get_pipeline(id):
        """
        Get an existing pipeline.
        """
        try:
            pipeline = Pipeline.objects.get(pk=id)
        except Pipeline.DoesNotExist:
            raise NameError("Couldn't find pipeline with id '%s' in the system" % id)
        return pipeline


# ENTRYPOINT
if __name__ == "__main__":
    manager = PipelineManager()
    manager.run()
