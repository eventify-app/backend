from django.urls import path, include
from apps.events.api.views import EventViewSet

urlpatterns = [
    path('events/', EventViewSet.as_view({'get': 'list', 'post': 'create'}), name='event-list'),
    path('events/<int:pk>/', EventViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='event-detail'),
]