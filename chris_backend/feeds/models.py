
from django.db import models

import django_filters
from django_filters.rest_framework import FilterSet


class Feed(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200, blank=True, db_index=True)
    owner = models.ManyToManyField('auth.User', related_name='feed')

    class Meta:
        ordering = ('-creation_date',)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        Overriden to save a new note to the DB the first time the feed is saved.
        """
        super(Feed, self).save(*args, **kwargs)
        if not hasattr(self, 'note'):
            self._save_note()

    def _save_note(self):
        """
        Custom method to create and save a new note to the DB.
        """
        note = Note()
        note.feed = self
        note.save()

    def get_creator(self):
        """
        Custom method to get the user that created the feed.
        """
        plg_inst = self.plugin_instances.filter(plugin__meta__type='fs')[0]
        return plg_inst.owner

    def get_plugin_instances_status_count(self, status):
        """
        Custom method to get the number of associated plugin instances with a given
        execution status.
        """
        return self.plugin_instances.filter(status=status).count()


class FeedFilter(FilterSet):
    min_id = django_filters.NumberFilter(field_name="id", lookup_expr='gte')
    max_id = django_filters.NumberFilter(field_name="id", lookup_expr='lte')
    min_creation_date = django_filters.IsoDateTimeFilter(field_name="creation_date",
                                                         lookup_expr='gte')
    max_creation_date = django_filters.IsoDateTimeFilter(field_name="creation_date",
                                                         lookup_expr='lte')
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    name_exact = django_filters.CharFilter(field_name='name', lookup_expr='exact')
    name_startswith = django_filters.CharFilter(field_name='name',
                                                lookup_expr='startswith')
    files_fname_icontains = django_filters.CharFilter(
        method='filter_by_fname_icontains')

    class Meta:
        model = Feed
        fields = ['id', 'name', 'name_exact', 'name_startswith', 'min_id', 'max_id',
                  'min_creation_date', 'max_creation_date', 'files_fname_icontains']

    def filter_by_fname_icontains(self, queryset, name, value):
        """
        Custom method to return the feeds that have files containing all the substrings
        from the queried string (which in turn represents a white-space-separated list of
        query strings) case insensitive anywhere in their fname.
        """
        # assume value is a string representing a white-space-separated list
        # of query strings
        value_l = value.split()
        qs = queryset
        for val in value_l:
            qs = qs.filter(plugin_instances__files__fname__icontains=val)
        return qs.distinct()


class Note(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=100, blank=True)
    content = models.TextField(blank=True)
    feed = models.OneToOneField(Feed, on_delete=models.CASCADE, related_name='note')

    def __str__(self):
        return self.title


class Tag(models.Model):
    name = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=20)
    feeds = models.ManyToManyField(Feed, related_name='tags',
                                   through='Tagging')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class TagFilter(FilterSet):
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    color = django_filters.CharFilter(field_name='color', lookup_expr='icontains')
    owner_username = django_filters.CharFilter(field_name='owner__username',
                                               lookup_expr='exact')

    class Meta:
        model = Tag
        fields = ['id', 'name', 'color', 'owner_username']


class Tagging(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('feed', 'tag',)

    def __str__(self):
        return str(self.id)


class Comment(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=100, blank=True)
    content = models.TextField(blank=True)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='comments')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    class Meta:
        ordering = ('-creation_date',)

    def __str__(self):
        return self.title


class CommentFilter(FilterSet):

    class Meta:
        model = Comment
        fields = ['id']
