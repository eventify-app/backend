from django.core.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from rest_framework import status

from apps.events.api.filters import EventFilter
from apps.events.models import Event, StudentEvent
from apps.events.api.serializers import EventSerializer, EventParticipantSerializer, EventCheckInSerializer

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


    @action(detail=True, methods=['get'], url_path='participants', permission_classes=[IsAuthenticated], serializer_class=EventParticipantSerializer)
    def event_participants(self, request, pk=None):
        """
        Retrieve participants of a specific event.
        """
        event = self.get_object()
        participants = event.attendees.all()
        page = self.paginate_queryset(participants)
        ser = self.get_serializer(page or participants, many=True)
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)


    @action(detail=True, methods=['post'], url_path='check-in', permission_classes=[IsAuthenticated], serializer_class=EventCheckInSerializer)
    def check_in_participant(self, request, pk=None):
        """
        Mark the attendance of a participant for the event. Only the event creator can perform this action.
        """
        event = self.get_object()
        self.check_event_permission(event)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        participant_id = serializer.validated_data['participant_id']

        # Use transaction to ensure data integrity
        with transaction.atomic():

            try:
                student_event_registry = (
                    StudentEvent.objects
                    .select_for_update() # Lock the row for update
                    .select_related('student')
                    .get(event=event, student__id = participant_id)
                )

            except StudentEvent.DoesNotExist:
                return Response({'detail': 'El participante no está inscrito en este evento.'}, status=status.HTTP_404_NOT_FOUND)

            if student_event_registry.attended:
                return Response({'detail': 'El participante ya ha sido registrado como asistente.'}, status=status.HTTP_200_OK)

            student_event_registry.attended = True
            student_event_registry.save()

        return Response({'detail': 'Asistencia registrada correctamente.'}, status=status.HTTP_200_OK)

