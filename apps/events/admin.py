from django.contrib import admin
from apps.events.models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """
    Configuración del admin para el modelo Event
    """
    lisplay = ('id', 'place', 'start_date', 'start_time', 'end_date', 'end_time', 'id_creator', 'deleted_at')
    list_filter = ('start_date', 'deleted_at')
    