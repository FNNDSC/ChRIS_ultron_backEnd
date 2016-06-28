
from rest_framework.fields import SerializerMethodField


class ItemLinkField(SerializerMethodField):
    def __init__(self, method_name, *args, **kwargs):
        super(ItemLinkField, self).__init__(method_name, *args, **kwargs)
        

class CollectionLinkField(SerializerMethodField):
    def __init__(self, method_name, *args, **kwargs):
        super(CollectionLinkField, self).__init__(method_name, *args, **kwargs)
        

class TemplateField(SerializerMethodField):
    def __init__(self, method_name, *args, **kwargs):
        super(TemplateField, self).__init__(method_name, *args, **kwargs)


