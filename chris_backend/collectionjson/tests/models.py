
from django.db import models
from django_filters.rest_framework import FilterSet

# Create your models here.
class Moron(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "collectionjson"
        

class MoronFilter(FilterSet):
    
    class Meta:
        model = Moron
        fields = ['name']

        
class Idiot(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "collectionjson"


class Dummy(models.Model):
    name = models.CharField(max_length=100)
    moron = models.ForeignKey('Moron', on_delete=models.CASCADE)
    idiots = models.ManyToManyField('Idiot')

    class Meta:
        app_label = "collectionjson"
        

class Simple(models.Model):
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = "collectionjson"



