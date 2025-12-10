from django.db import models
from django.conf import settings
from django.db.models.query_utils import Q


class Category(models.Model):
    """
    Model for event categories.
    Deportes, Cultura, Académico, Social, Tecnología, Arte.
    """
    type = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['type']
        
    def __str__(self):
        return self.type


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
    max_capacity = models.PositiveIntegerField(null=True, blank=True, help_text="Capacidad máxima de asistentes. Si es null, capacidad ilimitada.")

    categories = models.ManyToManyField(
        Category,
        related_name='events',
        blank=True,
        verbose_name='Categorías'
    )

    attendees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through= "events.StudentEvent",
        related_name="events_joined",
        blank=True
    )

class StudentEvent(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name='student_events')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_events')

    enrolled_at = models.DateTimeField(auto_now_add=True)
    attended = models.BooleanField(default=False)

    class Meta:
        unique_together = ('event', 'student')
        verbose_name = 'Asistencia de Estudiante a Evento'
        verbose_name_plural = 'Asistencias de Estudiantes a Eventos'


class EventRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='event_ratings')
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name='ratings')

    score = models.PositiveSmallIntegerField(null=False)

    class Meta:
        unique_together = ('user', 'event')
        verbose_name = 'Calificación de Evento'
        verbose_name_plural = 'Calificaciones de Eventos'


class EventComment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, help_text="Indica si el comentario está activo o inhabilitado")
    disabled_at = models.DateTimeField(null=True, blank=True)
    disabled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name='disabled_comments',
        on_delete=models.SET_NULL
    )
    
    class Meta:
        ordering = ['-created_at']


class CommentReport(models.Model):
    """
    Model for comment reports.
    Allows users to report inappropiate comments.
    """
    comment = models.ForeignKey(EventComment, on_delete=models.CASCADE, related_name='reports')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comment_reports')
    reason = models.TextField(help_text="Razón del reporte")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('comment', 'reported_by')
        verbose_name = 'Reporte de Comentario'
        verbose_name_plural = 'Reportes de Comentarios'
        ordering = ['-created_at']

    def __str__(self):
        return f"Reporte de comentario {self.reported_by.username} sobre el comentario {self.comment.id}"


class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notif_prefs")
    email_enabled = models.BooleanField(default=True)
    hours_before = models.PositiveSmallIntegerField(default=24)


class EventReminder(models.Model):
    KIND_CHOICES = [
        ("pre", "Pre-event"),
        ("post", "Post-event"),
    ]

    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name='reminders')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='event_reminders')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="pre")
    scheduled_for = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default="pending")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['event', 'user', 'kind'], name="unique_pre_post_reminder")
        ]

        indexes = [models.Index(fields=["scheduled_for"]), models.Index(fields=["event", "user"])]