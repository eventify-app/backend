from django.urls import path, include
from apps.events.api.views import EventViewSet
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r"events", EventViewSet, basename='events')

urlpatterns = router.urls