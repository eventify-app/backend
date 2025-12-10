from django.db import models
from django.conf import settings


class Notification(models.Model):
    """
    Model for notifications.
    """
    TYPE_CHOICES = [
        ('REPORT_ALERT', 'Report Alert'),
    ]
    
    description = models.TextField()
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.type}: {self.description[:50]}"


class UserNotification(models.Model):
    """
    Intermediate model for user notifications with read status.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='user_notifications'
    )
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='users'
    )
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('user', 'notification')
        verbose_name = 'User Notification'
        verbose_name_plural = 'User Notifications'
        ordering = ['-notification__created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.notification.type} - {'Read' if self.read else 'Unread'}"