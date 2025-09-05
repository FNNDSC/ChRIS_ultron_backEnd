
from django.db import models
from django_filters.rest_framework import FilterSet

# Create your models here.
class Employee(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "collectionjson"
        

class EmployeeFilter(FilterSet):
    
    class Meta:
        model = Employee
        fields = ['name']

        
class Person(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "collectionjson"


class Dummy(models.Model):
    name = models.CharField(max_length=100)
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE)
    persons = models.ManyToManyField('Person')

    class Meta:
        app_label = "collectionjson"
        

class Simple(models.Model):
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = "collectionjson"



