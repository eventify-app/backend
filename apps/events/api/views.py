from django.core.exceptions import PermissionDenied
from django.db.models.expressions import Exists, Value
from django.db.models.fields import BooleanField
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, OuterRef, Avg, Q, F, FloatField, ExpressionWrapper, Max
from rest_framework import status, mixins
from datetime import datetime, timedelta
from django.contrib.auth.models import Group

from apps.events.api.filters import EventFilter
from apps.events.models import Event, StudentEvent, EventRating, EventComment, Category, CommentReport, EventReport, NotificationPreference
from apps.events.api.serializers import (
    EventSerializer, EventParticipantSerializer, EventCheckInSerializer,
    EventRatingSerializer, EventCommentSerializer, StudentEventSerializer,
    EventStatsSerializer, AttendeeStatsSerializer, PopularEventSerializer,
    CategoryAttendeeStatsSerializer, CategorySerializer, CommentReportSerializer,
    ReportedCommentSerializer, ReportCommentSerializer, EventReportSerializer,
    ReportedEventSerializer, ReportEventSerializer, NotificationPreferenceSerializer, EventRatingsAverageSerializer
)
from apps.notifications.models import Notification, UserNotification

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
        Filters out inactive/disabled events by default.
        """
        
        queryset = Event.objects.all().filter(is_active=True)

        # Annotate with participants_count for each event
        queryset = queryset.annotate(
            participants_count= Count("student_events", distinct=True)
        )

        # Annotate with is_enrolled if user is authenticated
        if self.request.user.is_authenticated:
            subquery = StudentEvent.objects.filter(
                event=OuterRef("pk"), student = self.request.user
            )
            queryset = queryset.annotate(is_enrolled= Exists(subquery))
        else:
            queryset = queryset.annotate(is_enrolled= Value(False, output_field= BooleanField()))

        return queryset
    
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
        Soft delete: marks event as inactive instead of removing from DB.
        """
        user = self.request.user
        is_admin = user.groups.filter(name='Administrator').exists()
        is_creator = (user.id == instance.id_creator.id)
        if not (is_creator or is_admin):
            raise PermissionDenied("No tiene permiso para eliminar este evento.")

        instance.is_active = False
        instance.disabled_at = timezone.now()
        instance.disabled_by = self.request.user
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
        participants = (StudentEvent.objects.filter(event= event).select_related("student").order_by("student__username"))

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

    @action(detail=False, methods=['get'], url_path='calendar', permission_classes=[IsAuthenticatedOrReadOnly])
    def calendar(self, request):
        """
        Retrieve upcoming events within a date range.
        Query params:
        - from: start date (format: YYYY-MM-DD)
        - to: end date (format: YYYY-MM-DD)
        
        Only returns active (non-deleted) events that haven't ended yet.
        """

        #obtener parametros de la query
        from_date = request.query_params.get('from', None)
        to_date = request.query_params.get('to', None)

        #filtrar eventos proximos 
        today = timezone.now().date()
        queryset = self.get_queryset().filter(end_date__gte=today)

        #si se proporciona desde fecha, filtrar eventos desde esa fecha
        if from_date:
            try: 
                from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
                queryset = queryset.filter(start_date__gte=from_date_obj)
            except ValueError:
                return Response(
                    {'error': 'Formate de fecha inválido para "from". Use el formato YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if to_date:
            try: 
                to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
                queryset = queryset.filter(end_date__lte=to_date_obj)
            except ValueError:
                return Response(
                    {'error': 'Formate de fecha inválido para "to". Use el formato YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        queryset = queryset.order_by('start_date', 'start_time')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='my-stats', permission_classes=[IsAuthenticated])
    def my_event_stats(self, request):
        """
        Retrieve the total number of events, events last month and events list last month.
        """
        user = request.user
        one_month_ago = timezone.now() - timedelta(days=30)
        my_events = Event.objects.filter(id_creator=user, is_active=True)
        total_events = my_events.count()

        events_last_month = my_events.filter(
            start_date__gte=one_month_ago.date()).annotate(
                participants_count= Count("student_events", distinct=True)).annotate(
                    is_enrolled=Value(False, output_field=BooleanField()))
        
        events_last_month_count = events_last_month.count()

        data = {
            'total_events': total_events,
            'events_last_month': events_last_month_count,
            'events_list_last_month': events_last_month
        }

        serializer = EventStatsSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='my-attendee-stats', permission_classes=[IsAuthenticated])
    def my_attendee_stats(self, request):
        """
        Retrieve the total number of attendees, attendees last month.
        """
        user = request.user
        one_month_ago = timezone.now() - timedelta(days=30)
        my_events = Event.objects.filter(id_creator=user, is_active=True)
        
        total_enrolled = StudentEvent.objects.filter(event__in=my_events).count()
        
        total_attended = StudentEvent.objects.filter(event__in=my_events, attended=True).count()
        events_last_month = my_events.filter(start_date__gte=one_month_ago.date())
        enrolled_last_month = StudentEvent.objects.filter(event__in=events_last_month).count()
        attended_last_month = StudentEvent.objects.filter(
            event__in=events_last_month, 
            attended=True
        ).count()
        
        data = {
            'total_enrolled': total_enrolled,
            'total_attended': total_attended,
            'enrolled_last_month': enrolled_last_month,
            'attended_last_month': attended_last_month
        }
        
        serializer = AttendeeStatsSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='my-popular-events', permission_classes=[IsAuthenticated])
    def my_popular_events(self, request):
        """
        Retrieve the 5 most popular events of the user.
        """
        user = request.user
        my_events = Event.objects.filter(
            id_creator=user, 
            is_active=True
        ).annotate(
            total_participants=Count('student_events', distinct=True),
            total_attended=Count('student_events', filter=Q(student_events__attended=True), distinct=True),
            average_rating=Avg('ratings__score'),
            total_ratings=Count('ratings', distinct=True)
        ).filter(
            total_participants__gt=0  # Solo eventos con participantes
        ).annotate(
            # Calcular tasa de asistencia
            attendance_rate=ExpressionWrapper(
                F('total_attended') * 100.0 / F('total_participants'),
                output_field=FloatField()
            )
        ).order_by(
            '-total_participants',  # Primero por más participantes
            '-average_rating',       # Luego por mejor calificación
            '-attendance_rate'       # Finalmente por tasa de asistencia
        )[:5]

        popular_events_data = []
        for event in my_events:
            event_with_annotations = Event.objects.filter(pk=event.pk).annotate(
                participants_count=Count('student_events', distinct=True),
                is_enrolled=Value(False, output_field=BooleanField())
            ).first()
            
            popular_events_data.append({
                'event': event_with_annotations,
                'total_participants': event.total_participants,
                'total_attended': event.total_attended,
                'attendance_rate': round(event.attendance_rate, 2) if event.attendance_rate else 0,
                'average_rating': round(event.average_rating, 2) if event.average_rating else 0,
                'total_ratings': event.total_ratings
            })
        
        serializer = PopularEventSerializer(popular_events_data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='attendees-by-category', permission_classes=[IsAuthenticated])
    def attendees_by_category(self, request):
        """
        Retrieve the attendees by category of the user.
        """
        user = request.user
        categories = Category.objects.all()
        stats_by_category = []

        for category in categories:
            events_in_category = Event.objects.filter(
                id_creator=user,
                is_active=True,
                categories=category
            )
            
            total_events = events_in_category.count()
            
            if total_events > 0:
                total_enrolled = StudentEvent.objects.filter(
                    event__in=events_in_category
                ).count()
                
                total_attended = StudentEvent.objects.filter(
                    event__in=events_in_category,
                    attended=True
                ).count()
                
                attendance_rate = (total_attended / total_enrolled * 100) if total_enrolled > 0 else 0
                
                stats_by_category.append({
                    'category': category,
                    'total_events': total_events,
                    'total_enrolled': total_enrolled,
                    'total_attended': total_attended,
                    'attendance_rate': round(attendance_rate, 2)
                })

        serializer = CategoryAttendeeStatsSerializer(stats_by_category, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=ReportEventSerializer,
        responses={
            201: {'description': 'Evento reportado correctamente.'},
            400: {'description': 'Error en la validación o evento ya reportado.'},
            404: {'description': 'Evento no encontrado.'}
        })
    @action(detail=True, methods=['post'], url_path='report', permission_classes=[IsAuthenticated])
    def report_event(self, request, pk=None):
        """
        Report an event as inappropriate.
        Creates a notification for all administrators.
        """
        event = self.get_object()
        
        # Check if user already reported this event
        if EventReport.objects.filter(event=event, reported_by=request.user).exists():
            return Response(
                {'detail': 'Ya has reportado este evento.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason')
        if not reason:
            return Response(
                {'detail': 'Debe proporcionar un motivo para el reporte.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create the event report
        EventReport.objects.create(
            event=event,
            reported_by=request.user,
            reason=reason
        )
        
        # Create notification for administrators
        try:
            # Create the notification
            notification = Notification.objects.create(
                description=f"User {request.user.username} reported event '{event.title}': {reason}",
                type='REPORT_ALERT'
            )
            
            # Get all administrators
            admin_group = Group.objects.get(name='Administrator')
            admins = admin_group.user_set.all()
            
            # Create UserNotification for each admin with read=False
            for admin in admins:
                UserNotification.objects.create(
                    user=admin,
                    notification=notification,
                    read=False
                )
        except Group.DoesNotExist:
            # If Administrator group doesn't exist, just continue without creating notifications
            pass
        
        return Response(
            {'detail': 'Evento reportado correctamente.'},
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['get'], url_path='my-ratings-average')
    def my_ratings_average(self, request):
        """
        Get average ratings for finished events created by the user.
        Only includes events that have already ended.
        """
        user = request.user
        now = timezone.now()
        
        # Calculate statistics
        total_finished = finished_events.count()
        
        events_with_ratings = finished_events.filter(
            ratings__isnull=False
        ).distinct().count()
        
        total_ratings = EventRating.objects.filter(
            event__in=finished_events
        ).count()
        
        average = EventRating.objects.filter(
            event__in=finished_events
        ).aggregate(avg=Avg('score'))['avg']
        
        data = {
            'total_finished_events': total_finished,
            'events_with_ratings': events_with_ratings,
            'total_ratings': total_ratings,
            'average_rating': round(average, 2) if average else 0.0,
            'events_without_ratings': total_finished - events_with_ratings
        }
        
        serializer = EventRatingsAverageSerializer(data)
        return Response(serializer.data)


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
            return Event.objects.get(pk=event_id, is_active=True)
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


@extend_schema_view(
    list=extend_schema(tags=["Event Comments"]),
    retrieve=extend_schema(tags=["Event Comments"]),
    create=extend_schema(tags=["Event Comments"]),
    update=extend_schema(tags=["Event Comments"]),
    partial_update=extend_schema(tags=["Event Comments"]),
    destroy=extend_schema(tags=["Event Comments"]),
)
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
            return Event.objects.get(pk=event_id, is_active=True)
        except Event.DoesNotExist:
            raise NotFound({'detail': 'Evento no encontrado.'})

    def perform_create(self, serializer):
        """
        Create a comment for the event.
        Only users who attended the event can comment.
        """
        event = self.get_event()
        user = self.request.user

        attended = StudentEvent.objects.filter(
            event=event,
            student=user,
            attended=True
        ).exists()

        if not attended:
            raise PermissionDenied({'detail': 'Solo los participantes que asistieron al evento pueden comentar.'})

        serializer.save(author=user, event=event)

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

    @extend_schema(
    request=ReportCommentSerializer,
    responses={
        200: {'description': 'Comentario reportado correctamente.'},
        400: {'description': 'Error en la validación o comentario ya reportado.'},
        404: {'description': 'Comentario no encontrado.'}
    })
    @action(detail=True, methods=['post'], url_path='report', permission_classes=[IsAuthenticated])
    def report_comment(self, request, event_id=None, pk=None):
        """
        Report a comment as inappropriate.
        Creates a notification for all administrators.
        """
        try:
            comment = EventComment.objects.get(pk=pk, event_id=event_id)
        except EventComment.DoesNotExist:
            raise NotFound({'detail': 'Comentario no encontrado.'})
        
        # Check if user already reported this comment
        if CommentReport.objects.filter(comment=comment, reported_by=request.user).exists():
            return Response(
                {'detail': 'Ya has reportado este comentario.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason')
        if not reason:
            return Response(
                {'detail': 'Debe proporcionar una razón para el reporte.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create the comment report
        CommentReport.objects.create(
            comment=comment,
            reported_by=request.user,
            reason=reason
        )
        
        # Create notification for administrators
        try:
            # Create the notification
            notification = Notification.objects.create(
                description=f"User {request.user.username} reported a comment by {comment.author.username} on event '{comment.event.title}': {reason}",
                type='REPORT_ALERT'
            )
            
            # Get all administrators
            admin_group = Group.objects.get(name='Administrator')
            admins = admin_group.user_set.all()
            
            # Create UserNotification for each admin with read=False
            for admin in admins:
                UserNotification.objects.create(
                    user=admin,
                    notification=notification,
                    read=False
                )
        except Group.DoesNotExist:
            # If Administrator group doesn't exist, just continue without creating notifications
            pass
        
        return Response(
            {'detail': 'Comentario reportado correctamente.'},
            status=status.HTTP_201_CREATED
        )


@extend_schema_view(
    list=extend_schema(tags=["Categories"]),
    retrieve=extend_schema(tags=["Categories"]),
)
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para categorías de eventos.
    Las categorías son predefinidas: Deportes, Cultura, Académico, Social, Tecnología, Arte.
    
    Solo permite:
    - list: GET /api/categories/
    - retrieve: GET /api/categories/{id}/
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    queryset = Category.objects.all()


@extend_schema_view(
    list=extend_schema(tags=['Comment Reports']),
    retrieve=extend_schema(tags=['Comment Reports']),
    disable_comment=extend_schema(tags=['Comment Reports']),
    restore_comment=extend_schema(tags=['Comment Reports']),
)
class CommentReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for administrators to view reported comments.
    Only administrators can access this endpoint.
    """
    serializer_class = ReportedCommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get all comments that have been reported, with report counts.
        Only accessible by administrators.
        """
        # Prevent error during schema generation
        if getattr(self, 'swagger_fake_view', False):
            return EventComment.objects.none()

        user = self.request.user
        if not user.groups.filter(name='Administrator').exists():
            raise PermissionDenied("Solo los administradores pueden ver los comentarios reportados.")
        
        # Get comments that have at least one report
        reported_comments = EventComment.objects.filter(
            reports__isnull=False
        ).annotate(
            report_count=Count('reports', distinct=True),
            latest_report_date=Max('reports__created_at')
        ).distinct().order_by('-latest_report_date')
        
        return reported_comments

    def list(self, request, *args, **kwargs):
        """
        List all reported comments with their reports.
        """
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        
        # Prepare data with reports
        comments_data = []
        for comment in (page if page is not None else queryset):
            reports = CommentReport.objects.filter(comment=comment).select_related('reported_by')
            comments_data.append({
                'comment': comment,
                'report_count': comment.report_count,
                'latest_report_date': comment.latest_report_date,
                'reports': reports
            })
        
        serializer = self.get_serializer(comments_data, many=True)
        
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='disable')
    def disable_comment(self, request, pk=None):
        """
        Disable a reported comment.
        Only administrators can disable comments.
        """
        user = request.user 
        if not user.groups.filter(name='Administrator').exists():
            raise PermissionDenied("Solo los administradores pueden inhabilitar comentarios.")
        
        try:
            comment = EventComment.objects.get(pk=pk)
        except EventComment.DoesNotExist:
            raise NotFound({'detail': 'Comentario no encontrado.'})

        if not comment.is_active:
            return Response(
                {'detail': 'El comentario ya está inhabilitado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        comment.is_active = False
        comment.disabled_at = timezone.now()
        comment.disabled_by = user
        comment.save()

        return Response(
            {'detail': 'Comentario inhabilitado correctamente.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='restore')
    def restore_comment(self, request, pk=None):
        """
        Restore a disabled comment.
        Only administrators can restore comments.
        """
        user = request.user
        if not user.groups.filter(name='Administrator').exists():
            raise PermissionDenied("Solo los administradores pueden restaurar comentarios.")

        try:
            comment = EventComment.objects.get(pk=pk)
        except EventComment.DoesNotExist:
            raise NotFound({'detail': 'Comentario no encontrado.'})

        if comment.is_active:
            return Response(
                {'detail': 'El comentario ya está activo.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        comment.is_active = True
        comment.disabled_at = None
        comment.disabled_by = None
        comment.save()

        return Response(
            {'detail': 'Comentario restaurado correctamente.'},
            status=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a specific reported comment with its reports.
        """
        comment = self.get_object()
        
        reports = CommentReport.objects.filter(comment=comment).select_related('reported_by')
        comment_data = {
            'comment': comment,
            'report_count': comment.report_count,
            'latest_report_date': comment.latest_report_date,
            'reports': reports
        }
        
        serializer = self.get_serializer(comment_data)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(tags=['Event Reports']),
)
class EventReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for administrators to view reported events.
    Only administrators can access this endpoint.
    """
    serializer_class = ReportedEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get all events that have been reported, with report counts.
        Only accessible by administrators.
        """
        # Prevent error during schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Event.objects.none()

        user = self.request.user
        if not user.groups.filter(name='Administrator').exists():
            raise PermissionDenied("Solo los administradores pueden ver los eventos reportados.")
        
        # Get events that have at least one report
        reported_events = Event.objects.filter(
            reports__isnull=False,
            is_active=True  # Solo eventos activos
        ).annotate(
            report_count=Count('reports', distinct=True),
            latest_report_date=Max('reports__created_at')
        ).distinct().order_by('-latest_report_date')
        
        return reported_events

    def list(self, request, *args, **kwargs):
        """
        List all reported events with their reports.
        """
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        
        # Prepare data with reports
        events_data = []
        for event in (page if page is not None else queryset):
            reports = EventReport.objects.filter(event=event).select_related('reported_by')
            
            # Annotate event with required fields
            event_annotated = Event.objects.filter(pk=event.pk).annotate(
                participants_count=Count('student_events', distinct=True),
                is_enrolled=Value(False, output_field=BooleanField())
            ).first()
            
            events_data.append({
                'event': event_annotated,
                'report_count': event.report_count,
                'latest_report_date': event.latest_report_date,
                'reports': reports
            })
        
        serializer = self.get_serializer(events_data, many=True)
        
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a specific reported event with its reports.
        """
        event = self.get_object()
        
        # Annotate event with required fields
        event_annotated = Event.objects.filter(pk=event.pk).annotate(
            participants_count=Count('student_events', distinct=True),
            is_enrolled=Value(False, output_field=BooleanField())
        ).first()
        
        reports = EventReport.objects.filter(event=event).select_related('reported_by')
        event_data = {
            'event': event_annotated,
            'report_count': event.report_count,
            'latest_report_date': event.latest_report_date,
            'reports': reports
        }
        
        serializer = self.get_serializer(event_data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='disable')
    def disable_event(self, request, pk=None):
        """
        Disable a reported event.
        Only administrators can disable events.
        """
        user = request.user
        if not user.groups.filter(name='Administrator').exists():
            raise PermissionDenied("Solo los administradores pueden inhabilitar eventos.")
        
        try:
            event = Event.objects.get(pk=pk)
        except Event.DoesNotExist:
            raise NotFound({'detail': 'Evento no encontrado.'})

        if not event.is_active:
            return Response(
                {'detail': 'El evento ya está inhabilitado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        event.is_active = False
        event.disabled_at = timezone.now()
        event.disabled_by = user
        event.save()

        return Response(
            {'detail': 'Evento inhabilitado correctamente.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='restore')
    def restore_event(self, request, pk=None):
        """
        Restore a disabled event.
        Only administrators can restore events.
        """
        user = request.user
        if not user.groups.filter(name='Administrator').exists():
            raise PermissionDenied("Solo los administradores pueden restaurar eventos.")

        try:
            event = Event.objects.get(pk=pk)
        except Event.DoesNotExist:
            raise NotFound({'detail': 'Evento no encontrado.'})

        if event.is_active:
            return Response(
                {'detail': 'El evento ya está activo.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        event.is_active = True
        event.disabled_at = None
        event.disabled_by = None
        event.save()

        return Response(
            {'detail': 'Evento restaurado correctamente.'},
            status=status.HTTP_200_OK
        )


@extend_schema(tags=["Notifications"])
class NotificationPreferenceViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationPreferenceSerializer

    def get_object(self):
        obj, _ = NotificationPreference.objects.get_or_create(user=self.request.user)
        self.check_object_permissions(self.request, obj)
        return obj
