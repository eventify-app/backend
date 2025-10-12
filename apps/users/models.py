from django.core.validators import RegexValidator
from django.db import models
from django.contrib.auth.models import AbstractUser

e164_validator = RegexValidator(
    regex=r'^\+[1-9]\d{1,14}$',
    message="Use formato E.164, ej: +573001234567",
)

class User(AbstractUser):
    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=16, validators=[e164_validator], null=True, blank=True, unique=True)
    email_verified = models.BooleanField(default=False)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_photo = models.CharField(max_length=255, null=True, blank=True)
    deleted_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='deleted_users')
    deleted_at = models.DateTimeField(null=True, blank=True)