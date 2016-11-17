
from django.db.models import Model, CharField, ForeignKey, ManyToManyField
from rest_framework.filters import FilterSet

# Create your models here.
class Moron(Model):
    name = CharField(max_length=100)

    class Meta:
        app_label = "collectionjson"
        

class MoronFilter(FilterSet):
    
    class Meta:
        model = Moron
        fields = ['name']

        
class Idiot(Model):
    name = CharField(max_length=100)

    class Meta:
        app_label = "collectionjson"


class Dummy(Model):
    name = CharField(max_length=100)
    moron = ForeignKey('Moron')
    idiots = ManyToManyField('Idiot')

    class Meta:
        app_label = "collectionjson"
        

class Simple(Model):
    name = CharField(max_length=100)
    
    class Meta:
        app_label = "collectionjson"



