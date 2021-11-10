
from rest_framework import serializers


class NoModelSerializer(serializers.Serializer):
    """
    A serializer that is not associated to a DB model.
    """

    def get_url_field_name(self):
        """
        Custom method to get the name of the url field.
        """
        return 'url'
