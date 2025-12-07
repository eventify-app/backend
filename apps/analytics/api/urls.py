from django.urls import path
from .views import TopCategoriesView, TopCreatorsView, TopEventsView

urlpatterns = [
    path("analytics/top-categories/", TopCategoriesView.as_view(), name="analytics-top-categories"),
    path("analytics/top-creators/", TopCreatorsView.as_view(), name="analytics-top-creators"),
    path("analytics/top-events/", TopEventsView.as_view(), name="analytics-top-events"),
]