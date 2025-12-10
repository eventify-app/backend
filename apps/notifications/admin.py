from django.contrib import admin
from apps.notifications.models import Notification, UserNotification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'type', 'description', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['description']
    readonly_fields = ['created_at']


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'notification', 'read', 'read_at']
    list_filter = ['read', 'notification__type']
    search_fields = ['user__username', 'notification__description']
    readonly_fields = ['read_at']