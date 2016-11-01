
from django.db import models

class Feed(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, blank=True, default='')
    plugin_inst = models.OneToOneField('plugins.PluginInstance',
                                       on_delete=models.CASCADE, related_name='feed')
    owner = models.ManyToManyField('auth.User', related_name='feed')
    
    class Meta:
        ordering = ('creation_date',)

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
        note.feed = self;
        note.save()
        
            
class Note(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=100, blank=True, default='')
    content = models.TextField(blank=True, default='')
    feed = models.OneToOneField(Feed, on_delete=models.CASCADE, related_name='note')
    
    class Meta:
        ordering = ('creation_date',)

    def __str__(self):
        return self.title


class Tag(models.Model):
    name = models.CharField(max_length=100, blank=True, default='')
    color = models.CharField(max_length=20)
    feed = models.ManyToManyField(Feed, related_name='tags')
    owner = models.ForeignKey('auth.User')

    def __str__(self):
        return self.name


class Comment(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=100, blank=True, default='')
    content = models.TextField(blank=True, default='')
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='comments')
    owner = models.ForeignKey('auth.User')

    class Meta:
        ordering = ('creation_date',)

    def __str__(self):
        return self.title


class FeedFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    fname = models.FileField(max_length=2048)
    feed = models.ManyToManyField(Feed, related_name='files')
    plugin_inst = models.ForeignKey('plugins.PluginInstance', on_delete=models.CASCADE, related_name='file')

    def __str__(self):
        return self.fname.name   


