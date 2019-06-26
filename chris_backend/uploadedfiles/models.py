
from django.db import models
import django_filters
from django_filters.rest_framework import FilterSet


def uploaded_file_path(instance, filename):
    # file will be stored to Swift at:
    # SWIFT_CONTAINER_NAME/<username>/<uploads>/<instance.upload_path>
    owner = instance.owner
    username = owner.username
    return '{0}/{1}/{2}'.format(username, 'uploads', instance.upload_path.strip('/'))


class UploadedFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    fname = models.FileField(max_length=512, upload_to=uploaded_file_path)
    upload_path = models.CharField(max_length=512)
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    def __str__(self):
        return self.upload_path


class UploadedFileFilter(FilterSet):
    min_creation_date = django_filters.DateFilter(field_name='creation_date',
                                                  lookup_expr='gte')
    max_creation_date = django_filters.DateFilter(field_name='creation_date',
                                                 lookup_expr='lte')

    upload_path = django_filters.CharFilter(field_name='upload_path',
                                            lookup_expr='icontains')
    owner_username = django_filters.CharFilter(field_name='owner__username',
                                               lookup_expr='exact')

    class Meta:
        model = UploadedFile
        fields = ['id', 'min_creation_date', 'max_creation_date', 'upload_path',
                  'owner_username']
