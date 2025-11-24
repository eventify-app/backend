from django.core.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from django.utils import timezone
from django.db import transaction
from rest_framework import status

from apps.events.api.filters import EventFilter
from apps.events.models import Event, StudentEvent, EventRating, EventComment
from apps.events.api.serializers import EventSerializer, EventParticipantSerializer, EventCheckInSerializer, \
    EventRatingSerializer, EventCommentSerializer, StudentEventSerializer

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema_view, extend_schema


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

    @action(detail=False, methods=['get'], url_path='my-profile-events', permission_classes=[IsAuthenticated])
    def my_profile_events(self, request):
        """
        Retrieve events created by the user and events the user is enrolled in.
        Returns: {creados: [], inscritos: []}
        """
        user = request.user
        
        #mis eventos creados 
        created_events = (
            self.get_queryset()
            .filter(id_creator=user)
            .order_by('-start_date', '-start_time')
        )
        
        #eventos en los que me he inscrito
        enrolled_events = (
            self.get_queryset()
            .filter(attendees=user)
            .order_by('-start_date', '-start_time')
        )
        
        # Paginación para eventos creados
        created_page = self.paginate_queryset(created_events)
        if created_page is not None:
            created_serializer = self.get_serializer(created_page, many=True)
            created_data = created_serializer.data
        else:
            created_serializer = self.get_serializer(created_events, many=True)
            created_data = created_serializer.data
        
        # Paginación para eventos inscritos
        enrolled_page = self.paginate_queryset(enrolled_events)
        if enrolled_page is not None:
            enrolled_serializer = self.get_serializer(enrolled_page, many=True)
            enrolled_data = enrolled_serializer.data
        else:
            enrolled_serializer = self.get_serializer(enrolled_events, many=True)
            enrolled_data = enrolled_serializer.data 
        
        # Respuesta en el formato solicitado
        response_data = {
            'creados': created_data,
            'inscritos': enrolled_data
        }
        
        return Response(response_data)

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

    @action(detail=True, methods=['post'], url_path='enroll', permission_classes=[IsAuthenticated], serializer_class=StudentEventSerializer)
    def enroll_in_event(self, request, pk=None):
        """
        Enroll the authenticated user in an event.
        """
        event = self.get_object()
        user = request.user

        already_enrolled = StudentEvent.objects.filter(event=event, student=user).exists()
        if already_enrolled:
            return Response(
                {'detail': 'Ya estás inscrito en este evento.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if event.max_capacity is not None:
            current_attendees = event.attendees.count()
            if current_attendees >= event.max_capacity:
                return Response(
                    {'detail': 'El evento ha alcanzado su capacidad máxima.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        with transaction.atomic():
            student_event = StudentEvent.objects.create(
                event=event,
                student=user
            )
        
        serializer = self.get_serializer(student_event)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

@extend_schema_view(
    list=extend_schema(tags=["Event Ratings"]),
    retrieve=extend_schema(tags=["Event Ratings"]),
    create=extend_schema(tags=["Event Ratings"]),
    update=extend_schema(tags=["Event Ratings"]),
    partial_update=extend_schema(tags=["Event Ratings"]),
    destroy=extend_schema(tags=["Event Ratings"]),
)
class EventRatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing event ratings.
    """
    serializer_class = EventRatingSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        """
        Get event ratings from database.
        """
        return EventRating.objects.all()

    def get_event(self):
        """
        Retrieve the event based on event_id from URL kwargs.
        """
        event_id = self.kwargs.get('event_id')
        try:
            return Event.objects.get(pk=event_id, deleted_at__isnull=True)
        except Event.DoesNotExist:
            raise NotFound({'detail': 'Evento no encontrado.'})

    def perform_create(self, serializer):
        """
        Create event rating.
        """

        event = self.get_event()
        user = self.request.user

        # Check if user attended the event
        attended = StudentEvent.objects.filter(
            event=event,
            student=user,
            attended=True
        ).exists()

        if not attended:
            raise PermissionDenied({'detail': 'Solo los participantes que asistieron al evento pueden calificarlo.'})

        # Check if user has already rated the event
        scored = EventRating.objects.filter(
            event=event,
            user=user
        ).exists()

        if scored:
            raise PermissionDenied({'detail': 'Ya ha calificado este evento.'})

        serializer.save(user=user, event=event)


class EventCommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing event comments.
    Supports: List, Create, Update, Delete
    """
    serializer_class = EventCommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [JSONParser]

    def get_queryset(self):
        """
        Get comments for a specific event.
        """
        event_id = self.kwargs.get('event_id')
        return EventComment.objects.filter(event_id=event_id).select_related('author')

    def get_event(self):
        """
        Retrieve the event based on event_id from URL kwargs.
        """
        event_id = self.kwargs.get('event_id')
        try:
            return Event.objects.get(pk=event_id, deleted_at__isnull=True)
        except Event.DoesNotExist:
            raise NotFound({'detail': 'Evento no encontrado.'})

    def perform_create(self, serializer):
        """
        Create a comment for the event.
        Automatically assigns the authenticated user as author.
        """
        event = self.get_event()
        serializer.save(author=self.request.user, event=event)

    def perform_update(self, serializer):
        """
        Update a comment. Only the author can update their own comment.
        TODO: Allow administrators to delete any comment
        """
        comment = self.get_object()
        if comment.author != self.request.user:
            raise PermissionDenied({'detail': 'Solo puedes editar tus propios comentarios.'})
        serializer.save()

    def perform_destroy(self, instance):
        """
        Delete a comment. Only the author can delete their own comment.
        """
        if instance.author != self.request.user:
            raise PermissionDenied({'detail': 'Solo puedes eliminar tus propios comentarios.'})
        instance.delete()