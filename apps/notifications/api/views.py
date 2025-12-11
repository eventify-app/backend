from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema

from apps.notifications.models import UserNotification
from apps.notifications.api.serializers import UserNotificationSerializer


@extend_schema(tags=["Notifications"])
class UserNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for user notifications.
    Users can only see their own notifications.
    """
    serializer_class = UserNotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Get notifications for the authenticated user only.
        """
        return UserNotification.objects.filter(
            user=self.request.user
        ).select_related('notification')
    
    @action(detail=True, methods=['patch'], url_path='read')
    def mark_as_read(self, request, pk=None):
        """
        Mark a notification as read.
        Endpoint: PATCH /api/notifications/{id}/read/
        """
        user_notification = self.get_object()
        
        if user_notification.read:
            return Response(
                {'detail': 'La notificación ya está marcada como leída.'},
                status=status.HTTP_200_OK
            )
        
        user_notification.read = True
        user_notification.read_at = timezone.now()
        user_notification.save()
        
        serializer = self.get_serializer(user_notification)
        return Response(serializer.data, status=status.HTTP_200_OK)