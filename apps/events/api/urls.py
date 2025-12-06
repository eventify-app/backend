from django.urls import path, include
from apps.events.api.views import EventViewSet, EventRatingViewSet, EventCommentViewSet, CategoryViewSet, CommentReportViewSet
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r"events", EventViewSet, basename='Events')
router.register(r"categories", CategoryViewSet, basename='Categories')
router.register(r'reported-comments', CommentReportViewSet, basename='reported-comments')

urlpatterns = router.urls + [
    path("events/<int:event_id>/ratings/", EventRatingViewSet.as_view({'get': 'list', 'post': 'create'}), name='event-rating-list'),
    path("events/<int:event_id>/ratings/<int:pk>/", EventRatingViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update' , 'delete': 'destroy'}), name='event-rating-detail'),
    path("events/<int:event_id>/comments/", EventCommentViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name= 'event-comments-list'),
    path("events/<int:event_id>/comments/<int:pk>/", EventCommentViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name= 'event-comments-detail') ,
    path("events/<int:event_id>/comments/<int:pk>/report/", EventCommentViewSet.as_view({
        'post': 'report_comment'
    }), name='event-comment-report'),
]