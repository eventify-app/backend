from datetime import timezone

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

class UserStatusSerializer(serializers.ModelSerializer):
    """
    Serializer para inhabilitar/habilitar usuarios.
    Solo permite modificar el campo is_active.
    """
    is_active = serializers.BooleanField(required=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_active']
        read_only_fields = ['id', 'username', 'email']
    
    def validate(self, attrs):
        """
        Validación adicional si es necesario
        """
        user = self.instance
        
        # Prevenir que un admin se deshabilite a sí mismo
        request_user = self.context.get('request').user
        if user.id == request_user.id and not attrs.get('is_active', True):
            raise serializers.ValidationError(
                "No puedes deshabilitarte a ti mismo."
            )
        
        return attrs
    
    def update(self, instance, validated_data):
        """
        Actualiza el estado del usuario
        """
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.save(update_fields=['is_active'])
        return instance

class UserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        required=False,
        validators=[UniqueValidator(queryset=User.objects.all(), message="Este nombre de usuario ya está en uso.")]
    )
    phone = serializers.CharField(
        required=False,
        allow_null=True,
        validators=[UniqueValidator(queryset=User.objects.all(), message="Este número de teléfono ya está en uso.")]
    )

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name",
            "date_of_birth", "phone", "profile_photo", "email",
            "email_verified",
        ]
        read_only_fields = ["id", "email", "email_verified", "profile_photo"]

    def validate_date_of_birth(self, dob):
        if dob and dob >= timezone.localdate():
            raise serializers.ValidationError("La fecha de nacimiento debe ser en el pasado.")
        return dob


class EmailChangeRequestOTPSerializer(serializers.Serializer):
    new_email = serializers.EmailField()

    def validate_new_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Este email ya está en uso.")
        return value


class EmailChangeVerifyOTPSerializer(serializers.Serializer):
    new_email = serializers.EmailField()
    code = serializers.RegexField(r"^\d{6}$", help_text="Código de 6 dígitos")


def validate_image(file):
    """
    Validates an image file for size and format.
    """
    if file.size > 2 * 1024 * 1024:
        raise serializers.ValidationError("La imagen no puede superar 2 MB.")
    ct = getattr(file, "content_type", "")
    if ct not in {"image/jpeg", "image/png", "image/webp"}:
        raise serializers.ValidationError("Formatos permitidos: JPG, PNG, WEBP.")
    return file


class ProfilePhotoSerializer(serializers.Serializer):
    """
    Serializer for uploading a profile photo.
    """
    profile_photo = serializers.ImageField(required=True)

    def validate_profile_photo(self, f):
        return validate_image(f)

