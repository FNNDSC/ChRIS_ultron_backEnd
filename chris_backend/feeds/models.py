
from django.db import models

import django_filters
from django_filters.rest_framework import FilterSet


class Feed(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, blank=True, default='')
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


class FeedFilter(FilterSet):
    min_id = django_filters.NumberFilter(field_name="id", lookup_expr='gte')
    max_id = django_filters.NumberFilter(field_name="id", lookup_expr='lte')
    min_creation_date = django_filters.DateFilter(field_name="creation_date",
                                                  lookup_expr='gte')
    max_creation_date = django_filters.DateFilter(field_name="creation_date",
                                                  lookup_expr='lte')

    class Meta:
        model = Feed
        fields = ['id', 'name', 'min_id', 'max_id', 'min_creation_date',
                  'max_creation_date']


class Note(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=100, blank=True, default='')
    content = models.TextField(blank=True, default='')
    feed = models.OneToOneField(Feed, on_delete=models.CASCADE, related_name='note')

    def __str__(self):
        return self.title


class Tag(models.Model):
    name = models.CharField(max_length=100, blank=True, default='')
    color = models.CharField(max_length=20)
    feeds = models.ManyToManyField(Feed, related_name='tags',
                                   through='Tagging')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Tagging(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('feed', 'tag',)

    def __str__(self):
        return str(self.id)


class Comment(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=100, blank=True, default='')
    content = models.TextField(blank=True, default='')
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='comments')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    class Meta:
        ordering = ('-creation_date',)

    def __str__(self):
        return self.title
