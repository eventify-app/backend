from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True, validators=[UniqueValidator(queryset=User.objects.all(), message="Este email ya está en registrado.")])
    password = serializers.CharField(write_only=True, min_length=0, trim_whitespace=False)
    first_name = serializers.CharField(required=True, allow_blank=False)
    last_name = serializers.CharField(required=True, allow_blank=False)
    username = serializers.CharField(required=True, allow_blank=False, validators=[UniqueValidator(queryset=User.objects.all(), message="Este nombre de usuario ya está en uso.")])
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email", "password", "date_of_birth", "phone")

    def create(self, validated_data):
        """
        Creates and return a new user.
        """
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.is_active = True
        user.save()

        try:
            # Assign the user to the 'student' group by default
            student = Group.objects.get(name='student')
            user.groups.add(student)
        except Group.DoesNotExist:
            pass

        return user