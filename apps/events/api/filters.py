import django_filters as df
from apps.events.models import Event

class EventFilter(df.FilterSet):
    """
    Filter class for Event model.
    Allows filtering by title and place with case-insensitive containment.
    """
    title = df.CharFilter(field_name="title", lookup_expr="icontains")
    place = df.CharFilter(field_name="place", lookup_expr="icontains")
    description = df.CharFilter(field_name="description", lookup_expr="icontains")
    from_date = df.DateFilter(field_name="start_date", lookup_expr="gte")
    to_date = df.DateFilter(field_name="end_date", lookup_expr="lte")

    class Meta:
        model = Event
        fields = []