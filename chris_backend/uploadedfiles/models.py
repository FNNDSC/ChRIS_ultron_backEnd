
from django.db import models


def uploaded_file_path(instance, filename):
    # file will be stored to Swift at:
    # SWIFT_CONTAINER_NAME/<username>/<uploads>/<instance.upload_path>
    owner = instance.owner
    username = owner.username
    return '{0}/{1}/{2}'.format(username, 'uploads', instance.upload_path)


class UploadedFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    fname = models.FileField(max_length=512, upload_to=uploaded_file_path)
    upload_path = models.CharField(max_length=512)
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    def __str__(self):
        return self.upload_path
