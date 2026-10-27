import uuid
from django.db import models

def upload_video_path(instance, filename):
    return f'videos/{instance.uuid}/{filename}'

class Video(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to=upload_video_path)
    master_playlist = models.CharField(max_length=255, blank=True, null=True)
    thumbnail = models.ImageField(upload_to=upload_video_path, blank=True, null=True)
    view_count = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title