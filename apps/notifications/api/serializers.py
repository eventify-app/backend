from rest_framework import serializers
from apps.notifications.models import Notification, UserNotification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'description', 'type', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserNotificationSerializer(serializers.ModelSerializer):
    notification = NotificationSerializer(read_only=True)
    
    class Meta:
        model = UserNotification
        fields = ['id', 'notification', 'read', 'read_at']
        read_only_fields = ['id', 'notification', 'read_at']