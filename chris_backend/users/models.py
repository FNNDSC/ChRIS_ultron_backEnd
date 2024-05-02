
from django.contrib.auth.models import Group

import django_filters
from django_filters.rest_framework import FilterSet


class GroupFilter(FilterSet):
    name_icontains = django_filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = Group
        fields = ['id', 'name', 'name_icontains']
