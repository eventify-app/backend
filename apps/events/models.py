from django.db import models
from django.conf import settings

# Create your models here.
class Event(models.Model):
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='deleted_events', on_delete=models.SET_NULL)
    title = models.CharField(max_length=120, null=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to="events/covers/", null=True, blank=True)
    place = models.CharField(max_length=200)
    start_time = models.TimeField()
    start_date = models.DateField()
    end_time = models.TimeField()
    end_date = models.DateField()
    deleted_at = models.DateTimeField(null=True, blank=True)
    id_creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)