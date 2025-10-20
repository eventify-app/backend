from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for registering a new user.
    """
    email = serializers.EmailField(required=True, validators=[UniqueValidator(queryset=User.objects.all(), message="Este email ya está en registrado.")])
    password = serializers.CharField(write_only=True, min_length=0, trim_whitespace=False)
    first_name = serializers.CharField(required=True, allow_blank=False)
    last_name = serializers.CharField(required=True, allow_blank=False)
    username = serializers.CharField(required=True, allow_blank=False, validators=[UniqueValidator(queryset=User.objects.all(), message="Este nombre de usuario ya está en uso.")])
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True, validators=[UniqueValidator(queryset=User.objects.all(), message="Este número de teléfono ya está en uso.")])

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
            student = Group.objects.get(name='Student')
            user.groups.add(student)
        except Group.DoesNotExist:
            pass

        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom serializer to include additional claims in the JWT token.
    """
    @classmethod
    def get_token(cls, user):
        """
        Adds custom claims to the JWT token.
        """
        token = super().get_token(user)

        token['is_admin'] = user.groups.filter(name='Administrator').exists()
        token['groups'] = list(user.groups.values_list('name', flat=True))
        token['email_verified'] = user.email_verified

        return token

    def validate(self, attrs):
        """
        Adds user data to the response along with the token.
        """
        data = super().validate(attrs)
        user = self.user

        data['user'] = {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'username': user.username,
            'email': user.email,
            'phone': user.phone,
            'is_admin': user.groups.filter(name='Administrator').exists(),
            'email_verified': user.email_verified,
            'groups': list(user.groups.values_list('name', flat=True)),
        }
        return data

class VerifyEmailSerializer(serializers.Serializer):
    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    
    def validate(self, attrs):
        return attrs