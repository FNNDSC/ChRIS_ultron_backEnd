
from rest_framework.serializers import HyperlinkedIdentityField
from rest_framework.serializers import HyperlinkedModelSerializer, ModelSerializer

from collectionjson.fields import ItemLinkField
from .models import Dummy, Idiot, Moron, Simple

        
class MoronHyperlinkedModelSerializer(HyperlinkedModelSerializer):
    class Meta(object):
        model = Moron
        fields = ('url', 'name')
        

class IdiotHyperlinkedModelSerializer(HyperlinkedModelSerializer):
    class Meta(object):
        model = Idiot
        fields = ('url', 'name')


class DummyHyperlinkedModelSerializer(HyperlinkedModelSerializer):
    other_stuff = ItemLinkField('get_other_link')
    empty = ItemLinkField('get_empty_link')
    some_link = HyperlinkedIdentityField(view_name='moron-detail')

    class Meta(object):
        model = Dummy
        fields = ('url', 'name', 'moron', 'idiots', 'other_stuff', 'some_link', 'empty')

    def get_other_link(self, obj):
        return 'http://other-stuff.com/'

    def get_empty_link(self, obj):
        return None
    

class SimpleModelSerializer(ModelSerializer):

    class Meta(object):
        model = Simple
        fields = ('name', )
