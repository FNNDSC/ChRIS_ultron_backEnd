
import os, shutil, json

from django.test import TestCase
from django.conf import settings

from plugins.services.base import ChrisApp


def define_parameters(self):
    pass

class ChrisAppTests(TestCase):
    
    def setUp(self):
        # override abstract define_parameters method
        ChrisApp.define_parameters = define_parameters
        self.app = ChrisApp()

    def test_add_parameter(self):
        """
        Test whether add_parameter method adds a parameter to the app
        """
        self.app.add_parameter('--dir', action='store', dest='dir', type=str,
                               default='./', optional=True, help='look up directory')
        # input and output dirs are predefined positional arguments so we moc them
        inputdir = "./"
        outputdir = "./"
        options = self.app.parse_args([inputdir, outputdir])
        self.assertTrue(hasattr(options, "dir"))

    def test_get_json_representation(self):
        """
        Test whether get_json_representation method returns an appropriate json object
        """
        repres = self.app.get_json_representation()
        self.assertEquals(repres['type'], self.app.TYPE)
        self.assertTrue('parameters' in repres)

    def test_launch(self):
        """
        Test launch method 
        """
        # input and output dirs are predefined positional arguments so we moc them
        inputdir = "./"
        outputdir = "./"
        success = False
        try:
            self.app.launch([inputdir, outputdir])
        except NotImplementedError:
            success = True
        self.assertTrue(success)
        
    def test_save_options(self):
        """
        Test launch method 
        """
        # create test directory where files are created
        test_dir = settings.MEDIA_ROOT + '/test'
        settings.MEDIA_ROOT = test_dir
        if not os.path.exists(test_dir):
            os.makedirs(test_dir)
        inputdir = "./"
        outputdir = "./"
        options = self.app.parse_args([inputdir, outputdir])
        json_file_path = os.path.join(test_dir, "opts.json")
        self.app.save_options(options, json_file_path)
        success = os.path.isfile(json_file_path)
        self.assertTrue(success)
        expected_options_dir = {'json': False, 'outputdir': './', 'saveopts': False,
                                'opts': None, 'inputdir': './', 'description': False}
        if success:
            with open(json_file_path) as options_file:    
                options_dict = json.load(options_file)
                self.assertEquals(options_dict, expected_options_dir)
            shutil.rmtree(test_dir)
        settings.MEDIA_ROOT = os.path.dirname(test_dir)        

        


