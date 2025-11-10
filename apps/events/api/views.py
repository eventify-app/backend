from django.core.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from django.utils import timezone

from apps.events.api.filters import EventFilter
from apps.events.models import Event
from apps.events.api.serializers import EventSerializer

from django_filters.rest_framework import DjangoFilterBackend

class EventViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing events.
    """
    serializer_class = EventSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticatedOrReadOnly]

    # Filters
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EventFilter
    search_fields = ['title', 'place', 'description']
    ordering = ['-start_date', '-start_time']

    def get_queryset(self):
        """
        Get events from database.
        Filters out soft-deleted events by default.
        """
        
        query = Event.objects.all().filter(deleted_at__isnull = True)
        return query
    
    def check_event_permission(self, instance):
        """
        Check if user has permission to modify the event.
        """
        user = self.request.user
        is_admin = user.groups.filter(name='Administrator').exists()
        is_creator = (user.id == instance.id_creator.id)
        if not (is_creator or is_admin):
            raise PermissionDenied("No tiene permiso para modificar este evento.")
        
    def perform_update(self, serializer):
        """
        Update event after checking permissions.
        Only creator or admin can update.
        """
        instance = self.get_object()
        self.check_event_permission(instance)
        serializer.save()
        
    
    def perform_destroy(self, instance):
        """
        Soft delete: marks event as deleted instead of removing from DB.
        """
        user = self.request.user
        is_admin = user.groups.filter(name='Administrator').exists()
        is_creator = (user.id == instance.id_creator.id)
        if not (is_creator or is_admin):
            raise PermissionDenied("No tiene permiso para eliminar este evento.")

        instance.deleted_at = timezone.now()
        instance.deleted_by = self.request.user
        instance.save()

    @action(detail=False, methods=['get'], url_path='my-events', permission_classes=[IsAuthenticated])
    def my_events(self, request):
        """
        Retrieve events created by the authenticated user.
        """
        queryset = (
            self.get_queryset().filter(id_creator=request.user)
            .order_by('-start_date', '-start_time')
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)