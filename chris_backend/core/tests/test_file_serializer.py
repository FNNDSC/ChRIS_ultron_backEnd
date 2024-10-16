from django.test import TestCase

from core.file_serializer import ChrisFileSerializer


class ChrisFileSerializerTests(TestCase):
    def test_no_model(self):
        msg = 'ExampleClass must have an inner class called Meta'
        with self.assertRaisesMessage(TypeError, msg):
            class ExampleClass(ChrisFileSerializer):
                pass

    def test_wrong_model(self):
            msg = 'ExampleClass.Meta.model must be ChrisFile'
            with self.assertRaisesMessage(TypeError, msg):
                class ExampleClass(ChrisFileSerializer):
                    class Meta:
                        model = dict
