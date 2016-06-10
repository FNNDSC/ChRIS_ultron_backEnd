
from rest_framework.fields import SerializerMethodField


class LinkField(SerializerMethodField):
    def __init__(self, method_name, *args, **kwargs):
        self.method_name = method_name
        super(LinkField, self).__init__(method_name, *args, **kwargs)


