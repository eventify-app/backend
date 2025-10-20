from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from django.utils import timezone

from apps.events.models import Event
from apps.events.api.serializers import EventSerializer

class EventViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing events.
    """
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        """
        Get events from database.
        Filters out soft-deleted events by default.
        """
        
        query = Event.objects.all().filter(deleted_at__isnull = True)
        return query
    
    def perform_destroy(self, instance):
        """
        Soft delete: marks event as deleted instead of removing from DB.
        """
        instance.deleted_at = timezone.now()
        instance.deleted_by = self.request.user
        instance.save()
