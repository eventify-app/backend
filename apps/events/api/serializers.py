from rest_framework import serializers
from apps.events.models import Event
from apps.users.models import User


class EventCreatorSerializer(serializers.ModelSerializer):
    """
    Simplified serializer to display event creator information.
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = fields


class EventSerializer(serializers.ModelSerializer):
    """
    Main serializer for Event with custom validations.
    The creator is automatically assigned from the authenticated user.
    """
    id_creator = EventCreatorSerializer(read_only=True)
    deleted_by = EventCreatorSerializer(read_only=True)

    class Meta: 
        model = Event
        fields = ['id', 'place', 'start_date', 'start_time', 'end_date', 'end_time', 'id_creator', 'deleted_by', 'deleted_at']
        read_only_fields = ['id', 'id_creator', 'deleted_at', 'deleted_by']

    def validate(self, data):
        """
        Custom validation for dates and times.
        
        Validates:
        - end_date cannot be before start_date
        - If same day, end_time must be after start_time
        """
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        # Validate that end_date is not before start_date
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'End date cannot be before start date.'
            })
        
        # If same day, validate that end_time > start_time
        if start_date and end_date and start_date == end_date:
            if start_time and end_time and end_time <= start_time:
                raise serializers.ValidationError({
                    'end_time': 'End time must be after start time when the event is on the same day.'
                })
        
        return data

    def create(self, validated_data):
        """
        Automatically assigns the authenticated user as creator.
        """
        request = self.context.get('request')
        validated_data['id_creator'] = request.user
        return super().create(validated_data)