from rest_framework import serializers

from apps.events.api.serializers import EventSerializer


class TopCategoriesQuery(serializers.Serializer):
    from_ = serializers.DateField(source="from", required=False)
    to = serializers.DateField(required=False)
    limit = serializers.IntegerField(required=False, min_value=1, default=10)
    by = serializers.ChoiceField(required=False, choices=['enrollments', 'attendance'], default='enrollments')


class TopCreatorsQuery(TopCategoriesQuery):
    by = serializers.ChoiceField(required=False, choices=['enrollments', 'attendance', 'events'], default='enrollments')


class TopEventQuery(TopCategoriesQuery):
    pass

class TopCategorySerializer(serializers.Serializer):
    category_id = serializers.IntegerField()
    category_name = serializers.CharField()
    events = serializers.IntegerField()
    enrollments = serializers.IntegerField()
    attendance = serializers.IntegerField()  # check-ins


class TopCreatorSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    events = serializers.IntegerField()
    enrollments = serializers.IntegerField()
    attendance = serializers.IntegerField()


class TopEventSerializer(serializers.Serializer):
    event = EventSerializer()
    enrollments = serializers.IntegerField()
    attendance = serializers.IntegerField()