from django.db import models

# Create your models here.

class Plugin(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100)
    type = models.CharField(default='ds', max_length=4)

    class Meta:
        ordering = ('type',)

    def __str__(self):
        return self.name
