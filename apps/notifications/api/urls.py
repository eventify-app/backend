from rest_framework.routers import DefaultRouter
from apps.notifications.api.views import UserNotificationViewSet

router = DefaultRouter()
router.register(r'notifications', UserNotificationViewSet, basename='notifications')

urlpatterns = router.urls