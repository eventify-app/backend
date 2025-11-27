from rest_framework import serializers
from apps.events.models import Event, EventRating, EventComment, StudentEvent, Category
from apps.users.models import User
from django.utils import timezone
from datetime import datetime, date

class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for Category model.
    """
    class Meta:
        model = Category
        fields = ['id', 'type']
        read_only_fields = ['id']


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

    participants_count = serializers.IntegerField(read_only=True)
    is_enrolled = serializers.BooleanField(read_only=True)

    categories = CategorySerializer(many=True, read_only=True)
    categories_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Category.objects.all(), 
        source='categories',
        required=True,
        allow_empty=False
    )

    class Meta: 
        model = Event
        fields = [
            'id', 'place', 'title', 'description', 'cover_image' ,'start_date', 'start_time', 'end_date',
            'end_time', 'id_creator', 'deleted_by', 'deleted_at', 'max_capacity', 'participants_count', 'is_enrolled',
            'categories', 'categories_ids'
        ]
        read_only_fields = ['id', 'id_creator', 'deleted_at', 'deleted_by', 'participants_count', 'is_enrolled', 'categories']

    def validate(self, data):
        """
        Custom validation for dates and times.
        
        Validates:
        - start_date cannot be in the past
        - If start_date is today, start_time must be in the future
        - end_date cannot be before start_date
        - If same day, end_time must be after start_time
        """
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        # Get current date and time
        now = timezone.now()
        today = now.date()
        current_time = now.time()
        
        # Validate that start_date is not in the past
        if start_date and start_date < today:
            raise serializers.ValidationError({
                'start_date': 'La fecha de inicio no puede ser anterior a hoy.'
            })
        
        # If start_date is today, validate that start_time is in the future
        if start_date and start_date == today:
            if start_time and start_time <= current_time:
                raise serializers.ValidationError({
                    'start_time': 'La hora de inicio debe ser futura cuando el evento es hoy.'
                })
        
        # Validate that end_date is not before start_date
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'La fecha de fin no puede ser anterior a la fecha de inicio.'
            })
        
        # If same day, validate that end_time > start_time
        if start_date and end_date and start_date == end_date:
            if start_time and end_time and end_time <= start_time:
                raise serializers.ValidationError({
                    'end_time': 'La hora de fin debe ser posterior a la hora de inicio cuando el evento es en el mismo día.'
                })
        
        return data

    def validate_categories_ids(self, value):
        """ 
        Validate that almost one category is selected.
        """
        if not value or len(value) == 0:
            raise serializers.ValidationError("Al menos una categoría debe ser seleccionada.")
        return value

    def create(self, validated_data):
        """
        Automatically assigns the authenticated user as creator.
        """
        request = self.context.get('request')
        validated_data['id_creator'] = request.user
        return super().create(validated_data)


class EventParticipantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='student.id', read_only=True)
    username = serializers.CharField(source='student.username', read_only=True)
    email = serializers.EmailField(source='student.email', read_only=True)
    first_name = serializers.CharField(source='student.first_name', read_only=True)
    last_name = serializers.CharField(source='student.last_name', read_only=True)
    profile_photo = serializers.CharField(source='student.profile_photo', read_only=True)
    attended = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile_photo', 'attended']
        read_only_fields = fields


class EventCheckInSerializer(serializers.Serializer):
    """
    Serializer for checking in a participant to an event by the creator
    """
    participant_id = serializers.IntegerField()


class EventRatingSerializer(serializers.ModelSerializer):
    """
    Serializer for rating an event.
    """
    user = EventCreatorSerializer(read_only=True)

    class Meta:
        model = EventRating
        fields = ['id', 'user', 'event', 'score']
        read_only_fields = ['id', 'user', 'event']

    def validate_score(self, value):
        """
        Validates that the score is between 1 and 5.
        """
        if not 1 <= value <= 5:
            raise serializers.ValidationError("La calificación debe estar entre 1 y 5.")
        return value
    
class EventCommentSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True) #mostrar nombre autor
    author_id = serializers.IntegerField(source='author.id', read_only=True)

    class Meta: 
        model = EventComment
        fields = ['id', 'event', 'author', 'author_id', 'content', 'created_at']
        read_only_fields = ['id', 'event', 'author', 'author_id', 'created_at']

class StudentEventSerializer(serializers.ModelSerializer):
    """
    Serializer for student enrollment in an event.
    """
    student = EventParticipantSerializer(read_only=True)
    event = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = StudentEvent
        fields = ['id', 'event', 'student', 'enrolled_at', 'attended']
        read_only_fields = ['id', 'event', 'student', 'enrolled_at', 'attended']


class EventStatsSerializer(serializers.Serializer):
    """
    Serializer for general statistics of events of the creator.
    Total events, events last month.
    """
    total_events = serializers.IntegerField()
    events_last_month = serializers.IntegerField()
    events_list_last_month = EventSerializer(many=True)


class AttendeeStatsSerializer(serializers.Serializer):
    """
    Serializer for general statistics of attendees of the creator.
    Total attendees, attendees last month.
    """
    total_enrolled = serializers.IntegerField()
    total_attended = serializers.IntegerField()
    enrolled_last_month = serializers.IntegerField()
    attended_last_month = serializers.IntegerField() 


class PopularEventSerializer(serializers.Serializer):
    """
    Serializer for popular events of the creator.
    Top 5 events more popular.
    """
    event = EventSerializer()
    total_participants = serializers.IntegerField()
    total_attended = serializers.IntegerField()
    attendance_rate = serializers.FloatField()
    average_rating = serializers.FloatField()
    total_ratings = serializers.IntegerField()


class CategoryAttendeeStatsSerializer(serializers.Serializer):
    """
    Serializer for general statistics of attendees of the creator by category.
    Attendees by category.
    """
    category = CategorySerializer()
    total_events = serializers.IntegerField()
    total_enrolled = serializers.IntegerField()
    total_attended = serializers.IntegerField()
    attendance_rate = serializers.FloatField()

