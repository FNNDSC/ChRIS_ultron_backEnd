from django.db import models

# Create your models here.

class Feed(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100)
    owner = models.ForeignKey('auth.User', related_name='feed')
    #tags = models.ManyToManyField(Tag)

    class Meta:
        ordering = ('creation_date',)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=20)

    def __str__(self):
        return self.name

