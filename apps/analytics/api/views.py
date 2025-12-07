from datetime import datetime
from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework import status
from drf_spectacular.utils import extend_schema

from apps.analytics.api.serializers import TopCategorySerializer, TopCreatorSerializer, TopCategoriesQuery, \
    TopCreatorsQuery, TopEventQuery, TopEventSerializer
from apps.events.api.serializers import PopularEventSerializer, EventSerializer
from apps.events.models import Event, StudentEvent  # ajusta import al through real
from apps.users.permissions import IsInAdministratorGroup


def _parse_dates(request):
    try:
        f = request.query_params.get("from")
        t = request.query_params.get("to")
        date_from = datetime.fromisoformat(f).date() if f else None
        date_to   = datetime.fromisoformat(t).date() if t else None
        return date_from, date_to
    except Exception:
        raise ValueError("Parámetros 'from' y 'to' deben ser YYYY-MM-DD")


@extend_schema(
    tags=['analytics'],
    parameters=[TopCategoriesQuery],
    responses=TopCategorySerializer(many=True)
)
class TopCategoriesView(APIView):

    def get(self, request):
        """
        Returns the top event categories based on enrollments or attendance within a date range.
        """
        try:
            date_from, date_to = _parse_dates(request)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        limit = int(request.query_params.get("limit", 10))
        by = (request.query_params.get("by") or "enrollments").lower()

        ev = Event.objects.filter(deleted_at__isnull=True)
        if date_from: ev = ev.filter(start_date__gte=date_from)
        if date_to:   ev = ev.filter(start_date__lte=date_to)

        rows = (
            StudentEvent.objects
            .filter(event__in=ev)
            .values("event__categories__id", "event__categories__type")
            .annotate(
                enrollments=Count("id"),
                attendance=Count("id", filter=Q(attended=True)),
                events=Count("event", distinct=True),
            )
        )

        order_field = "-attendance" if by == "attendance" else "-enrollments"
        rows = rows.order_by(order_field)[:limit]

        payload = [
            {
                "category_id": r["event__categories__id"],
                "category_name": r.get("event__categories__type"),
                "events": r["events"],
                "enrollments": r["enrollments"],
                "attendance": r["attendance"],
            }
            for r in rows
            if r["event__categories__id"] is not None
        ]

        return Response(TopCategorySerializer(payload, many=True).data, status=status.HTTP_200_OK)


@extend_schema(
    tags=['analytics'],
    parameters=[TopCreatorsQuery],
    responses=TopCreatorSerializer(many=True)
)
class TopCreatorsView(APIView):

    def get(self, request):
        """
        Returns the top event creators based on enrollments, attendance, or number of events created.
        """
        try:
            date_from, date_to = _parse_dates(request)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        limit = int(request.query_params.get("limit", 10))
        by = (request.query_params.get("by") or "enrollments").lower()

        ev = Event.objects.filter(deleted_at__isnull=True)
        if date_from: ev = ev.filter(start_date__gte=date_from)
        if date_to:   ev = ev.filter(start_date__lte=date_to)

        rows = (
            StudentEvent.objects
            .filter(event__in=ev)
            .values("event__id_creator_id",
                    "event__id_creator__username",
                    "event__id_creator__first_name",
                    "event__id_creator__last_name")
            .annotate(
                events=Count("event", distinct=True),
                enrollments=Count("id"),
                attendance=Count("id", filter=Q(attended=True)),
            )
        )

        order_map = {"attendance": "-attendance", "events": "-events"}
        rows = rows.order_by(order_map.get(by, "-enrollments"))[:limit]

        payload = [
            {
                "user_id": r["event__id_creator_id"],
                "username": r["event__id_creator__username"],
                "first_name": r["event__id_creator__first_name"] or "",
                "last_name": r["event__id_creator__last_name"] or "",
                "events": r["events"],
                "enrollments": r["enrollments"],
                "attendance": r["attendance"],
            }
            for r in rows
        ]

        return Response(TopCreatorSerializer(payload, many=True).data, status=status.HTTP_200_OK)


@extend_schema(
    tags=['analytics'],
    parameters=[TopEventQuery],
    responses=TopEventSerializer(many=True)
)
class TopEventsView(APIView):

    def get(self, request):
        q = TopEventQuery(data=request.query_params)
        q.is_valid(raise_exception=True)
        p = q.validated_data

        by = p.get('by', 'enrollments')
        limit = p.get('limit', 10)
        date_from = p.get('from')
        date_to = p.get('to')

        qs = Event.objects.filter(deleted_at__isnull=True)
        if date_from:
            qs = qs.filter(start_date__gte=date_from)
        if date_to:
            qs = qs.filter(start_date__lte=date_to)

        qs = (
            qs.annotate(
                enrollments_count=Count("student_events", distinct=True),
                attendance_count=Count("student_events",
                                       filter=Q(student_events__attended=True),
                                       distinct=True),
            )
            .select_related("id_creator", "deleted_by")
            .prefetch_related("categories")
        )

        order_field = "-attendance_count" if by == "attendance" else "-enrollments_count"
        qs = qs.order_by(order_field, "-start_date", "-start_time")[:limit]

        payload = []
        for ev in qs:
            payload.append({
                "event": ev,
                "enrollments": ev.enrollments_count or 0,
                "attendance": ev.attendance_count or 0,
            })

        return Response(TopEventSerializer(payload, many=True).data, status=status.HTTP_200_OK)